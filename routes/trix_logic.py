from utils.trix_ai import TrixAILogic
import random
import logging
logger = logging.getLogger(__name__)


class TrixGameLogic:
    SUITS = ['♥', '♦', '♣', '♠']
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    RANK_VALUES = {r: i for i, r in enumerate(RANKS)}

    CONTRACTS = {
        'king': {'name': 'King of Hearts', 'score': -75},
        'queens': {'name': 'Queens', 'score': -25},
        'diamonds': {'name': 'Diamonds', 'score': -10},
        'slapping': {'name': 'Slapping', 'score': -15},
        'trix': {'name': 'Trix', 'score': 0}
    }

    @staticmethod
    def _hands_get(state, seat):
        hands = state.get('hands') or {}
        if isinstance(hands, list):
            return hands[seat] if seat < len(hands) else []
        if seat in hands:
            return hands[seat]
        return hands.get(str(seat), [])

    @staticmethod
    def _hands_set(state, seat, hand):
        hands = state.get('hands')
        if isinstance(hands, list):
            while len(hands) <= seat:
                hands.append([])
            hands[seat] = hand
        else:
            if seat in hands:
                hands[seat] = hand
            else:
                hands[str(seat)] = hand

    @staticmethod
    def get_bot_move(state, player_index):
        """
        Uses TrixAILogic to calculate the best move.
        """
        if state['phase'] == 'doubling':
            if player_index in state.get('doubling_confirms', []):
                return None  # Already confirmed

            action = TrixAILogic.get_doubling_action(state, player_index)
            if action['type'] == 'confirm':
                return {'type': 'confirm_doubling'}
            elif action['type'] == 'double':
                return action  # Contains item, suit

        # Bot only plays in 'playing' phase
        if state['phase'] != 'playing':
            return None

        card = TrixAILogic.get_best_move(state, player_index)
        if card:
            return {'type': 'play', 'card': card}
        return None

    @staticmethod
    def init_game(state):
        state['phase'] = 'init'
        state['hands'] = {0: [], 1: [], 2: [], 3: []}
        state['scores'] = {0: 0, 1: 0, 2: 0, 3: 0}
        state['kingdom_player'] = 0
        state['kingdoms_played'] = 0
        state['available_contracts'] = list(TrixGameLogic.CONTRACTS.keys())
        state['current_contract'] = None
        state['trick'] = []
        state['last_trick'] = []
        state['trix_piles'] = {s: [] for s in TrixGameLogic.SUITS}
        state['doubles'] = {'king': None, 'queens': {}}
        state['doubling_confirms'] = []
        state['hearts_broken'] = False
        state['finished_players'] = []
        state['turn_seat'] = 0
        TrixGameLogic.deal(state)

        if state.get('trix_style') == 'complex':
            state['current_contract'] = 'complex'
            state['phase'] = 'doubling'
            state['turn_seat'] = state['kingdom_player']
        else:
            state['phase'] = 'choose_contract'

    @staticmethod
    def deal(state):
        deck = [{'suit': s, 'rank': r}
                for s in TrixGameLogic.SUITS for r in TrixGameLogic.RANKS]
        random.shuffle(deck)
        for i in range(4):
            hand = deck[i * 13:(i + 1) * 13]
            hand.sort(key=lambda c: (TrixGameLogic.SUITS.index(
                c['suit']), TrixGameLogic.RANK_VALUES[c['rank']]))
            TrixGameLogic._hands_set(state, i, hand)

    @staticmethod
    def start_contract(state, contract):
        if contract not in state.get('available_contracts', []):
            return {'valid': False, 'message': 'Contract not available'}

        state['current_contract'] = contract
        state['available_contracts'].remove(contract)

        # Determine phase based on contract
        if contract in ['king', 'queens', 'complex']:
            state['phase'] = 'doubling'
            state['doubling_confirms'] = []
        else:
            state['phase'] = 'playing'

        state['trick'] = []
        state['last_trick'] = []
        state['turn_seat'] = state['kingdom_player']

        return {'valid': True, 'state': state}

    @staticmethod
    def confirm_doubling(state, player_index):
        if state['phase'] != 'doubling':
            return {'valid': False, 'message': 'Not in doubling phase'}

        confirms = state.get('doubling_confirms', [])
        if player_index not in confirms:
            confirms.append(player_index)
            state['doubling_confirms'] = confirms

        # Check if all players confirmed
        if len(confirms) >= 4:
            state['phase'] = 'playing'

        return {'valid': True, 'state': state}

    @staticmethod
    def play_card(state, player_index, card):
        if state['phase'] != 'playing':
            return {'valid': False, 'message': 'Not in playing phase'}

        if state['current_contract'] == 'trix':
            return TrixGameLogic.play_trix_card(state, player_index, card)
        else:
            return TrixGameLogic.play_trick_card(state, player_index, card)

    @staticmethod
    def play_trick_card(state, player_index, card):
        if state['turn_seat'] != player_index:
            return {'valid': False, 'message': 'Not your turn'}

        hand = TrixGameLogic._hands_get(state, player_index)
        card_in_hand = next(
            (c for c in hand if c['suit'] == card['suit'] and c['rank'] == card['rank']),
            None)

        if not card_in_hand:
            return {'valid': False, 'message': 'Card not in hand'}

        if not state['trick'] and card['suit'] == '♥' and state.get(
                'current_contract') == 'king':
            has_non_hearts = any(c['suit'] != '♥' for c in hand)
            if has_non_hearts and not state.get('hearts_broken'):
                return {
                    'valid': False,
                    'message': 'Cannot lead hearts unless only hearts remain'}

        # Validate follow suit
        if state['trick']:
            lead_suit = state['trick'][0]['card']['suit']
            if card['suit'] != lead_suit:
                has_suit = any(c['suit'] == lead_suit for c in hand)
                if has_suit:
                    try:
                        hand_str = " ".join(
                            [f"{h['suit']}{h['rank']}" for h in hand])
                        logger.debug(
                            "Trix follow-suit violation seat=%s lead=%s attempted=%s hand=%s",
                            player_index,
                            lead_suit,
                            card,
                            hand_str,
                        )
                    except Exception:
                        pass
                    return {'valid': False, 'message': 'Must follow suit'}

            # Check if hearts are broken (Playing hearts on non-heart suit)
            if lead_suit != '♥' and card['suit'] == '♥':
                state['hearts_broken'] = True

        hand.remove(card_in_hand)
        TrixGameLogic._hands_set(state, player_index, hand)
        state['trick'].append({'player': player_index, 'card': card_in_hand})
        state['turn_seat'] = (state['turn_seat'] + 1) % 4

        if len(state['trick']) == 4:
            TrixGameLogic.resolve_trick(state)

        return {'valid': True, 'state': state}

    @staticmethod
    def resolve_trick(state):
        trick = state['trick']
        lead_suit = trick[0]['card']['suit']

        # Find winner
        winner_play = max([p for p in trick if p['card']['suit'] == lead_suit],
                          key=lambda p: TrixGameLogic.RANK_VALUES[p['card']['rank']])
        winner_player = winner_play['player']

        # Calculate scores
        cards = [p['card'] for p in trick]
        contract = state['current_contract']
        doubles = state.get('doubles', {})

        if contract == 'king':
            for c in cards:
                if c['suit'] == '♥' and c['rank'] == 'K':
                    mult = 2 if doubles.get('king') is not None else 1
                    state['scores'][winner_player] += -75 * mult

        elif contract == 'queens':
            for c in cards:
                if c['rank'] == 'Q':
                    mult = 2 if c['suit'] in doubles.get('queens', {}) else 1
                    state['scores'][winner_player] += -25 * mult

        elif contract == 'diamonds':
            for c in cards:
                if c['suit'] == '♦':
                    state['scores'][winner_player] += -10

        elif contract == 'slapping':
            state['scores'][winner_player] += -15

        elif contract == 'complex':
            for c in cards:
                if c['suit'] == '♥' and c['rank'] == 'K':
                    state['scores'][winner_player] += (-150 if doubles.get(
                        'king') is not None else -75)
                if c['rank'] == 'Q':
                    mult = - \
                        50 if c['suit'] in doubles.get('queens', {}) else -25
                    state['scores'][winner_player] += mult
                if c['suit'] == '♦':
                    state['scores'][winner_player] += -10
            state['scores'][winner_player] += -15

        state['last_trick'] = list(trick)
        state['trick'] = []
        state['turn_seat'] = winner_player

        if not TrixGameLogic._hands_get(state, 0):
            TrixGameLogic.finish_contract(state)

    @staticmethod
    def finish_contract(state):
        # Complex style ends the game when hands are empty
        if state.get('trix_style') == 'complex':
            last_contract = state.get('current_contract')

            # Determine next contract
            # Cycle: Complex -> Trix -> Next Player
            next_contract = 'complex'
            rotate_king = False

            if last_contract == 'complex':
                next_contract = 'trix'
            else:
                # Finished Trix (or undefined), so end of this kingdom
                state['kingdoms_played'] = state.get('kingdoms_played', 0) + 1
                if state['kingdoms_played'] >= 4:
                    state['phase'] = 'finished'
                    return
                rotate_king = True
                next_contract = 'complex'

            if rotate_king:
                state['kingdom_player'] = (state['kingdom_player'] + 1) % 4

            # Redeal
            TrixGameLogic.deal(state)

            state['current_contract'] = next_contract
            state['trick'] = []
            state['last_trick'] = []
            state['trix_piles'] = {s: [] for s in TrixGameLogic.SUITS}
            state['doubles'] = {'king': None, 'queens': {}}
            state['doubling_confirms'] = []
            state['hearts_broken'] = False
            state['finished_players'] = []

            # Set turn seat & Phase
            state['turn_seat'] = state['kingdom_player']
            if next_contract == 'complex':
                state['phase'] = 'doubling'
            else:
                state['phase'] = 'playing'
        else:
            # Classic / Kingdom mode
            # Check if kingdom finished (all contracts played)
            if not state.get('available_contracts'):
                state['kingdoms_played'] = state.get('kingdoms_played', 0) + 1
                if state['kingdoms_played'] >= 4:
                    state['phase'] = 'finished'
                    return

                # New Kingdom
                state['kingdom_player'] = (state['kingdom_player'] + 1) % 4
                state['available_contracts'] = list(
                    TrixGameLogic.CONTRACTS.keys())
                TrixGameLogic.deal(state)
                state['doubles'] = {'king': None, 'queens': {}}

            # For next contract in kingdom
            state['phase'] = 'choose_contract'
            state['turn_seat'] = state['kingdom_player']
            # Reset board
            state['trick'] = []
            state['last_trick'] = []
            TrixGameLogic.deal(state)

    @staticmethod
    def play_trix_card(state, player_index, card):
        if state['turn_seat'] != player_index:
            return {'valid': False, 'message': 'Not your turn'}

        hand = TrixGameLogic._hands_get(state, player_index)

        # Check for pass action first
        if card.get('action') == 'pass':
            if TrixGameLogic.has_valid_trix_move(hand, state['trix_piles']):
                return {
                    'valid': False,
                    'message': 'You have valid moves, cannot pass'}
            else:
                state['turn_seat'] = (state['turn_seat'] + 1) % 4
                return {'valid': True, 'state': state}

        card_in_hand = next(
            (c for c in hand if c['suit'] == card['suit'] and c['rank'] == card['rank']),
            None)

        if not card_in_hand:
            return {'valid': False, 'message': 'Card not in hand'}

        # Validate Trix Logic
        # 1. Jacks can always be played if pile is empty.
        # 2. If pile has cards, must play next rank up or down.
        suit = card['suit']
        rank = card['rank']
        pile = state['trix_piles'][suit]

        valid = False
        if rank == 'J' and not pile:
            valid = True
        elif pile:
            # Get current bounds
            # In our piles, we store the sequence.
            # Actually, we just need to know what's played.
            # Logic: J is played.
            # If J is played, we can play 10 or Q.
            # If 10 is played, we can play 9.
            # If Q is played, we can play K.

            # Let's check what's present in the pile
            has_J = 'J' in pile
            if not has_J:
                # Should not happen if logic is correct
                pass
            else:
                # Upwards
                upper = ['J', 'Q', 'K', 'A']
                lower = ['J', '10', '9', '8', '7', '6', '5', '4', '3', '2']

                # Check if card is next in upper
                if rank in upper:
                    idx = upper.index(rank)
                    if idx > 0 and upper[idx - 1] in pile and rank not in pile:
                        valid = True

                # Check if card is next in lower
                if rank in lower:
                    idx = lower.index(rank)
                    if idx > 0 and lower[idx - 1] in pile and rank not in pile:
                        valid = True

        if not valid:
            return {'valid': False, 'message': 'Invalid Trix move'}

        # Execute
        hand.remove(card_in_hand)
        TrixGameLogic._hands_set(state, player_index, hand)
        state['trix_piles'][suit].append(rank)

        # Check if player finished
        if not hand:
            if player_index not in state['finished_players']:
                state['finished_players'].append(player_index)
                rank_finish = len(state['finished_players'])
                bonus = [200, 150, 100, 50]
                state['scores'][player_index] += bonus[rank_finish - 1]

        # Check if game over
        if len(state['finished_players']) == 4:
            TrixGameLogic.finish_contract(state)
        else:
            # Skip finished players
            next_seat = (state['turn_seat'] + 1) % 4
            while next_seat in state['finished_players']:
                next_seat = (next_seat + 1) % 4
            state['turn_seat'] = next_seat

        return {'valid': True, 'state': state}

    @staticmethod
    def declare_double(state, player_index, dtype, suit=None):
        if state['phase'] != 'playing' and state['phase'] != 'doubling':
            return {'valid': False, 'message': 'Not in doubling phase'}
        hand = TrixGameLogic._hands_get(state, player_index)
        if dtype == 'king':
            has_king = any(c['suit'] == '♥' and c['rank'] == 'K' for c in hand)
            if not has_king:
                return {
                    'valid': False,
                    'message': 'You must hold King of Hearts to double'}
            state['doubles']['king'] = player_index
            return {'valid': True, 'state': state}
        elif dtype == 'queen':
            if suit not in TrixGameLogic.SUITS:
                return {'valid': False, 'message': 'Invalid suit'}
            has_q = any(c['suit'] == suit and c['rank'] == 'Q' for c in hand)
            if not has_q:
                return {
                    'valid': False,
                    'message': 'You must hold this Queen to double'}
            state['doubles']['queens'][suit] = player_index
            return {'valid': True, 'state': state}
        else:
            return {'valid': False, 'message': 'Invalid double type'}

    @staticmethod
    def has_valid_trix_move(hand, piles):
        for card in hand:
            s = card['suit']
            r = card['rank']
            pile = piles[s]

            if r == 'J' and not pile:
                return True
            if not pile:
                continue

            upper = ['J', 'Q', 'K', 'A']
            lower = ['J', '10', '9', '8', '7', '6', '5', '4', '3', '2']

            if r in upper:
                idx = upper.index(r)
                if idx > 0 and upper[idx - 1] in pile and r not in pile:
                    return True
            if r in lower:
                idx = lower.index(r)
                if idx > 0 and lower[idx - 1] in pile and r not in pile:
                    return True
        return False
