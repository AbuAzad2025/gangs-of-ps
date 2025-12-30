from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from flask_babel import _
from models import Race, RaceParticipant, UserVehicle, User, Vehicle, Hostess
from datetime import datetime, timezone
import random

bp = Blueprint('racing', __name__, url_prefix='/casino/racing')

@bp.route('/')
@login_required
def index():
    # Show active lobbies
    active_races = Race.query.filter(Race.status == 'waiting').order_by(Race.created_at.desc()).all()
    
    # User's active car
    my_car = UserVehicle.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    return render_template('casino/racing/index.html', races=active_races, my_car=my_car)

@bp.route('/create', methods=['POST'])
@login_required
def create():
    bet = int(request.form.get('bet', 0))
    if bet < 100:
        flash(_('أقل رهان هو 100 شيكل!'), 'danger')
        return redirect(url_for('racing.index'))
        
    if current_user.money < bet:
        flash(_('معكش مصاري كفاية!'), 'danger')
        return redirect(url_for('racing.index'))
        
    my_car = UserVehicle.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not my_car:
        flash(_('لازم يكون عندك سيارة مفعلة عشان تسابق!'), 'danger')
        return redirect(url_for('racing.index'))
        
    if my_car.condition < 50:
        flash(_('سيارتك خربانة! صلحها قبل السباق.'), 'danger')
        return redirect(url_for('racing.index'))

    # Deduct money
    current_user.money -= bet
    
    race = Race(creator_id=current_user.id, bet_amount=bet)
    db.session.add(race)
    db.session.commit() # Commit to get ID
    
    # Add creator as participant
    participant = RaceParticipant(race_id=race.id, user_id=current_user.id, user_vehicle_id=my_car.id)
    db.session.add(participant)
    db.session.commit()
    
    flash(_('تم إنشاء السباق! بانتظار المتحدين...'), 'success')
    return redirect(url_for('racing.room', race_id=race.id))

@bp.route('/join/<int:race_id>', methods=['POST'])
@login_required
def join(race_id):
    race = db.session.get(Race, race_id)
    if not race or race.status != 'waiting':
        flash(_('السباق غير متاح!'), 'danger')
        return redirect(url_for('racing.index'))
        
    if current_user.money < race.bet_amount:
        flash(_('معكش مصاري كفاية للانضمام!'), 'danger')
        return redirect(url_for('racing.index'))
        
    my_car = UserVehicle.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not my_car:
        flash(_('لازم يكون عندك سيارة مفعلة!'), 'danger')
        return redirect(url_for('racing.index'))

    if my_car.condition < 50:
        flash(_('سيارتك خربانة! صلحها أول.'), 'danger')
        return redirect(url_for('racing.index'))
        
    # Check if already joined
    existing = RaceParticipant.query.filter_by(race_id=race.id, user_id=current_user.id).first()
    if existing:
        return redirect(url_for('racing.room', race_id=race.id))
        
    current_user.money -= race.bet_amount
    
    participant = RaceParticipant(race_id=race.id, user_id=current_user.id, user_vehicle_id=my_car.id)
    db.session.add(participant)
    db.session.commit()
    
    flash(_('انضممت للسباق!'), 'success')
    return redirect(url_for('racing.room', race_id=race.id))

@bp.route('/room/<int:race_id>')
@login_required
def room(race_id):
    race = db.session.get(Race, race_id)
    if not race:
        abort(404)
        
    participants = RaceParticipant.query.filter_by(race_id=race.id).all()
    is_participant = any(p.user_id == current_user.id for p in participants)
    
    # Spy Logic
    spy_data = {}
    if current_user.active_hostess_id:
        h = db.session.get(Hostess, current_user.active_hostess_id)
        if h and h.role == 'spy':
            # Check expiry
            now = datetime.now(timezone.utc)
            if current_user.casino_luck_until and current_user.casino_luck_until.replace(tzinfo=timezone.utc) > now:
                # Active Spy
                for p in participants:
                    if p.user_id != current_user.id:
                        spy_data[p.user_id] = {
                            'engine': p.user_vehicle.engine_level,
                            'tires': p.user_vehicle.tires_level,
                            'armor': p.user_vehicle.armor_level,
                            'condition': p.user_vehicle.condition,
                            'skill': p.user.driving_skill
                        }

    return render_template('casino/racing/room.html', race=race, participants=participants, is_participant=is_participant, user=current_user, spy_data=spy_data)

