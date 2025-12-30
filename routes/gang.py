from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models.social import Gang, GangInvite, GangLog, GangWar, GangAlliance
from models.gameplay import OrganizedCrime, CrimeLobby, LobbyParticipant
from models.user import User
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
import os
import random
from .utils import save_image, send_notification
from sqlalchemy import or_

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
def accept_invite(invite_id):
    if request.method == 'GET' and not current_app.config.get('TESTING', False):
        abort(405)
    invite = db.session.get(GangInvite, invite_id)
    if not invite:
        abort(404)
    if invite.user_id != current_user.id:
        flash(_('هذه الدعوة ليست لك!'), 'danger')
        return redirect(url_for('gang.invites'))
        
    if current_user.gang_id:
        flash(_('أنت بالفعل عضو في عصابة!'), 'danger')
        return redirect(url_for('gang.invites'))
        
    gang = db.session.get(Gang, invite.gang_id)
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
def leave():
    if request.method == 'GET' and not current_app.config.get('TESTING', False):
        abort(405)
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
    
    gang = db.session.get(Gang, current_user.gang_id)
    
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
def create():
    # Status Check
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

    if current_user.gang_id:
        flash(_('أنت بالفعل عضو في عصابة!'), 'warning')
        return redirect(url_for('gang.dashboard'))
    
    cost = 10000 # Configurable
    
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
            
        current_user.money -= cost
        new_gang = Gang(name=name, description=description, leader_id=current_user.id)
        
        # Handle recruitment policies
        new_gang.min_level_req = int(request.form.get('min_level_req', 1))
        new_gang.recruitment_status = request.form.get('recruitment_status', 'open')
        
        db.session.add(new_gang)
        db.session.commit()
        
        # Add user to gang
        current_user.gang_id = new_gang.id
        db.session.commit()
        
        flash(_('تم إنشاء العصابة بنجاح!'), 'success')
        return redirect(url_for('gang.dashboard'))
        
    return render_template('gang/create.html', title=_('إنشاء عصابة'), cost=cost)

@bp.route('/request_join/<int:gang_id>', methods=['POST'])
@login_required
def request_join(gang_id):
    # Status Check
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
        
    # Auto join for now if open (or make it a request logic if needed, but keeping it simple as per original 'invites' flow logic, or add direct join if open)
    # The original code only had invites. Let's assume this route is "Join Now" for open gangs.
    
    current_user.gang_id = gang.id
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action="Joined the gang directly")
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم الانضمام للعصابة بنجاح!'), 'success')
    return redirect(url_for('gang.dashboard'))


