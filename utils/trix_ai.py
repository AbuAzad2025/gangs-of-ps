import random

class TrixAILogic:
    @staticmethod
    def get_doubling_action(state, player_index):
        """
        Returns an action: {'type': 'double', 'item': 'king'|'queen', 'suit': ...} 
        or {'type': 'confirm'}
        """
        hand = TrixAILogic._hands_get(state, player_index)
        contract = state.get('current_contract')
        doubles = state.get('doubles', {})
        
        # King
        if contract in ['king', 'complex']:
            has_king = any(c['suit'] == '♥' and c['rank'] == 'K' for c in hand)
            if has_king and not doubles.get('king'):
                return {'type': 'double', 'item': 'king'}
                
        # Queens
        if contract in ['queens', 'complex']:
            queens_in_hand = [c['suit'] for c in hand if c['rank'] == 'Q']
            current_doubled_queens = doubles.get('queens', {}).keys()
            for s in queens_in_hand:
                if s not in current_doubled_queens:
                     return {'type': 'double', 'item': 'queen', 'suit': s}
                     
        return {'type': 'confirm'}

    @staticmethod
    def get_best_move(state, player_index):
        """
        Calculates the best move for a bot player based on the current game state.
        Returns a card object {suit, rank}.
        """
        hand = TrixAILogic._hands_get(state, player_index)
        valid_moves = TrixAILogic.get_valid_moves(state, player_index)
        
        if not valid_moves:
            return None # Should not happen if hand is not empty
            
        if len(valid_moves) == 1:
            return valid_moves[0]
            
        contract = state.get('current_contract')
        
        # Partnership Detection
        # Standard Trix partnership: 0 & 2 vs 1 & 3
        partner_index = (player_index + 2) % 4
        team_mode = state.get('team_mode', 'individual')
        is_partnership = team_mode == 'partnership'
        
        # Strategy Router
        if contract == 'trix':
            return TrixAILogic._play_trix_contract(state, player_index, valid_moves)
        else:
            return TrixAILogic._play_trick_contract(state, player_index, valid_moves, contract, is_partnership, partner_index)

    @staticmethod
    def get_valid_moves(state, player_index):
        """
        Replicates the server-side validation logic to find all legal moves.
        """
        hand = TrixAILogic._hands_get(state, player_index)
        contract = state.get('current_contract')
        
        if contract == 'trix':
            valid = []
            piles = state['trix_piles']
            for card in hand:
                if TrixAILogic._is_valid_trix_move(card, piles):
                    valid.append(card)
            
            # If no valid moves, must pass (if game logic requires explicit pass, handled by server)
            # In this AI, we return empty list if pass is needed, or handle pass as a special move
            # But usually server handles auto-pass or UI handles it. 
            # Let's assume this returns playable cards.
            return valid
        else:
            # Trick taking contracts
            trick = state['trick']
            if not trick:
                # Leading
                # Can lead anything, unless Hearts restrictions in King contract
                if contract == 'king' and not state.get('hearts_broken', False):
                    # Can only lead hearts if we have ONLY hearts
                    has_non_hearts = any(c['suit'] != '♥' for c in hand)
                    if has_non_hearts:
                        return [c for c in hand if c['suit'] != '♥']
                return hand
            else:
                # Following
                lead_suit = trick[0]['card']['suit']
                follow_suit_cards = [c for c in hand if c['suit'] == lead_suit]
                if follow_suit_cards:
                    return follow_suit_cards
                else:
                    return hand # Can play anything

    @staticmethod
    def _is_valid_trix_move(card, piles):
        s = card['suit']
        r = card['rank']
        pile = piles[s]
        
        if r == 'J' and not pile:
            return True
        if not pile:
            return False
            
        upper = ['J', 'Q', 'K', 'A']
        lower = ['J', '10', '9', '8', '7', '6', '5', '4', '3', '2']
        
        if r in upper:
            idx = upper.index(r)
            if idx > 0 and upper[idx-1] in pile and r not in pile:
                return True
        
        if r in lower:
            idx = lower.index(r)
            if idx > 0 and lower[idx-1] in pile and r not in pile:
                return True
                
        return False

    @staticmethod
    def _play_trix_contract(state, player_index, valid_moves):
        """
        Strategy for Trix (Card placing):
        - Try to get rid of cards.
        - Avoid opening up piles that help opponents (unless I have cards there).
        - Heuristic: Count how many cards I have in each suit.
        """
        if not valid_moves:
            return {'suit': '♥', 'rank': '2', 'action': 'pass'} # Special pass card
            
        # 1. Prioritize playing Jacks to open piles if I have many cards in that suit
        jacks = [c for c in valid_moves if c['rank'] == 'J']
        if jacks:
            # Pick the Jack where I have the most cards in that suit
            hand = TrixAILogic._hands_get(state, player_index)
            best_jack = max(jacks, key=lambda c: sum(1 for h in hand if h['suit'] == c['suit']))
            return best_jack
            
        # 2. If no Jack, play cards that extend sequences I own
        # (Simple greedy: just play random for now, but valid)
        return valid_moves[0] 

    @staticmethod
    def _play_trick_contract(state, player_index, valid_moves, contract, is_partnership, partner_index):
        """
        Strategy for Trick-taking (King, Queens, Diamonds, Slapping, Complex).
        """
        trick = state['trick']
        hand = TrixAILogic._hands_get(state, player_index)
        
        # Rank values for comparison
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        rank_map = {r: i for i, r in enumerate(ranks)}
        
        def get_card_value(card):
            return rank_map[card['rank']]

        # --- LEADING (First to play) ---
        if not trick:
            # 1. Complex/King: Do NOT lead Hearts unless necessary
            # 2. Generally lead low cards to save high cards for defense, OR lead high to drain if safe.
            # 3. If I have a dangerous card (e.g. King of Hearts), try to void a suit?
            
            safe_leads = valid_moves
            
            if contract in ['king', 'complex']:
                # Avoid leading Hearts if possible (enforced by rules usually, but AI should be smart too)
                non_hearts = [c for c in safe_leads if c['suit'] != '♥']
                if non_hearts:
                    safe_leads = non_hearts
            
            # Sort by rank
            safe_leads.sort(key=lambda c: get_card_value(c))
            
            # Strategy: Lead the lowest card of the shortest suit (to try to void it)
            # Or lead the lowest card generally.
            return safe_leads[0]

        # --- FOLLOWING (Playing 2nd, 3rd, or 4th) ---
        lead_suit = trick[0]['card']['suit']
        
        # Check who is currently winning
        current_winner_idx = TrixAILogic._get_trick_winner(trick)
        current_winner_is_partner = (current_winner_idx == partner_index) if is_partnership else False
        
        # Analyze the trick for danger
        trick_cards = [t['card'] for t in trick]
        danger_points = TrixAILogic._calculate_danger(trick_cards, contract, state.get('doubles', {}))
        
        # Am I the last player?
        is_last_player = len(trick) == 3
        
        # Can I win the trick?
        # Check if I have cards of lead suit that are higher than current winner
        lead_suit_moves = [c for c in valid_moves if c['suit'] == lead_suit]
        
        if not lead_suit_moves:
            # I am VOID in lead suit. I can discard! (Sloughing)
            # This is the best time to get rid of dangerous cards.
            
            # 1. If King contract/Complex: Dump King of Hearts if I have it!
            kh = next((c for c in valid_moves if c['suit'] == '♥' and c['rank'] == 'K'), None)
            if kh and (contract == 'king' or contract == 'complex'):
                return kh
                
            # 2. If Queens contract/Complex: Dump Queens
            qs = [c for c in valid_moves if c['rank'] == 'Q']
            if qs and (contract == 'queens' or contract == 'complex'):
                return qs[0]
                
            # 3. If Diamonds contract/Complex: Dump Diamonds
            ds = [c for c in valid_moves if c['suit'] == '♦']
            if ds and (contract == 'diamonds' or contract == 'complex'):
                # Dump highest diamond
                ds.sort(key=lambda c: get_card_value(c), reverse=True)
                return ds[0]
                
            # 4. Otherwise dump highest card generally to unblock hand
            valid_moves.sort(key=lambda c: get_card_value(c), reverse=True)
            return valid_moves[0]
            
        else:
            # I MUST follow suit.
            
            # Sort my legal moves by rank
            lead_suit_moves.sort(key=lambda c: get_card_value(c)) # Low to High
            
            highest_card_on_table = max([t['card'] for t in trick if t['card']['suit'] == lead_suit], key=lambda c: get_card_value(c))
            highest_val_on_table = get_card_value(highest_card_on_table)
            
            # LOGIC:
            
            # Scenario A: Partner is winning.
            if current_winner_is_partner:
                if danger_points > 0:
                    # Partner is eating shit. Do not add to it if possible? 
                    # But I must follow suit.
                    # Try to play lower than partner if possible to let them win? 
                    # Actually, if partner is winning, I want to play HIGH card (below theirs) if I can, to save low cards?
                    # No, if partner is eating points, I should play my HIGHEST card that is LOWER than theirs? No that doesn't matter.
                    # Just play highest possible card that is LOWER than partner's card to "save" my low cards for later?
                    # Or play highest card generally to get rid of it?
                    # If I play higher than partner, *I* take the points. 
                    # "Partners don't hurt each other": If I take the points, it's same for team. 
                    # But maybe I have x2 on me?
                    
                    # Simple logic: If partner winning negative trick, let them win (play low). 
                    # UNLESS I can win and I have a better multiplier (unlikely to know here).
                    # Play lowest card.
                    return lead_suit_moves[0] 
                else:
                    # Clean trick. Partner winning.
                    # Great! Play highest card possible (that is still lower than partner's, or higher? No if higher I take it).
                    # If I play higher, I steal the clean trick.
                    # Does it matter? Yes, maybe I want the lead.
                    # But generally, save high cards. Play high card that is LOWER than partner.
                    # If I can't stay lower, I have to take it.
                    
                    winner_card = trick[0]['card'] # Simplified, assume lead is winner for now (needs proper check)
                    # Find cards lower than current max
                    lower_moves = [c for c in lead_suit_moves if get_card_value(c) < highest_val_on_table]
                    if lower_moves:
                        return lower_moves[-1] # Highest of the lowers
                    else:
                        return lead_suit_moves[0] # Lowest of the highers (I have to overtake)
            
            # Scenario B: Opponent is winning.
            else:
                if danger_points > 0:
                    # Negative trick. AVOID WINNING.
                    # Play highest card that is LOWER than current winner.
                    lower_moves = [c for c in lead_suit_moves if get_card_value(c) < highest_val_on_table]
                    if lower_moves:
                        return lower_moves[-1] # Highest safe card (Duck)
                    else:
                        # I must win this trick (all my cards are higher).
                        # Play the HIGHEST card to get rid of it? Or LOWEST to save high?
                        # If I'm eating it anyway, play the highest to drain my hand of power.
                        return lead_suit_moves[-1]
                else:
                    # Clean trick (Slapping/Latrosh always has -15, so never clean technically unless specific cards)
                    # But if "Slapping" contract, every trick is -15.
                    if contract == 'slapping':
                        # Avoid winning.
                        lower_moves = [c for c in lead_suit_moves if get_card_value(c) < highest_val_on_table]
                        if lower_moves:
                            return lower_moves[-1]
                        return lead_suit_moves[-1] # Eat with highest
                    
                    # If King/Queens/Diamonds and no special cards, it's safe (0 points).
                    # Try to win it to control lead? Or duck to save power?
                    # Usually duck in Trix games until necessary.
                    return lead_suit_moves[0]

    @staticmethod
    def _get_trick_winner(trick):
        if not trick: return -1
        lead_suit = trick[0]['card']['suit']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        rank_map = {r: i for i, r in enumerate(ranks)}
        
        highest_val = -1
        winner_idx = -1
        
        for t in trick:
            c = t['card']
            if c['suit'] == lead_suit:
                val = rank_map[c['rank']]
                if val > highest_val:
                    highest_val = val
                    winner_idx = t['player']
        return winner_idx

    @staticmethod
    def _calculate_danger(cards, contract, doubles):
        points = 0
        for c in cards:
            if contract == 'king' or contract == 'complex':
                if c['suit'] == '♥' and c['rank'] == 'K': points += 75
            if contract == 'queens' or contract == 'complex':
                if c['rank'] == 'Q': points += 25
            if contract == 'diamonds' or contract == 'complex':
                if c['suit'] == '♦': points += 10
            if contract == 'slapping' or contract == 'complex':
                points += 0 # Trick itself is bad, handled by "contract type" check usually
        
        if contract == 'slapping' or contract == 'complex':
             points += 15 # The trick itself
             
        return points

    @staticmethod
    def _hands_get(state, seat):
        hands = state.get('hands') or {}
        if isinstance(hands, list):
            return hands[seat] if seat < len(hands) else []
        if seat in hands:
            return hands[seat]
        return hands.get(str(seat), [])
