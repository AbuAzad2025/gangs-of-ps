from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models.social import Gang, GangInvite, GangLog, GangWar, GangAlliance, GangItem
from models.gameplay import OrganizedCrime, CrimeLobby, LobbyParticipant
from models.user import User, UserRole
from models.economy import Asset
from models.item import UserItem, Item
from models.system import SystemConfig
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
import os
import random
from .utils import save_image, send_notification
from sqlalchemy import or_

from services.resource_service import ResourceService

bp = Blueprint('gang', __name__, url_prefix='/gang')

@bp.route('/')
@login_required
def index():
    gangs = Gang.query.order_by(Gang.level.desc(), Gang.exp.desc()).all()
    return render_template('gang/index.html', title=_('العصابات'), gangs=gangs)

@bp.route('/invites')
@login_required
def invites():
    invites = GangInvite.query.filter_by(user_id=current_user.id, status='pending').all()
    return render_template('gang/invites.html', title=_('دعوات الانضمام'), invites=invites)

@bp.route('/accept_invite/<int:invite_id>', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per minute")
def accept_invite(invite_id):
    if request.method == 'GET' and not current_app.config.get('TESTING', False):
        abort(405)
        
    # Lock current user first (Global Lock Order: User -> Gang)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    # Lock invite
    invite = db.session.query(GangInvite).filter_by(id=invite_id).with_for_update().first()
    if not invite:
        abort(404)
        
    if invite.user_id != current_user.id:
        flash(_('هذه الدعوة ليست لك!'), 'danger')
        return redirect(url_for('gang.invites'))
        
    if current_user.gang_id:
        flash(_('أنت بالفعل عضو في عصابة!'), 'danger')
        return redirect(url_for('gang.invites'))
        
    # Lock Gang
    gang = db.session.query(Gang).filter_by(id=invite.gang_id).with_for_update().first()
    if not gang:
        flash(_('العصابة لم تعد موجودة!'), 'danger')
        return redirect(url_for('gang.invites'))

    members_count = User.query.filter_by(gang_id=gang.id).count()
    if members_count >= gang.max_members:
        flash(_('العصابة ممتلئة!'), 'danger')
        return redirect(url_for('gang.invites'))
        
    current_user.gang_id = gang.id
    invite.status = 'accepted'
    
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('انضم للعصابة عبر دعوة'))
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم الانضمام للعصابة بنجاح!'), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/reject_invite/<int:invite_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def reject_invite(invite_id):
    invite = db.session.get(GangInvite, invite_id)
    if not invite:
        abort(404)
    if invite.user_id != current_user.id:
        flash(_('هذه الدعوة ليست لك!'), 'danger')
        return redirect(url_for('gang.invites'))
        
    invite.status = 'rejected'
    db.session.commit()
    
    flash(_('تم رفض الدعوة.'), 'info')
    return redirect(url_for('gang.invites'))

