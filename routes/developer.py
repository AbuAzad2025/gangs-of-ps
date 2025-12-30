from flask import render_template, request, flash, redirect, url_for, abort, current_app
from werkzeug.utils import secure_filename
import os
import json
from flask_login import current_user
from flask_babel import _
from . import bp
from decorators import developer_required
from models.user import User, UserRank, UserRole
from models.social import Gang, Message
from models.gameplay import Crime, DailyTask, HeistHistory, CrimeLobby, OrganizedCrime, ResurrectionRequest
from models.knowledge import HostessKnowledge
from models.bounty import Bounty
from models.system import SystemConfig, Announcement
from models.log import GameLog
from models.events import WeeklyWinner
from models.hostess import Hostess, VideoScenario, HostessChatMessage, HostessMemory
from services.hostess_training_service import build_greeter_leader_prompt, build_greeter_leader_training_json
from models.item import Item
from models.vehicle import Vehicle
from models.location import Location
from models.economy import Asset
from models.factory import FactoryJob
from models.market import MarketAsset, UserInvestment, FuturesPosition
from models.forum import ForumCategory, ForumTopic
from models.achievement import Achievement, UserAchievement
from forms.developer import (
    GangForm, HostessKnowledgeForm, OrganizedCrimeForm, HostessForm,
    VehicleForm, ItemForm, CrimeForm, AssetForm, TaskForm, AnnouncementForm,
    ForumCategoryForm, LocationForm, AchievementForm, VideoScenarioForm,
    SystemConfigForm, FactoryJobForm, MarketAssetForm
)
from extensions import db
from utils.backup_manager import BackupManager
from .utils import save_image
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

@bp.route('/developer')
@developer_required
def dev_dashboard():
    # Calculate stats
    total_users = User.query.count()
    total_money = db.session.query(func.sum(User.money)).scalar() or 0
    total_diamonds = db.session.query(func.sum(User.diamonds)).scalar() or 0
    new_users_today = User.query.filter(User.created_at >= datetime.now().date()).count()
    
    stats = SimpleNamespace(
        total_users=total_users,
        total_money=total_money,
        total_diamonds=total_diamonds,
        new_users_today=new_users_today
    )
    
    backups = BackupManager.get_backups()
    
    return render_template('developer/dashboard.html', stats=stats, backups=backups, title=_('لوحة تحكم المطور'))

# --- Backups ---
@bp.route('/developer/backup/create', methods=['POST'])
@developer_required
def create_backup():
    success, message = BackupManager.create_backup()
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('main.dev_dashboard'))

@bp.route('/developer/backup/restore/<filename>', methods=['POST'])
@developer_required
def restore_backup(filename):
    success, message = BackupManager.restore_backup(filename)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('main.dev_dashboard'))

@bp.route('/developer/backup/delete/<filename>', methods=['POST'])
@developer_required
def delete_backup(filename):
    success, message = BackupManager.delete_backup(filename)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('main.dev_dashboard'))

# --- Users & Players ---
@bp.route('/developer/users')
@developer_required
def dev_users():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()
    
    query = User.query
    if search_query:
        query = query.filter(User.username.ilike(f'%{search_query}%'))
    
    pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('developer/users.html', users=pagination.items, pagination=pagination, search_query=search_query, title=_('إدارة اللاعبين'))

@bp.route('/developer/user/edit/<int:id>', methods=['GET', 'POST'])
@developer_required
def dev_user_edit(id):
    user = db.session.get(User, id)
    if not user: abort(404)
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.level = int(request.form.get('level', 1))
        user.exp = int(request.form.get('exp', 0))
        user.money = int(request.form.get('money', 0))
        user.bank_balance = int(request.form.get('bank_balance', 0))
        user.diamonds = int(request.form.get('diamonds', 0))
        user.bullets = int(request.form.get('bullets', 0))
        
        user.strength = int(request.form.get('strength', 10))
        user.defense = int(request.form.get('defense', 10))
        user.agility = int(request.form.get('agility', 10))
        
        user.health = int(request.form.get('health', 100))
        user.max_health = int(request.form.get('max_health', 100))
        user.energy = int(request.form.get('energy', 100))
        user.max_energy = int(request.form.get('max_energy', 100))
        user.brave = int(request.form.get('brave', 100))
        user.max_brave = int(request.form.get('max_brave', 100))
        
        try:
            heat_value = int(request.form.get('heat', 0))
        except Exception:
            heat_value = 0
        heat_value = max(0, min(100, heat_value))
        user.heat_points = heat_value
        user.heat_updated_at = datetime.now(timezone.utc).replace(tzinfo=None) if heat_value > 0 else None
        user.daily_streak = int(request.form.get('daily_streak', 0))
        user.location_id = int(request.form.get('location_id', 1))

        user.is_ghost_mode = 'is_ghost_mode' in request.form
        
        ban_hours = request.form.get('ban_hours')
        if ban_hours and int(ban_hours) > 0:
            user.banned_until = datetime.now() + timedelta(hours=int(ban_hours))
            user.ban_reason = request.form.get('ban_reason')
        
        if 'clear_ban' in request.form:
            user.banned_until = None
            
        role_name = request.form.get('role')
        if role_name:
             role = UserRank.query.filter_by(name=role_name).first()
             if role:
                 user.role_id = role.id
        
        db.session.commit()
        flash(_('تم تحديث بيانات المستخدم'), 'success')
        return redirect(url_for('main.dev_user_edit', id=user.id))
        
    roles = UserRank.query.all()
    locations = Location.query.all()
    return render_template('developer/edit_user.html', user=user, roles=roles, locations=locations, title=_('تعديل مستخدم'))

@bp.route('/developer/user/clear_status/<int:id>', methods=['POST'])
@developer_required
def dev_user_clear_status(id):
    user = db.session.get(User, id)
    if user:
        user.health = user.max_health
        user.energy = user.max_energy
        user.brave = user.max_brave
        db.session.commit()
        flash(_('تم تصفير الحالة'), 'success')
    return redirect(url_for('main.dev_user_edit', id=id))

@bp.route('/developer/user/boost/<int:id>', methods=['POST'])
@developer_required
def dev_user_boost(id):
    user = db.session.get(User, id)
    if user:
        user.role = UserRole.DEVELOPER
        user.level = max(user.level, 100)
        user.money = max(user.money, 10_000_000_000)
        user.diamonds = max(user.diamonds, 10000)
        user.strength = max(user.strength, 9999)
        db.session.commit()
        flash(_('تمت الترقية!'), 'success')
    return redirect(url_for('main.dev_user_edit', id=id))

@bp.route('/developer/user/<int:id>/protection/enable', methods=['POST'])
@developer_required
def dev_user_protection_enable(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)
    user.is_admin_protected = True
    db.session.commit()
    flash(_('تم تفعيل حماية اللاعب'), 'success')
    return redirect(url_for('main.dev_user_edit', id=id))

@bp.route('/developer/user/<int:id>/protection/disable', methods=['POST'])
@developer_required
def dev_user_protection_disable(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)
    user.is_admin_protected = False
    db.session.commit()
    flash(_('تم إلغاء حماية اللاعب'), 'success')
    return redirect(url_for('main.dev_user_edit', id=id))