@bp.route('/start/<int:race_id>', methods=['POST'])
@login_required
def start(race_id):
    race = db.session.get(Race, race_id)
    if not race or race.status != 'waiting':
        flash(_('لا يمكن بدء السباق!'), 'danger')
        return redirect(url_for('racing.index'))
        
    if race.creator_id != current_user.id:
        flash(_('فقط المنشئ يمكنه بدء السباق!'), 'danger')
        return redirect(url_for('racing.room', race_id=race.id))
        
    participants = RaceParticipant.query.filter_by(race_id=race.id).all()
    if len(participants) < 2:
        flash(_('تحتاج لمتسابق واحد على الأقل لتبدأ!'), 'warning')
        return redirect(url_for('racing.room', race_id=race.id))
        
    # --- RACE LOGIC ---
    race.status = 'finished' # Simplify for now (instant result)
    
    results = []
    
    for p in participants:
        # Score Formula:
        # Base Speed + (Engine * 5) + (Tires * 3) + (Driver Skill * 2) + Random(0-20)
        
        base_speed = p.user_vehicle.vehicle.speed
        engine_bonus = p.user_vehicle.engine_level * 5
        tires_bonus = p.user_vehicle.tires_level * 3
        driver_bonus = p.user.driving_skill * 2
        luck = random.randint(0, 20)

        # Hostess Luck Bonus
        if p.user.casino_luck_until and p.user.casino_luck_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
             luck += 15 # Significant boost
        
        total_score = base_speed + engine_bonus + tires_bonus + driver_bonus + luck
        
        # Apply Condition Malus (if damaged)
        condition_factor = p.user_vehicle.condition / 100.0
        total_score *= condition_factor
        
        p.score = total_score
        results.append(p)
        
        # Damage the car slightly
        damage = random.randint(1, 5)
        p.user_vehicle.condition = max(0, p.user_vehicle.condition - damage)
        
        # Improve driver skill (small chance)
        if random.random() < 0.3:
            p.user.driving_skill += 1
            
    # Sort by score desc
    results.sort(key=lambda x: x.score, reverse=True)
    
    # Assign Ranks and Rewards
    total_pot = race.bet_amount * len(participants)
    
    # Winner takes all (or split 70/30 etc. - lets do Winner Takes All for excitement)
    winner = results[0]
    winner.reward = total_pot
    winner.user.money += total_pot
    
    for i, p in enumerate(results):
        p.rank = i + 1
        
    db.session.commit()
    
    flash(_('انتهى السباق! الفائز هو %(name)s', name=winner.user.username), 'success')
    return redirect(url_for('racing.room', race_id=race.id))

@bp.route('/train_driver', methods=['POST'])
@login_required
def train_driver():
    cost = 1000 * current_user.driving_skill
    
    if current_user.money < cost:
        flash(_('بدك %(cost)s للتدريب!', cost=cost), 'danger')
        return redirect(url_for('racing.index'))
        
    current_user.money -= cost
    current_user.driving_skill += 1
    db.session.commit()
    
    flash(_('تدربت وتحسنت مهاراتك في القيادة!'), 'success')
    return redirect(url_for('racing.index'))

@bp.route('/upgrade_car/<part_type>', methods=['POST'])
@login_required
def upgrade_car(part_type):
    my_car = UserVehicle.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not my_car:
        return redirect(url_for('racing.index'))
        
    cost = 0
    current_level = 0
    
    if part_type == 'engine':
        current_level = my_car.engine_level
        cost = 5000 * (current_level + 1)
    elif part_type == 'tires':
        current_level = my_car.tires_level
        cost = 3000 * (current_level + 1)
    elif part_type == 'armor':
        current_level = my_car.armor_level
        cost = 4000 * (current_level + 1)
    else:
        return redirect(url_for('racing.index'))
        
    if current_user.money < cost:
        flash(_('معكش مصاري للتطوير!'), 'danger')
        return redirect(url_for('racing.index'))
        
    if current_level >= 10: # Max level
        flash(_('وصلت للحد الأقصى لهذا التطوير!'), 'warning')
        return redirect(url_for('racing.index'))
        
    current_user.money -= cost
    
    if part_type == 'engine':
        my_car.engine_level += 1
    elif part_type == 'tires':
        my_car.tires_level += 1
    elif part_type == 'armor':
        my_car.armor_level += 1
        
    db.session.commit()
    flash(_('تم تطوير السيارة بنجاح!'), 'success')
    return redirect(url_for('racing.index'))
