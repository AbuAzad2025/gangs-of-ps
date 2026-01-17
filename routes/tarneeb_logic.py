import random


class TarneebGameLogic:
    SUITS = ['♥', '♦', '♣', '♠']
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    RANK_VALUES = {r: i for i, r in enumerate(RANKS)}

    @staticmethod
    def init_game(state):
        state['hands'] = [[] for _ in range(4)]
        state['turn_seat'] = 0
        state['phase'] = 'bidding'
        state['current_bid'] = {'value': 0, 'trump': None, 'bidder': None}
        state['bidding_history'] = []
        state['passes_in_row'] = 0
        state['trick'] = []
        state['tricks_won'] = [0, 0, 0, 0]
        state['team_mode'] = 'partnership'
        state['team_scores'] = {'A': 0, 'B': 0}
        state['team_tricks'] = {'A': 0, 'B': 0}
        state['declarer_team'] = None
        state['contract_value'] = None
        state['trump'] = None
        state['doubled'] = False
        state['redoubled'] = False
        state['doubling_history'] = []
        state['doubling_passes'] = 0

    @staticmethod
    def _fresh_deck():
        deck = [{'suit': s, 'rank': r}
                for s in TarneebGameLogic.SUITS for r in TarneebGameLogic.RANKS]
        random.shuffle(deck)
        return deck

    @staticmethod
    def deal(state):
        deck = TarneebGameLogic._fresh_deck()
        state['hands'] = [sorted(deck[i * 13:(i + 1) * 13],
                                 key=lambda c: (TarneebGameLogic.SUITS.index(c['suit']),
                                                TarneebGameLogic.RANK_VALUES[c['rank']])) for i in range(4)]
        state['turn_seat'] = 0
        state['phase'] = 'bidding'
        state['current_bid'] = {'value': 0, 'trump': None, 'bidder': None}
        state['bidding_history'] = []
        state['passes_in_row'] = 0
        state['trick'] = []
        state['tricks_won'] = [0, 0, 0, 0]
        state['team_tricks'] = {'A': 0, 'B': 0}
        state['declarer_team'] = None
        state['contract_value'] = None
        state['trump'] = None
        state['doubled'] = False
        state['redoubled'] = False
        state['doubling_history'] = []
        state['doubling_passes'] = 0
        return {'valid': True, 'state': state}

    @staticmethod
    def make_bid(state, player_index, bid):
        if state.get('phase') != 'bidding':
            return {'valid': False, 'message': 'Not in bidding phase'}
        if state.get('turn_seat') != player_index:
            return {'valid': False, 'message': 'Not your turn to bid'}

        # bid = {'action': 'pass'} or {'value': 7..13, 'trump': one of SUITS}
        action = bid.get('action')
        current = state.get('current_bid', {'value': 0})

        if action == 'pass':
            state['bidding_history'].append(
                {'player': player_index, 'action': 'pass'})
            state['passes_in_row'] = (state.get('passes_in_row', 0) + 1)
            state['turn_seat'] = (player_index + 1) % 4
            # Fallback: if 4 consecutive passes and no current bid, nudge
            # bidding to continue
            if state['passes_in_row'] >= 4 and state['current_bid'].get(
                    'bidder') is None:
                # Force minimal bid by next player based on longest suit to
                # avoid deadlock
                nxt = state['turn_seat']
                hand = state['hands'][nxt]
                suit_counts = {s: 0 for s in TarneebGameLogic.SUITS}
                for c in hand:
                    suit_counts[c['suit']] += 1
                best_suit = max(suit_counts, key=lambda s: suit_counts[s])
                state['current_bid'] = {
                    'value': 7, 'trump': best_suit, 'bidder': nxt}
                state['bidding_history'].append(
                    {'player': nxt, 'action': 'bid', 'value': 7, 'trump': best_suit})
                state['passes_in_row'] = 0
                state['turn_seat'] = (nxt + 1) % 4
        else:
            value = int(bid.get('value') or 0)
            trump = bid.get('trump')
            if value < 7 or value > 13 or trump not in TarneebGameLogic.SUITS:
                return {'valid': False, 'message': 'Invalid bid'}
            if value <= current.get('value', 0):
                return {
                    'valid': False,
                    'message': 'Bid must be higher than current'}
            state['current_bid'] = {
                'value': value,
                'trump': trump,
                'bidder': player_index}
            state['bidding_history'].append(
                {'player': player_index, 'action': 'bid', 'value': value, 'trump': trump})
            state['passes_in_row'] = 0
            state['turn_seat'] = (player_index + 1) % 4

        # End of bidding when there is a current bid and next three consecutive
        # passes occurred
        if state['current_bid'].get(
                'bidder') is not None and state['passes_in_row'] >= 3:
            # Move to doubling phase before playing
            state['trump'] = state['current_bid']['trump']
            state['contract_value'] = state['current_bid']['value']
            declarer = state['current_bid']['bidder']
            # Teams: A = seats 0 & 2, B = seats 1 & 3
            state['declarer_team'] = 'A' if declarer in (0, 2) else 'B'
            state['phase'] = 'doubling'
            state['doubling_passes'] = 0
            # First turn to opponents (next seat after declarer)
            state['turn_seat'] = (declarer + 1) % 4
        return {'valid': True, 'state': state}

    @staticmethod
    def handle_doubling(state, player_index, choice):
        if state.get('phase') != 'doubling':
            return {'valid': False, 'message': 'Not in doubling phase'}
        if state.get('turn_seat') != player_index:
            return {'valid': False, 'message': 'Not your turn'}

        declarer = state.get('current_bid', {}).get('bidder')
        if declarer is None:
            return {'valid': False, 'message': 'No declarer for doubling phase'}
        declarer_team = state.get('declarer_team')
        player_team = 'A' if player_index in (0, 2) else 'B'
        opp1 = (declarer + 1) % 4
        opp2 = (declarer + 3) % 4
        opponents = {opp1, opp2}

        action = (choice or {}).get('action')
        if action not in ['double', 'redouble', 'pass']:
            return {'valid': False, 'message': 'Invalid doubling action'}

        # Opponents may double; declarers may redouble after a double
        if not state.get('doubled', False):
            if player_index not in opponents and action != 'pass':
                return {'valid': False, 'message': 'Only opponents can double'}
            if action == 'double':
                state['doubled'] = True
                state['doubling_history'].append(
                    {'player': player_index, 'action': 'double'})
                state['doubling_passes'] = 0
                # Give turn to declarer to optionally redouble
                state['turn_seat'] = declarer
            else:
                # pass from opponent
                state['doubling_history'].append(
                    {'player': player_index, 'action': 'pass'})
                opponent_passes = [
                    h for h in state.get('doubling_history', [])
                    if h.get('action') == 'pass' and h.get('player') in opponents
                ]
                state['doubling_passes'] = len(opponent_passes)
                if state['doubling_passes'] >= 2:
                    state['phase'] = 'playing'
                    state['turn_seat'] = declarer
                else:
                    state['turn_seat'] = opp2 if player_index == opp1 else opp1
        else:
            # Already doubled; declarer team may redouble or pass, then start
            # playing
            if player_team != declarer_team and action != 'pass':
                return {
                    'valid': False,
                    'message': 'Only declarers can redouble'}
            if action == 'redouble':
                state['redoubled'] = True
                state['doubling_history'].append(
                    {'player': player_index, 'action': 'redouble'})
            else:
                state['doubling_history'].append(
                    {'player': player_index, 'action': 'pass'})
            state['phase'] = 'playing'
            state['turn_seat'] = declarer
        return {'valid': True, 'state': state}

    @staticmethod
    def play_card(state, player_index, card):
        if state.get('phase') != 'playing':
            return {'valid': False, 'message': 'Not in playing phase'}
        if state.get('turn_seat') != player_index:
            return {'valid': False, 'message': 'Not your turn'}

        hand = state['hands'][player_index]
        card_in_hand = next((c for c in hand if c['suit'] == card.get(
            'suit') and c['rank'] == card.get('rank')), None)
        if not card_in_hand:
            return {'valid': False, 'message': 'Card not in hand'}

        trick = state.get('trick', [])
        if trick:
            lead_suit = trick[0]['card']['suit']
            has_lead = any(c['suit'] == lead_suit for c in hand)
            if has_lead and card_in_hand['suit'] != lead_suit:
                return {
                    'valid': False,
                    'message': 'Must follow suit if possible'}

        # Execute play
        hand.remove(card_in_hand)
        state['hands'][player_index] = hand
        trick.append({'player': player_index, 'card': card_in_hand})
        state['trick'] = trick

        # If trick complete, resolve winner
        if len(trick) == 4:
            trump = state.get('trump')
            lead_suit = trick[0]['card']['suit']
            winning_play = trick[0]
            for play in trick[1:]:
                c = play['card']
                wp = winning_play['card']
                if c['suit'] == trump and wp['suit'] != trump:
                    winning_play = play
                elif c['suit'] == wp['suit']:
                    if TarneebGameLogic.RANK_VALUES[c['rank']
                                                    ] > TarneebGameLogic.RANK_VALUES[wp['rank']]:
                        winning_play = play
                elif c['suit'] == trump and wp['suit'] == trump:
                    if TarneebGameLogic.RANK_VALUES[c['rank']
                                                    ] > TarneebGameLogic.RANK_VALUES[wp['rank']]:
                        winning_play = play

            winner = winning_play['player']
            state['tricks_won'][winner] += 1
            if winner in (0, 2):
                state['team_tricks']['A'] += 1
            else:
                state['team_tricks']['B'] += 1

            state['last_trick'] = list(trick)
            state['trick'] = []
            state['turn_seat'] = winner

            # Check end of hand (13 tricks)
            total_tricks = sum(state['tricks_won'])
            if total_tricks >= 13:
                # Scoring
                declarer_team = state.get('declarer_team')
                other_team = 'B' if declarer_team == 'A' else 'A'
                contract_value = int(state.get('contract_value') or 0)
                team_tricks = state.get('team_tricks', {'A': 0, 'B': 0})
                mult = 4 if state.get('redoubled') else 2 if state.get('doubled') else 1
                declarer_tricks = int(team_tricks.get(declarer_team) or 0)
                other_tricks = int(team_tricks.get(other_team) or 0)

                if contract_value == 13:
                    if declarer_tricks == 13:
                        state['team_scores'][declarer_team] += 26 * mult
                    else:
                        state['team_scores'][declarer_team] -= 16 * mult
                        state['team_scores'][other_team] += other_tricks * 2
                else:
                    if declarer_tricks >= contract_value:
                        if declarer_tricks == 13:
                            state['team_scores'][declarer_team] += 16 * mult
                        else:
                            state['team_scores'][declarer_team] += declarer_tricks * mult
                    else:
                        state['team_scores'][declarer_team] -= contract_value * mult
                        state['team_scores'][other_team] += other_tricks

                # Check for Game End (Target 31)
                score_a = state['team_scores']['A']
                score_b = state['team_scores']['B']
                target_score = 31

                if score_a >= target_score or score_b >= target_score:
                    state['phase'] = 'finished'
                else:
                    # Start new round
                    TarneebGameLogic.deal(state)

        else:
            state['turn_seat'] = (player_index + 1) % 4
        return {'valid': True, 'state': state}

    @staticmethod
    def get_bot_action(state, player_index):
        if state.get('phase') == 'bidding':
            hand = state['hands'][player_index]
            current_bid = state.get('current_bid', {})
            current_val = current_bid.get('value', 0)
            current_bidder = current_bid.get('bidder')

            # Helper to evaluate hand strength per suit
            def eval_suit(suit):
                cards = [c for c in hand if c['suit'] == suit]
                if not cards:
                    return 0
                points = 0
                length = len(cards)
                # High card points
                ranks = [c['rank'] for c in cards]
                if 'A' in ranks:
                    points += 1
                if 'K' in ranks:
                    points += 0.8
                if 'Q' in ranks:
                    points += 0.6
                if 'J' in ranks:
                    points += 0.4

                # Length points
                if length >= 5:
                    points += (length - 4)

                # Trump strength bonus if this is trump
                return points + (length * 0.5)

            # Find best suit
            best_suit = None
            max_strength = -1
            for s in TarneebGameLogic.SUITS:
                strength = eval_suit(s)
                if strength > max_strength:
                    max_strength = strength
                    best_suit = s

            # Estimate bid
            estimated_bid = int(round(max_strength + 4))  # Base + strength
            if estimated_bid < 7:
                estimated_bid = 0  # Pass

            # Partner Logic
            partner_index = (player_index + 2) % 4
            is_partner_winning = (current_bidder == partner_index)

            if is_partner_winning:
                partner_strength = max(current_val - 4, 0)
                margin = max_strength - partner_strength
                if best_suit == current_bid.get('trump'):
                    if margin >= 0.8 and estimated_bid > current_val:
                        bid_val = current_val + 1
                        return {
                            'type': 'bid', 'bid': {
                                'value': bid_val, 'trump': best_suit}}
                    return {'type': 'pass', 'bid': {'action': 'pass'}}
                else:
                    if margin >= 1.5 and estimated_bid > current_val:
                        bid_val = current_val + 1
                        return {
                            'type': 'bid', 'bid': {
                                'value': bid_val, 'trump': best_suit}}
                    return {'type': 'pass', 'bid': {'action': 'pass'}}

            # Normal Bidding
            if estimated_bid > current_val:
                # Don't jump too high, just +1 or start at 7
                bid_val = max(7, current_val + 1)
                # Cap at estimated
                if bid_val > estimated_bid:
                    return {'type': 'pass', 'bid': {'action': 'pass'}}
                return {
                    'type': 'bid',
                    'bid': {
                        'value': bid_val,
                        'trump': best_suit}}
            else:
                return {'type': 'pass', 'bid': {'action': 'pass'}}

        elif state.get('phase') == 'doubling':
            return {'type': 'doubling', 'doubling': {'action': 'pass'}}

        elif state.get('phase') == 'playing':
            hand = state['hands'][player_index]
            trick = state.get('trick', [])
            trump = state.get('trump')

            chosen_card = None

            if not trick:
                # Leading
                # 1. Lead Ace of non-trump if available (Standard safe lead)
                aces = [c for c in hand if c['rank']
                        == 'A' and c['suit'] != trump]
                if aces:
                    chosen_card = aces[0]
                else:
                    # 2. Lead Trump if we have many to clear? Only if we are
                    # declarer usually.
                    trumps = [c for c in hand if c['suit'] == trump]
                    declarer_team = state.get('declarer_team')
                    my_team = 'A' if player_index in (0, 2) else 'B'

                    if my_team == declarer_team and len(trumps) >= 3:
                        # Lead high trump to draw
                        trumps.sort(
                            key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']], reverse=True)
                        chosen_card = trumps[0]
                    else:
                        # 3. Lead singleton/doubleton (short suits) to ruff later?
                        # Or just lead highest card of longest non-trump suit?
                        # Let's lead safe low card if not sure.
                        non_trumps = [c for c in hand if c['suit'] != trump]
                        if non_trumps:
                            # Low to high
                            non_trumps.sort(
                                key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']])
                            chosen_card = non_trumps[0]
                        else:
                            # Only trumps left
                            trumps.sort(
                                key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']])
                            chosen_card = trumps[0]
            else:
                # Following
                lead_suit = trick[0]['card']['suit']
                follow = [c for c in hand if c['suit'] == lead_suit]

                # Check who is winning
                winning_play = trick[0]
                for play in trick[1:]:
                    c = play['card']
                    wp = winning_play['card']
                    if c['suit'] == trump and wp['suit'] != trump:
                        winning_play = play
                    elif c['suit'] == wp['suit']:
                        if TarneebGameLogic.RANK_VALUES[c['rank']
                                                        ] > TarneebGameLogic.RANK_VALUES[wp['rank']]:
                            winning_play = play
                    elif c['suit'] == trump and wp['suit'] == trump:
                        if TarneebGameLogic.RANK_VALUES[c['rank']
                                                        ] > TarneebGameLogic.RANK_VALUES[wp['rank']]:
                            winning_play = play

                winning_player = winning_play['player']
                partner_index = (player_index + 2) % 4
                partner_winning = (winning_player == partner_index)

                if follow:
                    # Must follow suit
                    # Low to High
                    follow.sort(
                        key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']])

                    if partner_winning:
                        # Partner is winning. Do we need to overtake?
                        # If partner's card is not master (e.g. not Ace), and we have Ace?
                        # Simplified: If partner winning, play low.
                        chosen_card = follow[0]
                    else:
                        # Partner losing. Try to win.
                        # Can we beat the current winner?
                        # If winner is trump, we can't beat with lead suit.
                        current_winner_is_trump = (
                            winning_play['card']['suit'] == trump)
                        if current_winner_is_trump:
                            # We can't beat trump with follow suit. Play low.
                            chosen_card = follow[0]
                        else:
                            # Try to beat rank
                            win_val = TarneebGameLogic.RANK_VALUES[winning_play['card']['rank']]
                            better = [
                                c for c in follow if TarneebGameLogic.RANK_VALUES[c['rank']] > win_val]
                            if better:
                                chosen_card = better[0]  # Lowest winner
                            else:
                                chosen_card = follow[0]  # Can't win, play low
                else:
                    # Void in lead suit
                    # Can we trump?
                    trumps = [c for c in hand if c['suit'] == trump]
                    if trumps:
                        if partner_winning:
                            # Partner winning, no need to waste trump unless current winner is weak?
                            # Discard lowest non-trump
                            non_trumps = [
                                c for c in hand if c['suit'] != trump]
                            if non_trumps:
                                non_trumps.sort(
                                    key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']])
                                chosen_card = non_trumps[0]
                            else:
                                # Only trumps, play low trump
                                trumps.sort(
                                    key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']])
                                chosen_card = trumps[0]
                        else:
                            # Partner losing, try to trump
                            # Do we need to over-trump?
                            current_winner_is_trump = (
                                winning_play['card']['suit'] == trump)
                            if current_winner_is_trump:
                                win_val = TarneebGameLogic.RANK_VALUES[winning_play['card']['rank']]
                                better = [
                                    c for c in trumps if TarneebGameLogic.RANK_VALUES[c['rank']] > win_val]
                                if better:
                                    chosen_card = better[0]
                                else:
                                    # Can't overtrump, discard
                                    non_trumps = [
                                        c for c in hand if c['suit'] != trump]
                                    if non_trumps:
                                        non_trumps.sort(
                                            key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']])
                                        chosen_card = non_trumps[0]
                                    else:
                                        # Forced low trump
                                        chosen_card = trumps[0]
                            else:
                                # Winner is not trump, any trump wins. Play low
                                # trump.
                                trumps.sort(
                                    key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']])
                                chosen_card = trumps[0]
                    else:
                        # No trump, discard lowest
                        hand.sort(
                            key=lambda c: TarneebGameLogic.RANK_VALUES[c['rank']])
                        chosen_card = hand[0]

            return {'type': 'play', 'card': chosen_card}
        return {'type': 'none'}