@bp.route('/developer/user/<int:id>/protection/clear_all', methods=['POST'])
@developer_required
def dev_user_protection_clear_all(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)

    now = datetime.now(timezone.utc)
    now_naive = now.replace(tzinfo=None)

    user.is_admin_protected = False
    user.is_safe_house_active = False
    user.safe_house_until = None
    if user.created_at and user.created_at >= (now_naive - timedelta(days=7)):
        user.created_at = now_naive - timedelta(days=8)

    db.session.commit()
    flash(_('تم إخراج اللاعب من كل الحماية'), 'success')
    return redirect(url_for('main.dev_user_edit', id=id))

@bp.route('/developer/protection/clear_all', methods=['POST'])
@developer_required
def dev_clear_all_players_protection():
    now = datetime.now(timezone.utc)
    now_naive = now.replace(tzinfo=None)
    threshold = now_naive - timedelta(days=7)

    db.session.query(User).update(
        {
            User.is_safe_house_active: False,
            User.safe_house_until: None,
            User.is_admin_protected: False,
        },
        synchronize_session=False,
    )

    users_in_newbie_window = User.query.filter(User.created_at != None, User.created_at >= threshold).all()
    for u in users_in_newbie_window:
        u.created_at = now_naive - timedelta(days=8)

    db.session.commit()
    flash(_('تم إخراج جميع اللاعبين الحاليين من الحماية'), 'success')
    return redirect(url_for('main.dev_dashboard'))

@bp.route('/developer/heat')
@developer_required
def dev_heat():
    # Get users with heat > 0, ordered by heat desc
    users = User.query.filter(User.heat_points > 0).order_by(User.heat_points.desc()).all()
    return render_template('developer/heat.html', users=users, title=_('إدارة مستوى المطاردة'))

@bp.route('/developer/heat/clear_all', methods=['POST'])
@developer_required
def dev_heat_clear_all():
    db.session.query(User).update({User.heat_points: 0, User.heat_updated_at: None}, synchronize_session=False)
    db.session.commit()
    flash(_('تم تصفير عداد المطاردة لجميع اللاعبين'), 'success')
    return redirect(url_for('main.dev_heat'))

@bp.route('/developer/heat/clear/<int:user_id>', methods=['POST'])
@developer_required
def dev_heat_clear_user(user_id):
    user = db.session.get(User, user_id)
    if user:
        user.heat_points = 0
        user.heat_updated_at = None
        db.session.commit()
        flash(_('تم تصفير عداد المطاردة للاعب'), 'success')
    return redirect(url_for('main.dev_heat'))

@bp.route('/developer/user/<int:user_id>/achievements')
@developer_required
def dev_user_achievements(user_id):
    user = db.session.get(User, user_id)
    if not user: abort(404)
    user_achievements = UserAchievement.query.filter_by(user_id=user.id).all()
    return render_template('developer/user_achievements.html', user=user, user_achievements=user_achievements, title=_('إنجازات اللاعب'))

