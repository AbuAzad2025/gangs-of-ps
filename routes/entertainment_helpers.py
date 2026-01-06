from extensions import db
from models.entertainment import GamePlayer
from models.user import User
from flask import current_app
from models.system import SystemConfig
from services.resource_service import ResourceService

def _distribute_prizes(room):
    if room.pot_amount <= 0 or room.status != 'finished':
        return

    try:
        house_cut_percent = float(SystemConfig.get_value('house_cut_percent', '50') or '50')
    except Exception:
        house_cut_percent = 50.0
    if house_cut_percent < 0:
        house_cut_percent = 0.0
    if house_cut_percent > 100:
        house_cut_percent = 100.0
    house_cut = int(room.pot_amount * (house_cut_percent / 100.0))
    distributable_pot = room.pot_amount - house_cut
    
    # Identify Azad ID
    azad_user = User.query.filter_by(username='Azad').first()
    azad_id = azad_user.id if azad_user else None
            
    winners = []
    winner_user_ids = []
    state = room.game_state
    
    # 1. Identify Winners based on game type
    try:
        if room.game_type == 'chess':
            result = state.get('result') # '1-0', '0-1', '1/2-1/2'
            if result == '1-0': # White wins (Seat 0)
                 p = room.players.filter_by(seat_index=0).first()
                 if p: winners.append(p)
            elif result == '0-1': # Black wins (Seat 1)
                 p = room.players.filter_by(seat_index=1).first()
                 if p: winners.append(p)
            elif result == '1/2-1/2': # Draw
                 winners = room.players.all()
                 
        elif room.game_type == 'trix':
            scores = state.get('scores', [0,0,0,0])
            if state.get('team_mode') == 'partnership':
                score_a = scores[0] + scores[2]
                score_b = scores[1] + scores[3]
                winning_seats = [0, 2] if score_a > score_b else ([1, 3] if score_b > score_a else [0, 1, 2, 3])
            else:
                max_score = max(scores) if scores else 0
                winning_seats = [i for i, s in enumerate(scores) if s == max_score]
            
            for seat in winning_seats:
                p = room.players.filter_by(seat_index=seat).first()
                if p: winners.append(p)

        elif room.game_type == 'tarneeb':
            scores = state.get('team_scores', {'A': 0, 'B': 0})
            winning_seats = []
            if scores['A'] > scores['B']: winning_seats = [0, 2]
            elif scores['B'] > scores['A']: winning_seats = [1, 3]
            
            for seat in winning_seats:
                p = room.players.filter_by(seat_index=seat).first()
                if p: winners.append(p)

        # 2. Collect IDs and Calculate Shares
        # Logic varies by game for "Solo Draw" vs others
        
        users_to_lock = set()
        if azad_id and house_cut > 0:
            users_to_lock.add(azad_id)
            
        share_per_winner = 0
        remainder = 0
        
        # Special case: Chess Solo Draw
        if room.game_type == 'chess' and state.get('result') == '1/2-1/2' and state.get('is_solo'):
             share_per_winner = distributable_pot // 2
             # Bot's share goes to House (Azad)
             remainder = (distributable_pot // 2) + (distributable_pot % 2)
             
             p = room.players.filter_by(seat_index=0).first()
             if p:
                 winner_user_ids = [p.user_id]
                 users_to_lock.add(p.user_id)
             
        else:
            # Standard distribution
            if winners:
                winner_user_ids = [p.user_id for p in winners]
                users_to_lock.update(winner_user_ids)
                
                num_winners = len(winners)
                share_per_winner = distributable_pot // num_winners
                remainder = distributable_pot % num_winners
        
        # 3. Lock all users (Sorted)
        sorted_ids = sorted(list(users_to_lock))
        if not sorted_ids:
            # No one to pay? (e.g. Bot vs Bot?)
            room.pot_amount = 0
            db.session.commit()
            return

        # Lock users to prevent deadlocks (sorted order)
        # We hold the lock here, and ResourceService will be able to operate safely
        db.session.query(User).filter(User.id.in_(sorted_ids)).order_by(User.id).with_for_update().all()
        
        # 4. Apply Updates using ResourceService for atomicity and logging
        success = True
        
        # Azad (House Cut)
        if azad_id and azad_id in users_to_lock and house_cut > 0:
            changes = {'money': house_cut} if room.currency_type == 'money' else {'diamonds': house_cut}
            if not ResourceService.modify_resources(azad_id, changes, 'game_house_cut', auto_commit=False, expected_version=None):
                success = False

        # Remainder to Azad
        if success and azad_id and azad_id in users_to_lock and remainder > 0:
            changes = {'money': remainder} if room.currency_type == 'money' else {'diamonds': remainder}
            if not ResourceService.modify_resources(azad_id, changes, 'game_pot_remainder', auto_commit=False, expected_version=None):
                success = False
            
        # Winners
        if success:
            for uid in winner_user_ids:
                changes = {'money': share_per_winner} if room.currency_type == 'money' else {'diamonds': share_per_winner}
                if not ResourceService.modify_resources(uid, changes, 'game_win_prize', auto_commit=False, expected_version=None):
                    success = False
                    break
                    
        # 5. Commit
        if success:
            room.pot_amount = 0
            db.session.commit()
        else:
            db.session.rollback()
            current_app.logger.error("Failed to distribute prizes via ResourceService")
        
    except Exception as e:
        current_app.logger.error(f"Error distributing prizes: {e}")
        db.session.rollback()
