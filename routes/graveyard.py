from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models import User, ResurrectionRequest, SystemConfig, UserRank, Message
from models.user import UserRole
from datetime import datetime, timezone
from services.resource_service import ResourceService

bp = Blueprint('graveyard', __name__, url_prefix='/graveyard')

@bp.route('/')
def index():
    is_dead_viewer = False
    cost_diamonds = 10
    pending_request = None

    # Check if user is authenticated and DEAD (My Grave View)
    if current_user.is_authenticated and current_user.health <= 0:
        is_dead_viewer = True
        
        # Check for pending request
        pending_request = ResurrectionRequest.query.filter_by(user_id=current_user.id, status='pending').first()

        # Get Cost based on Rank
        try:
            rp = current_user.rank_points_value
            effective_level = current_user.level + (rp // 50)
            rank = UserRank.query.filter(UserRank.min_level <= effective_level).order_by(UserRank.min_level.desc()).first()
            if rank:
                cost_diamonds = max(1, int(rank.resurrection_cost))
        except:
            pass
        cost_diamonds = int(SystemConfig.get_value('graveyard_resurrection_cost_diamonds', str(cost_diamonds)) or cost_diamonds)
    
    # Public List (For everyone)
    dead_users = User.query.filter(User.health <= 0).order_by(User.level.desc()).limit(20).all()
    
    meta_description = _("مقبرة الشهداء والضحايا في عصابات فلسطين. هنا يرقد من خسروا المعركة.")

    return render_template('graveyard.html', 
                           user=current_user if current_user.is_authenticated else None, 
                           pending_request=pending_request, 
                           cost_diamonds=cost_diamonds,
                           is_dead_viewer=is_dead_viewer,
                           dead_users=dead_users,
                           meta_description=meta_description)


@bp.route('/resurrect', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def resurrect():
    if current_user.health > 0:
        return redirect(url_for('main.hara'))

    now = datetime.now(timezone.utc)

    cost_diamonds = 10
    try:
        rp = current_user.rank_points_value
        effective_level = current_user.level + (rp // 50)
        rank = UserRank.query.filter(UserRank.min_level <= effective_level).order_by(UserRank.min_level.desc()).first()
        if rank:
            cost_diamonds = max(1, int(rank.resurrection_cost))
    except Exception:
        pass
    try:
        cost_diamonds = int(SystemConfig.get_value('graveyard_resurrection_cost_diamonds', str(cost_diamonds)) or cost_diamonds)
    except Exception:
        cost_diamonds = 10

    # Lock user to prevent race conditions
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Atomic Deduction using ResourceService
    if not ResourceService.modify_resources(
        current_user.id,
        {'diamonds': -cost_diamonds},
        'resurrection_cost',
        auto_commit=False,
        expected_version=None
    ):
        db.session.rollback()
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=cost_diamonds), 'danger')
        return redirect(url_for('graveyard.index'))

    current_user.health = current_user.max_health
    current_user.energy = current_user.max_energy

    try:
        current_user.is_dead = False
        current_user.death_time = None
    except Exception:
        pass
    try:
        from models.user import clear_elite_title_reservation_on_resurrect
        clear_elite_title_reservation_on_resurrect(current_user.id, now=now)
    except Exception:
        pass

    db.session.commit()
    flash(_('تم إحياؤك بنجاح!'), 'success')
    return redirect(url_for('main.hara'))

@bp.route('/request_resurrection', methods=['POST'])
@login_required
@limiter.limit("3 per minute")
def request_resurrection():
    if current_user.health > 0:
        return redirect(url_for('main.hara'))
        
    existing = ResurrectionRequest.query.filter_by(user_id=current_user.id, status='pending').first()
    if existing:
        flash(_('لديك طلب قيد الانتظار بالفعل!'), 'warning')
        return redirect(url_for('graveyard.index'))
        
    new_req = ResurrectionRequest(user_id=current_user.id)
    db.session.add(new_req)
    db.session.commit()
    
    # Notify developers
    developers = User.query.filter_by(role=UserRole.DEVELOPER).all()
    for dev in developers:
        msg = Message(
            sender_id=current_user.id,
            receiver_id=dev.id,
            subject=_('طلب إحياء جديد'),
            body=_('اللاعب %(user)s قدم طلب إحياء.', user=current_user.username)
        )
        db.session.add(msg)
    db.session.commit()

    flash(_('تم إرسال طلب الإحياء للمطور. سيتم مراجعة طلبك قريباً.'), 'success')
    return redirect(url_for('graveyard.index'))