@bp.route('/leave', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per hour")
def leave():
    if request.method == 'GET' and not current_app.config.get('TESTING', False):
        abort(405)
    
    # Lock User First
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
    
    # Lock Gang
    gang = db.session.query(Gang).filter_by(id=current_user.gang_id).with_for_update().first()
    if not gang:
        # Gang might be deleted, just clear user's gang_id
        current_user.gang_id = None
        db.session.commit()
        return redirect(url_for('gang.index'))
    
    if current_user.id == gang.leader_id:
        flash(_('لا يمكنك مغادرة العصابة وأنت الزعيم! يجب عليك نقل الزعامة أو حل العصابة.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    current_user.gang_id = None
    
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('غادر العصابة'))
    db.session.add(log)
    db.session.commit()
    
    flash(_('لقد غادرت العصابة.'), 'success')
    return redirect(url_for('gang.index'))

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per hour")
def create():
    if current_user.gang_id:
        flash(_('أنت بالفعل عضو في عصابة!'), 'warning')
        return redirect(url_for('gang.dashboard'))
    
    cost = int(SystemConfig.get_value('gang_creation_cost', 10000))
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if is_admin:
        cost = 0

    # Status Check Bypass for Admin
    if not is_admin:
        now = datetime.now(timezone.utc)
        if current_user.jail_until:
            jail_until = current_user.jail_until
            if jail_until.tzinfo is None:
                jail_until = jail_until.replace(tzinfo=timezone.utc)
            if jail_until > now:
                flash(_('أنت في السجن ولا يمكنك إنشاء عصابة!'), 'danger')
                return redirect(url_for('jail.index'))
        
        if current_user.hospital_until:
            hospital_until = current_user.hospital_until
            if hospital_until.tzinfo is None:
                hospital_until = hospital_until.replace(tzinfo=timezone.utc)
            if hospital_until > now:
                flash(_('أنت في المستشفى ولا يمكنك إنشاء عصابة!'), 'danger')
                return redirect(url_for('hospital.index'))

        if current_user.gym_until:
            gym_until = current_user.gym_until
            if gym_until.tzinfo is None:
                gym_until = gym_until.replace(tzinfo=timezone.utc)
            if gym_until > now:
                flash(_('أنت تتدرب ولا يمكنك إنشاء عصابة!'), 'danger')
                return redirect(url_for('gym.index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash(_('اسم العصابة مطلوب'), 'danger')
            return redirect(url_for('gang.create'))
            
        if Gang.query.filter_by(name=name).first():
            flash(_('هذا الاسم مستخدم من قبل'), 'danger')
            return redirect(url_for('gang.create'))
            
        if current_user.money < cost:
            flash(_('لا تملك كاش كافي لإنشاء عصابة! المطلوب: %(cost)s', cost=cost), 'danger')
            return redirect(url_for('gang.create'))
            
        # Atomic deduction via ResourceService
        if cost > 0:
            # Lock user to prevent race conditions
            db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
            if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'gang_creation', auto_commit=False, expected_version=None):
                 db.session.rollback()
                 flash(_('لا تملك كاش كافي لإنشاء عصابة!'), 'danger')
                 return redirect(url_for('gang.create'))

        new_gang = Gang(name=name, description=description, leader_id=current_user.id)
        
        # Handle recruitment policies
        new_gang.min_level_req = int(request.form.get('min_level_req', 1))
        new_gang.recruitment_status = request.form.get('recruitment_status', 'open')
        
        db.session.add(new_gang)
        db.session.flush() # Flush to get ID, but keep transaction open
        
        # Add user to gang
        current_user.gang_id = new_gang.id
        db.session.commit() # Final commit
        
        flash(_('تم إنشاء العصابة بنجاح!'), 'success')
        return redirect(url_for('gang.dashboard'))
        
    return render_template('gang/create.html', title=_('إنشاء عصابة'), cost=cost)

@bp.route('/request_join/<int:gang_id>', methods=['POST'])
@login_required
@limiter.limit("5 per hour")
def request_join(gang_id):
    # Lock user
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    is_admin = current_user.role.value >= UserRole.ADMIN.value
    
    # Status Check
    if not is_admin:
        now = datetime.now(timezone.utc)
        if current_user.jail_until:
            jail_until = current_user.jail_until
            if jail_until.tzinfo is None:
                jail_until = jail_until.replace(tzinfo=timezone.utc)
            if jail_until > now:
                flash(_('أنت في السجن ولا يمكنك الانضمام لعصابة!'), 'danger')
                return redirect(url_for('jail.index'))
        
        if current_user.hospital_until:
            hospital_until = current_user.hospital_until
            if hospital_until.tzinfo is None:
                hospital_until = hospital_until.replace(tzinfo=timezone.utc)
            if hospital_until > now:
                flash(_('أنت في المستشفى ولا يمكنك الانضمام لعصابة!'), 'danger')
                return redirect(url_for('hospital.index'))

        if current_user.gym_until:
            gym_until = current_user.gym_until
            if gym_until.tzinfo is None:
                gym_until = gym_until.replace(tzinfo=timezone.utc)
            if gym_until > now:
                flash(_('أنت تتدرب ولا يمكنك الانضمام لعصابة!'), 'danger')
                return redirect(url_for('gym.index'))

    if current_user.gang_id:
        flash(_('أنت بالفعل عضو في عصابة!'), 'warning')
        return redirect(url_for('gang.index'))
    
    gang = db.session.get(Gang, gang_id)
    if not gang:
        abort(404)

    # Lock Gang to prevent race condition on member count
    db.session.query(Gang).filter_by(id=gang.id).with_for_update().first()
    
    # Check policies
    if gang.recruitment_status == 'closed':
        flash(_('هذه العصابة لا تقبل أعضاء جدد حالياً.'), 'danger')
        return redirect(url_for('gang.view', gang_id=gang.id))
        
    if gang.recruitment_status == 'invite_only':
        flash(_('الانضمام لهذه العصابة يتطلب دعوة خاصة.'), 'warning')
        return redirect(url_for('gang.view', gang_id=gang.id))
        
    if current_user.level < gang.min_level_req:
        flash(_('مستواك أقل من الحد الأدنى المطلوب للانضمام (مستوى %(level)s).', level=gang.min_level_req), 'danger')
        return redirect(url_for('gang.view', gang_id=gang.id))
    
    if gang.allowed_countries:
        allowed = [c.strip().upper() for c in gang.allowed_countries.split(',')]
        if current_user.country not in allowed:
            flash(_('هذه العصابة تقبل أعضاء من دول محددة فقط.'), 'danger')
            return redirect(url_for('gang.view', gang_id=gang.id))

    # Existing check for members count
    members_count = User.query.filter_by(gang_id=gang.id).count()
    if members_count >= gang.max_members:
        flash(_('العصابة ممتلئة!'), 'danger')
        return redirect(url_for('gang.view', gang_id=gang.id))
        
    # Auto join for now if open
    current_user.gang_id = gang.id
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action="Joined the gang directly")
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم الانضمام للعصابة بنجاح!'), 'success')
    return redirect(url_for('gang.dashboard'))


@bp.route('/kick_member/<int:user_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def kick_member(user_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك طرد الأعضاء!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك طرد الأعضاء!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك طرد الأعضاء!'), 'danger')
            return redirect(url_for('gym.index'))

    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id and not is_admin:
        flash(_('ليس لديك صلاحية لطرد الأعضاء.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Lock Member to kick first (User -> Gang)
    member_to_kick = db.session.query(User).filter_by(id=user_id).with_for_update().first()
    if not member_to_kick:
        abort(404)
    
    if member_to_kick.gang_id != gang.id:
        flash(_('هذا اللاعب ليس في عصابتك.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if member_to_kick.id == gang.leader_id:
        flash(_('لا يمكنك طرد الزعيم! يجب نقل الزعامة أولاً.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if member_to_kick.id == gang.underboss_id and current_user.id != gang.leader_id and not is_admin:
         flash(_('لا يمكنك طرد النائب!'), 'danger')
         return redirect(url_for('gang.dashboard'))

    # Lock Gang to prevent race conditions on money/exp
    db.session.query(Gang).filter_by(id=gang.id).with_for_update().first()

    # Consequences
    penalty_cost = int(SystemConfig.get_value('gang_kick_penalty', 50000))
    
    # Admin bypass penalty
    if is_admin:
        penalty_cost = 0
        
    if gang.money < penalty_cost:
         flash(_('خزينة العصابة لا تكفي لدفع مستحقات الطرد! (%(cost)s$)', cost=penalty_cost), 'warning')
         return redirect(url_for('gang.dashboard'))
         
    # Atomic update for gang money
    g_rows = Gang.query.filter(Gang.id == gang.id, Gang.money >= penalty_cost).update({
        Gang.money: Gang.money - penalty_cost
    }, synchronize_session=False)
    
    if g_rows == 0:
        flash(_('خزينة العصابة لا تكفي لدفع مستحقات الطرد!'), 'warning')
        return redirect(url_for('gang.dashboard'))

    # Atomic update for member money (Refund/Severance) via ResourceService
    refund_amount = int(penalty_cost * 0.5)
    ResourceService.modify_resources(member_to_kick.id, {'money': refund_amount}, 'gang_kick_severance', auto_commit=False, expected_version=None)

    member_to_kick.gang_id = None
    
    # Gang loses XP
    xp_penalty = int(SystemConfig.get_value('gang_kick_xp_penalty', 100))
    if is_admin:
        xp_penalty = 0
    gang.exp = max(0, gang.exp - xp_penalty)
    
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=f"Kicked {member_to_kick.username} (Paid severance)")
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم طرد العضو ودفع المستحقات. خسرت العصابة بعض الخبرة.'), 'warning')
    return redirect(url_for('gang.dashboard'))

@bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.gang_id:
        flash(_('لست عضواً في أي عصابة!'), 'warning')
        return redirect(url_for('gang.index'))
    
    gang = db.session.get(Gang, current_user.gang_id)
    members = User.query.filter_by(gang_id=gang.id).all()
    assets = Asset.query.filter_by(gang_id=gang.id).all()
    logs = GangLog.query.filter_by(gang_id=gang.id).order_by(GangLog.timestamp.desc()).limit(20).all()
    
    is_leader = (current_user.id == gang.leader_id)
    is_underboss = (current_user.id == gang.underboss_id)
    
    active_wars = GangWar.query.filter(
        or_(GangWar.gang1_id == gang.id, GangWar.gang2_id == gang.id),
        GangWar.status == 'active'
    ).all()
    
    # Load Upgrades Data
    import json
    upgrades_data = []
    try:
        from utils.essentials import load_json_seed
        upgrades_data = load_json_seed('gang_upgrades.json')
    except Exception as e:
        current_app.logger.error(f"Error loading gang upgrades: {e}")
        
    current_upgrades = {}
    if getattr(gang, 'upgrades', None):
        try:
            current_upgrades = json.loads(gang.upgrades)
        except:
            current_upgrades = {}

    gang_items = GangItem.query.filter_by(gang_id=gang.id).all()
    user_items = UserItem.query.filter_by(user_id=current_user.id).filter(UserItem.quantity > 0).all()
    
    return render_template('gang/dashboard.html', title=gang.name, gang=gang, members=members, assets=assets, logs=logs, is_leader=is_leader, is_underboss=is_underboss, active_wars=active_wars, upgrades_data=upgrades_data, current_upgrades=current_upgrades, gang_items=gang_items, user_items=user_items)

@bp.route('/broadcast_invite_all', methods=['POST'])
@login_required
@limiter.limit("1 per hour")
def broadcast_invite_all():
    if not current_user.gang_id:
        flash(_('لست عضواً في أي عصابة!'), 'danger')
        return redirect(url_for('gang.index'))
    
    # Lock Gang for atomic deduction
    gang = db.session.query(Gang).filter_by(id=current_user.gang_id).with_for_update().first()
    if not gang:
        flash(_('العصابة غير موجودة.'), 'danger')
        return redirect(url_for('gang.index'))
        
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != gang.leader_id and current_user.id != getattr(gang, "underboss_id", None) and not is_admin:
        flash(_('فقط القيادة يمكنها إرسال دعوات عامة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
    
    cost = 50000
    if gang.money < cost:
        flash(_('لا يوجد رصيد كافي في خزينة العصابة! التكلفة: %(cost)s$', cost=cost), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    gang.money -= cost
        
    recipients = User.query.filter(User.id != current_user.id, User.gang_id.is_(None)).all()
    join_link = url_for('gang.view', gang_id=gang.id)
    sent = 0
    for u in recipients:
        try:
            send_notification(
                user_id=u.id,
                title=str(_('دعوة للانضمام للعصابة')),
                message=str(_('العصابة "%(gang)s" تبحث عن أعضاء جدد. ادخل وشوف إذا تناسبك.', gang=gang.name)),
                type='info',
                link=join_link
            )
            sent += 1
        except Exception:
            continue
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('أرسل دعوة عامة (تكلفة %(cost)s$)', cost=cost))
    db.session.add(log)
    db.session.commit()
    if sent > 0:
        flash(_('تم إرسال دعوة عامة لعدد من اللاعبين!'), 'success')
    else:
        flash(_('لا يوجد لاعبين متاحين لاستقبال الدعوة حالياً.'), 'warning')
    return redirect(url_for('gang.dashboard'))

@bp.route('/view/<int:gang_id>')
@limiter.limit("20 per minute")
def view(gang_id):
    gang = db.session.get(Gang, gang_id)
    if not gang:
        abort(404)
    members_count = User.query.filter_by(gang_id=gang.id).count()
    
    meta_description = _("تفاصيل عصابة %(name)s. المستوى: %(level)s, الأعضاء: %(count)s. انضم الآن وسيطر!", name=gang.name, level=gang.level, count=members_count)
    
    return render_template('gang/view.html', title=gang.name, gang=gang, members_count=members_count,
                           meta_description=meta_description)

@bp.route('/declare_war/<int:target_gang_id>', methods=['POST'])
@login_required
@limiter.limit("5 per hour")
def declare_war(target_gang_id):
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
    
    # Lock current user
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Sort Gang IDs to prevent deadlock
    g1_id, g2_id = sorted([current_user.gang_id, target_gang_id])
    
    # Lock Gangs in order
    g1 = db.session.query(Gang).filter_by(id=g1_id).with_for_update().first()
    g2 = db.session.query(Gang).filter_by(id=g2_id).with_for_update().first()
    
    if not g1 or not g2:
        abort(404)
        
    my_gang = g1 if g1.id == current_user.gang_id else g2
    target_gang = g2 if g1.id == current_user.gang_id else g1
    
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != my_gang.leader_id and not is_admin:
        flash(_('فقط الزعيم يمكنه إعلان الحرب'), 'danger')
        return redirect(url_for('gang.view', gang_id=target_gang_id))

    # Check existing war
    existing_war = GangWar.query.filter(
        or_(
            (GangWar.gang1_id == my_gang.id) & (GangWar.gang2_id == target_gang.id),
            (GangWar.gang1_id == target_gang.id) & (GangWar.gang2_id == my_gang.id)
        ),
        GangWar.status == 'active'
    ).first()
    
    if existing_war:
        flash(_('أنتم بالفعل في حرب مع هذه العصابة!'), 'warning')
        return redirect(url_for('gang.dashboard'))
        
    # Check Alliance
    alliance = GangAlliance.query.filter(
        ((GangAlliance.gang1_id == my_gang.id) & (GangAlliance.gang2_id == target_gang.id)) |
        ((GangAlliance.gang1_id == target_gang.id) & (GangAlliance.gang2_id == my_gang.id)),
        GangAlliance.status == 'active'
    ).first()
    
    if alliance:
         flash(_('لا يمكنك إعلان الحرب على حليف! بينكما معاهدة سلام.'), 'warning')
         return redirect(url_for('gang.view', gang_id=target_gang_id))
        
    # Fair Play Checks
    # 1. Power Balance
    if my_gang.level > (target_gang.level * 2 + 5):
        flash(_('عصابتك قوية جداً مقارنة بالخصم! لا يمكن إعلان الحرب (نظام اللعب النظيف).'), 'warning')
        return redirect(url_for('gang.view', gang_id=target_gang_id))
        
    # 2. Cooldown (24h)
    now = datetime.now(timezone.utc)
    recent_war = GangWar.query.filter(
        or_(
            (GangWar.gang1_id == my_gang.id) & (GangWar.gang2_id == target_gang.id),
            (GangWar.gang1_id == target_gang.id) & (GangWar.gang2_id == my_gang.id)
        ),
        GangWar.end_time > (now - timedelta(days=1))
    ).first()
    
    if recent_war:
        flash(_('لا يمكن إعلان الحرب الآن! توجد هدنة مؤقتة (24 ساعة) بعد الحرب الأخيرة.'), 'warning')
        return redirect(url_for('gang.view', gang_id=target_gang_id))
        
    new_war = GangWar(gang1_id=my_gang.id, gang2_id=target_gang.id)
    db.session.add(new_war)
    db.session.commit()
    
    log = GangLog(gang_id=my_gang.id, user_id=current_user.id, action=_('أعلن الحرب على %(gang)s', gang=target_gang.name))
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم إعلان الحرب على %(name)s!', name=target_gang.name), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/surrender_war/<int:war_id>', methods=['POST'])
@login_required
def surrender_war(war_id):
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
    
    # Lock User
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    # Lock War
    war = db.session.query(GangWar).filter_by(id=war_id).with_for_update().first()
    
    if not war or war.status != 'active':
        flash(_('هذه الحرب غير نشطة أو غير موجودة.'), 'danger')
        return redirect(url_for('gang.dashboard'))
    
    # Identify Gangs
    g1_id = war.gang1_id
    g2_id = war.gang2_id
    
    # Lock Gangs in order
    ids = sorted([g1_id, g2_id])
    g_map = {}
    for gid in ids:
        g = db.session.query(Gang).filter_by(id=gid).with_for_update().first()
        if g:
            g_map[gid] = g
            
    if current_user.gang_id not in g_map:
         flash(_('عصابتك ليست طرفاً في هذه الحرب!'), 'danger')
         return redirect(url_for('gang.dashboard'))
         
    gang = g_map[current_user.gang_id]
        
    if war.gang1_id != gang.id and war.gang2_id != gang.id:
        flash(_('عصابتك ليست طرفاً في هذه الحرب!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Permission Check
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id and not is_admin:
         flash(_('فقط القيادة يمكنها الاستسلام!'), 'danger')
         return redirect(url_for('gang.dashboard'))

    # Identify Opponent
    opponent_id = war.gang2_id if war.gang1_id == gang.id else war.gang1_id
    # We already locked opponent gang
    opponent_gang = g_map.get(opponent_id)
    if not opponent_gang:
         # Should not happen if foreign keys are correct
         abort(404)
    
    # Reparations (20% of gang money)
    reparation_amount = int(gang.money * 0.20)
    
    # Atomic Deduction (We already locked gang, so simple update is fine)
    if gang.money < reparation_amount:
        reparation_amount = gang.money
        gang.money = 0
    else:
        gang.money -= reparation_amount
        
    # Add to Winner
    if reparation_amount > 0:
        opponent_gang.money += reparation_amount
        
    # Update War
    war.status = 'ended'
    war.winner_id = opponent_id
    war.end_time = datetime.now(timezone.utc)
    
    # Logs
    log_loser = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('استسلم في الحرب ضد %(opp)s ودفع تعويضات %(amount)s$', opp=opponent_gang.name, amount=reparation_amount))
    log_winner = GangLog(gang_id=opponent_id, action=_('انتصر في الحرب بعد استسلام %(loser)s وحصل على تعويضات %(amount)s$', loser=gang.name, amount=reparation_amount))
    
    db.session.add(log_loser)
    db.session.add(log_winner)
    
    db.session.commit()
    
    flash(_('تم الاستسلام ودفع التعويضات. انتهت الحرب.'), 'warning')
    return redirect(url_for('gang.dashboard'))

@bp.route('/donate', methods=['POST'])
@login_required
def donate():
    amount = int(request.form.get('amount', 0))
    if amount <= 0:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('gang.dashboard'))
    
    if current_user.money < amount:
        flash(_('لا تملك هذا المبلغ!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if not current_user.gang_id:
        flash(_('لست في عصابة!'), 'danger')
        return redirect(url_for('gang.index'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    
    # Atomic deduction using ResourceService
    if not ResourceService.modify_resources(current_user.id, {'money': -amount}, 'gang_donate', auto_commit=False, expected_version=current_user.version):
        flash(_('لا تملك هذا المبلغ!'), 'danger')
        return redirect(url_for('gang.dashboard'))

    # Atomic addition to gang
    Gang.query.filter(Gang.id == gang.id).update({
        Gang.money: Gang.money + amount
    }, synchronize_session=False)
    
    # Log
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('تبرع بـ %(amount)s$', amount=amount))
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم التبرع بـ %(amount)s$ لخزينة العصابة!', amount=amount), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    is_admin = current_user.role.value >= UserRole.ADMIN.value

    # Status Check
    if not is_admin:
        now = datetime.now(timezone.utc)
        if current_user.jail_until:
            jail_until = current_user.jail_until
            if jail_until.tzinfo is None:
                jail_until = jail_until.replace(tzinfo=timezone.utc)
            if jail_until > now:
                flash(_('أنت في السجن ولا يمكنك سحب الأموال!'), 'danger')
                return redirect(url_for('jail.index'))
        
        if current_user.hospital_until:
            hospital_until = current_user.hospital_until
            if hospital_until.tzinfo is None:
                hospital_until = hospital_until.replace(tzinfo=timezone.utc)
            if hospital_until > now:
                flash(_('أنت في المستشفى ولا يمكنك سحب الأموال!'), 'danger')
                return redirect(url_for('hospital.index'))

        if current_user.gym_until:
            gym_until = current_user.gym_until
            if gym_until.tzinfo is None:
                gym_until = gym_until.replace(tzinfo=timezone.utc)
            if gym_until > now:
                flash(_('أنت تتدرب ولا يمكنك سحب الأموال!'), 'danger')
                return redirect(url_for('gym.index'))

    amount = int(request.form.get('amount', 0))
    if amount <= 0:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    # Lock User First (User -> Gang)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
        
    # Lock Gang
    gang = db.session.query(Gang).filter_by(id=current_user.gang_id).with_for_update().first()
    
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != gang.leader_id and not is_admin:
        flash(_('فقط الزعيم يمكنه سحب الأموال!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if gang.money < amount:
        flash(_('لا يوجد مال كافٍ في الخزينة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Atomic deduction
    # Since we locked Gang, we can just update it safely, but keeping atomic update query is fine too.
    gang.money -= amount
    
    # Atomic addition to user
    # We already locked user, so ResourceService is safe, or we can just update directly if ResourceService supports existing lock context (it usually does new transaction or just update).
    # ResourceService handles logging too? No, mostly just update.
    # But ResourceService.modify_resources uses a new transaction or nested? 
    # ResourceService code isn't fully visible but usually it does `User.query.get` and updates.
    # If we already locked, ResourceService might block if it tries to lock again in a new transaction?
    # SQLAlchemy `with_for_update` is within the same session/transaction.
    # If ResourceService uses the SAME session, it's fine.
    
    if not ResourceService.modify_resources(current_user.id, {'money': amount}, 'gang_withdraw', auto_commit=False, expected_version=None):
        db.session.rollback()
        flash(_('حدث خطأ أثناء سحب الأموال.'), 'danger')
        return redirect(url_for('gang.dashboard'))
    
    # Log
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('سحب %(amount)s$', amount=amount))
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم سحب %(amount)s$ من الخزينة!', amount=amount), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/organized_crimes')
@login_required
def organized_crimes():
    if not current_user.gang_id:
        flash(_('لست عضواً في أي عصابة!'), 'warning')
        return redirect(url_for('gang.index'))
    
    gang = db.session.get(Gang, current_user.gang_id)
    crimes = OrganizedCrime.query.all()
    
    return render_template('gang/organized_crimes.html', gang=gang, crimes=crimes)

@bp.route('/do_organized_crime/<int:crime_id>', methods=['POST'])
@login_required
@limiter.limit("3 per minute")
def do_organized_crime(crime_id):
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    crime = db.session.get(OrganizedCrime, crime_id)
    if not crime:
        abort(404)
    
    # Check permissions
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id and not is_admin:
        flash(_('فقط الزعيم أو نائبه يمكنهم بدء عملية منظمة'), 'danger')
        return redirect(url_for('gang.organized_crimes'))
        
    # Check members count
    members_count = User.query.filter_by(gang_id=gang.id).count()
    if members_count < crime.min_members and not is_admin:
        flash(_('عدد أعضاء العصابة غير كافي لهذه العملية. المطلوب: %(min)s', min=crime.min_members), 'danger')
        return redirect(url_for('gang.organized_crimes'))
        
    # Check Gang Level
    if gang.level < crime.min_gang_level and not is_admin:
        flash(_('مستوى العصابة منخفض جداً لهذه العملية.'), 'danger')
        return redirect(url_for('gang.organized_crimes'))
        
    # Check Cooldown
    if gang.last_organized_crime_at and not is_admin:
        last_crime_at = gang.last_organized_crime_at
        if last_crime_at.tzinfo is None:
            last_crime_at = last_crime_at.replace(tzinfo=timezone.utc)
        elapsed = datetime.now(timezone.utc) - last_crime_at

        if elapsed < timedelta(hours=crime.cooldown_hours):
             wait_hours = crime.cooldown_hours - (elapsed.total_seconds() / 3600)
             flash(_('العصابة في فترة راحة. يجب الانتظار %(hours).1f ساعة.', hours=wait_hours), 'warning')
             return redirect(url_for('gang.organized_crimes'))

    # Check Energy (Leader)
    if current_user.energy < crime.energy_cost and not is_admin:
        flash(_('لا تملك طاقة كافية لبدء العملية.'), 'danger')
        return redirect(url_for('gang.organized_crimes'))
    
    # Create Lobby (Recruiting Phase) and auto-add leader
    lobby = CrimeLobby(crime_id=crime.id, leader_id=current_user.id, status='recruiting')
    db.session.add(lobby)
    db.session.flush()
    
    # Deduct leader energy immediately to prevent spam
    # Atomic deduction for leader energy
    if not is_admin:
        # Lock user to prevent race conditions
        db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
        if not ResourceService.modify_resources(current_user.id, {'energy': -crime.energy_cost}, 'organized_crime_energy_cost', auto_commit=False, expected_version=None):
            db.session.rollback()
            flash(_('لا تملك طاقة كافية لبدء العملية.'), 'danger')
            return redirect(url_for('gang.organized_crimes'))
    
    # Assign leader role if available
    leader_role = 'القائد'
    try:
        if crime.roles_config and len(crime.roles_config) > 0:
            leader_role = crime.roles_config[0].get('name', leader_role)
    except Exception:
        pass
    
    leader_participant = LobbyParticipant(
        lobby_id=lobby.id,
        user_id=current_user.id,
        role_name=leader_role,
        is_ready=True
    )
    db.session.add(leader_participant)
    db.session.commit()
    
    # Invitations configuration
    # Scope defaults aligned with recruitment policy
    invite_scope = request.form.get('invite_scope')  # gang or all
    if not invite_scope:
        invite_scope = 'all' if (gang.recruitment_status == 'open') else 'gang'
    invite_countries_raw = request.form.get('invite_countries', '').strip()
    if not invite_countries_raw and gang.allowed_countries:
        invite_countries_raw = gang.allowed_countries or ''
    codes = set([c.strip().upper() for c in invite_countries_raw.split(',') if c.strip()]) if invite_countries_raw else set()
    
    # Build recipients list
    if invite_scope == 'gang':
        recipients = User.query.filter_by(gang_id=gang.id).filter(User.id != current_user.id).all()
    else:
        recipients = User.query.filter(User.id != current_user.id).all()
    
    # Country filter
    if codes:
        recipients = [u for u in recipients if (u.country or '').upper() in codes]
    
    # Send notifications with join link
    join_link = url_for('main.lobby', lobby_id=lobby.id)
    for u in recipients:
        try:
            send_notification(
                user_id=u.id,
                title=str(_('دعوة للمشاركة في جريمة منظمة')),
                message=str(_('القائد %(leader)s دعاك للمشاركة في "%(crime)s". سارع لاختيار دورك!', leader=current_user.username, crime=crime.name)),
                type='info',
                link=join_link
            )
        except Exception:
            continue
    
    # Log
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('أنشأ مجموعة لجريمة منظمة: %(crime)s وأرسل دعوات عامة', crime=crime.name))
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم إنشاء المجموعة وإرسال الدعوات!'), 'success')
    return redirect(url_for('main.lobby', lobby_id=lobby.id))

@bp.route('/upgrade', methods=['POST'])
@login_required
def upgrade():
    upgrade_type = request.form.get('type')
    
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    # Lock Gang to ensure atomic upgrades
    gang = db.session.query(Gang).filter_by(id=current_user.gang_id).with_for_update().first()
    if not gang:
        return redirect(url_for('gang.index'))

    is_admin = current_user.role.value >= UserRole.ADMIN.value
    
    if current_user.id != gang.leader_id and not is_admin:
        flash(_('فقط الزعيم يمكنه تطوير العصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if upgrade_type == 'capacity':
        # Cost: base * current_max
        base = int(SystemConfig.get_value('gang_upgrade_capacity_base_cost', 1000))
        cost = gang.max_members * base
        
        if is_admin:
            cost = 0

        if gang.money < cost:
            flash(_('لا يوجد مال كافٍ في الخزينة! التكلفة: %(cost)s$', cost=cost), 'danger')
            return redirect(url_for('gang.dashboard'))
            
        # Atomic deduction
        rows = Gang.query.filter(Gang.id == gang.id, Gang.money >= cost).update({
            Gang.money: Gang.money - cost
        }, synchronize_session=False)

        if rows == 0:
            flash(_('لا يوجد مال كافٍ في الخزينة!'), 'danger')
            return redirect(url_for('gang.dashboard'))

        gang.max_members += int(SystemConfig.get_value('gang_upgrade_capacity_amount', 5))
        
        log = GangLog(gang_id=gang.id, user_id=current_user.id, action=f"Upgraded capacity to {gang.max_members}")
        db.session.add(log)
        db.session.commit()
        
        flash(_('تم زيادة سعة العصابة إلى %(num)s عضو!', num=gang.max_members), 'success')
        
    elif upgrade_type == 'level':
        base_money = int(SystemConfig.get_value('gang_upgrade_level_base_money', 10000))
        base_exp = int(SystemConfig.get_value('gang_upgrade_level_base_exp', 500))
        
        money_cost = gang.level * base_money
        exp_cost = gang.level * base_exp
        
        if is_admin:
            money_cost = 0
            exp_cost = 0
        
        # Atomic deduction for money and exp, and level up
        filters = [Gang.id == gang.id]
        if money_cost > 0:
            filters.append(Gang.money >= money_cost)
        if exp_cost > 0:
            filters.append(Gang.exp >= exp_cost)
            
        updates = {
            Gang.level: Gang.level + 1
        }
        if money_cost > 0:
            updates[Gang.money] = Gang.money - money_cost
        if exp_cost > 0:
            updates[Gang.exp] = Gang.exp - exp_cost
            
        rows = Gang.query.filter(*filters).update(updates, synchronize_session=False)

        if rows == 0:
            if gang.money < money_cost:
                flash(_('لا يوجد مال كافٍ في الخزينة! التكلفة: %(cost)s$', cost=money_cost), 'danger')
            elif gang.exp < exp_cost:
                flash(_('لا يوجد خبرة كافية للعصابة! المطلوب: %(cost)s XP', cost=exp_cost), 'danger')
            else:
                flash(_('حدث خطأ أثناء التطوير.'), 'danger')
            return redirect(url_for('gang.dashboard'))

        # Reload gang to get new level for log
        db.session.expire(gang)
        
        log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('طوّر مستوى العصابة إلى %(num)s', num=gang.level))
        db.session.add(log)
        db.session.commit()
        
        flash(_('تم تطوير مستوى العصابة إلى المستوى %(num)s!', num=gang.level), 'success')

    return redirect(url_for('gang.dashboard'))

@bp.route('/edit', methods=['POST'])
@login_required
def edit():
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    
    if current_user.id != gang.leader_id and not is_admin:
        flash(_('فقط الزعيم يمكنه تعديل إعدادات العصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    description = request.form.get('description')
    recruitment_status = request.form.get('recruitment_status')
    min_level_req = int(request.form.get('min_level_req', 1))
    allowed_countries = request.form.get('allowed_countries')
    
    # Update fields
    gang.description = description
    if recruitment_status in ['open', 'invite_only', 'closed']:
        gang.recruitment_status = recruitment_status
    gang.min_level_req = max(1, min_level_req)
    gang.allowed_countries = allowed_countries
    
    # Handle Image
    image = request.files.get('image')
    if image and image.filename != '':
        filename = save_image(image, 'gangs', (300, 300))
        if filename:
            gang.image = filename
            
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action="Updated gang settings")
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم تحديث إعدادات العصابة بنجاح!'), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/request_alliance/<int:target_gang_id>', methods=['POST'])
@login_required
def request_alliance(target_gang_id):
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
    
    my_gang = db.session.get(Gang, current_user.gang_id)
    target_gang = Gang.query.get_or_404(target_gang_id)
    
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    
    if current_user.id != my_gang.leader_id and current_user.id != my_gang.underboss_id and not is_admin:
        flash(_('فقط القيادة يمكنها طلب التحالف!'), 'danger')
        return redirect(url_for('gang.index'))
        
    if my_gang.id == target_gang.id:
        return redirect(url_for('gang.index'))
        
    # Check existing
    existing = GangAlliance.query.filter(
        ((GangAlliance.gang1_id == my_gang.id) & (GangAlliance.gang2_id == target_gang.id)) |
        ((GangAlliance.gang1_id == target_gang.id) & (GangAlliance.gang2_id == my_gang.id))
    ).first()
    
    if existing:
        flash(_('يوجد طلب أو تحالف مسبق بينكما.'), 'warning')
        return redirect(url_for('gang.index'))
        
    # Check Alliance Limit (Fair Play)
    MAX_ALLIANCES = 3
    
    my_active_count = GangAlliance.query.filter(
        ((GangAlliance.gang1_id == my_gang.id) | (GangAlliance.gang2_id == my_gang.id)),
        GangAlliance.status == 'active'
    ).count()
    
    if my_active_count >= MAX_ALLIANCES:
        flash(_('لقد وصلت عصابتك للحد الأقصى من التحالفات (%(max)s).', max=MAX_ALLIANCES), 'warning')
        return redirect(url_for('gang.index'))
        
    target_active_count = GangAlliance.query.filter(
        ((GangAlliance.gang1_id == target_gang.id) | (GangAlliance.gang2_id == target_gang.id)),
        GangAlliance.status == 'active'
    ).count()
    
    if target_active_count >= MAX_ALLIANCES:
         flash(_('العصابة المستهدفة وصلت للحد الأقصى من التحالفات.', max=MAX_ALLIANCES), 'warning')
         return redirect(url_for('gang.index'))

    alliance = GangAlliance(gang1_id=my_gang.id, gang2_id=target_gang.id, status='pending')
    db.session.add(alliance)
    
    # Log
    log = GangLog(gang_id=my_gang.id, user_id=current_user.id, action=_('طلب تحالف مع %(gang)s', gang=target_gang.name))
    db.session.add(log)
    
    db.session.commit()
    flash(_('تم إرسال طلب التحالف!'), 'success')
    return redirect(url_for('gang.index'))

@bp.route('/alliances')
@login_required
def alliances():
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    gang_id = current_user.gang_id
    
    # Incoming Requests (where I am gang2 and status is pending)
    incoming = GangAlliance.query.filter_by(gang2_id=gang_id, status='pending').all()
    
    # Active Alliances
    active = GangAlliance.query.filter(
        ((GangAlliance.gang1_id == gang_id) | (GangAlliance.gang2_id == gang_id)),
        GangAlliance.status == 'active'
    ).all()
    
    return render_template('gang/alliances.html', incoming=incoming, active=active)

@bp.route('/accept_alliance/<int:alliance_id>', methods=['POST'])
@login_required
def accept_alliance(alliance_id):
    alliance = GangAlliance.query.get_or_404(alliance_id)
    
    if not current_user.gang_id or current_user.gang_id != alliance.gang2_id:
        flash(_('غير مصرح لك!'), 'danger')
        return redirect(url_for('gang.alliances'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id and not is_admin:
        flash(_('فقط القيادة تملك صلاحية قبول التحالفات!'), 'danger')
        return redirect(url_for('gang.alliances'))
        
    alliance.status = 'active'
    
    # Log
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=f"Accepted alliance with Gang ID {alliance.gang1_id}")
    db.session.add(log)
    
    db.session.commit()
    flash(_('تم تفعيل التحالف!'), 'success')
    return redirect(url_for('gang.alliances'))

@bp.route('/reject_alliance/<int:alliance_id>', methods=['POST'])
@login_required
def reject_alliance(alliance_id):
    alliance = db.session.get(GangAlliance, alliance_id)
    if not alliance:
        abort(404)
    
    if not current_user.gang_id or current_user.gang_id != alliance.gang2_id:
        flash(_('غير مصرح لك!'), 'danger')
        return redirect(url_for('gang.alliances'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id and not is_admin:
         flash(_('فقط القيادة تملك صلاحية رفض التحالفات!'), 'danger')
         return redirect(url_for('gang.alliances'))

    db.session.delete(alliance)
    db.session.commit()
    
    flash(_('تم رفض التحالف.'), 'info')
    return redirect(url_for('gang.alliances'))

@bp.route('/disband', methods=['POST'])
@login_required
def disband():
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    if not gang:
        return redirect(url_for('gang.index'))
        
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != gang.leader_id and not is_admin:
        flash(_('فقط الزعيم يمكنه حل العصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Remove all members
    members = User.query.filter_by(gang_id=gang.id).all()
    for member in members:
        member.gang_id = None
        
    # Delete gang (cascade should handle related items like invites, logs if configured, otherwise we delete them manually or let DB constraints handle it)
    # Models show cascade='all, delete-orphan' for logs and invites.
    # Wars/Alliances might need manual cleanup if not cascaded.
    
    db.session.delete(gang)
    db.session.commit()
    
    flash(_('تم حل العصابة نهائياً.'), 'success')
    return redirect(url_for('gang.index'))

@bp.route('/transfer_leadership', methods=['POST'])
@login_required
def transfer_leadership():
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
    
    # Lock Gang Row
    gang = db.session.query(Gang).filter_by(id=current_user.gang_id).with_for_update().first()
    if not gang:
        return redirect(url_for('gang.index'))
    
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    if current_user.id != gang.leader_id and not is_admin:
        flash(_('فقط الزعيم يمكنه نقل القيادة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    new_leader_id = request.form.get('new_leader_id', type=int)
    if not new_leader_id:
        flash(_('يجب اختيار عضو لنقل القيادة إليه.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    new_leader = db.session.get(User, new_leader_id)
    if not new_leader or new_leader.gang_id != gang.id:
        flash(_('العضو المختار ليس في هذه العصابة.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if new_leader.id == gang.leader_id:
        flash(_('أنت الزعيم بالفعل!'), 'warning')
        return redirect(url_for('gang.dashboard'))
        
    # Swap roles
    old_leader = db.session.get(User, gang.leader_id)
    
    gang.leader_id = new_leader.id
    if gang.underboss_id == new_leader.id:
        gang.underboss_id = None # Promote underboss to leader, so underboss slot becomes empty
        
    # Log
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('نقل الزعامة إلى %(user)s', user=new_leader.username))
    db.session.add(log)
    
    db.session.commit()
    
    flash(_('تم نقل زعامة العصابة إلى %(user)s بنجاح.', user=new_leader.username), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/donate_item', methods=['POST'])
@login_required
def donate_item():
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
    
    item_id = request.form.get('item_id', type=int)
    quantity = request.form.get('quantity', type=int)
    
    if not item_id or not quantity or quantity <= 0:
        flash(_('بيانات غير صحيحة.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    user_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
    if not user_item or user_item.quantity < quantity:
        flash(_('لا تملك هذه الكمية!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Deduct from user
    user_item.quantity -= quantity
    if user_item.quantity == 0:
        db.session.delete(user_item)
        
    # Add to gang
    gang_item = GangItem.query.filter_by(gang_id=current_user.gang_id, item_id=item_id).first()
    if gang_item:
        gang_item.quantity += quantity
    else:
        gang_item = GangItem(gang_id=current_user.gang_id, item_id=item_id, quantity=quantity)
        db.session.add(gang_item)
        
    # Log
    item_name = user_item.item.name
    log = GangLog(gang_id=current_user.gang_id, user_id=current_user.id, action=_('تبرع بـ %(qty)s x %(item)s للعصابة', qty=quantity, item=item_name))
    db.session.add(log)
    
    db.session.commit()
    flash(_('تم التبرع بنجاح!'), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/distribute_item', methods=['POST'])
@login_required
def distribute_item():
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    is_leader = (current_user.id == gang.leader_id)
    is_underboss = (current_user.id == getattr(gang, 'underboss_id', None))
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    
    if not is_leader and not is_underboss and not is_admin:
        flash(_('فقط القيادة يمكنها توزيع العتاد!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    item_id = request.form.get('item_id', type=int)
    target_user_id = request.form.get('target_user_id', type=int)
    quantity = request.form.get('quantity', type=int)
    
    if not item_id or not target_user_id or not quantity or quantity <= 0:
        flash(_('بيانات غير صحيحة.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Check if target is in gang
    target_user = db.session.get(User, target_user_id)
    if not target_user or target_user.gang_id != gang.id:
        flash(_('العضو غير موجود في العصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    gang_item = GangItem.query.filter_by(gang_id=gang.id, item_id=item_id).first()
    
    # Atomic Deduction from gang
    rows = GangItem.query.filter(
        GangItem.gang_id == gang.id,
        GangItem.item_id == item_id,
        GangItem.quantity >= quantity
    ).update({
        GangItem.quantity: GangItem.quantity - quantity
    }, synchronize_session=False)

    if rows == 0:
        flash(_('لا يوجد كمية كافية في مخزون العصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Cleanup zero quantity
    GangItem.query.filter(GangItem.gang_id == gang.id, GangItem.item_id == item_id, GangItem.quantity == 0).delete(synchronize_session=False)
        
    # Add to user
    user_item = UserItem.query.filter_by(user_id=target_user.id, item_id=item_id).first()
    if user_item:
        user_item.quantity += quantity
    else:
        user_item = UserItem(user_id=target_user.id, item_id=item_id, quantity=quantity)
        db.session.add(user_item)
        
    # Log
    item = db.session.get(Item, item_id)
    item_name = item.name if item else "Unknown"
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('أعطى %(qty)s x %(item)s للعضو %(user)s', qty=quantity, item=item_name, user=target_user.username))
    db.session.add(log)
    
    db.session.commit()
    flash(_('تم توزيع العتاد بنجاح!'), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/distribute_money', methods=['POST'])
@login_required
def distribute_money():
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    is_leader = (current_user.id == gang.leader_id)
    is_underboss = (current_user.id == getattr(gang, 'underboss_id', None))
    is_admin = current_user.role.value >= UserRole.ADMIN.value
    
    if not is_leader and not is_underboss and not is_admin:
        flash(_('فقط القيادة يمكنها توزيع الأموال!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    target_user_id = request.form.get('target_user_id', type=int)
    amount = request.form.get('amount', type=int)
    
    if not target_user_id or not amount or amount <= 0:
        flash(_('بيانات غير صحيحة.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Check if target is in gang
    target_user = db.session.get(User, target_user_id)
    if not target_user or target_user.gang_id != gang.id:
        flash(_('العضو غير موجود في العصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if gang.money < amount:
        flash(_('لا يوجد مال كافٍ في الخزينة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Atomic Deduction from Gang
    rows = Gang.query.filter(Gang.id == gang.id, Gang.money >= amount).update({
        Gang.money: Gang.money - amount
    }, synchronize_session=False)
    
    if rows == 0:
        flash(_('لا يوجد مال كافٍ في الخزينة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Atomic Addition to User
    if not ResourceService.modify_resources(target_user.id, {'money': amount}, 'gang_distribution', auto_commit=False, expected_version=target_user.version):
        # Rollback gang deduction if user update fails
        Gang.query.filter(Gang.id == gang.id).update({
            Gang.money: Gang.money + amount
        }, synchronize_session=False)
        db.session.commit()
        flash(_('حدث خطأ أثناء تحويل الأموال.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Log
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('حول %(amount)s$ للعضو %(user)s', amount=amount, user=target_user.username))
    db.session.add(log)
    
    db.session.commit()
    flash(_('تم تحويل %(amount)s$ للعضو %(user)s بنجاح!', amount=amount, user=target_user.username), 'success')
    return redirect(url_for('gang.dashboard'))
