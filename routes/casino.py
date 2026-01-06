from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from extensions import db, limiter
from models.user import User
from models.hostess import Hostess
from models.casino_game import CasinoGame
from services.ai_hostess_service import AIHostessService
from services.resource_service import ResourceService
from flask_babel import _
import random
from datetime import datetime, timedelta, timezone

bp = Blueprint('casino', __name__, url_prefix='/casino')

def trigger_hostess_reaction(user, amount, is_win):
    """
    Checks if active hostess should react to win/loss
    """
    if not user.active_hostess_id:
        return

    now = datetime.now(timezone.utc)
    luck_until = user.casino_luck_until
    if not luck_until:
        return
        
    if luck_until.tzinfo is None:
        luck_until = luck_until.replace(tzinfo=timezone.utc)
        
    if luck_until <= now:
        return

    h = db.session.get(Hostess, user.active_hostess_id)
    if not h:
        return

    # Threshold for reaction
    reaction_msg = None
    
    if is_win and amount >= 1000:
        # Big Win
        msgs = [
            _("واو! أنت مذهل يا حبيبي! 🤑"),
            _("يا سلام على الفلوس! 💰"),
            _("أنت بطلي! كمل كمل! 🔥"),
            _("أحب الرجل الغني 😉")
        ]
        reaction_msg = random.choice(msgs)
    elif not is_win and amount >= 500: # Lost big amount
        # Big Loss
        msgs = [
            _("لا تزعل يا عمري، معوضة."),
            _("بسيطة، الجايات أكثر."),
            _("جرب كمان مرة عشاني؟ 🥺"),
            _("المال يروح ويجي، أهم شي صحتك.")
        ]
        reaction_msg = random.choice(msgs)

    if reaction_msg:
        # Flash special category: "Name|Image|Message"
        flash(f"{h.name}|{h.image}|{reaction_msg}", "hostess_reaction")

# --- Blackjack Logic ---

class Deck:
    def __init__(self):
        suits = ['C', 'D', 'S', 'H']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.cards = [{'suit': s, 'rank': r} for s in suits for r in ranks]
        random.shuffle(self.cards)

    def draw(self):
        return self.cards.pop()

def calculate_score(hand):
    score = 0
    aces = 0
    for card in hand:
        rank = card['rank']
        if rank in ['J', 'Q', 'K']:
            score += 10
        elif rank == 'A':
            score += 11
            aces += 1
        else:
            score += int(rank)
    
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score

@bp.route('/')
@login_required
def index():
    return render_template('casino/index.html', user=current_user, now=datetime.now(timezone.utc).replace(tzinfo=None))

@bp.route('/blackjack')
@login_required
def blackjack_index():
    # Load active game from DB
    game = CasinoGame.query.filter_by(user_id=current_user.id, game_type='blackjack', status='active').first()
    game_state = game.state if game else None
    
    # If game is completed but we want to show result (flash message handled, but maybe show state?)
    # For now, if no active game, show empty state.
    # We can check for recently completed game to show result if we want, but flash is enough.
    
    return render_template('casino/blackjack.html', game_state=game_state, now=datetime.now(timezone.utc).replace(tzinfo=None))

