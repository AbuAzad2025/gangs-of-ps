from flask import Blueprint, render_template, redirect, url_for, flash, session, abort
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from datetime import datetime, timedelta, timezone
import random

bp = Blueprint('police_chase', __name__, url_prefix='/police_chase')

@bp.route('/')
@login_required
def index():
    # Check if user is in an active chase state
    active_chase = session.get('active_chase', False)
    chase_difficulty = session.get('chase_difficulty', 1)
    
    can_chase = True
    remaining_time = 0
    
    # Cooldown Check
    if current_user.last_chase:
        last_chase = current_user.last_chase
        if last_chase.tzinfo is None:
            last_chase = last_chase.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        if now - last_chase < timedelta(minutes=5):
            can_chase = False
            remaining = timedelta(minutes=5) - (now - last_chase)
            remaining_time = int(remaining.total_seconds())
            
    return render_template('police_chase.html', can_chase=can_chase, remaining_time=remaining_time, user=current_user, active_chase=active_chase, difficulty=chase_difficulty)

@bp.route('/start', methods=['POST'])
@login_required
def start():
    # Check cooldown
    if current_user.last_chase:
        last_chase = current_user.last_chase
        if last_chase.tzinfo is None:
            last_chase = last_chase.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        if now - last_chase < timedelta(minutes=5):
            flash(_('عليك الانتظار قبل المطاردة التالية!'), 'danger')
            return redirect(url_for('police_chase.index'))
    
    # Start Active Chase Session
    session['active_chase'] = True
    session['chase_difficulty'] = 1 # Standard difficulty for manual start
    current_user.last_chase = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    return redirect(url_for('police_chase.index'))

@bp.route('/escape/<method>', methods=['POST'])
@login_required
def escape(method):
    if not session.get('active_chase'):
        return redirect(url_for('police_chase.index'))
    
    difficulty = session.get('chase_difficulty', 1)
    
    # Base difficulty score needed to escape
    required_score = 50 + (difficulty * 10)
    try:
        heat = current_user.heat_value()
    except Exception:
        heat = 0
    required_score += int(heat / 5)
    
    user_score = 0
    msg = ""
    
    if method == 'hide':
        # Intelligence Check
        user_score = current_user.intelligence * 2 + random.randint(1, 50)
        # Bonus if in own neighborhood/location (concept)
        msg = _('حاولت الاختباء في الأزقة الضيقة...')
        
    elif method == 'run':
        # Agility + Vehicle Check
        user_score = current_user.agility * 2 + random.randint(1, 50)
        # Vehicle bonus could be added here
        msg = _('دعست بنزين وحاولت تسبقهم...')
        
    elif method == 'fight':
        # Strength Check
        user_score = current_user.strength * 2 + random.randint(1, 50)
        # Weapon bonus could be added here
        msg = _('قررت تواجههم وتفتح النار!')
        required_score += 20 # Fighting is harder/riskier
        
    else:
        abort(404)
        
    # Result
    
    # Add Random Event Flavor
    events = [
        _('🚧 قفزت فوق حاجز شرطة!'),
        _('⛔ دخلت في شارع عكس السير!'),
        _('💨 رميت عليهم قنبلة دخانية!'),
        _('🚕 استخدمت زحمة السير لصالحك!'),
        _('🚓 صدمت سيارة دورية على الماشي!')
    ]
    random_event = random.choice(events)
    msg += " " + random_event

    animation = 'speed' if method == 'run' else 'smoke' if method == 'hide' else 'spark'
    image = 'crimes/car_theft.jpg' if method == 'run' else 'crimes/smuggling.jpg' if method == 'hide' else 'crimes/arms_deal.jpg'

    if user_score >= required_score:
        winnings = random.randint(150, 850) * difficulty
        current_user.money += winnings
        current_user.exp += 5 * difficulty
        try:
            if method == 'hide':
                current_user.add_heat(-20)
            elif method == 'run':
                current_user.add_heat(-10)
            else:
                current_user.add_heat(5)
        except Exception:
            pass

        session.pop('active_chase', None)
        session.pop('chase_difficulty', None)
        db.session.commit()

        session['story'] = {
            'title': _('مطاردة الشرطة'),
            'subtitle': _('هروب ناجح'),
            'text': msg + " " + _('ونجحت! هربت منهم وكسبت %(money)s شيكل.', money=winnings),
            'image': image,
            'animation': animation,
            'status': 'success',
            'badge': _('نجاح'),
            'next_url': url_for('main.crimes'),
            'alt_url': url_for('police_chase.index'),
            'alt_label': _('رجوع'),
            'stats': {'money': winnings, 'exp': 5 * difficulty}
        }

        return redirect(url_for('main.story'))
    else:
        jail_time = 60 * difficulty
        current_user.jail_until = (datetime.now(timezone.utc) + timedelta(seconds=jail_time)).replace(tzinfo=None)
        try:
            current_user.clear_heat()
        except Exception:
            pass

        session.pop('active_chase', None)
        session.pop('chase_difficulty', None)
        db.session.commit()

        session['story'] = {
            'title': _('مطاردة الشرطة'),
            'subtitle': _('انتهت بسجن'),
            'text': msg + " " + _('لكنهم مسكوك! رايح عالحبس يا معلم.'),
            'image': image,
            'animation': animation,
            'status': 'danger',
            'badge': _('فشل'),
            'next_url': url_for('jail.index'),
            'alt_url': url_for('main.crimes'),
            'alt_label': _('رجوع للجرائم'),
            'stats': None
        }

        return redirect(url_for('main.story'))