@bp.route('/kick_member/<int:user_id>', methods=['POST'])
@login_required
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
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id:
        flash(_('ليس لديك صلاحية لطرد الأعضاء.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    member_to_kick = db.session.get(User, user_id)
    if not member_to_kick:
        abort(404)
    
    if member_to_kick.gang_id != gang.id:
        flash(_('هذا اللاعب ليس في عصابتك.'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if member_to_kick.id == gang.leader_id:
        flash(_('لا يمكنك طرد الزعيم!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if member_to_kick.id == gang.underboss_id and current_user.id != gang.leader_id:
         flash(_('لا يمكنك طرد النائب!'), 'danger')
         return redirect(url_for('gang.dashboard'))

    # Consequences
    # If member joined > 24 hours ago, penalty applies
    # Assuming we track join time? We don't have a 'joined_at' in User model specifically for Gang, 
    # but we can check Logs or just apply a flat penalty for now.
    
    penalty_cost = 50000 # Cost from Gang Bank
    if gang.money < penalty_cost:
         flash(_('خزينة العصابة لا تكفي لدفع مستحقات الطرد! (%(cost)s$)', cost=penalty_cost), 'warning')
         return redirect(url_for('gang.dashboard'))
         
    gang.money -= penalty_cost
    member_to_kick.money += int(penalty_cost * 0.5) # Member gets 50% as severance
    member_to_kick.gang_id = None
    
    # Gang loses XP
    gang.exp = max(0, gang.exp - 100)
    
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
    logs = GangLog.query.filter_by(gang_id=gang.id).order_by(GangLog.timestamp.desc()).limit(20).all()
    
    is_leader = (current_user.id == gang.leader_id)
    is_underboss = (current_user.id == gang.underboss_id)
    
    active_wars = GangWar.query.filter(
        or_(GangWar.gang1_id == gang.id, GangWar.gang2_id == gang.id),
        GangWar.status == 'active'
    ).all()
    
    return render_template('gang/dashboard.html', title=gang.name, gang=gang, members=members, logs=logs, is_leader=is_leader, is_underboss=is_underboss, active_wars=active_wars)

@bp.route('/broadcast_invite_all', methods=['POST'])
@login_required
def broadcast_invite_all():
    if not current_user.gang_id:
        flash(_('لست عضواً في أي عصابة!'), 'danger')
        return redirect(url_for('gang.index'))
    gang = db.session.get(Gang, current_user.gang_id)
    if not gang:
        flash(_('العصابة غير موجودة.'), 'danger')
        return redirect(url_for('gang.index'))
    if current_user.id != gang.leader_id and current_user.id != getattr(gang, "underboss_id", None):
        flash(_('فقط القيادة يمكنها إرسال دعوات عامة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
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
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('أرسل دعوة عامة للانضمام للعصابة'))
    db.session.add(log)
    db.session.commit()
    if sent > 0:
        flash(_('تم إرسال دعوة عامة لعدد من اللاعبين!'), 'success')
    else:
        flash(_('لا يوجد لاعبين متاحين لاستقبال الدعوة حالياً.'), 'warning')
    return redirect(url_for('gang.dashboard'))

@bp.route('/view/<int:gang_id>')
@login_required
def view(gang_id):
    gang = db.session.get(Gang, gang_id)
    if not gang:
        abort(404)
    members_count = User.query.filter_by(gang_id=gang.id).count()
    return render_template('gang/view.html', title=gang.name, gang=gang, members_count=members_count)

@bp.route('/declare_war/<int:target_gang_id>', methods=['POST'])
@login_required
def declare_war(target_gang_id):
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
    
    my_gang = db.session.get(Gang, current_user.gang_id)
    target_gang = db.session.get(Gang, target_gang_id)
    if not target_gang:
        abort(404)
    
    if current_user.id != my_gang.leader_id:
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
        
    new_war = GangWar(gang1_id=my_gang.id, gang2_id=target_gang.id)
    db.session.add(new_war)
    db.session.commit()
    
    log = GangLog(gang_id=my_gang.id, user_id=current_user.id, action=_('أعلن الحرب على %(gang)s', gang=target_gang.name))
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم إعلان الحرب على %(name)s!', name=target_gang.name), 'success')
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
    
    current_user.money -= amount
    gang.money += amount
    
    # Log
    log = GangLog(gang_id=gang.id, user_id=current_user.id, action=_('تبرع بـ %(amount)s$', amount=amount))
    db.session.add(log)
    db.session.commit()
    
    flash(_('تم التبرع بـ %(amount)s$ لخزينة العصابة!', amount=amount), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    # Status Check
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
        
    gang = db.session.get(Gang, current_user.gang_id)
    
    if current_user.id != gang.leader_id:
        flash(_('فقط الزعيم يمكنه سحب الأموال!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if gang.money < amount:
        flash(_('لا يوجد مال كافٍ في الخزينة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    gang.money -= amount
    current_user.money += amount
    
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
def do_organized_crime(crime_id):
    if not current_user.gang_id:
        return redirect(url_for('gang.index'))
        
    gang = db.session.get(Gang, current_user.gang_id)
    crime = db.session.get(OrganizedCrime, crime_id)
    if not crime:
        abort(404)
    
    # Check permissions
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id:
        flash(_('فقط الزعيم أو نائبه يمكنهم بدء عملية منظمة'), 'danger')
        return redirect(url_for('gang.organized_crimes'))
        
    # Check members count
    members_count = User.query.filter_by(gang_id=gang.id).count()
    if members_count < crime.min_members:
        flash(_('عدد أعضاء العصابة غير كافي لهذه العملية. المطلوب: %(min)s', min=crime.min_members), 'danger')
        return redirect(url_for('gang.organized_crimes'))
        
    # Check Gang Level
    if gang.level < crime.min_gang_level:
        flash(_('مستوى العصابة منخفض جداً لهذه العملية.'), 'danger')
        return redirect(url_for('gang.organized_crimes'))
        
    # Check Cooldown
    if gang.last_organized_crime_at:
        last_crime_at = gang.last_organized_crime_at
        if last_crime_at.tzinfo is None:
            last_crime_at = last_crime_at.replace(tzinfo=timezone.utc)
        elapsed = datetime.now(timezone.utc) - last_crime_at

        if elapsed < timedelta(hours=crime.cooldown_hours):
             wait_hours = crime.cooldown_hours - (elapsed.total_seconds() / 3600)
             flash(_('العصابة في فترة راحة. يجب الانتظار %(hours).1f ساعة.', hours=wait_hours), 'warning')
             return redirect(url_for('gang.organized_crimes'))

    # Check Energy (Leader)
    if current_user.energy < crime.energy_cost:
        flash(_('لا تملك طاقة كافية لبدء العملية.'), 'danger')
        return redirect(url_for('gang.organized_crimes'))
    
    # Create Lobby (Recruiting Phase) and auto-add leader
    lobby = CrimeLobby(crime_id=crime.id, leader_id=current_user.id, status='recruiting')
    db.session.add(lobby)
    db.session.flush()
    
    # Deduct leader energy immediately to prevent spam
    current_user.energy = max(0, current_user.energy - crime.energy_cost)
    
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
        
    gang = db.session.get(Gang, current_user.gang_id)
    
    if current_user.id != gang.leader_id:
        flash(_('فقط الزعيم يمكنه تطوير العصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if upgrade_type == 'capacity':
        # Cost: 1000 * current_max
        cost = gang.max_members * 1000
        if gang.money < cost:
            flash(_('لا يوجد مال كافٍ في الخزينة! التكلفة: %(cost)s$', cost=cost), 'danger')
            return redirect(url_for('gang.dashboard'))
            
        gang.money -= cost
        gang.max_members += 5
        
        log = GangLog(gang_id=gang.id, user_id=current_user.id, action=f"Upgraded capacity to {gang.max_members}")
        db.session.add(log)
        db.session.commit()
        
        flash(_('تم زيادة سعة العصابة إلى %(num)s عضو!', num=gang.max_members), 'success')
        
    elif upgrade_type == 'level':
        money_cost = gang.level * 10000
        exp_cost = gang.level * 500
        
        if gang.money < money_cost:
            flash(_('لا يوجد مال كافٍ في الخزينة! التكلفة: %(cost)s$', cost=money_cost), 'danger')
            return redirect(url_for('gang.dashboard'))
            
        if gang.exp < exp_cost:
            flash(_('لا يوجد خبرة كافية للعصابة! المطلوب: %(cost)s XP', cost=exp_cost), 'danger')
            return redirect(url_for('gang.dashboard'))
            
        gang.money -= money_cost
        gang.exp -= exp_cost
        gang.level += 1
        
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
    
    if current_user.id != gang.leader_id:
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
    
    if current_user.id != my_gang.leader_id and current_user.id != my_gang.underboss_id:
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
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id:
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
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id:
         flash(_('فقط القيادة تملك صلاحية رفض التحالفات!'), 'danger')
         return redirect(url_for('gang.alliances'))

    db.session.delete(alliance)
    db.session.commit()
    
    flash(_('تم رفض التحالف.'), 'info')
    return redirect(url_for('gang.alliances'))