@bp.route('/developer/user/<int:user_id>/achievements/grant', methods=['POST'])
@developer_required
def dev_user_achievements_grant(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    achievement_id = request.form.get('achievement_id')
    try:
        achievement_id = int(achievement_id)
    except Exception:
        flash(_('معرف الإنجاز غير صالح'), 'danger')
        return redirect(url_for('main.dev_user_achievements', user_id=user_id))

    achievement = db.session.get(Achievement, achievement_id)
    if not achievement:
        abort(404)

    existing = UserAchievement.query.filter_by(user_id=user.id, achievement_id=achievement.id).first()
    if not existing:
        db.session.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
        db.session.commit()
        flash(_('تم منح الإنجاز للاعب'), 'success')
    else:
        flash(_('هذا الإنجاز ممنوح مسبقاً'), 'info')

    return redirect(url_for('main.dev_user_achievements', user_id=user.id))

@bp.route('/developer/user/<int:user_id>/achievements/revoke/<int:user_achievement_id>', methods=['POST'])
@developer_required
def dev_user_achievements_revoke(user_id, user_achievement_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    ua = db.session.get(UserAchievement, user_achievement_id)
    if not ua or ua.user_id != user.id:
        abort(404)

    db.session.delete(ua)
    db.session.commit()
    flash(_('تم سحب الإنجاز من اللاعب'), 'success')
    return redirect(url_for('main.dev_user_achievements', user_id=user.id))

@bp.route('/developer/achievements')
@developer_required
def dev_achievements():
    achievements = Achievement.query.order_by(Achievement.points.asc()).all()
    unlock_counts = {}
    results = db.session.query(UserAchievement.achievement_id, func.count(UserAchievement.user_id)).group_by(UserAchievement.achievement_id).all()
    for aid, count in results:
        unlock_counts[aid] = count
        
    return render_template('developer/achievements.html', achievements=achievements, unlock_counts=unlock_counts, title=_('إدارة الإنجازات'))

@bp.route('/developer/achievement/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/achievement/new', methods=['GET', 'POST'])
@developer_required
def dev_achievement_edit(id=None):
    if id:
        achievement = db.session.get(Achievement, id)
        if not achievement: abort(404)
        title = _('تعديل إنجاز')
    else:
        achievement = Achievement()
        title = _('إضافة إنجاز')
    
    form = AchievementForm(obj=achievement)
    if form.validate_on_submit():
        form.populate_obj(achievement)
        db.session.add(achievement)
        db.session.commit()
        flash(_('تم حفظ الإنجاز'), 'success')
        return redirect(url_for('main.dev_achievements'))
        
    return render_template('developer/edit_achievement.html', form=form, title=title)

@bp.route('/developer/achievement/delete/<int:id>', methods=['POST'])
@developer_required
def dev_achievement_delete(id):
    a = db.session.get(Achievement, id)
    if a:
        db.session.delete(a)
        db.session.commit()
        flash(_('تم حذف الإنجاز'), 'success')
    return redirect(url_for('main.dev_achievements'))

@bp.route('/developer/unverified')
@developer_required
def unverified_users():
    users = User.query.filter_by(is_verified=False).order_by(User.created_at.desc()).all()
    return render_template('developer/unverified_users.html', users=users, title=_('مستخدمين بانتظار التفعيل'))

@bp.route('/developer/user/verify/<int:user_id>/<action>', methods=['POST'])
@developer_required
def handle_verification(user_id, action):
    user = db.session.get(User, user_id)
    if not user: abort(404)
    
    if action == 'confirm':
        user.is_verified = True
        db.session.commit()
        
        # Send welcome email or message if needed
        msg = Message(
            sender_id=current_user.id,
            receiver_id=user.id,
            subject=_('تم تفعيل حسابك'),
            body=_('مرحباً بك! تم تفعيل حسابك بنجاح. استمتع باللعب!')
        )
        db.session.add(msg)
        db.session.commit()
        flash(_('تم تفعيل المستخدم بنجاح'), 'success')
        
    elif action == 'reject':
        db.session.delete(user)
        db.session.commit()
        flash(_('تم رفض وحذف المستخدم'), 'info')
        
    return redirect(url_for('main.unverified_users'))

@bp.route('/developer/resurrection')
@developer_required
def resurrection_requests():
    requests = ResurrectionRequest.query.filter_by(status='pending').order_by(ResurrectionRequest.created_at.desc()).all()
    return render_template('developer/resurrection_requests.html', requests=requests, title=_('طلبات الإحياء'))

@bp.route('/developer/resurrection/handle/<int:req_id>/<action>', methods=['POST'])
@developer_required
def handle_resurrection_request(req_id, action):
    req = db.session.get(ResurrectionRequest, req_id)
    if not req or req.status != 'pending':
        flash(_('الطلب غير موجود أو تمت معالجته مسبقاً.'), 'danger')
        return redirect(url_for('main.resurrection_requests'))
        
    if action == 'approve':
        req.status = 'approved'
        # Resurrect user
        user = req.user
        user.health = user.max_health
        user.energy = user.max_energy
        user.is_dead = False
        user.death_time = None
        
        # Log notification or message to user
        msg = Message(
            sender_id=current_user.id,
            receiver_id=user.id,
            subject=_('تم قبول طلب الإحياء'),
            body=_('تهانينا! تمت الموافقة على طلبك وتم إحياؤك من جديد. حظاً موفقاً!')
        )
        db.session.add(msg)
        flash(_('تم قبول الطلب وإحياء اللاعب.'), 'success')
        
    elif action == 'reject':
        req.status = 'rejected'
        # Log notification or message to user
        msg = Message(
            sender_id=current_user.id,
            receiver_id=req.user_id,
            subject=_('رفض طلب الإحياء'),
            body=_('عذراً، تم رفض طلب الإحياء الخاص بك.')
        )
        db.session.add(msg)
        flash(_('تم رفض الطلب.'), 'info')
    
    db.session.commit()
    return redirect(url_for('main.resurrection_requests'))

@bp.route('/developer/hostesses')
@developer_required
def dev_hostesses():
    hostesses = Hostess.query.all()
    return render_template('developer/hostesses.html', hostesses=hostesses, title=_('إدارة المضيفات'))

@bp.route('/developer/hostess/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/hostess/new', methods=['GET', 'POST'])
@developer_required
def dev_hostess_edit(id=None):
    if id:
        hostess = db.session.get(Hostess, id)
        if not hostess:
            abort(404)
        title = _('تعديل مضيفة')
    else:
        hostess = Hostess()
        title = _('إضافة مضيفة جديدة')

    form = HostessForm(obj=hostess)

    try:
        videos_dir = os.path.join(current_app.root_path, 'static', 'videos', 'hostesses')
        os.makedirs(videos_dir, exist_ok=True)
        files = []
        for fn in os.listdir(videos_dir):
            ext = os.path.splitext(fn)[1].lower()
            if ext in ['.mp4', '.webm', '.gif']:
                files.append(fn)
        files.sort()
        form.video_choice.choices = [('', _('بدون فيديو'))] + [(f, f) for f in files]
        if request.method == 'GET':
            form.video_choice.data = hostess.video or ''
    except Exception:
        form.video_choice.choices = [('', _('بدون فيديو'))]

    if form.validate_on_submit():
        form.populate_obj(hostess)
        
        # Handle Image
        if form.image.data:
            image_path = save_image(form.image.data, 'hostesses')
            if image_path:
                hostess.image = os.path.basename(image_path)
                
        # Handle Video
        if form.video.data:
            f = form.video.data
            filename = secure_filename(f.filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext in ['.mp4', '.webm', '.gif']:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                new_filename = f"{timestamp}_{os.urandom(8).hex()}{ext}"
                upload_path = os.path.join(current_app.root_path, 'static', 'videos', 'hostesses')
                os.makedirs(upload_path, exist_ok=True)
                f.save(os.path.join(upload_path, new_filename))
                hostess.video = new_filename
        else:
            chosen = (form.video_choice.data or '').strip()
            if chosen:
                hostess.video = chosen
            else:
                hostess.video = None

        if not id:
            db.session.add(hostess)
            
        db.session.commit()
        flash(_('تم حفظ المضيفة بنجاح'), 'success')
        return redirect(url_for('main.dev_hostesses'))

    return render_template('developer/edit_hostess.html', form=form, title=title, hostess=hostess)

@bp.route('/developer/hostess/delete/<int:id>', methods=['POST'])
@developer_required
def dev_hostess_delete(id):
    hostess = db.session.get(Hostess, id)
    if hostess:
        db.session.delete(hostess)
        db.session.commit()
        flash(_('تم حذف المضيفة'), 'success')
    return redirect(url_for('main.dev_hostesses'))

def _build_hostess_role_pack(hostess: Hostess):
    role = (hostess.role or 'companion').lower()
    name = hostess.name or 'مضيفة'
    style = hostess.dialogue_style or 'friendly'

    if role == 'greeter':
        prompt = build_greeter_leader_prompt(hostess)
        examples = json.loads(build_greeter_leader_training_json(hostess))
        return prompt, examples

    prompt = f"أنت {name}، مضيفة داخل لعبة GangsOfPalestine. "
    prompt += f"الدور: {role}. أسلوبك: {style}. "
    prompt += "\nالهدف: مساعدة اللاعب داخل اللعبة بشكل احترافي (خطوات واضحة، نصائح دقيقة، بدون حشو)."
    prompt += "\nلا تختلق معلومات أو أسعار/قوانين غير موجودة في المعرفة. إذا لم تعرف، قل ذلك وقدّم بدائل."
    prompt += "\nاحترم الخصوصية: لا تطلب بيانات حساسة."
    prompt += "\nممنوع محتوى إباحي/فاضح/تحريض/كراهية/تعليمات خطرة."
    prompt += "\nاستخدم ذاكرة اللاعب (إن وُجدت) لتخصيص الرد: اسمه/تفضيلاته/هدفه."

    if role == 'greeter':
        prompt += "\nركز على: استقبال، شرح سريع للميزات، توجيه للصفحات، مساعدة تسجيل/تفعيل."
    elif role == 'spy':
        prompt += "\nركز على: استخبارات سباقات، تجنب المخاطر، قراءة الخصوم، نصائح تكتيكية."
    elif role == 'luck':
        prompt += "\nركز على: الكازينو، إدارة المخاطر، اقتراح رهانات حسب المال، تنبيه من الإفراط."
    elif role == 'support':
        prompt += "\nركز على: دعم نفسي، نصائح علاج/طاقة، قرارات آمنة وقت الإصابة والخسارة."
    else:
        prompt += "\nركز على: مرافقة لطيفة داخل سياق اللعبة مع نصائح لعب مفيدة."

    examples = []
    if role == 'greeter':
        examples = [
            {"role": "user", "content": "شو أعمل أول شي؟"},
            {"role": "assistant", "content": "أهلاً! ابدأ بالمكافأة اليومية، بعدها جرّب جريمة بسيطة، وإذا طاقتك نزلت روح الجيم أو استخدم مشروب طاقة."},
            {"role": "user", "content": "كيف أزيد فلوسي بسرعة؟"},
            {"role": "assistant", "content": "ركز على الجرائم المناسبة لمستواك + المهام اليومية. لا تراهن بكل فلوسك بالكازينو وخلي جزء للطاقة والعناصر."},
            {"role": "user", "content": "وين الجرائم المنظمة؟"},
            {"role": "assistant", "content": "من قائمة الجرائم المنظمة، اختار عملية وشف شروط الأدوار والمطلوبات، وبعدها أنشئ مجموعة أو انضم لمجموعة جاهزة."}
        ]
    elif role == 'spy':
        examples = [
            {"role": "user", "content": "بدّي أفوز بالسباق، شو أهم شي؟"},
            {"role": "assistant", "content": "شوف سرعة السيارة ودفاعها أولاً، وخلي معك خطة للهروب إذا صار مطاردة. لا تدخل سباق أعلى من تجهيزك."},
            {"role": "user", "content": "الخصم قوي… شو أعمل؟"},
            {"role": "assistant", "content": "العب على الأمان: خفف المخاطرة، ركّز على ترقيات السيارة، وحاول تجمع معلومات عن خصمك قبل المواجهة."}
        ]
    elif role == 'luck':
        examples = [
            {"role": "user", "content": "أراهن قدّيش؟"},
            {"role": "assistant", "content": "خليك ذكي: راهن 5–10% من فلوسك كحد أقصى، ووقّف إذا خسرت مرتين ورا بعض."},
            {"role": "user", "content": "خسرت كثير…"},
            {"role": "assistant", "content": "وقّف شوي وخليها إدارة مخاطر: ارجع للجرائم والمهام اليومية لتعويض، وبعدين ارجع برهانات صغيرة."}
        ]
    elif role == 'support':
        examples = [
            {"role": "user", "content": "أنا تعبان وخسرت…"},
            {"role": "assistant", "content": "سلامتك أولاً. إذا صحتك منخفضة روح المستشفى، وبعدها ارجع بخطة بسيطة: مهام يومية + جيم + جرائم آمنة."},
            {"role": "user", "content": "كيف أرفع طاقتي بسرعة؟"},
            {"role": "assistant", "content": "استخدم عناصر استرجاع الطاقة إذا موجودة، أو خذ استراحة تدريب/جيم حسب نظام اللعبة، وخفف جرائم تستهلك طاقة عالية."}
        ]
    else:
        examples = [
            {"role": "user", "content": "بدّي نصيحة عامة"},
            {"role": "assistant", "content": "خليك ثابت: ركز على مهام يومية + تطوير إحصائياتك، وخلي مخزون عناصر للطوارئ قبل أي مخاطرة."}
        ]

    return prompt, examples

@bp.route('/developer/hostess/trainer/<int:id>', methods=['GET', 'POST'])
@developer_required
def dev_hostess_trainer(id):
    hostess = db.session.get(Hostess, id)
    if not hostess:
        abort(404)

    if request.method == 'POST':
        action = request.form.get('action') or 'save'
        if action == 'train':
            prompt, examples = _build_hostess_role_pack(hostess)
            hostess.system_prompt = prompt
            hostess.training_examples = json.dumps(examples, ensure_ascii=False)
            hostess.last_trained_at = datetime.now(timezone.utc).replace(tzinfo=None)
            hostess.self_learning_enabled = 'self_learning_enabled' in request.form
            hostess.memory_enabled = 'memory_enabled' in request.form
            db.session.commit()
            flash(_('تم تدريب المضيفة وحفظ الحزمة بنجاح'), 'success')
            return redirect(url_for('main.dev_hostess_trainer', id=id))
        elif action == 'clear_memory':
            HostessMemory.query.filter_by(hostess_id=hostess.id).delete()
            db.session.commit()
            flash(_('تم مسح ذاكرة المضيفة'), 'success')
            return redirect(url_for('main.dev_hostess_trainer', id=id))
        elif action == 'delete_memory':
            mid = request.form.get('memory_id', type=int)
            mem = db.session.get(HostessMemory, mid) if mid else None
            if mem and mem.hostess_id == hostess.id:
                db.session.delete(mem)
                db.session.commit()
                flash(_('تم حذف عنصر الذاكرة'), 'success')
            return redirect(url_for('main.dev_hostess_trainer', id=id))
        else:
            hostess.system_prompt = request.form.get('system_prompt') or hostess.system_prompt
            hostess.knowledge_base = request.form.get('knowledge_base') or hostess.knowledge_base
            hostess.training_examples = request.form.get('training_examples') or hostess.training_examples
            hostess.self_learning_enabled = 'self_learning_enabled' in request.form
            hostess.memory_enabled = 'memory_enabled' in request.form
            db.session.commit()
            flash(_('تم حفظ إعدادات التدريب'), 'success')
            return redirect(url_for('main.dev_hostess_trainer', id=id))

    memories = HostessMemory.query.filter_by(hostess_id=hostess.id).order_by(HostessMemory.updated_at.desc()).limit(30).all()
    chats = HostessChatMessage.query.filter_by(hostess_id=hostess.id).order_by(HostessChatMessage.id.desc()).limit(30).all()
    chats.reverse()
    return render_template('developer/hostess_trainer.html', hostess=hostess, memories=memories, chats=chats, title=_('تدريب المضيفة'))

@bp.route('/developer/scenarios')
@developer_required
def dev_scenarios():
    scenarios = VideoScenario.query.all()
    hostesses = Hostess.query.all()
    return render_template('developer/scenarios.html', scenarios=scenarios, hostesses=hostesses, title=_('مكتبة السيناريوهات'))

@bp.route('/developer/scenario/new_alias', methods=['GET', 'POST'])
@developer_required
def dev_scenario_new():
    return dev_scenario_edit()

@bp.route('/developer/scenario/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/scenario/new', methods=['GET', 'POST'])
@developer_required
def dev_scenario_edit(id=None):
    if id:
        scenario = db.session.get(VideoScenario, id)
        if not scenario: abort(404)
        title = _('تعديل سيناريو')
    else:
        scenario = VideoScenario()
        title = _('إضافة سيناريو')
    
    form = VideoScenarioForm(obj=scenario)
    if form.validate_on_submit():
        form.populate_obj(scenario)
        db.session.add(scenario)
        db.session.commit()
        flash(_('تم حفظ السيناريو'), 'success')
        return redirect(url_for('main.dev_scenarios'))
        
    return render_template('developer/edit_scenario.html', form=form, title=title)

@bp.route('/developer/scenario/delete/<int:id>', methods=['POST'])
@developer_required
def dev_scenario_delete(id):
    s = db.session.get(VideoScenario, id)
    if s:
        db.session.delete(s)
        db.session.commit()
        flash(_('تم حذف السيناريو'), 'success')
    return redirect(url_for('main.dev_scenarios'))

@bp.route('/developer/scenario/apply/<int:scenario_id>/<int:hostess_id>', methods=['POST'])
@developer_required
def dev_scenario_apply(scenario_id, hostess_id):
    scenario = db.session.get(VideoScenario, scenario_id)
    hostess = db.session.get(Hostess, hostess_id)
    if scenario and hostess:
        # Update hostess video prompt with scenario content
        hostess.video_prompt = scenario.script_content
        db.session.commit()
        flash(_('تم تطبيق السيناريو على المضيفة ') + hostess.name, 'success')
    return redirect(url_for('main.dev_scenarios'))

@bp.route('/developer/settings')
@developer_required
def dev_settings():
    settings = SystemConfig.query.order_by(SystemConfig.key.asc()).all()
    return render_template('developer/settings.html', settings=settings, title=_('إعدادات النظام'))

@bp.route('/developer/settings/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/settings/new', methods=['GET', 'POST'])
@developer_required
def dev_settings_edit(id=None):
    if id:
        setting = db.session.get(SystemConfig, id)
        if not setting:
            # If id=0, it might be a new setting via query params
            if id == 0:
                setting = SystemConfig()
            else:
                abort(404)
        title = _('تعديل إعداد')
    else:
        setting = SystemConfig()
        title = _('إضافة إعداد')
    
    # Pre-fill from query params if new
    if not setting.id:
        if request.args.get('key'): setting.key = request.args.get('key')
        if request.args.get('description'): setting.description = request.args.get('description')
        
    form = SystemConfigForm(obj=setting)
    if form.validate_on_submit():
        form.populate_obj(setting)
        db.session.add(setting)
        db.session.commit()
        flash(_('تم حفظ الإعداد'), 'success')
        return redirect(url_for('main.dev_settings'))
        
    return render_template('developer/edit_setting.html', form=form, title=title)

@bp.route('/developer/settings/delete/<int:id>', methods=['POST'])
@developer_required
def dev_settings_delete(id):
    setting = db.session.get(SystemConfig, id)
    if setting:
        db.session.delete(setting)
        db.session.commit()
        flash(_('تم حذف الإعداد'), 'success')
    return redirect(url_for('main.dev_settings'))


@bp.route('/developer/messages')
@developer_required
def admin_messages():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = Message.query
    if search:
        query = query.join(User, Message.sender_id == User.id).filter(
            (User.username.ilike(f'%{search}%')) | 
            (Message.subject.ilike(f'%{search}%'))
        )
        
    messages = query.order_by(Message.timestamp.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('developer/messages.html', messages=messages, title=_('رسائل النظام'))

@bp.route('/developer/message/delete/<int:msg_id>', methods=['POST'])
@developer_required
def admin_delete_message(msg_id):
    msg = db.session.get(Message, msg_id)
    if msg:
        db.session.delete(msg)
        db.session.commit()
        flash(_('تم حذف الرسالة نهائياً'), 'success')
    return redirect(url_for('main.admin_messages'))

@bp.route('/developer/generate_users', methods=['POST'])
@developer_required
def generate_test_users():
    # Placeholder for test user generation logic
    flash(_('هذه الميزة غير مفعلة حالياً في البيئة الحية.'), 'info')
    return redirect(url_for('main.dev_dashboard'))

@bp.route('/developer/items')
@developer_required
def dev_items():
    items = Item.query.order_by(Item.id.desc()).all()
    return render_template('developer/items.html', items=items, title=_('إدارة الأغراض'))

@bp.route('/developer/item/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/item/new', methods=['GET', 'POST'])
@developer_required
def dev_item_edit(id=None):
    if id:
        item = db.session.get(Item, id)
        if not item: abort(404)
        title = _('تعديل غرض')
    else:
        item = Item()
        title = _('إضافة غرض')
    
    form = ItemForm(obj=item)
    if form.validate_on_submit():
        form.populate_obj(item)
        image_path = save_image(form.image.data, 'items')
        if image_path: item.image = image_path
        
        db.session.add(item)
        db.session.commit()
        flash(_('تم حفظ الغرض'), 'success')
        return redirect(url_for('main.dev_items'))
        
    return render_template('developer/edit_item.html', form=form, title=title)

@bp.route('/developer/item/delete/<int:id>', methods=['POST'])
@developer_required
def dev_item_delete(id):
    item = db.session.get(Item, id)
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(_('تم حذف الغرض'), 'success')
    return redirect(url_for('main.dev_items'))

@bp.route('/developer/vehicles')
@developer_required
def dev_vehicles():
    vehicles = Vehicle.query.order_by(Vehicle.price.asc()).all()
    return render_template('developer/vehicles.html', vehicles=vehicles, title=_('إدارة المركبات'))

@bp.route('/developer/vehicle/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/vehicle/new', methods=['GET', 'POST'])
@developer_required
def dev_vehicle_edit(id=None):
    if id:
        vehicle = db.session.get(Vehicle, id)
        if not vehicle: abort(404)
        title = _('تعديل مركبة')
    else:
        vehicle = Vehicle()
        title = _('إضافة مركبة')
    
    form = VehicleForm(obj=vehicle)
    if form.validate_on_submit():
        form.populate_obj(vehicle)
        image_path = save_image(form.image.data, 'vehicles')
        if image_path: vehicle.image = image_path
        
        db.session.add(vehicle)
        db.session.commit()
        flash(_('تم حفظ المركبة'), 'success')
        return redirect(url_for('main.dev_vehicles'))
        
    return render_template('developer/edit_vehicle.html', form=form, title=title)

@bp.route('/developer/vehicle/delete/<int:id>', methods=['POST'])
@developer_required
def dev_vehicle_delete(id):
    vehicle = db.session.get(Vehicle, id)
    if vehicle:
        db.session.delete(vehicle)
        db.session.commit()
        flash(_('تم حذف المركبة'), 'success')
    return redirect(url_for('main.dev_vehicles'))

@bp.route('/developer/assets')
@developer_required
def dev_assets():
    assets = Asset.query.order_by(Asset.value.asc()).all()
    return render_template('developer/assets.html', assets=assets, title=_('إدارة العقارات'))

@bp.route('/developer/asset/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/asset/new', methods=['GET', 'POST'])
@developer_required
def dev_asset_edit(id=None):
    if id:
        asset = db.session.get(Asset, id)
        if not asset: abort(404)
        title = _('تعديل عقار')
    else:
        asset = Asset()
        title = _('إضافة عقار')
    
    form = AssetForm(obj=asset)
    if form.validate_on_submit():
        form.populate_obj(asset)
        image_path = save_image(form.image.data, 'assets')
        if image_path: asset.image = image_path
        
        db.session.add(asset)
        db.session.commit()
        flash(_('تم حفظ العقار'), 'success')
        return redirect(url_for('main.dev_assets'))
        
    return render_template('developer/edit_asset.html', form=form, title=title)

@bp.route('/developer/asset/delete/<int:id>', methods=['POST'])
@developer_required
def dev_asset_delete(id):
    asset = db.session.get(Asset, id)
    if asset:
        db.session.delete(asset)
        db.session.commit()
        flash(_('تم حذف العقار'), 'success')
    return redirect(url_for('main.dev_assets'))

@bp.route('/developer/locations')
@developer_required
def dev_locations():
    locations = Location.query.order_by(Location.cost.asc()).all()
    return render_template('developer/locations.html', locations=locations, title=_('إدارة المواقع'))

@bp.route('/developer/location/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/location/new', methods=['GET', 'POST'])
@developer_required
def dev_location_edit(id=None):
    if id:
        location = db.session.get(Location, id)
        if not location: abort(404)
        title = _('تعديل موقع')
    else:
        location = Location()
        title = _('إضافة موقع')
    
    form = LocationForm(obj=location)
    if form.validate_on_submit():
        form.populate_obj(location)
        image_path = save_image(form.image.data, 'locations')
        if image_path: location.image = image_path
        
        db.session.add(location)
        db.session.commit()
        flash(_('تم حفظ الموقع'), 'success')
        return redirect(url_for('main.dev_locations'))
        
    return render_template('developer/edit_location.html', form=form, title=title)

@bp.route('/developer/location/delete/<int:id>', methods=['POST'])
@developer_required
def dev_location_delete(id):
    location = db.session.get(Location, id)
    if location:
        db.session.delete(location)
        db.session.commit()
        flash(_('تم حذف الموقع'), 'success')
    return redirect(url_for('main.dev_locations'))

@bp.route('/developer/crimes')
@developer_required
def dev_crimes():
    crimes = Crime.query.order_by(Crime.min_level.asc()).all()
    return render_template('developer/crimes.html', crimes=crimes, title=_('إدارة الجرائم'))

@bp.route('/developer/crime/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/crime/new', methods=['GET', 'POST'])
@developer_required
def dev_crime_edit(id=None):
    if id:
        crime = db.session.get(Crime, id)
        if not crime: abort(404)
        title = _('تعديل جريمة')
    else:
        crime = Crime()
        title = _('إضافة جريمة')
    
    form = CrimeForm(obj=crime)
    # Populate reward items
    items = Item.query.all()
    form.reward_item_id.choices = [(0, _('لا يوجد'))] + [(i.id, i.name) for i in items]
    
    if form.validate_on_submit():
        form.populate_obj(crime)
        image_path = save_image(form.image.data, 'crimes')
        if image_path: crime.image = image_path
        
        if form.reward_item_id.data == 0:
            crime.reward_item_id = None
            
        db.session.add(crime)
        db.session.commit()
        flash(_('تم حفظ الجريمة'), 'success')
        return redirect(url_for('main.dev_crimes'))
        
    return render_template('developer/edit_crime.html', form=form, title=title)

@bp.route('/developer/crime/delete/<int:id>', methods=['POST'])
@developer_required
def dev_crime_delete(id):
    crime = db.session.get(Crime, id)
    if crime:
        db.session.delete(crime)
        db.session.commit()
        flash(_('تم حذف الجريمة'), 'success')
    return redirect(url_for('main.dev_crimes'))

@bp.route('/developer/organized_crimes')
@developer_required
def dev_organized_crimes():
    crimes = OrganizedCrime.query.order_by(OrganizedCrime.min_gang_level.asc()).all()
    reqs_map = {}
    for crime in crimes:
        try:
            reqs_map[crime.id] = json.loads(crime.requirements) if crime.requirements else {}
        except:
            reqs_map[crime.id] = {}
    return render_template('developer/organized_crimes.html', crimes=crimes, reqs_map=reqs_map, title=_('إدارة الجرائم المنظمة'))

@bp.route('/developer/organized_crime/update/<int:id>', methods=['POST'])
@developer_required
def dev_organized_crime_update(id):
    crime = db.session.get(OrganizedCrime, id)
    if not crime:
        abort(404)

    reqs = {}
    try:
        reqs = json.loads(crime.requirements) if crime.requirements else {}
    except Exception:
        reqs = {}

    role_bonuses_json = request.form.get('role_bonuses_json')
    if role_bonuses_json is not None:
        try:
            reqs['role_bonuses'] = json.loads(role_bonuses_json) if role_bonuses_json.strip() else {}
        except Exception:
            flash(_('صيغة JSON غير صحيحة في علاوات الأدوار'), 'danger')
            return redirect(url_for('main.dev_organized_crimes'))

    for key, value in request.form.items():
        if key in ('csrf_token', 'role_bonuses_json'):
            continue

        if value is None:
            continue

        raw = value.strip()
        if raw == '':
            continue

        try:
            if '.' in raw:
                reqs[key] = float(raw)
            else:
                reqs[key] = int(raw)
        except Exception:
            reqs[key] = raw

    crime.requirements = json.dumps(reqs, ensure_ascii=False)
    db.session.commit()
    flash(_('تم تحديث إعدادات الجريمة المنظمة'), 'success')
    return redirect(url_for('main.dev_organized_crimes'))

@bp.route('/developer/organized_crime/delete/<int:id>', methods=['POST'])
@developer_required
def dev_organized_crime_delete(id):
    crime = db.session.get(OrganizedCrime, id)
    if crime:
        db.session.delete(crime)
        db.session.commit()
        flash(_('تم حذف الجريمة المنظمة'), 'success')
    return redirect(url_for('main.dev_organized_crimes'))

@bp.route('/developer/tasks')
@developer_required
def dev_tasks():
    tasks = DailyTask.query.order_by(DailyTask.id.desc()).all()
    return render_template('developer/tasks.html', tasks=tasks, title=_('المهام اليومية'))

@bp.route('/developer/task/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/task/new', methods=['GET', 'POST'])
@developer_required
def dev_task_edit(id=None):
    if id:
        task = db.session.get(DailyTask, id)
        if not task: abort(404)
        title = _('تعديل مهمة')
    else:
        task = DailyTask()
        title = _('إضافة مهمة')
    
    form = TaskForm(obj=task)
    if form.validate_on_submit():
        form.populate_obj(task)
        image_path = save_image(form.image.data, 'tasks')
        if image_path: task.image = image_path
        
        db.session.add(task)
        db.session.commit()
        flash(_('تم حفظ المهمة'), 'success')
        return redirect(url_for('main.dev_tasks'))
        
    return render_template('developer/edit_task.html', form=form, title=title)

@bp.route('/developer/task/delete/<int:id>', methods=['POST'])
@developer_required
def dev_task_delete(id):
    task = db.session.get(DailyTask, id)
    if task:
        db.session.delete(task)
        db.session.commit()
        flash(_('تم حذف المهمة'), 'success')
    return redirect(url_for('main.dev_tasks'))

@bp.route('/developer/announcements')
@developer_required
def dev_announcements():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('developer/announcements.html', announcements=announcements, title=_('إدارة الإعلانات'))

@bp.route('/developer/announcement/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/announcement/new', methods=['GET', 'POST'])
@developer_required
def dev_announcement_edit(id=None):
    if id:
        announcement = db.session.get(Announcement, id)
        if not announcement: abort(404)
        title = _('تعديل إعلان')
    else:
        announcement = Announcement()
        title = _('إضافة إعلان')
    
    form = AnnouncementForm(obj=announcement)
    if form.validate_on_submit():
        form.populate_obj(announcement)
        
        db.session.add(announcement)
        db.session.commit()
        flash(_('تم حفظ الإعلان'), 'success')
        return redirect(url_for('main.dev_announcements'))
        
    return render_template('developer/edit_announcement.html', form=form, title=title)

@bp.route('/developer/announcement/delete/<int:id>', methods=['POST'])
@developer_required
def dev_announcement_delete(id):
    announcement = db.session.get(Announcement, id)
    if announcement:
        db.session.delete(announcement)
        db.session.commit()
        flash(_('تم حذف الإعلان'), 'success')
    return redirect(url_for('main.dev_announcements'))

@bp.route('/developer/forum')
@developer_required
def forum_categories():
    categories = ForumCategory.query.order_by(ForumCategory.order.asc()).all()
    return render_template('developer/forum/index.html', categories=categories, title=_('إدارة المنتدى'))

@bp.route('/developer/forum/category/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/forum/category/new', methods=['GET', 'POST'])
@developer_required
def dev_forum_category_edit(id=None):
    if id:
        category = db.session.get(ForumCategory, id)
        if not category: abort(404)
        title = _('تعديل قسم')
    else:
        category = ForumCategory()
        title = _('إضافة قسم')
    
    form = ForumCategoryForm(obj=category)
    if form.validate_on_submit():
        form.populate_obj(category)
        
        db.session.add(category)
        db.session.commit()
        flash(_('تم حفظ القسم'), 'success')
        return redirect(url_for('main.forum_categories'))
        
    return render_template('developer/forum/category_form.html', form=form, title=title)

@bp.route('/developer/forum/category/delete/<int:id>', methods=['POST'])
@developer_required
def dev_forum_category_delete(id):
    category = db.session.get(ForumCategory, id)
    if category:
        db.session.delete(category)
        db.session.commit()
        flash(_('تم حذف القسم'), 'success')
    return redirect(url_for('main.forum_categories'))

@bp.route('/developer/forum/category/add', methods=['GET', 'POST'])
@developer_required
def add_forum_category():
    return dev_forum_category_edit()

@bp.route('/developer/forum/category/edit_alias/<int:id>', methods=['GET', 'POST'])
@developer_required
def edit_forum_category(id):
    return dev_forum_category_edit(id=id)

@bp.route('/developer/forum/category/delete_alias/<int:id>', methods=['POST'])
@developer_required
def delete_forum_category(id):
    return dev_forum_category_delete(id=id)

@bp.route('/developer/config', methods=['GET', 'POST'])
@developer_required
def dev_config():
    if request.method == 'POST':
        for key, value in request.form.items():
            if key == 'csrf_token': continue
            
            # If multiple values exist (e.g. hidden false + checkbox true), request.form.getlist handles it.
            # But standard iteration yields the first one or we need to be careful.
            # request.form is a MultiDict. Iterating items() yields the first value for each key.
            # For checkboxes with hidden fallback:
            # <input type="hidden" name="foo" value="false">
            # <input type="checkbox" name="foo" value="true">
            # If checked: form sends foo=false, foo=true. items() might give 'false' (first one).
            # We want 'true' if present.
            
            vals = request.form.getlist(key)
            final_val = value
            if len(vals) > 1:
                # If 'true' is in values, assume true (for our specific boolean logic)
                if 'true' in vals:
                    final_val = 'true'
                else:
                    final_val = vals[-1] # Take last one usually
            
            config = SystemConfig.query.filter_by(key=key).first()
            if config:
                config.value = final_val
            else:
                # Auto-create if not exists (optional, but safer to stick to existing)
                pass
        
        db.session.commit()
        flash(_('تم حفظ الإعدادات'), 'success')
        return redirect(url_for('main.dev_config'))

    configs = SystemConfig.query.order_by(SystemConfig.key.asc()).all()
    return render_template('developer/config.html', configs=configs, title=_('إعدادات النظام'))


# --- Gangs ---
@bp.route('/developer/gangs')
@developer_required
def dev_gangs():
    gangs = Gang.query.order_by(Gang.level.desc()).all()
    return render_template('developer/gangs.html', gangs=gangs, title=_('إدارة العصابات'))

@bp.route('/developer/gang/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/gang/new', methods=['GET', 'POST'])
@developer_required
def dev_gang_edit(id=None):
    if id:
        gang = db.session.get(Gang, id)
        if not gang:
            abort(404)
        title = _('تعديل عصابة')
    else:
        gang = Gang()
        title = _('إضافة عصابة')

    form = GangForm(obj=gang)
    if form.validate_on_submit():
        # Validate leader exists
        leader = db.session.get(User, form.leader_id.data)
        if not leader:
            flash(_('المستخدم القائد غير موجود.'), 'danger')
            return render_template('developer/edit_gang.html', form=form, title=title)
            
        form.populate_obj(gang)
        image_path = save_image(form.image.data, 'gangs')
        if image_path:
            gang.image = image_path
            
        db.session.add(gang)
        db.session.commit()
        
        # Ensure leader relationship is set correctly if new
        if leader.gang_id != gang.id:
            leader.gang_id = gang.id
            db.session.commit()
            
        flash(_('تم حفظ العصابة'), 'success')
        return redirect(url_for('main.dev_gangs'))

    return render_template('developer/edit_gang.html', form=form, title=title)

@bp.route('/developer/gang/delete/<int:id>', methods=['POST'])
@developer_required
def dev_gang_delete(id):
    gang = db.session.get(Gang, id)
    if gang:
        # Reset members
        for member in gang.members:
            member.gang_id = None
        db.session.delete(gang)
        db.session.commit()
        flash(_('تم حذف العصابة'), 'success')
    return redirect(url_for('main.dev_gangs'))


# --- Hostess Knowledge ---
@bp.route('/developer/knowledge')
@developer_required
def dev_knowledge():
    page = request.args.get('page', 1, type=int)
    query = HostessKnowledge.query.order_by(HostessKnowledge.id.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    return render_template('developer/knowledge.html', knowledge=pagination.items, pagination=pagination, title=_('قاعدة معرفة المضيفات'))

@bp.route('/developer/knowledge/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/knowledge/new', methods=['GET', 'POST'])
@developer_required
def dev_knowledge_edit(id=None):
    if id:
        knowledge = db.session.get(HostessKnowledge, id)
        if not knowledge:
            abort(404)
        title = _('تعديل معرفة')
    else:
        knowledge = HostessKnowledge()
        title = _('إضافة معرفة')

    form = HostessKnowledgeForm(obj=knowledge)
    
    # Populate hostess choices
    hostesses = Hostess.query.all()
    form.hostess_id.choices = [(0, _('عام (لكل المضيفات)'))] + [(h.id, h.name) for h in hostesses]
    
    if form.validate_on_submit():
        form.populate_obj(knowledge)
        if form.hostess_id.data == 0:
            knowledge.hostess_id = None
            
        db.session.add(knowledge)
        db.session.commit()
        flash(_('تم حفظ المعرفة'), 'success')
        return redirect(url_for('main.dev_knowledge'))

    return render_template('developer/edit_knowledge.html', form=form, title=title)

@bp.route('/developer/knowledge/delete/<int:id>', methods=['POST'])
@developer_required
def dev_knowledge_delete(id):
    k = db.session.get(HostessKnowledge, id)
    if k:
        db.session.delete(k)
        db.session.commit()
        flash(_('تم حذف المعرفة'), 'success')
    return redirect(url_for('main.dev_knowledge'))


# --- Bounties ---
@bp.route('/developer/bounties')
@developer_required
def dev_bounties():
    bounties = Bounty.query.order_by(Bounty.amount.desc()).all()
    return render_template('developer/bounties.html', bounties=bounties, title=_('إدارة المكافآت (Bounties)'))

@bp.route('/developer/bounty/delete/<int:id>', methods=['POST'])
@developer_required
def dev_bounty_delete(id):
    b = db.session.get(Bounty, id)
    if b:
        db.session.delete(b)
        db.session.commit()
        flash(_('تم حذف المكافأة'), 'success')
    return redirect(url_for('main.dev_bounties'))


@bp.route('/developer/config/add', methods=['POST'])
@developer_required
def dev_config_add():
    key = (request.form.get('key') or '').strip()
    value = (request.form.get('value') or '').strip()
    if not key:
        flash(_('المفتاح مطلوب.'), 'danger')
        return redirect(url_for('main.dev_config'))
    existing = SystemConfig.query.filter_by(key=key).first()
    if existing:
        existing.value = value
    else:
        db.session.add(SystemConfig(key=key, value=value))
    db.session.commit()
    flash(_('تم حفظ الإعداد'), 'success')
    return redirect(url_for('main.dev_config'))


@bp.route('/developer/config/reset_market_defaults', methods=['POST'])
@developer_required
def dev_config_reset_market_defaults():
    defaults = {
        'market_enable_spot': 'true',
        'market_enable_futures': 'true',
        'market_enable_limit_orders': 'true',
        'market_spot_min_buy_usd': '10',
        'market_futures_leverages': '1,5,10,20,50,100',
        'market_update_interval_seconds': '60',
        'market_intel_cost': '500',
    }
    for key, value in defaults.items():
        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            config = SystemConfig(key=key)
            db.session.add(config)
        config.value = value
    db.session.commit()
    flash(_('تمت إعادة إعدادات السوق الافتراضية.'), 'success')
    return redirect(url_for('main.dev_config'))


@bp.route('/developer/logs')
@developer_required
def dev_logs():
    page = request.args.get('page', 1, type=int)
    action = request.args.get('action', '').strip()
    admin_username = request.args.get('admin_username', '').strip()
    search = request.args.get('search', '').strip()

    query = GameLog.query.order_by(GameLog.timestamp.desc())
    if action:
        query = query.filter(GameLog.action == action)
    if admin_username:
        query = query.join(User, GameLog.admin_id == User.id).filter(User.username.ilike(f'%{admin_username}%'))
    if search:
        query = query.filter(GameLog.details.ilike(f'%{search}%'))

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    actions = [row[0] for row in db.session.query(GameLog.action).distinct().order_by(GameLog.action.asc()).all()]
    current_filters = SimpleNamespace(action=action, admin_username=admin_username, search=search)

    return render_template(
        'developer/logs.html',
        logs=pagination.items,
        pagination=pagination,
        actions=actions,
        current_filters=current_filters,
        title=_('سجلات النظام'),
    )


@bp.route('/developer/heist_history')
@developer_required
def dev_heist_history():
    page = request.args.get('page', 1, type=int)
    pagination = HeistHistory.query.order_by(HeistHistory.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    heists = [
        SimpleNamespace(
            id=h.id,
            crime_name=h.crime_name,
            leader_name=h.leader_name,
            is_success=bool(h.success),
            total_reward=int(h.money_earned or 0),
            created_at=h.created_at,
            participants_snapshot=h.participants_snapshot or [],
            result_log=h.log_details or '',
        )
        for h in pagination.items
    ]
    return render_template('developer/heist_history.html', heists=heists, pagination=pagination, title=_('سجل الجرائم المنظمة'))


@bp.route('/developer/lobbies/delete/<int:lobby_id>', methods=['POST'])
@developer_required
def dev_delete_lobby(lobby_id):
    lobby = db.session.get(CrimeLobby, lobby_id)
    if lobby:
        db.session.delete(lobby)
        db.session.commit()
        flash(_('تم حذف المجموعة.'), 'success')
    return redirect(url_for('main.dev_dashboard'))


@bp.route('/developer/organized_crime/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/organized_crime/new', methods=['GET', 'POST'])
@developer_required
def dev_organized_crime_edit(id=None):
    if id:
        crime = db.session.get(OrganizedCrime, id)
        if not crime:
            abort(404)
        title = _('تعديل جريمة منظمة')
    else:
        crime = OrganizedCrime()
        title = _('إضافة جريمة منظمة')

    form = OrganizedCrimeForm(obj=crime)
    if form.validate_on_submit():
        form.populate_obj(crime)
        image_path = save_image(form.image.data, 'crimes')
        if image_path:
            crime.image = image_path
        db.session.add(crime)
        db.session.commit()
        flash(_('تم حفظ الجريمة المنظمة'), 'success')
        return redirect(url_for('main.dev_organized_crimes'))

    return render_template('developer/edit_organized_crime.html', form=form, title=title)

@bp.route('/developer/lobbies')
@developer_required
def dev_active_lobbies():
    lobbies = CrimeLobby.query.order_by(CrimeLobby.created_at.desc()).all()
    return render_template('developer/active_lobbies.html', lobbies=lobbies, title=_('المجموعات النشطة'))

# --- Factories ---
@bp.route('/developer/factories')
@developer_required
def dev_factories():
    jobs = FactoryJob.query.order_by(FactoryJob.started_at.desc()).limit(50).all()
    return render_template('developer/factories.html', jobs=jobs, title=_('إدارة المصانع'))

@bp.route('/developer/factory/job/<int:id>/cancel', methods=['POST'])
@developer_required
def dev_factory_job_cancel(id):
    job = db.session.get(FactoryJob, id)
    if job:
        job.status = 'canceled'
        db.session.commit()
        flash(_('تم إلغاء مهمة المصنع'), 'success')
    return redirect(url_for('main.dev_factories'))

@bp.route('/developer/factory/job/<int:id>/complete', methods=['POST'])
@developer_required
def dev_factory_job_complete(id):
    job = db.session.get(FactoryJob, id)
    if job and job.status == 'running':
        job.ends_at = datetime.now(timezone.utc)
        db.session.commit()
        flash(_('تم إكمال مهمة المصنع فوراً'), 'success')
    return redirect(url_for('main.dev_factories'))

@bp.route('/developer/factory/job/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/factory/job/new', methods=['GET', 'POST'])
@developer_required
def dev_factory_job_edit(id=None):
    if id:
        job = db.session.get(FactoryJob, id)
        if not job: abort(404)
        title = _('تعديل مهمة مصنع')
    else:
        job = FactoryJob()
        title = _('إضافة مهمة مصنع')
    
    form = FactoryJobForm(obj=job)
    
    # Populate user choices for new job (optional, but helpful if list is small)
    # If user list is huge, this might be slow. Maybe just text input for User ID?
    # Let's assume text input for user_id in form or just keep it simple.
    # The form definition needs to be checked.
    
    if form.validate_on_submit():
        form.populate_obj(job)
        
        if not id:
            db.session.add(job)
            
        db.session.commit()
        flash(_('تم حفظ مهمة المصنع'), 'success')
        return redirect(url_for('main.dev_factories'))
        
    return render_template('developer/edit_factory_job.html', form=form, title=title)

@bp.route('/developer/factory/job/delete/<int:id>', methods=['POST'])
@developer_required
def dev_factory_job_delete(id):
    job = db.session.get(FactoryJob, id)
    if job:
        db.session.delete(job)
        db.session.commit()
        flash(_('تم حذف مهمة المصنع'), 'success')
    return redirect(url_for('main.dev_factories'))

# --- Market ---
@bp.route('/developer/market')
@developer_required
def dev_market():
    assets = MarketAsset.query.all()
    return render_template('developer/market.html', assets=assets, title=_('سوق الأسهم'))

@bp.route('/developer/market/update_price', methods=['POST'])
@developer_required
def dev_market_update_price():
    asset_id = request.form.get('asset_id', type=int)
    new_price = request.form.get('price', type=float)
    
    asset = db.session.get(MarketAsset, asset_id)
    if asset and new_price is not None:
        old_price = asset.current_price
        asset.current_price = new_price
        
        # Calculate change
        if old_price > 0:
            change_pct = ((new_price - old_price) / old_price) * 100
            asset.price_change_24h = change_pct
            
        asset.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        flash(_('تم تحديث سعر السهم'), 'success')
    
    return redirect(url_for('main.dev_market'))

@bp.route('/developer/market/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/market/new', methods=['GET', 'POST'])
@developer_required
def dev_market_edit(id=None):
    if id:
        asset = db.session.get(MarketAsset, id)
        if not asset: abort(404)
        title = _('تعديل أصل')
    else:
        asset = MarketAsset()
        title = _('إضافة أصل جديد')
    
    form = MarketAssetForm(obj=asset)
    if form.validate_on_submit():
        form.populate_obj(asset)
        
        # Ensure change is calculated if new price differs (optional, mostly for display)
        # Here we just save the config.
        
        if not id:
            db.session.add(asset)
            
        db.session.commit()
        flash(_('تم حفظ الأصل المالي'), 'success')
        return redirect(url_for('main.dev_market'))
        
    return render_template('developer/edit_market_asset.html', form=form, title=title)

@bp.route('/developer/market/delete/<int:id>', methods=['POST'])
@developer_required
def dev_market_delete(id):
    asset = db.session.get(MarketAsset, id)
    if asset:
        db.session.delete(asset)
        db.session.commit()
        flash(_('تم حذف الأصل المالي'), 'success')
    return redirect(url_for('main.dev_market'))