@bp.route('/blackjack/deal', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def blackjack_deal():
    # Lock user to prevent race conditions (starting multiple games)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك اللعب!'), 'danger')
            return redirect(url_for('jail.index'))
            
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك اللعب!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك اللعب!'), 'danger')
            return redirect(url_for('gym.index'))

    # Check existing game
    active_game = CasinoGame.query.filter_by(user_id=current_user.id, game_type='blackjack', status='active').first()
    if active_game:
        flash(_('لديك لعبة جارية بالفعل!'), 'warning')
        return redirect(url_for('casino.blackjack_index'))

    bet = request.form.get('bet', type=int)
    if not bet or bet < 10:
        flash(_('أقل رهان هو 10!'), 'danger')
        return redirect(url_for('casino.blackjack_index'))
    
    # Atomic deduction
    success = ResourceService.modify_resources(
        user_id=current_user.id,
        changes={'money': -bet},
        reason='casino_blackjack_bet',
        auto_commit=False,
        expected_version=None
    )
    
    if not success:
        db.session.rollback()
        flash(_('ليس لديك مال كافٍ!'), 'danger')
        return redirect(url_for('casino.blackjack_index'))

    deck = Deck()
    player_hand = [deck.draw(), deck.draw()]
    dealer_hand = [deck.draw(), deck.draw()]

    game_state = {
        'deck': deck.cards,
        'player_hand': player_hand,
        'dealer_hand': dealer_hand,
        'bet': bet,
        'status': 'playing', # playing, player_bust, dealer_bust, player_win, dealer_win, push
        'message': ''
    }
    
    # Create Game Record
    new_game = CasinoGame(
        user_id=current_user.id,
        game_type='blackjack',
        bet_amount=bet,
        state=game_state,
        status='active'
    )
    db.session.add(new_game)
    
    # Check for initial Blackjack
    player_score = calculate_score(player_hand)
    if player_score == 21:
        # Blackjack!
        winnings = int(bet * 2.5)
        ResourceService.modify_resources(
            user_id=current_user.id,
            changes={'money': winnings},
            reason='casino_blackjack_win_natural',
            auto_commit=False
        )
        game_state['status'] = 'player_win'
        game_state['message'] = _('بلاك جاك! ربحت %(amount)s!', amount=winnings)
        
        new_game.status = 'completed'
        new_game.result = 'win'
        new_game.winnings = winnings
        new_game.state = game_state # Update state
    
    db.session.commit()
    # session['blackjack_game'] = game_state # Removed
    return redirect(url_for('casino.blackjack_index'))

@bp.route('/blackjack/hit', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def blackjack_hit():
    # Lock user to serialize moves and prevent state corruption
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    game = CasinoGame.query.filter_by(user_id=current_user.id, game_type='blackjack', status='active').first()
    if not game:
        return redirect(url_for('casino.blackjack_index'))
    
    game_state = game.state
    if not game_state or game_state['status'] != 'playing':
        return redirect(url_for('casino.blackjack_index'))

    deck_cards = game_state['deck']
    # Reconstruct deck logic
    class ReconstructedDeck:
        def __init__(self, cards):
            self.cards = cards
        def draw(self):
            return self.cards.pop() if self.cards else None

    deck = ReconstructedDeck(deck_cards)
    
    card = deck.draw()
    if not card:
         flash(_('انتهت البطاقات!'), 'danger')
         return redirect(url_for('casino.blackjack_index'))

    game_state['player_hand'].append(card)
    game_state['deck'] = deck.cards # Save back
    
    score = calculate_score(game_state['player_hand'])
    if score > 21:
        game_state['status'] = 'player_bust'
        game_state['message'] = _('تجاوزت 21! خسرت الرهان.')
        
        game.status = 'completed'
        game.result = 'loss'
        game.winnings = 0
        
        # Force version update to prevent replay attacks (even on loss)
        ResourceService.modify_resources(
             user_id=current_user.id,
             changes={}, # No resource change
             reason='casino_blackjack_loss',
             auto_commit=False,
             expected_version=None
        )
        
    game.state = game_state
    db.session.commit()
        
    return redirect(url_for('casino.blackjack_index'))

@bp.route('/blackjack/stand', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def blackjack_stand():
    # Lock user to prevent race conditions
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    game = CasinoGame.query.filter_by(user_id=current_user.id, game_type='blackjack', status='active').first()
    if not game:
        return redirect(url_for('casino.blackjack_index'))
    
    game_state = game.state
    if not game_state or game_state['status'] != 'playing':
        return redirect(url_for('casino.blackjack_index'))
        
    deck_cards = game_state['deck']
    
    # Dealer Logic
    dealer_hand = game_state['dealer_hand']
    dealer_score = calculate_score(dealer_hand)
    
    # Reconstruct deck
    class ReconstructedDeck:
        def __init__(self, cards):
            self.cards = cards
        def draw(self):
            return self.cards.pop() if self.cards else None
            
    deck = ReconstructedDeck(deck_cards)

    while dealer_score < 17:
        card = deck.draw()
        if not card: break
        dealer_hand.append(card)
        dealer_score = calculate_score(dealer_hand)
        
    game_state['dealer_hand'] = dealer_hand
    game_state['deck'] = deck.cards
    
    player_score = calculate_score(game_state['player_hand'])
    
    winnings = 0
    result_status = 'loss'
    
    if dealer_score > 21:
        game_state['status'] = 'dealer_bust'
        winnings = game_state['bet'] * 2
        result_status = 'win'
        
        # Hostess Bonus
        if current_user.active_hostess_id:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'casino_luck':
                bonus_mult = hostess.buff_value if hostess.buff_value else 0.1
                winnings = int(winnings * (1 + bonus_mult))
        
        # Legacy support
        elif current_user.casino_luck_until and current_user.casino_luck_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            winnings = int(winnings * 1.1) # 10% Bonus
            
        ResourceService.modify_resources(
            user_id=current_user.id,
            changes={'money': winnings},
            reason='casino_blackjack_dealer_bust',
            auto_commit=False,
            expected_version=None
        )
        game_state['message'] = _('الموزع تجاوز 21! ربحت %(amount)s!', amount=winnings)
        trigger_hostess_reaction(current_user, winnings, True)
    elif dealer_score > player_score:
        game_state['status'] = 'dealer_win'
        game_state['message'] = _('الموزع فاز! حظاً أوفر.')
        result_status = 'loss'
        
        # Hostess Second Chance
        saved_by_hostess = False
        if current_user.active_hostess_id:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'casino_luck':
                chance = 0.2 + (hostess.buff_value if hostess.buff_value else 0)
                if random.random() < chance:
                    saved_by_hostess = True

        if not saved_by_hostess and current_user.casino_luck_until and current_user.casino_luck_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
             if random.random() < 0.2:
                 saved_by_hostess = True

        if saved_by_hostess:
                game_state['status'] = 'push'
                result_status = 'push'
                winnings = game_state['bet']
                ResourceService.modify_resources(
                    user_id=current_user.id,
                    changes={'money': game_state['bet']},
                    reason='casino_blackjack_hostess_save',
                    auto_commit=False,
                    expected_version=None
                )
                game_state['message'] = _('المضيفة أنقذتك! استرجعت رهانك.')
        else:
            trigger_hostess_reaction(current_user, game_state['bet'], False)
            # Force version update on loss
            ResourceService.modify_resources(
                 user_id=current_user.id,
                 changes={},
                 reason='casino_blackjack_loss',
                 auto_commit=False,
                 expected_version=current_user.version
            )

    elif dealer_score < player_score:
        game_state['status'] = 'player_win'
        winnings = game_state['bet'] * 2
        result_status = 'win'
        
        # Hostess Bonus
        if current_user.active_hostess_id:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'casino_luck':
                bonus_mult = hostess.buff_value if hostess.buff_value else 0.1
                winnings = int(winnings * (1 + bonus_mult))

        # Legacy Support
        elif current_user.casino_luck_until and current_user.casino_luck_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            winnings = int(winnings * 1.1) # 10% Bonus
            
        ResourceService.modify_resources(
            user_id=current_user.id,
            changes={'money': winnings},
            reason='casino_blackjack_win',
            auto_commit=False,
            expected_version=None
        )
        game_state['message'] = _('مبروك! ربحت %(amount)s!', amount=winnings)
        trigger_hostess_reaction(current_user, winnings, True)
    else:
        game_state['status'] = 'push'
        result_status = 'push'
        winnings = game_state['bet']
        ResourceService.modify_resources(
            user_id=current_user.id,
            changes={'money': game_state['bet']},
            reason='casino_blackjack_push',
            auto_commit=False,
            expected_version=None
        )
        game_state['message'] = _('تعادل! استرجعت رهانك.')
        
    game.status = 'completed'
    game.result = result_status
    game.winnings = winnings
    game.state = game_state
    
    db.session.commit()
    # session['blackjack_game'] = game_state # Removed
    return redirect(url_for('casino.blackjack_index'))

@bp.route('/blackjack/reset')
@login_required
@limiter.limit("30 per minute")
def blackjack_reset():
    session.pop('blackjack_game', None)
    return redirect(url_for('casino.blackjack_index'))

# --- Slots Logic ---

@bp.route('/slots')
@login_required
def slots_index():
    last_result = session.pop('slots_result', None)
    result = last_result.get('result') if last_result else None
    winnings = last_result.get('winnings', 0) if last_result else 0
    message = last_result.get('message') if last_result else None
    return render_template('casino/slots.html', user=current_user, result=result, winnings=winnings, message=message, now=datetime.now(timezone.utc))

@bp.route('/slots/spin', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def slots_spin():
    # Lock user to prevent race conditions
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك اللعب!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك اللعب!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك اللعب!'), 'danger')
            return redirect(url_for('gym.index'))

    bet = request.form.get('bet', type=int)
    if not bet or bet < 10:
        flash(_('أقل رهان هو 10!'), 'danger')
        return redirect(url_for('casino.slots_index'))
        
    if current_user.money < bet:
        flash(_('ليس لديك مال كافٍ!'), 'danger')
        return redirect(url_for('casino.slots_index'))
        
    # Atomic deduction
    success = ResourceService.modify_resources(
        user_id=current_user.id,
        changes={'money': -bet},
        reason='casino_slots_bet',
        auto_commit=False,
        expected_version=None
    )

    if not success:
        flash(_('ليس لديك مال كافٍ!'), 'danger')
        return redirect(url_for('casino.slots_index'))

    # current_user.money -= bet # Removed
    
    # Symbols: 🍒 🍋 🍊 🍇 🔔 💎 7️⃣
    symbols = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '7️⃣']
    weights = [30, 25, 20, 15, 7, 2, 1] # Weighted probabilities
    
    # Spin 3 reels
    result = random.choices(symbols, weights=weights, k=3)
    
    winnings = 0
    message = ""
    status = "loss"
    
    # Win Logic
    if result[0] == result[1] == result[2]:
        # Jackpot!
        if result[0] == '7️⃣':
            winnings = bet * 100
            message = _("JACKPOT!!! 777")
        elif result[0] == '💎':
            winnings = bet * 50
            message = _("DIAMONDS!!!")
        else:
            winnings = bet * 10
            message = _("Big Win!")
        status = "win"
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        # Small win (2 matching)
        winnings = int(bet * 1.5)
        message = _("Nice Match!")
        status = "win"
    
    # Hostess Buff
    if status == "win":
        if current_user.active_hostess_id:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'casino_luck':
                 bonus_mult = hostess.buff_value if hostess.buff_value else 0.1
                 winnings = int(winnings * (1 + bonus_mult))
        
        # Legacy
        elif current_user.casino_luck_until and current_user.casino_luck_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            winnings = int(winnings * 1.1)
            
        ResourceService.modify_resources(
            user_id=current_user.id,
            changes={'money': winnings},
            reason='casino_slots_win',
            auto_commit=False,
            expected_version=None
        )
        flash(f"{message} " + _("ربحت %(amount)s!", amount=winnings), 'success')
        trigger_hostess_reaction(current_user, winnings, True)
    else:
        # Hostess Second Chance? (Maybe for slots too?)
        flash(_("حظاً أوفر! ") + "".join(result), 'warning')
        trigger_hostess_reaction(current_user, bet, False)
        # Force version update on loss
        ResourceService.modify_resources(
             user_id=current_user.id,
             changes={},
             reason='casino_slots_loss',
             auto_commit=False,
             expected_version=None
        )

    # Record Game
    new_game = CasinoGame(
        user_id=current_user.id,
        game_type='slots',
        bet_amount=bet,
        state={'result': result, 'message': message},
        status='completed',
        result=status,
        winnings=winnings
    )
    db.session.add(new_game)
    db.session.commit()
    
    session['slots_result'] = {
        'result': result,
        'winnings': winnings,
        'message': message
    }
    
    return redirect(url_for('casino.slots_index'))


# --- Roulette Logic ---
# Simplified Roulette (Red/Black/Green/Number)

@bp.route('/roulette')
@login_required
def roulette_index():
    return render_template('casino/roulette.html', user=current_user, now=datetime.now(timezone.utc))

@bp.route('/roulette/spin', methods=['POST'])
@login_required
def roulette_spin():
    # Lock user to prevent race conditions
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Status Checks (Jail/Hospital/Gym)
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن!'), 'danger')
            return redirect(url_for('jail.index'))
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى!'), 'danger')
            return redirect(url_for('hospital.index'))
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب!'), 'danger')
            return redirect(url_for('gym.index'))

    bet_amount = request.form.get('bet_amount', type=int)
    bet_type = request.form.get('bet_type') # red, black, number, green
    bet_number = request.form.get('bet_number', type=int) # if number
    
    if not bet_amount or bet_amount < 10:
        flash(_('أقل رهان هو 10!'), 'danger')
        return redirect(url_for('casino.roulette_index'))
        
    if current_user.money < bet_amount:
        flash(_('ليس لديك مال كافٍ!'), 'danger')
        return redirect(url_for('casino.roulette_index'))
        
    # Atomic deduction
    if not ResourceService.modify_resources(
        user_id=current_user.id,
        changes={'money': -bet_amount},
        reason='casino_roulette_bet',
        auto_commit=False,
        expected_version=None
    ):
        flash(_('ليس لديك مال كافٍ!'), 'danger')
        return redirect(url_for('casino.roulette_index'))

    # current_user.money -= bet_amount # Removed
    
    # Spin
    landing = random.randint(0, 36)
    
    color = 'green'
    if landing == 0:
        color = _('أخضر')
    elif (1 <= landing <= 10) or (19 <= landing <= 28):
        color = _('أحمر') if landing % 2 != 0 else _('أسود')
    else:
        color = _('أسود') if landing % 2 != 0 else _('أحمر')
        
    winnings = 0
    won = False
    
    if bet_type == 'number':
        if landing == bet_number:
            winnings = bet_amount * 35
            won = True
    elif bet_type == 'red':
        if color == _('أحمر'):
            winnings = bet_amount * 2
            won = True
    elif bet_type == 'black':
        if color == _('أسود'):
            winnings = bet_amount * 2
            won = True
    elif bet_type == 'green': # Betting on 0
        if landing == 0:
            winnings = bet_amount * 35
            won = True
            
    status_str = 'loss'
    message = ""
    
    if won:
        status_str = 'win'
        # Hostess Bonus
        if current_user.active_hostess_id:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'casino_luck':
                 bonus_mult = hostess.buff_value if hostess.buff_value else 0.1
                 winnings = int(winnings * (1 + bonus_mult))

        # Legacy
        elif current_user.casino_luck_until and current_user.casino_luck_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            winnings = int(winnings * 1.1)
            
        # Atomic Update
        ResourceService.modify_resources(
            user_id=current_user.id,
            changes={'money': winnings},
            reason='casino_roulette_win',
            auto_commit=False
        )

        trigger_hostess_reaction(current_user, winnings, True)
        message = _('الكرة وقفت على %(num)s (%(col)s). مبروك! ربحت %(win)s!', num=landing, col=color, win=winnings)
        flash(message, 'success')
    else:
        # Hostess Second Chance
        saved = False
        if current_user.casino_luck_until and current_user.casino_luck_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            if random.random() < 0.2:
                refund = int(bet_amount * 0.5)
                # Atomic Update
                ResourceService.modify_resources(
                    user_id=current_user.id,
                    changes={'money': refund},
                    reason='casino_roulette_refund',
                    auto_commit=False,
                    expected_version=None
                )
                message = _('الكرة وقفت على %(num)s. لكن المضيفة عوضتك بـ %(ref)s!', num=landing, ref=refund)
                flash(message, 'warning')
                status_str = 'refund'
                winnings = refund
                saved = True
        
        if not saved:
            trigger_hostess_reaction(current_user, bet_amount, False)
            message = _('الكرة وقفت على %(num)s (%(col)s). حظاً أوفر!', num=landing, col=color)
            flash(message, 'danger')
            # Force version update on loss
            ResourceService.modify_resources(
                 user_id=current_user.id,
                 changes={},
                 reason='casino_roulette_loss',
                 auto_commit=False,
                 expected_version=None
            )

    # Record Game
    new_game = CasinoGame(
        user_id=current_user.id,
        game_type='roulette',
        bet_amount=bet_amount,
        state={
            'landing': landing, 
            'color': color, 
            'bet_type': bet_type, 
            'bet_number': bet_number,
            'message': message
        },
        status='completed',
        result=status_str,
        winnings=winnings
    )
    db.session.add(new_game)
    db.session.commit()

    return redirect(url_for('casino.roulette_index'))

# --- Bar Logic ---

@bp.route('/bar')
@login_required
def bar():
    drinks = [
        {'id': 1, 'name': _('ويسكي رخيص'), 'cost': 100, 'energy': 10, 'brave': 0, 'health': -5, 'desc': _('طعم سيء لكن يفي بالغرض')},
        {'id': 2, 'name': _('بيرة باردة'), 'cost': 250, 'energy': 20, 'brave': 1, 'health': 0, 'desc': _('منعشة في هذا الجو الحار')},
        {'id': 3, 'name': _('فودكا روسي'), 'cost': 500, 'energy': 40, 'brave': 5, 'health': -2, 'desc': _('قوية جداً!')},
        {'id': 4, 'name': _('كوكتيل الزعيم'), 'cost': 1500, 'energy': 100, 'brave': 10, 'health': 10, 'desc': _('المشروب المفضل للزعماء. يعيد طاقتك بالكامل!')}
    ]
    return render_template('casino/bar.html', drinks=drinks, user=current_user, now=datetime.utcnow())

@bp.route('/bar/buy/<int:drink_id>', methods=['POST'])
@login_required
def buy_drink(drink_id):
    # Lock user to prevent race conditions
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك الشرب في البار!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك الشرب في البار!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك الشرب في البار!'), 'danger')
            return redirect(url_for('gym.index'))

    drinks = {
        1: {'cost': 100, 'energy': 10, 'brave': 0, 'health': -5},
        2: {'cost': 250, 'energy': 20, 'brave': 1, 'health': 0},
        3: {'cost': 500, 'energy': 40, 'brave': 5, 'health': -2},
        4: {'cost': 1500, 'energy': 100, 'brave': 10, 'health': 10}
    }
    
    drink = drinks.get(drink_id)
    if not drink:
        return redirect(url_for('casino.bar'))
        
    if current_user.money < drink['cost']:
        flash(_('طفرنا! ما معك حق المشروب.'), 'danger')
        return redirect(url_for('casino.bar'))
        
    # Atomic deduction
    if not ResourceService.modify_resources(
        user_id=current_user.id,
        changes={'money': -drink['cost']},
        reason=f'casino_bar_buy_{drink_id}',
        auto_commit=False,
        expected_version=current_user.version
    ):
        flash(_('طفرنا! ما معك حق المشروب.'), 'danger')
        return redirect(url_for('casino.bar'))

    # Calculate effects based on fresh state (locked by previous call)
    user = db.session.get(User, current_user.id)
    
    energy_gain = min(drink['energy'], user.max_energy - user.energy)
    brave_gain = min(drink['brave'], user.max_brave - user.brave)
    
    # Health logic: min(max, max(0, current + delta))
    target_health = min(user.max_health, max(0, user.health + drink['health']))
    health_delta = target_health - user.health
    
    effect_changes = {}
    if energy_gain != 0: effect_changes['energy'] = energy_gain
    if brave_gain != 0: effect_changes['brave'] = brave_gain
    if health_delta != 0: effect_changes['health'] = health_delta
    
    if effect_changes:
        ResourceService.modify_resources(user.id, effect_changes, f'casino_bar_effect_{drink_id}', auto_commit=False)
    
    db.session.commit()
    flash(_('شربت المشروب! صحتين.'), 'success')
    return redirect(url_for('casino.bar'))

# --- Hostess Logic ---

from models import Hostess

@bp.route('/hostess')
@login_required
def hostess():
    now = datetime.now(timezone.utc)
    
    # Lazy Cleanup: Release hostesses with expired contracts
    # This ensures availability is accurate
    active_hostesses = Hostess.query.filter(Hostess.current_player_id != None).all()
    for h in active_hostesses:
        if h.current_player:
            expiry = h.current_player.casino_luck_until
            if not expiry:
                h.current_player_id = None
                h.current_player.active_hostess_id = None
            else:
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= now:
                    h.current_player_id = None
                    h.current_player.active_hostess_id = None
    db.session.commit()

    # Fetch Displayable Hostesses (Exclude Public/Concierge like Jasmin)
    hostesses_list = Hostess.query.filter_by(is_active=True, is_public=False).order_by(Hostess.price.asc()).all()
    
    # Convert to dict for template compatibility (id -> object)
    hostesses = {h.id: h for h in hostesses_list}
    
    # Determine Active Chat Endpoint and History Key
    chat_endpoint = url_for('casino.chat_hostess') # Default fallback
    history_key = 'hostess_chat_history'
    
    if current_user.active_hostess_id:
        active_h = db.session.get(Hostess, current_user.active_hostess_id) # Fetch fresh
        if active_h:
             if 'Jasmin' in active_h.name:
                 chat_endpoint = url_for('jasmin.chat')
             elif 'Layla' in active_h.name:
                 chat_endpoint = url_for('layla.chat')
             elif 'Ruby' in active_h.name:
                 chat_endpoint = url_for('ruby.chat')
             elif 'Sarah' in active_h.name:
                 chat_endpoint = url_for('sarah.chat')
             
             history_key = f'chat_history_{active_h.id}'
    
    chat_history = session.get(history_key, [])
    
    return render_template('casino/hostess.html', 
                           hostesses=hostesses, 
                           user=current_user, 
                           chat_history=chat_history, 
                           chat_endpoint=chat_endpoint,
                           now=now.replace(tzinfo=None))

@bp.route('/hostess/hire/<int:h_id>', methods=['POST'])
@login_required
def hire_hostess(h_id):
    # Lock User first to prevent race conditions on active_hostess_id
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Use with_for_update to prevent race conditions on exclusivity
    h = Hostess.query.filter_by(id=h_id).with_for_update().first()
    
    if not h:
        return redirect(url_for('casino.hostess'))
    
    # Exclusivity Check
    if h.current_player_id and h.current_player_id != current_user.id:
        flash(_('عذراً، هذه المضيفة مشغولة مع لاعب آخر حالياً!'), 'danger')
        return redirect(url_for('casino.hostess'))

    # Rank Check
    # Assuming user.level corresponds to rank or using user.level directly
    # Ideally we check UserRank titles, but for now Level is the numeric proxy
    if current_user.level < h.min_rank:
        flash(_('مستواك لا يسمح بالجلوس مع هذه المضيفة! (مطلوب مستوى %(lvl)s)', lvl=h.min_rank), 'warning')
        return redirect(url_for('casino.hostess'))

    if current_user.money < h.price:
        flash(_('ما معك كاش يكفي لجلوس مع هذه الجميلة!'), 'danger')
        return redirect(url_for('casino.hostess'))
    
    # Free previous hostess if exists
    if current_user.active_hostess_id:
        prev_h = db.session.get(Hostess, current_user.active_hostess_id)
        if prev_h:
            prev_h.current_player_id = None

    if not ResourceService.modify_resources(current_user.id, {'money': -h.price}, 'hire_hostess', auto_commit=False, expected_version=None):
        flash(_('ما معك كاش يكفي لجلوس مع هذه الجميلة!'), 'danger')
        return redirect(url_for('casino.hostess'))
    
    # Set luck/contract expiry (1 hour for all for now, or based on price)
    # Let's say 30 mins standard
    duration = 30 
    
    now = datetime.now(timezone.utc)
    if current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)
            
        if luck_until > now:
            current_user.casino_luck_until = luck_until + timedelta(minutes=duration)
        else:
            current_user.casino_luck_until = now + timedelta(minutes=duration)
    else:
        current_user.casino_luck_until = now + timedelta(minutes=duration)
    
    # Set Active Hostess ID & Exclusivity
    current_user.active_hostess_id = h_id
    h.current_player_id = current_user.id
    
    # Reset Chat History for new session
    session.pop(f'chat_history_{h.id}', None) # Clear specific history
    session.pop('hostess_chat_history', None) # Clear legacy history
        
    db.session.commit()
    flash(_('تم التعاقد مع %(name)s! ستكون بجانبك لمدة %(min)s دقيقة.', name=h.name, min=duration), 'success')
    return redirect(url_for('casino.hostess'))

@bp.route('/hostess/chat', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def chat_hostess():
    msg = request.form.get('message')
    if not msg:
        return jsonify({'response': _('لم اسمعك جيدا؟')})

    if not current_user.active_hostess_id:
        return jsonify({'response': _('عذرا، يجب عليك التعاقد معي اولا.')})
        
    # Check if contract expired
    now = datetime.now(timezone.utc)
    if not current_user.casino_luck_until:
         return jsonify({'response': _('انتهى وقتنا يا عزيزي. جدد العقد اذا اردت المزيد.')})
         
    luck_until = current_user.casino_luck_until
    if luck_until.tzinfo is None:
        luck_until = luck_until.replace(tzinfo=timezone.utc)
        
    if luck_until <= now:
         return jsonify({'response': _('انتهى وقتنا يا عزيزي. جدد العقد اذا اردت المزيد.')})

    h = db.session.get(Hostess, current_user.active_hostess_id)
    if not h:
         return jsonify({'response': _('من انت؟')})

    # Prepare Contexts
    hostess_context = {
        'name': h.name,
        'role': h.role,
        'description': h.description,
        'dialogue_style': h.dialogue_style,
        'system_prompt': h.system_prompt
    }
    
    user_context = {
                'name': current_user.username,
                'money': current_user.money,
                'level': current_user.level,
                'health': current_user.health,
                'energy': current_user.energy,
                'brave': current_user.brave,
                'rank': current_user.rank_title,
                'is_voice': request.form.get('is_voice') == 'true'
            }
    
    # Get Chat History
    history_key = 'hostess_chat_history'
    if current_user.active_hostess_id:
        history_key = f'chat_history_{current_user.active_hostess_id}'
        
    chat_history = session.get(history_key, [])
    
    service = AIHostessService()
    response_text = service.get_response(msg, hostess_context, user_context, chat_history)
    
    # Update Chat History
    chat_history.append({'role': 'user', 'content': msg})
    chat_history.append({'role': 'assistant', 'content': response_text})
    
    # Keep only last 10 messages
    session[history_key] = chat_history[-10:]
    
    return jsonify({
        'response': response_text,
        'voice_config': h.voice_config, # Return voice config for frontend TTS
        'personality_config': h.personality_config
    })


