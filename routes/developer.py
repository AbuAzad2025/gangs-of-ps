from flask import render_template, request, flash, redirect, url_for, abort, current_app, session
from werkzeug.utils import secure_filename
import os
import json
from flask_login import current_user
from flask_babel import _
from sqlalchemy import or_
from . import bp
from decorators import developer_required, double_verification_required
from models.user import User, UserRank, UserRole
from models.social import Gang, Message, GangWar, GangAlliance
from models.gameplay import Crime, DailyTask, HeistHistory, CrimeLobby, OrganizedCrime, ResurrectionRequest
from models.knowledge import HostessKnowledge
from models.bounty import Bounty
from models.system import SystemConfig, Announcement
from models.log import GameLog, UserLog, ConfigLog, MoneySinkLog
from models.hostess import Hostess, VideoScenario, HostessChatMessage, HostessMemory
from services.hostess_training_service import build_greeter_leader_prompt, build_greeter_leader_training_json
from services.resource_service import ResourceService
from models.item import Item
from models.vehicle import Vehicle
from models.location import Location
from models.economy import Asset
from models.factory import FactoryJob
from models.market import MarketAsset, Auction, AuctionBid
from models.forum import ForumCategory
from models.achievement import Achievement, UserAchievement
from services.market_simulation import MarketSimulationService
from forms.developer import (
    GangForm, HostessKnowledgeForm, OrganizedCrimeForm, HostessForm,
    VehicleForm, ItemForm, CrimeForm, AssetForm, TaskForm, AnnouncementForm,
    ForumCategoryForm, LocationForm, AchievementForm, VideoScenarioForm,
    SystemConfigForm, FactoryJobForm, MarketAssetForm
)
from extensions import db
from utils.backup_manager import BackupManager
from flask_migrate import upgrade
from .utils import save_image
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from sqlalchemy import func


@bp.route('/developer')
@developer_required
def dev_dashboard():
    # Calculate stats
    today_start = datetime.now(
        timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0)
    today_start_naive = today_start.replace(tzinfo=None)

    total_users = User.query.count()
    total_money = db.session.query(func.sum(User.money)).scalar() or 0
    total_diamonds = db.session.query(func.sum(User.diamonds)).scalar() or 0
    new_users_today = User.query.filter(
        User.created_at >= today_start_naive).count()

    # Auction Stats
    active_auctions_money = db.session.query(
        func.sum(
            Auction.current_price)).filter(
        Auction.status == 'active').scalar() or 0
    burned_auction_money = db.session.query(func.sum(Auction.current_price)).filter(
        Auction.status == 'completed', Auction.seller_id is None).scalar() or 0

    # Economy Sinks Stats
    daily_sunk_money = db.session.query(func.sum(MoneySinkLog.amount)).filter(
        MoneySinkLog.timestamp >= today_start_naive).scalar() or 0

    # Specific Sink Totals (Today)
    gang_maintenance_today = db.session.query(
        func.sum(
            MoneySinkLog.amount)).filter(
        MoneySinkLog.timestamp >= today_start_naive,
        MoneySinkLog.sink_type == 'gang_property_maintenance').scalar() or 0

    factory_smelt_today = db.session.query(
        func.sum(
            MoneySinkLog.amount)).filter(
        MoneySinkLog.timestamp >= today_start_naive,
        MoneySinkLog.sink_type == 'factory_smelt_cost').scalar() or 0

    # Top Sink Types
    sink_breakdown = db.session.query(
        MoneySinkLog.sink_type,
        func.sum(
            MoneySinkLog.amount).label('total')).group_by(
        MoneySinkLog.sink_type).order_by(
                func.sum(
                    MoneySinkLog.amount).desc()).limit(5).all()

    stats = SimpleNamespace(
        total_users=total_users,
        total_money=total_money,
        total_diamonds=total_diamonds,
        new_users_today=new_users_today,
        active_auctions_money=active_auctions_money,
        burned_auction_money=burned_auction_money,
        daily_sunk_money=daily_sunk_money,
        gang_maintenance_today=gang_maintenance_today,
        factory_smelt_today=factory_smelt_today,
        sink_breakdown=sink_breakdown
    )

    backups = BackupManager.get_backups()

    maintenance_mode = SystemConfig.get_value('maintenance_mode') == 'true'
    maintenance_message = SystemConfig.get_value('maintenance_message', '')

    # Occupation Settings
    occupation_alert_level = int(
        SystemConfig.get_value(
            'occupation_alert_level', '1'))
    mashtoub_campaign_active = SystemConfig.get_value(
        'mashtoub_campaign_active', 'false') == 'true'

    entertainment_enabled = SystemConfig.get_value(
        'entertainment_enabled', 'true') == 'true'
    betting_enabled = SystemConfig.get_value(
        'betting_enabled', 'true') == 'true'
    allowed_currencies = SystemConfig.get_value(
        'betting_allowed_currencies',
        'money,diamonds') or 'money,diamonds'
    house_cut_percent = SystemConfig.get_value(
        'house_cut_percent', '50') or '50'
    betting_min_stake = SystemConfig.get_value('betting_min_stake', '0') or '0'
    betting_max_stake = SystemConfig.get_value(
        'betting_max_stake', '1000000000') or '1000000000'
    game_chess_enabled = SystemConfig.get_value(
        'game_chess_enabled', 'true') == 'true'
    game_trix_enabled = SystemConfig.get_value(
        'game_trix_enabled', 'true') == 'true'
    game_tarneeb_enabled = SystemConfig.get_value(
        'game_tarneeb_enabled', 'true') == 'true'

    return render_template(
        'developer/dashboard.html',
        stats=stats,
        backups=backups,
        maintenance_mode=maintenance_mode,
        maintenance_message=maintenance_message,
        occupation_alert_level=occupation_alert_level,
        mashtoub_campaign_active=mashtoub_campaign_active,
        entertainment_enabled=entertainment_enabled,
        betting_enabled=betting_enabled,
        allowed_currencies=allowed_currencies,
        house_cut_percent=house_cut_percent,
        betting_min_stake=betting_min_stake,
        betting_max_stake=betting_max_stake,
        game_chess_enabled=game_chess_enabled,
        game_trix_enabled=game_trix_enabled,
        game_tarneeb_enabled=game_tarneeb_enabled,
        title=_('لوحة تحكم المطور'))


@bp.route('/developer/maintenance', methods=['POST'])
@developer_required
@double_verification_required
def dev_maintenance_mode():
    mode = request.form.get('mode') == 'on'
    message = request.form.get('message', '')

    SystemConfig.set_value(
        'maintenance_mode',
        'true' if mode else 'false',
        description='System Maintenance Mode')
    SystemConfig.set_value(
        'maintenance_message',
        message,
        description='Maintenance Message')

    flash(_('تم تحديث وضع الصيانة'), 'success')
    return redirect(url_for('main.dev_dashboard'))


@bp.route('/developer/verify', methods=['GET', 'POST'])
@developer_required
def admin_verify():
    if request.method == 'POST':
        password = request.form.get('password')
        if current_user.check_password(password):
            session['admin_verified_at'] = datetime.now(
                timezone.utc).isoformat()
            next_url = session.get('next_url', url_for('main.dev_dashboard'))
            session.pop('next_url', None)
            flash(_('تم التحقق بنجاح.'), 'success')
            return redirect(next_url)
        else:
            flash(_('كلمة المرور غير صحيحة.'), 'danger')

    return render_template('developer/verify.html', title=_('التحقق الأمني'))

# --- Backups ---


@bp.route('/developer/backup/create', methods=['POST'])
@developer_required
@double_verification_required
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
@double_verification_required
def delete_backup(filename):
    success, message = BackupManager.delete_backup(filename)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('main.dev_dashboard'))


@bp.route('/developer/system/migrate', methods=['POST'])
@developer_required
@double_verification_required
def run_migrations():
    try:
        upgrade()
        flash(_('تم تحديث قاعدة البيانات بنجاح (Migrations Applied).'), 'success')
    except Exception as e:
        flash(_('فشل تحديث قاعدة البيانات: %(error)s', error=str(e)), 'danger')
    return redirect(url_for('main.dev_dashboard'))


@bp.route('/developer/occupation/update', methods=['POST'])
@developer_required
def update_occupation_settings():
    try:
        level = int(request.form.get('occupation_alert_level', 1))
        SystemConfig.set_value(
            'occupation_alert_level',
            level,
            description='Occupation Alert Level (1-3)')
        flash(_('تم تحديث مستوى حالة الاحتلال.'), 'success')
    except Exception as e:
        flash(_('حدث خطأ: %(error)s', error=str(e)), 'danger')
    return redirect(url_for('main.dev_dashboard'))


@bp.route('/developer/occupation/mashtoub', methods=['POST'])
@developer_required
def toggle_mashtoub_campaign():
    try:
        active = request.form.get('active') == 'true'
        SystemConfig.set_value(
            'mashtoub_campaign_active',
            'true' if active else 'false',
            description='Mashtoub Car Campaign')
        if active:
            flash(_('تم تفعيل حملة المشطوب! الشرطة منتشرة.'), 'warning')
        else:
            flash(_('تم إيقاف حملة المشطوب.'), 'success')
    except Exception as e:
        flash(_('حدث خطأ: %(error)s', error=str(e)), 'danger')
    return redirect(url_for('main.dev_dashboard'))


@bp.route('/developer/entertainment/update', methods=['POST'])
@developer_required
@double_verification_required
def update_entertainment_settings():
    try:
        entertainment_enabled = request.form.get(
            'entertainment_enabled') == 'true'
        betting_enabled = request.form.get('betting_enabled') == 'true'
        allowed_currencies = request.form.get(
            'allowed_currencies', 'money,diamonds')
        house_cut_percent = request.form.get('house_cut_percent', '50')
        min_stake = request.form.get('betting_min_stake', '0')
        max_stake = request.form.get('betting_max_stake', '1000000000')
        game_chess_enabled = request.form.get('game_chess_enabled') == 'true'
        game_trix_enabled = request.form.get('game_trix_enabled') == 'true'
        game_tarneeb_enabled = request.form.get(
            'game_tarneeb_enabled') == 'true'

        SystemConfig.set_value(
            'entertainment_enabled',
            'true' if entertainment_enabled else 'false',
            description='Enable entertainment module')
        SystemConfig.set_value(
            'betting_enabled',
            'true' if betting_enabled else 'false',
            description='Enable betting')
        SystemConfig.set_value(
            'betting_allowed_currencies',
            allowed_currencies,
            description='Allowed currencies for betting')
        SystemConfig.set_value(
            'house_cut_percent',
            house_cut_percent,
            description='House cut percent for Azad')
        SystemConfig.set_value(
            'betting_min_stake',
            min_stake,
            description='Minimum stake per room')
        SystemConfig.set_value(
            'betting_max_stake',
            max_stake,
            description='Maximum stake per room')
        SystemConfig.set_value(
            'game_chess_enabled',
            'true' if game_chess_enabled else 'false',
            description='Chess game enabled')
        SystemConfig.set_value(
            'game_trix_enabled',
            'true' if game_trix_enabled else 'false',
            description='Trix game enabled')
        SystemConfig.set_value(
            'game_tarneeb_enabled',
            'true' if game_tarneeb_enabled else 'false',
            description='Tarneeb game enabled')

        flash(_('تم تحديث إعدادات الترفيه والرهانات'), 'success')
    except Exception as e:
        flash(_('فشل التحديث: %(error)s', error=str(e)), 'danger')
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

    pagination = query.order_by(
        User.id.desc()).paginate(
        page=page,
        per_page=20,
        error_out=False)
    return render_template(
        'developer/users.html',
        users=pagination.items,
        pagination=pagination,
        search_query=search_query,
        title=_('إدارة اللاعبين'))


@bp.route('/developer/user/delete/<int:id>', methods=['POST'])
@developer_required
@double_verification_required
def dev_user_delete(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)

    if int(user.id) == int(current_user.id):
        flash(_('لا يمكنك حذف حسابك من لوحة المطور.'), 'danger')
        return redirect(url_for('main.dev_users'))

    if user.gang and user.gang.leader_id == user.id:
        flash(
            _(
                'لا يمكن حذف المستخدم %(username)s لأنه قائد عصابة %(gang_name)s. '
                'يرجى نقل القيادة أو حذف العصابة أولاً.',
                username=user.username,
                gang_name=user.gang.name,
            ),
            'danger',
        )
        return redirect(url_for('main.dev_users'))

    try:
        from models import (
            UserItem, UserVehicle, UserDailyTask, UserCrimeCooldown,
            Message, Notification, Bounty, CombatLog, UserInvestment,
            UserProgress, ResurrectionRequest, PaymentTransaction,
            GangInvite, LobbyParticipant, CrimeLobby, ForumTopic,
            ForumPost, Referral, RaceParticipant
        )

        UserItem.query.filter_by(user_id=user.id).delete()
        uv_ids = [
            row[0]
            for row in db.session.query(UserVehicle.id)
            .filter_by(user_id=user.id)
            .all()
        ]
        if uv_ids:
            RaceParticipant.query.filter(
                RaceParticipant.user_vehicle_id.in_(uv_ids)
            ).delete(synchronize_session=False)
        RaceParticipant.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )
        UserVehicle.query.filter_by(user_id=user.id).delete()
        UserDailyTask.query.filter_by(user_id=user.id).delete()
        UserCrimeCooldown.query.filter_by(user_id=user.id).delete()
        UserInvestment.query.filter_by(user_id=user.id).delete()
        UserProgress.query.filter_by(user_id=user.id).delete()
        ResurrectionRequest.query.filter_by(user_id=user.id).delete()
        PaymentTransaction.query.filter_by(user_id=user.id).delete()
        GangInvite.query.filter_by(user_id=user.id).delete()

        ForumPost.query.filter_by(user_id=user.id).delete()
        ForumTopic.query.filter_by(user_id=user.id).delete()

        Referral.query.filter(
            (Referral.referrer_id == user.id) | (
                Referral.referred_id == user.id)).delete()

        Message.query.filter(
            (Message.sender_id == user.id) | (
                Message.receiver_id == user.id)).delete()
        Notification.query.filter_by(user_id=user.id).delete()

        Bounty.query.filter(
            (Bounty.placer_id == user.id) | (
                Bounty.target_id == user.id)).delete()
        CombatLog.query.filter(
            (CombatLog.attacker_id == user.id) | (
                CombatLog.defender_id == user.id)).delete()

        lobbies_led = CrimeLobby.query.filter_by(leader_id=user.id).all()
        for lobby in lobbies_led:
            LobbyParticipant.query.filter_by(lobby_id=lobby.id).delete()

        LobbyParticipant.query.filter_by(user_id=user.id).delete()
        CrimeLobby.query.filter_by(leader_id=user.id).delete()

        db.session.flush()
        db.session.delete(user)
        db.session.commit()
        flash(_('تم حذف اللاعب نهائياً.'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('فشل حذف اللاعب. %(error)s', error=str(e)), 'danger')

    return redirect(url_for('main.dev_users'))


@bp.route('/developer/user/disable/<int:id>', methods=['POST'])
@developer_required
@double_verification_required
def dev_user_disable(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)

    if int(user.id) == int(current_user.id):
        flash(_('لا يمكنك تعطيل حسابك من لوحة المطور.'), 'danger')
        return redirect(url_for('main.dev_users'))

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    user.banned_until = now_naive + timedelta(days=3650)
    user.ban_reason = _('تم تعطيل الحساب من قبل المطور.')
    db.session.commit()
    flash(_('تم تعطيل اللاعب.'), 'success')
    return redirect(url_for('main.dev_users'))


@bp.route('/developer/user/enable/<int:id>', methods=['POST'])
@developer_required
@double_verification_required
def dev_user_enable(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)

    user.banned_until = None
    user.ban_reason = None
    db.session.commit()
    flash(_('تم تفعيل اللاعب.'), 'success')
    return redirect(url_for('main.dev_users'))


@bp.route('/developer/user/kill/<int:id>', methods=['POST'])
@developer_required
@double_verification_required
def dev_user_kill(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)

    if int(user.id) == int(current_user.id):
        flash(_('لا يمكنك قتل نفسك من لوحة المطور.'), 'danger')
        return redirect(url_for('main.dev_users'))

    if user.health <= 0:
        flash(_('اللاعب ميت بالفعل.'), 'warning')
        return redirect(url_for('main.dev_users'))

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    user.health = 0
    user.hospital_until = now_naive + timedelta(minutes=10)
    db.session.commit()
    flash(_('تم قتل اللاعب ونقله للمقبرة.'), 'success')
    return redirect(url_for('main.dev_users'))


@bp.route('/developer/user/resurrect/<int:id>', methods=['POST'])
@developer_required
@double_verification_required
def dev_user_resurrect(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)

    if user.health > 0:
        flash(_('اللاعب ليس ميتاً.'), 'warning')
        return redirect(url_for('main.dev_users'))

    now = datetime.now(timezone.utc)
    user.health = user.max_health
    user.energy = user.max_energy
    user.hospital_until = None
    try:
        user.is_dead = False
        user.death_time = None
    except Exception:
        pass
    try:
        from models.user import clear_elite_title_reservation_on_resurrect
        clear_elite_title_reservation_on_resurrect(user.id, now=now)
        db.session.flush()
    except Exception:
        pass

    db.session.commit()
    flash(_('تم إحياء اللاعب.'), 'success')
    return redirect(url_for('main.dev_users'))


@bp.route('/developer/resources/distribute', methods=['GET', 'POST'])
@developer_required
@double_verification_required
def dev_distribute_resources():
    resource_options = [
        ("money", _("كاش (Money)")),
        ("bank_balance", _("رصيد بنكي (Bank Balance)")),
        ("diamonds", _("الماس (Diamonds)")),
        ("bullets", _("رصاص (Bullets)")),
        ("energy", _("طاقة (Energy)")),
        ("max_energy", _("الحد الأقصى للطاقة (Max Energy)")),
        ("health", _("صحة (Health)")),
        ("max_health", _("الحد الأقصى للصحة (Max Health)")),
        ("brave", _("شجاعة (Brave)")),
        ("max_brave", _("الحد الأقصى للشجاعة (Max Brave)")),
        ("strength", _("قوة (Strength)")),
        ("defense", _("دفاع (Defense)")),
        ("agility", _("رشاقة (Agility)")),
        ("intelligence", _("ذكاء (Intelligence)")),
        ("driving_skill", _("مهارة القيادة (Driving Skill)")),
    ]
    allowed_resource_types = {k for k, _label in resource_options}

    if request.method == 'POST':
        # 'all', 'online', 'user_id'
        target_type = request.form.get('target_type')
        # 'money', 'diamonds', 'bullets'
        resource_type = request.form.get('resource_type')

        # Enhanced input validation
        if target_type not in ['all', 'user_id']:
            flash(_('نوع الهدف غير صالح'), 'danger')
            return redirect(url_for('main.dev_distribute_resources'))

        if resource_type not in allowed_resource_types:
            flash(_('نوع المورد غير صالح'), 'danger')
            return redirect(url_for('main.dev_distribute_resources'))

        try:
            amount = int(request.form.get('amount', 0))
            if amount <= 0 or amount > 1000000000:  # Max limit
                raise ValueError("Invalid amount")
        except ValueError:
            flash(
                _('الكمية يجب أن تكون رقمًا صالحًا بين 1 و 1,000,000,000'),
                'danger')
            return redirect(url_for('main.dev_distribute_resources'))

        reason_key = (request.form.get('distribution_reason')
                      or 'admin_distribution').strip()
        distribution_note = (request.form.get(
            'distribution_note') or '').strip()
        if len(distribution_note) > 300:
            flash(_('ملاحظة السبب طويلة جدًا (الحد الأقصى 300 حرف)'), 'danger')
            return redirect(url_for('main.dev_distribute_resources'))

        allowed_reason_keys = {
            "admin_distribution",
            "real_money_purchase",
            "event_reward",
            "bug_compensation",
            "support_compensation",
            "content_creator_reward",
            "partnership_promo",
            "referral_reward",
            "chargeback_reversal",
            "manual_adjustment",
            "test_distribution",
        }
        if reason_key not in allowed_reason_keys:
            flash(_('سبب التوزيع غير صالح'), 'danger')
            return redirect(url_for('main.dev_distribute_resources'))

        real_money_amount = None
        real_money_currency = (request.form.get(
            'real_money_currency') or 'USD').strip().upper()
        if reason_key == "real_money_purchase":
            if target_type != "user_id":
                flash(
                    _('عمليات المال الحقيقي يجب أن تكون للاعب محدد (User ID).'),
                    'danger')
                return redirect(url_for('main.dev_distribute_resources'))
            try:
                real_money_amount = float(
                    request.form.get('real_money_amount') or 0)
                if real_money_amount <= 0 or real_money_amount > 1000000:
                    raise ValueError("Invalid real money amount")
            except Exception:
                flash(_('مبلغ المال الحقيقي غير صالح'), 'danger')
                return redirect(url_for('main.dev_distribute_resources'))
            if real_money_currency not in {"USD", "ILS", "EUR"}:
                real_money_currency = "USD"

        reason = f"admin_{reason_key}"
        log_extra = {
            "distribution_reason_key": reason_key,
            "distribution_note": distribution_note,
            "distribution_target_type": target_type,
            "distribution_resource_type": resource_type,
            "distribution_resource_amount": amount,
        }
        if real_money_amount is not None:
            log_extra["real_money_amount"] = real_money_amount
            log_extra["real_money_currency"] = real_money_currency

        target_users = []
        if target_type == 'all':
            target_users = User.query.all()
        elif target_type == 'user_id':
            uid = request.form.get('user_id', type=int)
            user = db.session.get(User, uid) if uid else None
            if user:
                target_users = [user]
        # For 'online', we assume active in last 5 minutes (requires tracking, skipping for now or assume all)
        # Simplification: Only All or Single for now as user tracking might not
        # be reliable

        count = 0
        for user in target_users:
            changes = {resource_type: amount}
            if ResourceService.modify_resources(
                    user.id,
                    changes,
                    reason,
                    check_balance=False,
                    auto_commit=False,
                    log_extra=log_extra):
                count += 1

        if real_money_amount is not None and count > 0:
            dev_log = UserLog(
                user_id=current_user.id,
                action="REAL_MONEY_REVENUE",
                details=json.dumps({
                    "amount": real_money_amount,
                    "currency": real_money_currency,
                    "targets_count": count,
                    "target_type": target_type,
                    "resource_type": resource_type,
                    "resource_amount": amount,
                    "reason_key": reason_key,
                    "note": distribution_note,
                }),
                result="success",
                ip_address=request.remote_addr,
                user_agent=str(request.user_agent),
            )
            db.session.add(dev_log)

        db.session.commit()
        flash(_('تم توزيع الموارد على %(count)s لاعب بنجاح', count=count), 'success')
        return redirect(url_for('main.dev_distribute_resources'))

    return render_template(
        'developer/distribute_resources.html',
        title=_('توزيع الموارد'),
        resource_options=resource_options)


@bp.route('/developer/revenue/reset', methods=['POST'])
@developer_required
@double_verification_required
def reset_real_money_report():
    deleted = 0
    try:
        deleted += UserLog.query.filter(UserLog.action.in_(
            ["ADMIN_REAL_MONEY_PURCHASE", "REAL_MONEY_REVENUE"])).delete(synchronize_session=False)
    except Exception:
        db.session.rollback()
        deleted = 0

    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    SystemConfig.set_value(
        'real_money_report_start_at',
        now,
        description='Start time for real money report (reset baseline)')
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(_('حدث خطأ أثناء تصفير التقرير.'), 'danger')
        return redirect(
            url_for(
                'main.profile',
                user_id=current_user.id) +
            '#revenue')

    flash(_('تم تصفير تقرير المال الحقيقي من الآن.'), 'success')
    return redirect(
        url_for(
            'main.profile',
            user_id=current_user.id) +
        '#revenue')


@bp.route('/developer/user/edit/<int:id>', methods=['GET', 'POST'])
@developer_required
def dev_user_edit(id):
    user = db.session.get(User, id)
    if not user:
        abort(404)

    if request.method == 'POST':
        try:
            # Enhanced input validation for user edit
            new_money = int(request.form.get('money', 0))
            if new_money < 0 or new_money > 1000000000000:  # Max 1 trillion
                raise ValueError("Invalid money amount")

            new_bank = int(request.form.get('bank_balance', 0))
            if new_bank < 0 or new_bank > 1000000000000:
                raise ValueError("Invalid bank amount")

            new_diamonds = int(request.form.get('diamonds', 0))
            if new_diamonds < 0 or new_diamonds > 1000000:
                raise ValueError("Invalid diamonds amount")

            new_bullets = int(request.form.get('bullets', 0))
            if new_bullets < 0 or new_bullets > 1000000:
                raise ValueError("Invalid bullets amount")

            new_exp = int(request.form.get('exp', 0))
            if new_exp < 0 or new_exp > 1000000000:
                raise ValueError("Invalid exp amount")

            new_strength = int(request.form.get('strength', 10))
            if new_strength < 1 or new_strength > 99999:
                raise ValueError("Invalid strength value")

            new_defense = int(request.form.get('defense', 10))
            if new_defense < 1 or new_defense > 99999:
                raise ValueError("Invalid defense value")

            new_agility = int(request.form.get('agility', 10))
            if new_agility < 1 or new_agility > 99999:
                raise ValueError("Invalid agility value")

            new_intelligence = int(request.form.get('intelligence', 10))
            if new_intelligence < 1 or new_intelligence > 99999:
                raise ValueError("Invalid intelligence value")

            changes = {
                'money': new_money - (user.money or 0),
                'bank_balance': new_bank - (user.bank_balance or 0),
                'diamonds': new_diamonds - (user.diamonds or 0),
                'bullets': new_bullets - (user.bullets or 0),
                'exp': new_exp - (user.exp or 0),
                'strength': new_strength - (user.strength or 0),
                'defense': new_defense - (user.defense or 0),
                'agility': new_agility - (user.agility or 0),
                'intelligence': new_intelligence - (user.intelligence or 0)
            }

            # Remove 0 changes to avoid clutter
            changes = {k: v for k, v in changes.items() if v != 0}

            # Prepare set_fields for non-resource attributes
            set_fields = {
                'username': request.form.get('username'),
                'level': int(request.form.get('level', 1)),
                'health': int(request.form.get('health', 100)),
                'max_health': int(request.form.get('max_health', 100)),
                'energy': int(request.form.get('energy', 100)),
                'max_energy': int(request.form.get('max_energy', 100)),
                'brave': int(request.form.get('brave', 100)),
                'max_brave': int(request.form.get('max_brave', 100)),
                'daily_streak': int(request.form.get('daily_streak', 0)),
                'location_id': int(request.form.get('location_id', 1)),
                'is_ghost_mode': 'is_ghost_mode' in request.form
            }

            # Gang ID Handling
            gang_id_input = request.form.get('gang_id')
            if gang_id_input:
                try:
                    gid = int(gang_id_input)
                    gang = db.session.get(Gang, gid)
                    if gang:
                        set_fields['gang_id'] = gid
                    else:
                        flash(_('عصابة غير موجودة'), 'warning')
                except ValueError:
                    pass
            elif 'gang_id' in request.form and not gang_id_input:
                # If field exists but empty, user wants to leave gang
                set_fields['gang_id'] = None

            try:
                heat_value = int(request.form.get('heat', 0))
            except Exception:
                heat_value = 0
            heat_value = max(0, min(100, heat_value))
            set_fields['heat_points'] = heat_value
            set_fields['heat_updated_at'] = datetime.now(
                timezone.utc).replace(
                tzinfo=None) if heat_value > 0 else None

            ban_hours = request.form.get('ban_hours')
            if ban_hours and int(ban_hours) > 0:
                set_fields['banned_until'] = datetime.now(
                ) + timedelta(hours=int(ban_hours))
                set_fields['ban_reason'] = request.form.get('ban_reason')

            if 'clear_ban' in request.form:
                set_fields['banned_until'] = None

            # Administrative Detention (Jail)
            jail_hours = request.form.get('jail_hours')
            if jail_hours and int(jail_hours) > 0:
                set_fields['jail_until'] = datetime.now(
                ) + timedelta(hours=int(jail_hours))

            if 'clear_jail' in request.form:
                set_fields['jail_until'] = None

            # Collaborator/Suspicious Status
            set_fields['is_suspicious'] = 'is_suspicious' in request.form

            role_name = request.form.get('role')
            if role_name:
                role = UserRank.query.filter_by(name=role_name).first()
                if role:
                    set_fields['role_id'] = role.id

            # Apply changes via ResourceService
            # Note: expected_version is None because Admin overrides everything
            ResourceService.modify_resources(
                user.id,
                changes,
                'admin_edit',
                auto_commit=True,
                set_fields=set_fields)

            flash(_('تم تحديث بيانات المستخدم'), 'success')
        except Exception as e:
            flash(_('حدث خطأ أثناء التحديث: %(e)s', e=str(e)), 'danger')

        return redirect(url_for('main.dev_user_edit', id=user.id))

    roles = UserRank.query.all()
    locations = Location.query.all()
    return render_template(
        'developer/edit_user.html',
        user=user,
        roles=roles,
        locations=locations,
        title=_('تعديل مستخدم'))


@bp.route('/developer/user/clear_status/<int:id>', methods=['POST'])
@developer_required
def dev_user_clear_status(id):
    user = db.session.get(User, id)
    if user:
        set_fields = {
            'health': user.max_health,
            'energy': user.max_energy,
            'brave': user.max_brave
        }
        ResourceService.modify_resources(
            user.id,
            {},
            'admin_clear_status',
            auto_commit=True,
            set_fields=set_fields)
        flash(_('تم تصفير الحالة'), 'success')
    return redirect(url_for('main.dev_user_edit', id=id))


@bp.route('/developer/user/reset_daily_limit/<int:id>', methods=['POST'])
@developer_required
def dev_user_reset_daily_limit(id):
    user = db.session.get(User, id)
    if user:
        user.daily_money_earned = 0
        user.daily_money_date = datetime.now(timezone.utc).date()
        db.session.commit()
        flash(_('تم تصفير الحد اليومي للكسب'), 'success')
    return redirect(url_for('main.dev_user_edit', id=id))


@bp.route('/developer/user/boost/<int:id>', methods=['POST'])
@developer_required
def dev_user_boost(id):
    user = db.session.get(User, id)
    if user:
        changes = {
            'money': max(user.money or 0, 10_000_000_000) - (user.money or 0),
            'diamonds': max(user.diamonds or 0, 10000) - (user.diamonds or 0),
            'strength': max(user.strength or 0, 9999) - (user.strength or 0)
        }
        changes = {k: v for k, v in changes.items() if v != 0}

        set_fields = {
            'role': UserRole.DEVELOPER,
            'level': max(user.level, 100)
        }

        ResourceService.modify_resources(
            user.id,
            changes,
            'admin_boost',
            auto_commit=True,
            set_fields=set_fields)
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

    users_in_newbie_window = User.query.filter(
        User.created_at is not None,
        User.created_at >= threshold).all()
    for u in users_in_newbie_window:
        u.created_at = now_naive - timedelta(days=8)

    db.session.commit()
    flash(_('تم إخراج جميع اللاعبين الحاليين من الحماية'), 'success')
    return redirect(url_for('main.dev_dashboard'))


@bp.route('/developer/heat')
@developer_required
def dev_heat():
    # Get users with heat > 0, ordered by heat desc with limit
    users = User.query.filter(
        User.heat_points > 0).order_by(
        User.heat_points.desc()).limit(1000).all()
    return render_template(
        'developer/heat.html',
        users=users,
        title=_('إدارة مستوى المطاردة'))


@bp.route('/developer/heat/clear_all', methods=['POST'])
@developer_required
def dev_heat_clear_all():
    db.session.query(User).update(
        {User.heat_points: 0, User.heat_updated_at: None}, synchronize_session=False)
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
    if not user:
        abort(404)
    user_achievements = UserAchievement.query.filter_by(user_id=user.id).all()
    return render_template(
        'developer/user_achievements.html',
        user=user,
        user_achievements=user_achievements,
        title=_('إنجازات اللاعب'))


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

    existing = UserAchievement.query.filter_by(
        user_id=user.id, achievement_id=achievement.id).first()
    if not existing:
        db.session.add(
            UserAchievement(
                user_id=user.id,
                achievement_id=achievement.id))
        db.session.commit()
        flash(_('تم منح الإنجاز للاعب'), 'success')
    else:
        flash(_('هذا الإنجاز ممنوح مسبقاً'), 'info')

    return redirect(url_for('main.dev_user_achievements', user_id=user.id))


@bp.route('/developer/user/<int:user_id>/achievements/revoke/<int:user_achievement_id>',
          methods=['POST'])
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
    achievements = Achievement.query.order_by(
        Achievement.points.asc()).limit(500).all()
    unlock_counts = {}
    results = db.session.query(
        UserAchievement.achievement_id, func.count(
            UserAchievement.user_id)).group_by(
        UserAchievement.achievement_id).limit(500).all()
    for aid, count in results:
        unlock_counts[aid] = count

    return render_template(
        'developer/achievements.html',
        achievements=achievements,
        unlock_counts=unlock_counts,
        title=_('إدارة الإنجازات'))


@bp.route('/developer/achievement/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/achievement/new', methods=['GET', 'POST'])
@developer_required
def dev_achievement_edit(id=None):
    if id:
        achievement = db.session.get(Achievement, id)
        if not achievement:
            abort(404)
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

    return render_template(
        'developer/edit_achievement.html',
        form=form,
        title=title)


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
    users = User.query.filter_by(
        is_verified=False).order_by(
        User.created_at.desc()).limit(100).all()
    return render_template(
        'developer/unverified_users.html',
        users=users,
        title=_('مستخدمين بانتظار التفعيل'))


@bp.route('/developer/user/verify/<int:user_id>/<action>', methods=['POST'])
@developer_required
def handle_verification(user_id, action):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

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
    requests = ResurrectionRequest.query.filter_by(
        status='pending').order_by(
        ResurrectionRequest.created_at.desc()).all()
    return render_template(
        'developer/resurrection_requests.html',
        requests=requests,
        title=_('طلبات الإحياء'))


@bp.route('/developer/resurrection/handle/<int:req_id>/<action>',
          methods=['POST'])
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

        set_fields = {
            'health': user.max_health,
            'energy': user.max_energy,
            'is_dead': False,
            'death_time': None
        }
        ResourceService.modify_resources(
            user.id,
            {},
            'admin_resurrect',
            auto_commit=False,
            set_fields=set_fields)

        # Log notification or message to user
        msg = Message(
            sender_id=current_user.id,
            receiver_id=user.id,
            subject=_('تم قبول طلب الإحياء'),
            body=_('تهانينا! تمت الموافقة على طلبك وتم إحياؤك من جديد. حظاً موفقاً!'))
        db.session.add(msg)
        db.session.commit()
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
    # Limit to prevent memory issues
    hostesses = Hostess.query.limit(100).all()
    return render_template(
        'developer/hostesses.html',
        hostesses=hostesses,
        title=_('إدارة المضيفات'))


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
        videos_dir = os.path.join(
            current_app.root_path,
            'static',
            'videos',
            'hostesses')
        os.makedirs(videos_dir, exist_ok=True)
        files = []
        for fn in os.listdir(videos_dir):
            ext = os.path.splitext(fn)[1].lower()
            if ext in ['.mp4', '.webm', '.gif']:
                files.append(fn)
        files.sort()
        form.video_choice.choices = [
            ('', _('بدون فيديو'))] + [(f, f) for f in files]
        if request.method == 'GET':
            form.video_choice.data = hostess.video or ''
    except Exception:
        form.video_choice.choices = [('', _('بدون فيديو'))]

    if form.validate_on_submit():
        prev_system_prompt = hostess.system_prompt if id else None
        prev_knowledge_base = hostess.knowledge_base if id else None
        prev_training_examples = hostess.training_examples if id else None
        form.populate_obj(hostess)
        if id:
            if 'system_prompt' not in request.form:
                hostess.system_prompt = prev_system_prompt
            if 'knowledge_base' not in request.form:
                hostess.knowledge_base = prev_knowledge_base
            if 'training_examples' not in request.form:
                hostess.training_examples = prev_training_examples

        # Handle Image
        if form.image.data:
            image_path = save_image(form.image.data, 'hostesses')
            if image_path:
                hostess.image = image_path

        # Handle Video
        if form.video.data:
            f = form.video.data
            filename = secure_filename(f.filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext in ['.mp4', '.webm', '.gif']:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                new_filename = f"{timestamp}_{os.urandom(8).hex()}{ext}"
                upload_path = os.path.join(
                    current_app.root_path, 'static', 'videos', 'hostesses')
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

    return render_template(
        'developer/edit_hostess.html',
        form=form,
        title=title,
        hostess=hostess)


@bp.route('/developer/hostess/delete/<int:id>', methods=['POST'])
@developer_required
def dev_hostess_delete(id):
    hostess = db.session.get(Hostess, id)
    if hostess:
        db.session.delete(hostess)
        db.session.commit()
        flash(_('تم حذف المضيفة'), 'success')
    return redirect(url_for('main.dev_hostesses'))


_HOSTESS_PROFILE_FOLDER_CACHE = {}
_HOSTESS_PROFILE_FOLDER_CACHE_BUILT = False


def _resolve_hostess_folder_by_profile(hostess_name: str):
    global _HOSTESS_PROFILE_FOLDER_CACHE_BUILT
    if not _HOSTESS_PROFILE_FOLDER_CACHE_BUILT:
        _HOSTESS_PROFILE_FOLDER_CACHE = {}
        try:
            root = os.path.join(
                current_app.root_path,
                'data',
                'training',
                'hostesses')
            for entry in os.listdir(root):
                if entry.startswith('role_') or entry.startswith('id_'):
                    continue
                folder = os.path.join(root, entry)
                if not os.path.isdir(folder):
                    continue
                profile_path = os.path.join(folder, 'profile.json')
                if not os.path.exists(profile_path):
                    continue
                try:
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    nm = (data.get('name') or '').strip()
                    if nm:
                        _HOSTESS_PROFILE_FOLDER_CACHE[nm] = entry
                except Exception:
                    continue
        except Exception:
            _HOSTESS_PROFILE_FOLDER_CACHE = {}
        _HOSTESS_PROFILE_FOLDER_CACHE_BUILT = True

    name_key = (hostess_name or '').strip()
    if not name_key:
        return None
    return _HOSTESS_PROFILE_FOLDER_CACHE.get(name_key)


def _build_hostess_role_pack(hostess: Hostess):
    role = (hostess.role or 'companion').lower()
    name = hostess.name or 'مضيفة'
    style = hostess.dialogue_style or 'friendly'

    name_map = {
        'ياسمين': 'jasmin',
        'سارة': 'sarah',
        'ليلى': 'layla',
        'روبي': 'ruby'
    }
    folder_name = name_map.get(hostess.name, None)
    profile_folder = _resolve_hostess_folder_by_profile(hostess.name)
    folder_candidates = []
    try:
        if getattr(hostess, 'id', None):
            folder_candidates.append(f"id_{int(hostess.id)}")
    except Exception:
        folder_candidates = []
    if profile_folder:
        folder_candidates.append(profile_folder)
    if folder_name:
        folder_candidates.append(folder_name)
    folder_candidates.append(f"role_{role}")

    prompt = ""
    examples = []

    # 1. Try to load system_prompt.txt from file
    system_prompt_loaded = False
    for cand in folder_candidates:
        prompt_path = os.path.join(
            current_app.root_path,
            'data',
            'training',
            'hostesses',
            cand,
            'system_prompt.txt')
        if not os.path.exists(prompt_path):
            continue
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
                system_prompt_loaded = True
                break
        except Exception as e:
            current_app.logger.error(
                f"Error loading system_prompt for {hostess.name}: {e}")

    # 2. If not loaded, generate default based on role
    if not system_prompt_loaded:
        if role == 'greeter':
            prompt = build_greeter_leader_prompt(hostess)
            examples = json.loads(build_greeter_leader_training_json(hostess))
        else:
            prompt = f"أنت {name}، مضيفة داخل لعبة GangsOfPalestine. "
            prompt += f"الدور: {role}. أسلوبك: {style}. "
            prompt += "\nالهدف: مساعدة اللاعب داخل اللعبة بشكل احترافي (خطوات واضحة، نصائح دقيقة، بدون حشو)."
            prompt += "\nلا تختلق معلومات أو أسعار/قوانين غير موجودة في المعرفة. إذا لم تعرف، قل ذلك وقدّم بدائل."
            prompt += "\nاحترم الخصوصية: لا تطلب بيانات حساسة."
            prompt += "\nممنوع محتوى إباحي/فاضح/تحريض/كراهية/تعليمات خطرة."
            prompt += "\nاستخدم ذاكرة اللاعب (إن وُجدت) لتخصيص الرد: اسمه/تفضيلاته/هدفه."

            if role == 'spy':
                prompt += "\nركز على: استخبارات سباقات، تجنب المخاطر، قراءة الخصوم، نصائح تكتيكية."
            elif role == 'luck':
                prompt += "\nركز على: الكازينو، إدارة المخاطر، اقتراح رهانات حسب المال، تنبيه من الإفراط."
            elif role == 'support':
                prompt += "\nركز على: دعم نفسي، نصائح علاج/طاقة، قرارات آمنة وقت الإصابة والخسارة."
            else:
                prompt += "\nركز على: مرافقة لطيفة داخل سياق اللعبة مع نصائح لعب مفيدة."

            if role == 'spy':
                examples = [
                    {"role": "user", "content": "بدّي أفوز بالسباق، شو أهم شي؟"},
                    {
                        "role": "assistant",
                        "content": (
                            "شوف سرعة السيارة ودفاعها أولاً، وخلي معك خطة للهروب إذا صار مطاردة. "
                            "لا تدخل سباق أعلى من تجهيزك."
                        )
                    },
                    {"role": "user", "content": "الخصم قوي… شو أعمل؟"},
                    {
                        "role": "assistant",
                        "content": (
                            "العب على الأمان: خفف المخاطرة، ركّز على ترقيات السيارة، "
                            "وحاول تجمع معلومات عن خصمك قبل المواجهة."
                        )
                    }
                ]
            elif role == 'luck':
                examples = [
                    {"role": "user", "content": "أراهن قدّيش؟"},
                    {
                        "role": "assistant",
                        "content": "خليك ذكي: راهن 5–10% من فلوسك كحد أقصى، ووقّف إذا خسرت مرتين ورا بعض."
                    },
                    {"role": "user", "content": "خسرت كثير…"},
                    {
                        "role": "assistant",
                        "content": (
                            "وقّف شوي وخليها إدارة مخاطر: ارجع للجرائم والمهام اليومية لتعويض، "
                            "وبعدين ارجع برهانات صغيرة."
                        )
                    }
                ]
            elif role == 'support':
                examples = [
                    {"role": "user", "content": "أنا تعبان وخسرت…"},
                    {
                        "role": "assistant",
                        "content": (
                            "سلامتك أولاً. إذا صحتك منخفضة روح المستشفى، وبعدها ارجع بخطة بسيطة: "
                            "مهام يومية + جيم + جرائم آمنة."
                        )
                    },
                    {"role": "user", "content": "كيف أرفع طاقتي بسرعة؟"},
                    {
                        "role": "assistant",
                        "content": (
                            "استخدم عناصر استرجاع الطاقة إذا موجودة، أو خذ استراحة تدريب/جيم حسب نظام اللعبة، "
                            "وخفف جرائم تستهلك طاقة عالية."
                        )
                    }
                ]
            else:
                examples = [
                    {"role": "user", "content": "بدّي نصيحة عامة"},
                    {
                        "role": "assistant",
                        "content": (
                            "خليك ثابت: ركز على مهام يومية + تطوير إحصائياتك، "
                            "وخلي مخزون عناصر للطوارئ قبل أي مخاطرة."
                        )
                    }
                ]

    # 2.5 Load training examples from file if present
    for cand in folder_candidates:
        ex_path = os.path.join(
            current_app.root_path,
            'data',
            'training',
            'hostesses',
            cand,
            'training_examples.json')
        if not os.path.exists(ex_path):
            continue
        try:
            with open(ex_path, 'r', encoding='utf-8') as f:
                ex_data = json.load(f)
            if isinstance(ex_data, list):
                examples = ex_data
                break
        except Exception as e:
            current_app.logger.error(
                f"Error loading training_examples for {hostess.name}: {e}")

    # 3. Inject Knowledge Base from File (Always check, even if prompt loaded
    # from file)
    for cand in folder_candidates:
        kb_path = os.path.join(
            current_app.root_path,
            'data',
            'training',
            'hostesses',
            cand,
            'knowledge_base.json')
        if not os.path.exists(kb_path):
            continue
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                kb_data = json.load(f)
                prompt += "\n\n# قاعدة المعرفة (Knowledge Base):\n"
                prompt += "استخدمي المعلومات التالية للإجابة على أسئلة اللاعب بدقة:\n"
                prompt += json.dumps(kb_data, ensure_ascii=False, indent=2)
                break
        except Exception as e:
            current_app.logger.error(
                f"Error loading knowledge base for {hostess.name}: {e}")

    return prompt, examples


def _hostess_chat_pairs(chats):
    pairs = []
    i = 0
    while i < len(chats) - 1:
        a = chats[i]
        b = chats[i + 1]
        if a.role == 'user' and b.role == 'assistant':
            pairs.append(
                SimpleNamespace(
                    user_id=a.user_id,
                    user_msg_id=a.id,
                    assistant_msg_id=b.id,
                    user_text=a.content,
                    assistant_text=b.content,
                    created_at=getattr(
                        b,
                        'created_at',
                        None) or getattr(
                        a,
                        'created_at',
                        None),
                ))
            i += 2
            continue
        i += 1
    return pairs


def _detect_lang_simple(text):
    t = text or ''
    for ch in t:
        if '\u0600' <= ch <= '\u06FF' or '\u0750' <= ch <= '\u077F' or '\u08A0' <= ch <= '\u08FF':
            return 'ar'
    return 'en'


def _norm_for_compare(text, language=None):
    s = (text or '').strip()
    s = ' '.join(s.split())
    if not s:
        return ''
    lang = language or _detect_lang_simple(s)
    if lang == 'ar':
        out = []
        diacritics = {
            '\u0610',
            '\u0611',
            '\u0612',
            '\u0613',
            '\u0614',
            '\u0615',
            '\u064B',
            '\u064C',
            '\u064D',
            '\u064E',
            '\u064F',
            '\u0650',
            '\u0651',
            '\u0652',
            '\u0653',
            '\u0654',
            '\u0655',
            '\u0670',
            '\u06D6',
            '\u06D7',
            '\u06D8',
            '\u06D9',
            '\u06DA',
            '\u06DB',
            '\u06DC',
            '\u06DF',
            '\u06E0',
            '\u06E1',
            '\u06E2',
            '\u06E3',
            '\u06E4',
            '\u06E7',
            '\u06E8',
            '\u06EA',
            '\u06EB',
            '\u06EC',
            '\u06ED',
        }
        for ch in s:
            if ch in diacritics:
                continue
            if ch == 'ـ':
                continue
            if ch in ('أ', 'إ', 'آ'):
                out.append('ا')
            elif ch == 'ة':
                out.append('ه')
            elif ch == 'ى':
                out.append('ي')
            else:
                out.append(ch)
        s = ''.join(out)
    else:
        s = s.lower()
    keep = []
    for ch in s:
        if ch.isalnum() or ch.isspace():
            keep.append(ch)
            continue
        if lang == 'ar' and ('\u0600' <= ch <= '\u06FF' or '\u0750' <=
                             ch <= '\u077F' or '\u08A0' <= ch <= '\u08FF'):
            keep.append(ch)
    return ' '.join(''.join(keep).split())


def _words_count(text):
    s = (text or '').strip()
    if not s:
        return 0
    return len([w for w in s.replace('،', ' ').replace(
        ',', ' ').split() if w.strip()])


def _is_low_quality_question(text, language):
    q = (text or '').strip()
    if len(q) < 6:
        return True
    if _words_count(q) < 2:
        return True
    nq = _norm_for_compare(q, language)
    if not nq:
        return True
    if language == 'ar':
        generic = {
            'مرحبا', 'اهلا', 'هلا', 'السلام عليكم', 'سلام عليكم', 'سلام',
            'كيفك', 'كيف حالك', 'كيف الحال', 'تمام', 'اوكي', 'شكرا', 'يسلمو',
        }
    else:
        generic = {
            'hi',
            'hello',
            'hey',
            'thanks',
            'ok',
            'okay',
            'good morning',
            'good evening',
            'how are you'}
    if nq in generic:
        return True
    return False


def _is_low_quality_answer(text, language):
    a = (text or '').strip()
    if len(a) < 20:
        return True
    if _words_count(a) < 4:
        return True
    na = _norm_for_compare(a, language)
    if not na:
        return True
    if language == 'ar':
        generic = {
            'ما بعرف', 'مش عارف', 'لا اعلم', 'لا اعرف', 'ما بعرفش',
            'تمام', 'اوكي', 'حسنا', 'طيب',
        }
    else:
        generic = {
            'i dont know',
            "i don't know",
            'not sure',
            'ok',
            'okay',
            'sure'}
    if na in generic:
        return True
    return False


def _clean_selected_pairs(pairs, mode, existing_question_keys=None, limit=30):
    existing_question_keys = existing_question_keys or set()
    kept = []
    seen_q = set()
    rejected = 0
    for q, ans, uid in pairs:
        q = (q or '').strip()
        ans = (ans or '').strip()
        lang = _detect_lang_simple(q + ' ' + ans)
        if _is_low_quality_question(
                q,
                lang) or _is_low_quality_answer(
                ans,
                lang):
            rejected += 1
            continue
        q_key = _norm_for_compare(q, lang)
        if not q_key:
            rejected += 1
            continue
        if q_key in existing_question_keys or q_key in seen_q:
            rejected += 1
            continue
        if _norm_for_compare(ans, lang) == q_key:
            rejected += 1
            continue
        kept.append((q, ans, uid, lang, q_key))
        seen_q.add(q_key)
        if len(kept) >= int(max(1, limit)):
            break
    return kept, rejected


def _keywords_from_question(q, language):
    raw = (
        q or '').replace(
        '?',
        ' ').replace(
            '!',
            ' ').replace(
                '.',
                ' ').replace(
                    ',',
                    ' ').replace(
                        '،',
        ' ')
    words = [w.strip() for w in raw.split() if w.strip()]
    if language == 'ar':
        stop = {
            'كيف',
            'شو',
            'ايش',
            'ليش',
            'متى',
            'وين',
            'أين',
            'ما',
            'ماذا',
            'هل',
            'انا',
            'انت',
            'انتي',
            'هو',
            'هي',
            'نحن',
            'هم',
            'عن',
            'في',
            'على',
            'من',
            'الى',
            'إلى',
            'مع',
            'هذا',
            'هذه',
            'ذلك',
            'تلك',
            'بدّي',
            'بدي',
            'بدك',
            'بده',
            'بديش'}
    else:
        stop = {
            'the',
            'is',
            'are',
            'was',
            'were',
            'what',
            'where',
            'when',
            'how',
            'who',
            'why',
            'can',
            'could',
            'should',
            'would',
            'do',
            'does',
            'did',
            'have',
            'has',
            'had',
            'to',
            'in',
            'on',
            'at',
            'of',
            'for',
            'with',
            'by',
            'from',
            'about',
            'this',
            'that',
            'these',
            'those',
            'it',
            'its',
            'my',
            'your',
            'his',
            'her',
            'their',
            'our'}
    out = []
    for w in words:
        wl = w.lower()
        if wl in stop:
            continue
        if len(wl) < 2:
            continue
        if wl not in out:
            out.append(wl)
        if len(out) >= 10:
            break
    return ','.join(out)


@bp.route('/developer/hostess/trainer/<int:id>', methods=['GET'])
@developer_required
def dev_hostess_trainer(id):
    hostess = db.session.get(Hostess, id)
    if not hostess:
        abort(404)

    memories = HostessMemory.query.filter_by(
        hostess_id=hostess.id).order_by(
        HostessMemory.updated_at.desc()).limit(30).all()
    chats = HostessChatMessage.query.filter_by(
        hostess_id=hostess.id).order_by(
        HostessChatMessage.id.desc()).limit(60).all()
    chats.reverse()
    pairs = _hostess_chat_pairs(chats)

    return render_template(
        'developer/hostess_trainer.html',
        hostess=hostess,
        memories=memories,
        chats=chats,
        pairs=pairs,
        title=_('تدريب المضيفة')
    )


@bp.route('/developer/hostess/trainer/<int:id>', methods=['POST'])
@developer_required
@double_verification_required
def dev_hostess_trainer_post(id):
    hostess = db.session.get(Hostess, id)
    if not hostess:
        abort(404)

    action = request.form.get('action') or 'save'

    if action == 'train':
        prompt, examples = _build_hostess_role_pack(hostess)
        hostess.system_prompt = prompt
        hostess.training_examples = json.dumps(examples, ensure_ascii=False)
        hostess.last_trained_at = datetime.now(
            timezone.utc).replace(tzinfo=None)
        db.session.commit()
        flash(_('تم تدريب المضيفة وحفظ الحزمة بنجاح'), 'success')
        return redirect(url_for('main.dev_hostess_trainer', id=id))

    if action == 'clear_memory':
        HostessMemory.query.filter_by(hostess_id=hostess.id).delete()
        db.session.commit()
        flash(_('تم مسح ذاكرة المضيفة'), 'success')
        return redirect(url_for('main.dev_hostess_trainer', id=id))

    if action == 'delete_memory':
        mid = request.form.get('memory_id', type=int)
        mem = db.session.get(HostessMemory, mid) if mid else None
        if mem and mem.hostess_id == hostess.id:
            db.session.delete(mem)
            db.session.commit()
            flash(_('تم حذف عنصر الذاكرة'), 'success')
        return redirect(url_for('main.dev_hostess_trainer', id=id))

    if action in ('learn_examples', 'learn_knowledge'):
        picked = request.form.getlist('pair')
        if not picked:
            flash(_('لم يتم اختيار أي محادثة.'), 'warning')
            return redirect(url_for('main.dev_hostess_trainer', id=id))

        ids = set()
        for token in picked:
            try:
                u_id, a_id = token.split(':', 1)
                ids.add(int(u_id))
                ids.add(int(a_id))
            except Exception:
                continue

        msgs = HostessChatMessage.query.filter(
            HostessChatMessage.hostess_id == hostess.id,
            HostessChatMessage.id.in_(list(ids))
        ).all()
        by_id = {m.id: m for m in msgs}

        pairs = []
        for token in picked:
            try:
                u_id, a_id = token.split(':', 1)
                u_id = int(u_id)
                a_id = int(a_id)
            except Exception:
                continue
            u = by_id.get(u_id)
            a = by_id.get(a_id)
            if not u or not a:
                continue
            if u.role != 'user' or a.role != 'assistant':
                continue
            pairs.append((u.content or '', a.content or '', u.user_id))

        if not pairs:
            flash(_('لم يتم العثور على أزواج صالحة.'), 'warning')
            return redirect(url_for('main.dev_hostess_trainer', id=id))

        if action == 'learn_examples':
            try:
                existing = json.loads(
                    hostess.training_examples) if hostess.training_examples else []
            except Exception:
                existing = []
            if not isinstance(existing, list):
                existing = []

            existing_q_keys = set()
            for m in existing:
                if not isinstance(m, dict):
                    continue
                if m.get('role') != 'user':
                    continue
                existing_q_keys.add(
                    _norm_for_compare(
                        m.get('content') or '',
                        _detect_lang_simple(
                            m.get('content') or '')))

            cleaned, rejected = _clean_selected_pairs(
                pairs, mode='examples', existing_question_keys=existing_q_keys, limit=20)
            added = 0
            for q, ans, _uid, _lang, _q_key in cleaned:
                existing.append({'role': 'user', 'content': q})
                existing.append({'role': 'assistant', 'content': ans})
                added += 1

            hostess.training_examples = json.dumps(
                existing, ensure_ascii=False)
            hostess.last_trained_at = datetime.now(
                timezone.utc).replace(tzinfo=None)
            db.session.commit()
            flash(_('تمت إضافة %(n)s مثال تدريب بعد التنظيف. تم تجاهل %(m)s.',
                  n=added, m=rejected), 'success')
            return redirect(url_for('main.dev_hostess_trainer', id=id))

        existing_q_keys = set()
        for row in HostessKnowledge.query.filter(
                HostessKnowledge.hostess_id == hostess.id).order_by(
                HostessKnowledge.id.desc()).limit(1200).all():
            existing_q_keys.add(
                _norm_for_compare(
                    row.question or '',
                    _detect_lang_simple(
                        row.question or '')))

        cleaned, rejected = _clean_selected_pairs(
            pairs, mode='knowledge', existing_question_keys=existing_q_keys, limit=30)
        added = 0
        for q, ans, _uid, lang, _q_key in cleaned:
            keywords = _keywords_from_question(q, lang)
            db.session.add(
                HostessKnowledge(
                    hostess_id=hostess.id,
                    question=q,
                    answer=ans,
                    category='trainer',
                    keywords=keywords,
                    language=lang))
            added += 1

        db.session.commit()
        flash(_('تمت إضافة %(n)s عنصر معرفة بعد التنظيف. تم تجاهل %(m)s.',
              n=added, m=rejected), 'success')
        return redirect(url_for('main.dev_hostess_trainer', id=id))

    hostess.system_prompt = request.form.get(
        'system_prompt') or hostess.system_prompt
    hostess.knowledge_base = request.form.get(
        'knowledge_base') or hostess.knowledge_base
    raw_examples = request.form.get('training_examples')
    if raw_examples:
        try:
            ex = json.loads(raw_examples)
        except Exception:
            ex = None
        if isinstance(ex, list):
            cleaned_msgs = []
            seen_q = set()
            i = 0
            while i < len(ex) - 1:
                u = ex[i]
                a = ex[i + 1]
                if not (isinstance(u, dict) and isinstance(a, dict)):
                    i += 1
                    continue
                if u.get('role') != 'user' or a.get('role') != 'assistant':
                    i += 1
                    continue
                q = (u.get('content') or '').strip()
                ans = (a.get('content') or '').strip()
                lang = _detect_lang_simple(q + ' ' + ans)
                if _is_low_quality_question(
                        q,
                        lang) or _is_low_quality_answer(
                        ans,
                        lang):
                    i += 2
                    continue
                q_key = _norm_for_compare(q, lang)
                if not q_key or q_key in seen_q:
                    i += 2
                    continue
                cleaned_msgs.append({'role': 'user', 'content': q})
                cleaned_msgs.append({'role': 'assistant', 'content': ans})
                seen_q.add(q_key)
                i += 2
            hostess.training_examples = json.dumps(
                cleaned_msgs, ensure_ascii=False)
        else:
            hostess.training_examples = raw_examples
    elif hostess.training_examples:
        hostess.training_examples = hostess.training_examples
    hostess.self_learning_enabled = 'self_learning_enabled' in request.form
    hostess.memory_enabled = 'memory_enabled' in request.form
    db.session.commit()
    flash(_('تم حفظ إعدادات التدريب'), 'success')
    return redirect(url_for('main.dev_hostess_trainer', id=id))


@bp.route('/developer/scenarios')
@developer_required
def dev_scenarios():
    scenarios = VideoScenario.query.all()
    hostesses = Hostess.query.all()
    return render_template(
        'developer/scenarios.html',
        scenarios=scenarios,
        hostesses=hostesses,
        title=_('مكتبة السيناريوهات'))


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
        if not scenario:
            abort(404)
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

    return render_template(
        'developer/edit_scenario.html',
        form=form,
        title=title)


@bp.route('/developer/scenario/delete/<int:id>', methods=['POST'])
@developer_required
def dev_scenario_delete(id):
    s = db.session.get(VideoScenario, id)
    if s:
        db.session.delete(s)
        db.session.commit()
        flash(_('تم حذف السيناريو'), 'success')
    return redirect(url_for('main.dev_scenarios'))


@bp.route('/developer/scenario/apply/<int:scenario_id>/<int:hostess_id>',
          methods=['POST'])
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
    settings = SystemConfig.query.order_by(
        SystemConfig.key.asc()).limit(200).all()
    return render_template(
        'developer/settings.html',
        settings=settings,
        title=_('إعدادات النظام'))


@bp.route('/developer/settings/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/settings/new', methods=['GET', 'POST'])
@developer_required
@double_verification_required
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
        if request.args.get('key'):
            setting.key = request.args.get('key')
        if request.args.get('description'):
            setting.description = request.args.get('description')

    form = SystemConfigForm(obj=setting)
    if form.validate_on_submit():
        # Log changes
        old_val = setting.value
        form.populate_obj(setting)
        new_val = setting.value

        if setting.id and old_val != new_val:
            db.session.add(ConfigLog(
                admin_id=current_user.id,
                key=setting.key,
                old_value=str(old_val) if old_val else None,
                new_value=str(new_val) if new_val else None,
                reason="Manual Edit"
            ))
        elif not setting.id:
            db.session.add(ConfigLog(
                admin_id=current_user.id,
                key=setting.key,
                old_value=None,
                new_value=str(new_val) if new_val else None,
                reason="New Config"
            ))

        db.session.add(setting)
        db.session.commit()
        flash(_('تم حفظ الإعداد'), 'success')
        return redirect(url_for('main.dev_settings'))

    return render_template(
        'developer/edit_setting.html',
        form=form,
        title=title)


@bp.route('/developer/settings/delete/<int:id>', methods=['POST'])
@developer_required
@double_verification_required
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

    messages = query.order_by(
        Message.timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template(
        'developer/messages.html',
        messages=messages,
        title=_('رسائل النظام'))


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
    return render_template(
        'developer/items.html',
        items=items,
        title=_('إدارة الأغراض'))


@bp.route('/developer/item/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/item/new', methods=['GET', 'POST'])
@developer_required
def dev_item_edit(id=None):
    if id:
        item = db.session.get(Item, id)
        if not item:
            abort(404)
        title = _('تعديل غرض')
    else:
        item = Item()
        title = _('إضافة غرض')

    form = ItemForm(obj=item)
    if form.validate_on_submit():
        form.populate_obj(item)
        image_path = save_image(form.image.data, 'items')
        if image_path:
            item.image = image_path

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
    vehicles = Vehicle.query.order_by(Vehicle.price.asc()).limit(500).all()
    return render_template(
        'developer/vehicles.html',
        vehicles=vehicles,
        title=_('إدارة المركبات'))


@bp.route('/developer/vehicle/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/vehicle/new', methods=['GET', 'POST'])
@developer_required
def dev_vehicle_edit(id=None):
    if id:
        vehicle = db.session.get(Vehicle, id)
        if not vehicle:
            abort(404)
        title = _('تعديل مركبة')
    else:
        vehicle = Vehicle()
        title = _('إضافة مركبة')

    # Get list of existing vehicle images
    vehicles_dir = os.path.join(
        current_app.root_path,
        'static',
        'images',
        'vehicles')
    existing_images = []
    if os.path.exists(vehicles_dir):
        existing_images = sorted([f for f in os.listdir(
            vehicles_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))])

    form = VehicleForm(obj=vehicle)
    if form.validate_on_submit():
        form.populate_obj(vehicle)
        image_path = save_image(form.image.data, 'vehicles')
        if image_path:
            vehicle.image = image_path
        else:
            # Handle selected image from existing files only if no new upload
            selected_image = request.form.get('selected_image')
            if selected_image and selected_image in existing_images:
                vehicle.image = f"vehicles/{selected_image}"

        db.session.add(vehicle)
        db.session.commit()
        flash(_('تم حفظ المركبة'), 'success')
        return redirect(url_for('main.dev_vehicles'))

    return render_template(
        'developer/edit_vehicle.html',
        form=form,
        title=title,
        existing_images=existing_images,
        vehicle=vehicle)


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
    assets = Asset.query.order_by(Asset.value.asc()).limit(500).all()
    return render_template(
        'developer/assets.html',
        assets=assets,
        title=_('إدارة العقارات'))


@bp.route('/developer/asset/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/asset/new', methods=['GET', 'POST'])
@developer_required
def dev_asset_edit(id=None):
    if id:
        asset = db.session.get(Asset, id)
        if not asset:
            abort(404)
        title = _('تعديل عقار')
    else:
        asset = Asset()
        title = _('إضافة عقار')

    form = AssetForm(obj=asset)
    if form.validate_on_submit():
        form.populate_obj(asset)
        image_path = save_image(form.image.data, 'assets')
        if image_path:
            asset.image = image_path

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
    locations = Location.query.order_by(Location.cost.asc()).limit(200).all()
    return render_template(
        'developer/locations.html',
        locations=locations,
        title=_('إدارة المواقع'))


@bp.route('/developer/location/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/location/new', methods=['GET', 'POST'])
@developer_required
def dev_location_edit(id=None):
    if id:
        location = db.session.get(Location, id)
        if not location:
            abort(404)
        title = _('تعديل موقع')
    else:
        location = Location()
        title = _('إضافة موقع')

    form = LocationForm(obj=location)
    if form.validate_on_submit():
        form.populate_obj(location)
        image_path = save_image(form.image.data, 'locations')
        if image_path:
            location.image = image_path

        db.session.add(location)
        db.session.commit()
        flash(_('تم حفظ الموقع'), 'success')
        return redirect(url_for('main.dev_locations'))

    return render_template(
        'developer/edit_location.html',
        form=form,
        title=title)


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
    crimes = Crime.query.order_by(Crime.min_level.asc()).limit(500).all()
    return render_template(
        'developer/crimes.html',
        crimes=crimes,
        title=_('إدارة الجرائم'))


@bp.route('/developer/crime/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/crime/new', methods=['GET', 'POST'])
@developer_required
def dev_crime_edit(id=None):
    if id:
        crime = db.session.get(Crime, id)
        if not crime:
            abort(404)
        title = _('تعديل جريمة')
    else:
        crime = Crime()
        title = _('إضافة جريمة')

    form = CrimeForm(obj=crime)
    # Populate reward items
    items = Item.query.all()
    form.reward_item_id.choices = [
        (0, _('لا يوجد'))] + [(i.id, i.name) for i in items]

    if form.validate_on_submit():
        form.populate_obj(crime)
        image_path = save_image(form.image.data, 'crimes')
        if image_path:
            crime.image = image_path

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
    crimes = OrganizedCrime.query.order_by(
        OrganizedCrime.min_gang_level.asc()).all()
    reqs_map = {}
    for crime in crimes:
        try:
            reqs_map[crime.id] = json.loads(
                crime.requirements) if crime.requirements else {}
        except BaseException:
            reqs_map[crime.id] = {}
    return render_template(
        'developer/organized_crimes.html',
        crimes=crimes,
        reqs_map=reqs_map,
        title="Organized Crimes")


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
            reqs['role_bonuses'] = json.loads(
                role_bonuses_json) if role_bonuses_json.strip() else {}
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
    return render_template(
        'developer/tasks.html',
        tasks=tasks,
        title=_('المهام اليومية'))


@bp.route('/developer/task/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/task/new', methods=['GET', 'POST'])
@developer_required
def dev_task_edit(id=None):
    if id:
        task = db.session.get(DailyTask, id)
        if not task:
            abort(404)
        title = _('تعديل مهمة')
    else:
        task = DailyTask()
        title = _('إضافة مهمة')

    form = TaskForm(obj=task)
    if form.validate_on_submit():
        form.populate_obj(task)
        image_path = save_image(form.image.data, 'tasks')
        if image_path:
            task.image = image_path

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
    announcements = Announcement.query.order_by(
        Announcement.created_at.desc()).all()
    return render_template(
        'developer/announcements.html',
        announcements=announcements,
        title=_('إدارة الإعلانات'))


@bp.route('/developer/announcement/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/announcement/new', methods=['GET', 'POST'])
@developer_required
def dev_announcement_edit(id=None):
    if id:
        announcement = db.session.get(Announcement, id)
        if not announcement:
            abort(404)
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

    return render_template(
        'developer/edit_announcement.html',
        form=form,
        title=title)


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
    return render_template(
        'developer/forum/index.html',
        categories=categories,
        title=_('إدارة المنتدى'))


@bp.route('/developer/forum/category/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/forum/category/new', methods=['GET', 'POST'])
@developer_required
def dev_forum_category_edit(id=None):
    if id:
        category = db.session.get(ForumCategory, id)
        if not category:
            abort(404)
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

    return render_template(
        'developer/forum/category_form.html',
        form=form,
        title=title)


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


@bp.route('/developer/forum/category/edit_alias/<int:id>',
          methods=['GET', 'POST'])
@developer_required
def edit_forum_category(id):
    return dev_forum_category_edit(id=id)


@bp.route('/developer/forum/category/delete_alias/<int:id>', methods=['POST'])
@developer_required
def delete_forum_category(id):
    return dev_forum_category_delete(id=id)


@bp.route('/developer/config', methods=['GET'])
@developer_required
def dev_config():
    q = (request.args.get('q') or '').strip()
    query = SystemConfig.query
    if q:
        query = query.filter(or_(
            SystemConfig.key.ilike(f'%{q}%'),
            SystemConfig.description.ilike(f'%{q}%')
        ))
    configs = query.order_by(SystemConfig.key.asc()).all()
    return render_template(
        'developer/config.html',
        configs=configs,
        q=q,
        title=_('إعدادات النظام'))


@bp.route('/developer/config/save', methods=['POST'])
@developer_required
@double_verification_required
def dev_config_save():
    changed = 0
    for key in request.form.keys():
        if key == 'csrf_token':
            continue
        vals = request.form.getlist(key)
        if not vals:
            continue
        final_val = vals[-1]
        if len(vals) > 1 and 'true' in vals:
            final_val = 'true'

        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            continue

        old_val = config.value
        if str(old_val) == str(final_val):
            continue

        config.value = str(final_val)
        db.session.add(ConfigLog(
            admin_id=current_user.id,
            key=key,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(final_val) if final_val is not None else None,
            reason="Bulk Edit"
        ))
        changed += 1

    db.session.commit()
    flash(_('تم حفظ %(n)s تعديل في الإعدادات.', n=changed), 'success')
    return redirect(url_for('main.dev_config'))


# --- Gangs ---
@bp.route('/developer/gangs')
@developer_required
def dev_gangs():
    gangs = Gang.query.order_by(Gang.level.desc()).all()
    return render_template(
        'developer/gangs.html',
        gangs=gangs,
        title=_('إدارة العصابات'))


@bp.route('/developer/gang/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/developer/gang/new', methods=['GET', 'POST'])
@developer_required
def dev_gang_edit(id=None):
    active_wars = []
    active_alliances = []

    if id:
        gang = db.session.get(Gang, id)
        if not gang:
            abort(404)
        title = _('تعديل عصابة')

        active_wars = GangWar.query.filter(
            or_(GangWar.gang1_id == gang.id, GangWar.gang2_id == gang.id),
            GangWar.status == 'active'
        ).all()

        active_alliances = GangAlliance.query.filter(
            or_(GangAlliance.gang1_id == gang.id, GangAlliance.gang2_id == gang.id),
            GangAlliance.status == 'active'
        ).all()
    else:
        gang = Gang()
        title = _('إضافة عصابة')

    form = GangForm(obj=gang)
    if form.validate_on_submit():
        # Validate leader exists
        leader = db.session.get(User, form.leader_id.data)
        if not leader:
            flash(_('المستخدم القائد غير موجود.'), 'danger')
            return render_template(
                'developer/edit_gang.html',
                form=form,
                title=title,
                active_wars=active_wars,
                active_alliances=active_alliances,
                gang=gang)

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

    return render_template(
        'developer/edit_gang.html',
        form=form,
        title=title,
        active_wars=active_wars,
        active_alliances=active_alliances,
        gang=gang)


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


@bp.route('/developer/gang/war/end/<int:war_id>', methods=['POST'])
@developer_required
def dev_gang_war_end(war_id):
    war = db.session.get(GangWar, war_id)
    if war:
        war.status = 'ended'
        war.end_time = datetime.now(timezone.utc)
        db.session.commit()
        flash(_('تم إنهاء الحرب قسرياً'), 'success')
    return redirect(request.referrer or url_for('main.dev_gangs'))


@bp.route('/developer/gang/alliance/break/<int:alliance_id>', methods=['POST'])
@developer_required
def dev_gang_alliance_break(alliance_id):
    alliance = db.session.get(GangAlliance, alliance_id)
    if alliance:
        db.session.delete(alliance)
        db.session.commit()
        flash(_('تم فسخ التحالف قسرياً'), 'success')
    return redirect(request.referrer or url_for('main.dev_gangs'))


# --- Hostess Knowledge ---
@bp.route('/developer/knowledge')
@developer_required
def dev_knowledge():
    page = request.args.get('page', 1, type=int)
    query = HostessKnowledge.query.order_by(HostessKnowledge.id.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    return render_template(
        'developer/knowledge.html',
        knowledge=pagination.items,
        pagination=pagination,
        title=_('قاعدة معرفة المضيفات'))


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
    form.hostess_id.choices = [
        (0, _('عام (لكل المضيفات)'))] + [(h.id, h.name) for h in hostesses]

    if form.validate_on_submit():
        form.populate_obj(knowledge)
        if form.hostess_id.data == 0:
            knowledge.hostess_id = None

        db.session.add(knowledge)
        db.session.commit()
        flash(_('تم حفظ المعرفة'), 'success')
        return redirect(url_for('main.dev_knowledge'))

    return render_template(
        'developer/edit_knowledge.html',
        form=form,
        title=title)


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
    return render_template(
        'developer/bounties.html',
        bounties=bounties,
        title=_('إدارة المكافآت (Bounties)'))


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
@double_verification_required
def dev_config_add():
    key = (request.form.get('key') or '').strip()
    value = (request.form.get('value') or '').strip()
    if not key:
        flash(_('المفتاح مطلوب.'), 'danger')
        return redirect(url_for('main.dev_config'))
    existing = SystemConfig.query.filter_by(key=key).first()
    if existing:
        old_val = existing.value
        existing.value = value
        if str(old_val) != str(value):
            db.session.add(ConfigLog(
                admin_id=current_user.id,
                key=key,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(value) if value is not None else None,
                reason="Manual Edit"
            ))
    else:
        db.session.add(SystemConfig(key=key, value=value))
        db.session.add(ConfigLog(
            admin_id=current_user.id,
            key=key,
            old_value=None,
            new_value=str(value) if value is not None else None,
            reason="New Config"
        ))
    db.session.commit()
    flash(_('تم حفظ الإعداد'), 'success')
    return redirect(url_for('main.dev_config'))


@bp.route('/developer/config/reset_market_defaults', methods=['POST'])
@developer_required
@double_verification_required
def dev_config_reset_market_defaults():
    defaults = {
        'market_enable_spot': 'true',
        'market_enable_futures': 'true',
        'market_enable_limit_orders': 'true',
        'market_spot_min_buy_usd': '10',
        'market_futures_leverages': '1,5,10,20,50,100',
        'market_update_interval_seconds': '60',
        'market_intel_cost': '500',
        'market_volatility_multiplier': '1.0',
    }
    for key, value in defaults.items():
        config = SystemConfig.query.filter_by(key=key).first()
        old_val = None
        if not config:
            config = SystemConfig(key=key)
            db.session.add(config)
        else:
            old_val = config.value

        if old_val != value:
            config.value = value
            db.session.add(ConfigLog(
                admin_id=current_user.id,
                key=key,
                old_value=str(old_val) if old_val else None,
                new_value=str(value),
                reason="Reset Market Defaults"
            ))
    db.session.commit()
    flash(_('تمت إعادة إعدادات السوق الافتراضية.'), 'success')
    return redirect(url_for('main.dev_config'))


@bp.route('/developer/config/reset_gameplay_defaults', methods=['POST'])
@developer_required
@double_verification_required
def dev_config_reset_gameplay_defaults():
    defaults = {
        'crime_base_success_chance': '60',
        'crime_level_money_multiplier': '0.02',
        'crime_heat_gain_base': '2',
        'crime_global_cooldown_seconds': '20',
        'crime_global_cooldown_max_seconds': '240',
        'heat_success_penalty_per_point': '0.15'
    }
    for key, value in defaults.items():
        config = SystemConfig.query.filter_by(key=key).first()
        old_val = None
        if not config:
            config = SystemConfig(key=key)
            db.session.add(config)
        else:
            old_val = config.value

        if old_val != value:
            config.value = value
            db.session.add(ConfigLog(
                admin_id=current_user.id,
                key=key,
                old_value=str(old_val) if old_val else None,
                new_value=str(value),
                reason="Reset Gameplay Defaults"
            ))

    db.session.commit()
    flash(_('تمت إعادة إعدادات اللعب الافتراضية.'), 'success')
    return redirect(url_for('main.dev_config'))


@bp.route('/developer/config/reset_jail_defaults', methods=['POST'])
@developer_required
@double_verification_required
def dev_config_reset_jail_defaults():
    defaults = {
        'jail_enable_daily_event': 'true',
        'jail_enable_document_report': 'true',
        'jail_document_report_energy_cost': '5',
        'jail_document_report_cooldown_hours': '3',
        'jail_document_report_success_chance': '0.35',
        'jail_document_report_reduction_min': '3',
        'jail_document_report_reduction_max': '8',
        'jail_document_report_exp_reward': '40',
        'jail_enable_family_visit': 'true',
        'jail_family_visit_cooldown_hours': '12',
        'jail_family_visit_approve_chance': '0.45',
        'jail_family_visit_reduction_min': '6',
        'jail_family_visit_reduction_max': '14',
        'jail_family_visit_exp_reward': '20',
        'jail_enable_self_escape': 'true',
        'jail_self_escape_daily_limit': '3',
        'jail_self_escape_energy_cost': '30',
        'jail_self_escape_money_cost': '5000',
        'jail_self_escape_success_chance': '0.12',
        'jail_self_escape_penalty_min': '15',
        'jail_self_escape_penalty_max': '35',
        'jail_self_escape_injury_pct': '0.05',
        'jail_self_escape_exp_reward': '60',
        'jail_enable_gilboa_escape': 'true',
        'jail_gilboa_daily_limit': '2',
        'jail_gilboa_cooldown_hours': '6',
        'jail_gilboa_energy_cost': '45',
        'jail_gilboa_diamond_cost': '8',
        'jail_gilboa_success_chance': '0.35',
        'jail_gilboa_penalty_min': '25',
        'jail_gilboa_penalty_max': '55',
        'jail_gilboa_injury_pct': '0.10',
        'jail_gilboa_exp_reward': '180',
        'jail_enable_self_bail_diamonds': 'true',
        'jail_self_bail_cost_diamonds': '15',
        'jail_self_bail_cooldown_hours': '12',
    }
    for key, value in defaults.items():
        config = SystemConfig.query.filter_by(key=key).first()
        old_val = None
        if not config:
            config = SystemConfig(key=key)
            db.session.add(config)
        else:
            old_val = config.value

        if old_val != value:
            config.value = value
            db.session.add(ConfigLog(
                admin_id=current_user.id,
                key=key,
                old_value=str(old_val) if old_val else None,
                new_value=str(value),
                reason="Reset Jail Defaults"
            ))
    db.session.commit()
    flash(_('تمت إعادة إعدادات السجن الافتراضية.'), 'success')
    return redirect(url_for('main.dev_config'))


@bp.route('/developer/config/reset_gym_defaults', methods=['POST'])
@developer_required
@double_verification_required
def dev_config_reset_gym_defaults():
    defaults = {
        'gym_energy_cost_default': '5',
        'gym_energy_cost_intelligence': '10',
        'gym_money_base_cost': '100',
        'gym_money_per_level': '10',
        'gym_money_per_stat': '2',
        'gym_money_round_step': '50',
        'gym_gain_basic': '1',
        'gym_exp_basic': '2',
        'gym_duration_basic_seconds': '1800',
        'gym_money_factor_basic': '1.0',
        'gym_diamonds_basic': '0',
        'gym_gain_advanced': '2',
        'gym_exp_advanced': '6',
        'gym_duration_advanced_seconds': '2700',
        'gym_money_factor_advanced': '2.5',
        'gym_diamonds_advanced': '0',
        'gym_gain_elite': '3',
        'gym_exp_elite': '14',
        'gym_duration_elite_seconds': '3600',
        'gym_money_factor_elite': '4.5',
        'gym_diamonds_elite': '2',
        'gym_daily_sessions_limit': '100',
        'gym_injury_chance_percent': '2',
        'gym_injury_hospital_seconds': '120',
        'gym_enable_speedup': 'true',
        'gym_speedup_daily_limit': '50',
        'gym_speedup_per_min_money': '120',
        'gym_speedup_finish_diamonds': '5',
        'gym_speedup_options_minutes': '15,60',
    }
    for key, value in defaults.items():
        config = SystemConfig.query.filter_by(key=key).first()
        old_val = None
        if not config:
            config = SystemConfig(key=key)
            db.session.add(config)
        else:
            old_val = config.value

        if old_val != value:
            config.value = value
            db.session.add(ConfigLog(
                admin_id=current_user.id,
                key=key,
                old_value=str(old_val) if old_val else None,
                new_value=str(value),
                reason="Reset Gym Defaults"
            ))
    db.session.commit()
    flash(_('تمت إعادة إعدادات الجيم الافتراضية.'), 'success')
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
        query = query.join(
            User,
            GameLog.admin_id == User.id).filter(
            User.username.ilike(
                f'%{admin_username}%'))
    if search:
        query = query.filter(GameLog.details.ilike(f'%{search}%'))

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    actions = [
        row[0] for row in db.session.query(
            GameLog.action).distinct().order_by(
            GameLog.action.asc()).all()]
    current_filters = SimpleNamespace(
        action=action,
        admin_username=admin_username,
        search=search)

    return render_template(
        'developer/logs.html',
        logs=pagination.items,
        pagination=pagination,
        actions=actions,
        current_filters=current_filters,
        title=_('سجلات النظام'),
    )


@bp.route('/developer/user_logs')
@developer_required
def dev_user_logs():
    page = request.args.get('page', 1, type=int)
    action = request.args.get('action', '').strip()
    username = request.args.get('username', '').strip()
    ip_address = request.args.get('ip', '').strip()

    query = UserLog.query.order_by(UserLog.timestamp.desc())
    if action:
        query = query.filter(UserLog.action == action)
    if username:
        query = query.join(
            User,
            UserLog.user_id == User.id).filter(
            User.username.ilike(
                f'%{username}%'))
    if ip_address:
        query = query.filter(UserLog.ip_address.ilike(f'%{ip_address}%'))

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    actions = [
        row[0] for row in db.session.query(
            UserLog.action).distinct().order_by(
            UserLog.action.asc()).all()]

    current_filters = SimpleNamespace(
        action=action,
        username=username,
        ip_address=ip_address)

    return render_template(
        'developer/user_logs.html',
        logs=pagination.items,
        pagination=pagination,
        actions=actions,
        current_filters=current_filters,
        title=_('سجلات المستخدمين'),
    )


@bp.route('/developer/config_logs')
@developer_required
def dev_config_logs():
    page = request.args.get('page', 1, type=int)
    key = request.args.get('key', '').strip()
    admin_username = request.args.get('admin_username', '').strip()
    reason = request.args.get('reason', '').strip()

    query = ConfigLog.query.order_by(ConfigLog.timestamp.desc())
    if key:
        query = query.filter(ConfigLog.key.ilike(f'%{key}%'))
    if reason:
        query = query.filter(ConfigLog.reason == reason)
    if admin_username:
        query = query.join(
            User,
            ConfigLog.admin_id == User.id).filter(
            User.username.ilike(
                f'%{admin_username}%'))

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    reasons = [
        r[0] for r in db.session.query(
            ConfigLog.reason).distinct().order_by(
            ConfigLog.reason.asc()).all() if r and r[0]]
    current_filters = SimpleNamespace(
        key=key, admin_username=admin_username, reason=reason)

    return render_template(
        'developer/config_logs.html',
        logs=pagination.items,
        pagination=pagination,
        reasons=reasons,
        current_filters=current_filters,
        title=_('سجل تغييرات الإعدادات'),
    )


@bp.route('/developer/heist_history')
@developer_required
def dev_heist_history():
    page = request.args.get('page', 1, type=int)
    pagination = HeistHistory.query.order_by(
        HeistHistory.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False)
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
    return render_template(
        'developer/heist_history.html',
        heists=heists,
        pagination=pagination,
        title=_('سجل الجرائم المنظمة'))


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

    return render_template(
        'developer/edit_organized_crime.html',
        form=form,
        title=title)


@bp.route('/developer/lobbies')
@developer_required
def dev_active_lobbies():
    lobbies = CrimeLobby.query.order_by(
        CrimeLobby.created_at.desc()).limit(100).all()
    return render_template(
        'developer/active_lobbies.html',
        lobbies=lobbies,
        title=_('المجموعات النشطة'))

# --- Factories ---


@bp.route('/developer/factories')
@developer_required
def dev_factories():
    jobs = FactoryJob.query.order_by(
        FactoryJob.started_at.desc()).limit(50).all()
    return render_template(
        'developer/factories.html',
        jobs=jobs,
        title=_('إدارة المصانع'))


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
        if not job:
            abort(404)
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

    return render_template(
        'developer/edit_factory_job.html',
        form=form,
        title=title)


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
    cfg = MarketSimulationService.get_asset_config()
    cfg_symbols = list(cfg.keys())

    if cfg_symbols:
        assets = MarketAsset.query.filter(
            MarketAsset.symbol.in_(cfg_symbols)).all()
        unknown_assets = MarketAsset.query.filter(
            ~MarketAsset.symbol.in_(cfg_symbols)).all()
    else:
        assets = MarketAsset.query.all()
        unknown_assets = []

    by_symbol = {a.symbol: a for a in assets}
    rows = []
    for symbol in sorted(cfg_symbols):
        meta = cfg.get(symbol) or {}
        asset = by_symbol.get(symbol)
        rows.append(SimpleNamespace(
            id=getattr(asset, 'id', None),
            symbol=symbol,
            name=meta.get('name') or (asset.name if asset else symbol),
            asset_type=meta.get('type') or (asset.asset_type if asset else 'stock'),
            enabled=bool(meta.get('enabled', True)),
            base_price=float(meta.get('base_price') or 0),
            volatility=float(meta.get('volatility') or 0) * 100.0,
            current_price=float(getattr(asset, 'current_price', 0) or 0),
            price_change_24h=float(getattr(asset, 'price_change_24h', 0) or 0),
        ))

    settings = SimpleNamespace(
        market_volatility_multiplier=SystemConfig.get_value(
            'market_volatility_multiplier', '1.0'), market_intel_cost=SystemConfig.get_value(
            'market_intel_cost', '500'), market_update_interval_seconds=SystemConfig.get_value(
                'market_update_interval_seconds', '60'), )

    return render_template(
        'developer/market.html',
        assets=rows,
        unknown_assets=unknown_assets,
        settings=settings,
        title=_('سوق الأسهم'))


@bp.route('/developer/market/settings', methods=['POST'])
@developer_required
@double_verification_required
def dev_market_settings():
    market_volatility_multiplier = (request.form.get(
        'market_volatility_multiplier') or '').strip()
    market_intel_cost = (request.form.get('market_intel_cost') or '').strip()
    market_update_interval_seconds = (request.form.get(
        'market_update_interval_seconds') or '').strip()

    def set_logged(key, new_val):
        cfg = SystemConfig.query.filter_by(key=key).first()
        old_val = cfg.value if cfg else None
        if not cfg:
            cfg = SystemConfig(key=key)
            db.session.add(cfg)
        if str(old_val) == str(new_val):
            return False
        cfg.value = str(new_val)
        db.session.add(ConfigLog(
            admin_id=current_user.id,
            key=key,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(new_val) if new_val is not None else None,
            reason="Market Settings"
        ))
        return True

    if market_volatility_multiplier:
        set_logged(
            'market_volatility_multiplier',
            market_volatility_multiplier)
    if market_intel_cost:
        set_logged('market_intel_cost', market_intel_cost)
    if market_update_interval_seconds:
        set_logged(
            'market_update_interval_seconds',
            market_update_interval_seconds)

    db.session.commit()

    flash(_('تم حفظ إعدادات البورصة.'), 'success')
    return redirect(url_for('main.dev_market'))


@bp.route('/developer/market/sync', methods=['POST'])
@developer_required
def dev_market_sync():
    MarketSimulationService.initialize_assets()
    flash(_('تمت مزامنة الأصول.'), 'success')
    return redirect(url_for('main.dev_market'))


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
        if not asset:
            abort(404)
        title = _('تعديل أصل')
    else:
        asset = MarketAsset()
        title = _('إضافة أصل جديد')

    form = MarketAssetForm(obj=asset)
    cfg = MarketSimulationService.get_asset_config()

    if request.method == 'GET':
        sym = (asset.symbol or '').strip().upper()
        meta = cfg.get(sym) if sym else None
        if meta:
            form.symbol.data = sym
            form.name.data = meta.get('name') or asset.name
            form.type.data = meta.get('type') or asset.asset_type
            form.base_price.data = int(float(meta.get('base_price') or 0) or 0)
            form.volatility.data = int(
                round(float(meta.get('volatility') or 0) * 100))
            form.is_active.data = bool(meta.get('enabled', True))

    if form.validate_on_submit():
        raw_cfg = SystemConfig.get_value('market_assets_json')
        try:
            user_cfg = json.loads(raw_cfg) if raw_cfg else {}
        except Exception:
            user_cfg = {}
        if not isinstance(user_cfg, dict):
            user_cfg = {}

        old_symbol = (asset.symbol or '').strip().upper()
        symbol = (form.symbol.data or '').strip().upper()
        if not symbol:
            flash(_('رمز الأصل مطلوب.'), 'danger')
            return render_template(
                'developer/edit_market_asset.html',
                form=form,
                title=title)

        name = (form.name.data or '').strip()
        atype = (form.type.data or 'stock').strip().lower()
        base_price = float(form.base_price.data or 1)
        vol = float(form.volatility.data or 1) / 100.0
        enabled = bool(form.is_active.data)

        user_cfg[symbol] = {
            'name': name or symbol,
            'type': atype,
            'base_price': base_price,
            'volatility': vol,
            'enabled': enabled,
        }
        if old_symbol and old_symbol != symbol:
            if old_symbol in user_cfg:
                user_cfg.pop(old_symbol, None)

        SystemConfig.set_value(
            'market_assets_json', json.dumps(
                user_cfg, ensure_ascii=False))

        existing = MarketAsset.query.filter_by(symbol=symbol).first()
        if id and old_symbol != symbol and existing and existing.id != id:
            flash(_('رمز الأصل مستخدم مسبقاً.'), 'danger')
            return render_template(
                'developer/edit_market_asset.html',
                form=form,
                title=title)

        asset.symbol = symbol
        asset.name = name or symbol
        asset.asset_type = atype
        if not asset.current_price or asset.current_price <= 0:
            asset.current_price = base_price
        asset.last_updated = datetime.now(timezone.utc)

        if not id:
            db.session.add(asset)

        db.session.commit()
        MarketSimulationService.initialize_assets()
        flash(_('تم حفظ الأصل المالي'), 'success')
        return redirect(url_for('main.dev_market'))

    return render_template(
        'developer/edit_market_asset.html',
        form=form,
        title=title)


@bp.route('/developer/market/delete/<int:id>', methods=['POST'])
@developer_required
def dev_market_delete(id):
    asset = db.session.get(MarketAsset, id)
    if asset:
        raw_cfg = SystemConfig.get_value('market_assets_json')
        try:
            user_cfg = json.loads(raw_cfg) if raw_cfg else {}
        except Exception:
            user_cfg = {}
        if not isinstance(user_cfg, dict):
            user_cfg = {}

        symbol = (asset.symbol or '').strip().upper()
        meta = user_cfg.get(symbol, {})
        if not isinstance(meta, dict):
            meta = {}
        meta['enabled'] = False
        meta.setdefault('name', asset.name or symbol)
        meta.setdefault('type', asset.asset_type or 'stock')
        meta.setdefault('base_price', float(asset.current_price or 1))
        meta.setdefault('volatility', 0.02)
        user_cfg[symbol] = meta
        SystemConfig.set_value(
            'market_assets_json', json.dumps(
                user_cfg, ensure_ascii=False))

        db.session.commit()
        flash(_('تم تعطيل الأصل المالي'), 'success')
    return redirect(url_for('main.dev_market'))

# --- Auctions Management ---


@bp.route('/developer/auctions')
@developer_required
def dev_auctions():
    page = request.args.get('page', 1, type=int)
    auctions = Auction.query.order_by(Auction.end_time.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template(
        'developer/auctions.html',
        auctions=auctions.items,
        pagination=auctions,
        title=_('إدارة المزادات'),
    )


@bp.route('/developer/auctions/delete/<int:auction_id>', methods=['POST'])
@developer_required
def dev_delete_auction(auction_id):
    auction = Auction.query.get_or_404(auction_id)
    # Optional: Refund highest bidder if active
    if auction.status == 'active':
        highest_bid = (
            AuctionBid.query.filter_by(auction_id=auction.id)
            .order_by(AuctionBid.amount.desc())
            .first()
        )
        if highest_bid:
            bidder = User.query.get(highest_bid.bidder_id)
            if bidder:
                ResourceService.modify_resources(
                    bidder.id,
                    {'money': highest_bid.amount},
                    'auction_refund_admin',
                    auto_commit=False,
                    expected_version=bidder.version,
                )
                flash(
                    _(
                        'تم إعادة المبلغ للمزايد الأخير: %(amount)s',
                        amount=highest_bid.amount,
                    ),
                    'info',
                )

    db.session.delete(auction)
    db.session.commit()
    flash(_('تم حذف المزاد بنجاح'), 'success')
    return redirect(url_for('main.dev_auctions'))

# --- Image Management ---


@bp.route('/developer/images')
@developer_required
def dev_images():
    # List images from all subdirectories in static/images
    base_path = os.path.join(current_app.root_path, 'static', 'images')

    if not os.path.exists(base_path):
        os.makedirs(base_path)

    # Get all subdirectories
    all_items = os.listdir(base_path)
    categories = [
        d for d in all_items if os.path.isdir(
            os.path.join(
                base_path, d))]
    categories.sort()

    # Add 'root' for files in the base images directory
    root_images = [
        f
        for f in all_items
        if os.path.isfile(os.path.join(base_path, f))
        and f.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.gif'))
    ]
    if root_images:
        categories.insert(0, 'root')

    images_by_category = {}

    for category in categories:
        if category == 'root':
            target_path = base_path
            imgs = root_images
        else:
            target_path = os.path.join(base_path, category)
            imgs = [
                f
                for f in os.listdir(target_path)
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.gif'))
            ]

        images_by_category[category] = sorted(imgs)

    return render_template(
        'developer/images.html',
        images_by_category=images_by_category,
        title=_('إدارة الصور'),
    )


@bp.route('/developer/images/upload', methods=['POST'])
@developer_required
def dev_upload_image():
    if 'file' not in request.files:
        flash(_('لم يتم اختيار ملف'), 'danger')
        return redirect(url_for('main.dev_images'))

    file = request.files['file']
    category = request.form.get('category')

    if file.filename == '':
        flash(_('لم يتم اختيار ملف'), 'danger')
        return redirect(url_for('main.dev_images'))

    base_path = os.path.join(current_app.root_path, 'static', 'images')

    if category == 'root':
        save_path = base_path
    else:
        # Basic validation for category name to prevent path traversal
        if not category or '..' in category or '/' in category or '\\' in category:
            flash(_('فئة غير صالحة'), 'danger')
            return redirect(url_for('main.dev_images'))

        save_path = os.path.join(base_path, secure_filename(category))
        if not os.path.exists(save_path):
            os.makedirs(save_path)

    if file:
        filename = secure_filename(file.filename)
        full_path = os.path.join(save_path, filename)
        file.save(full_path)
        flash(_('تم رفع الصورة بنجاح: %(name)s', name=filename), 'success')

    return redirect(url_for('main.dev_images'))


@bp.route('/developer/images/delete', methods=['POST'])
@developer_required
def dev_delete_image():
    category = request.form.get('category')
    filename = request.form.get('filename')

    if not category or not filename:
        flash(_('بيانات غير مكتملة'), 'danger')
        return redirect(url_for('main.dev_images'))

    base_path = os.path.join(current_app.root_path, 'static', 'images')

    if category == 'root':
        file_path = os.path.join(base_path, secure_filename(filename))
    else:
        file_path = os.path.join(
            base_path, secure_filename(category), secure_filename(filename)
        )

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            flash(_('تم حذف الصورة'), 'success')
        except Exception as e:
            flash(_('خطأ في الحذف: %(error)s', error=str(e)), 'danger')
    else:
        flash(_('الصورة غير موجودة'), 'danger')

    return redirect(url_for('main.dev_images'))


@bp.route('/developer/auctions/create', methods=['POST'])
@developer_required
def dev_create_auction():
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')
    try:
        start_price = int(request.form.get('start_price'))
        duration_hours = int(request.form.get('duration_hours'))
    except ValueError:
        flash(_('بيانات غير صالحة'), 'danger')
        return redirect(url_for('main.dev_auctions'))

    now = datetime.now(timezone.utc)
    end_time = now + timedelta(hours=duration_hours)

    # Optional validation: Check if item/vehicle exists
    if item_type == 'item':
        if not Item.query.get(item_id):
            flash(_('العنصر غير موجود!'), 'danger')
            return redirect(url_for('main.dev_auctions'))
    elif item_type == 'vehicle':
        if not Vehicle.query.get(item_id):
            flash(_('المركبة غير موجودة!'), 'danger')
            return redirect(url_for('main.dev_auctions'))

    new_auction = Auction(
        item_type=item_type,
        item_id=item_id,
        start_price=start_price,
        current_price=start_price,
        min_bid_increment=max(1, int(start_price * 0.05)),
        start_time=now,
        end_time=end_time,
        status='active'
    )

    db.session.add(new_auction)
    db.session.commit()

    flash(_('تم إنشاء المزاد بنجاح'), 'success')
    return redirect(url_for('main.dev_auctions'))


@bp.route('/developer/alerts')
@developer_required
def dev_alerts():
    """System alerts and notifications dashboard"""
    alerts = []

    # Check for suspicious activities
    recent_logs = UserLog.query.filter(
        UserLog.timestamp >= datetime.now(timezone.utc) - timedelta(hours=1)
    ).order_by(UserLog.timestamp.desc()).limit(50).all()

    for log in recent_logs:
        if log.action in [
            'COMBAT_WIN',
                'COMBAT_LOSE'] and log.result == 'success':
            details = json.loads(log.details) if log.details else {}
            if details.get('money_stolen', 0) > 1000000:  # Large amounts
                message = (
                    f"المستخدم {log.user.username} قام بهجوم كبير بقيمة "
                    f"${details.get('money_stolen', 0):,}"
                )
                alerts.append({
                    'type': 'warning',
                    'title': 'هجوم كبير',
                    'message': message,
                    'timestamp': log.timestamp
                })

        if log.action == 'AUCTION_BID' and log.result == 'success':
            details = json.loads(log.details) if log.details else {}
            if details.get('bid_amount', 0) > 10000000:  # Large bids
                message = (
                    f"مزايدة كبيرة بقيمة ${details.get('bid_amount', 0):,} "
                    "على مزاد"
                )
                alerts.append({
                    'type': 'info',
                    'title': 'مزايدة كبيرة',
                    'message': message,
                    'timestamp': log.timestamp
                })

    # Check system health
    total_users = User.query.count()
    active_users = db.session.query(
        func.count(
            func.distinct(
                UserLog.user_id))).filter(
        UserLog.timestamp >= datetime.now(
            timezone.utc) -
        timedelta(
            days=1)).scalar() or 0

    if total_users > 0 and (
            active_users /
            total_users) < 0.1:  # Less than 10% active
        pct = (active_users / total_users) * 100
        alerts.append({
            'type': 'danger',
            'title': 'انخفاض النشاط',
            'message': (
                f'نسبة المستخدمين النشطين منخفضة: '
                f'{active_users}/{total_users} ({pct:.1f}%)'
            ),
            'timestamp': datetime.now(timezone.utc)
        })

    # Check for system issues
    recent_errors = GameLog.query.filter(
        GameLog.action == 'ERROR',
        GameLog.timestamp >= datetime.now(timezone.utc) - timedelta(hours=1)
    ).count()

    if recent_errors > 10:
        alerts.append({
            'type': 'danger',
            'title': 'أخطاء متكررة',
            'message': f'تم تسجيل {recent_errors} خطأ في الساعة الأخيرة',
            'timestamp': datetime.now(timezone.utc)
        })

    return render_template(
        'developer/alerts.html',
        alerts=alerts,
        title=_('تنبيهات النظام'))


@bp.route('/developer/alerts/dismiss/<int:alert_id>', methods=['POST'])
@developer_required
def dismiss_alert(alert_id):
    """Dismiss a system alert"""
    # In a real implementation, you would store dismissed alerts in the
    # database
    flash(_('تم تجاهل التنبيه'), 'success')
    return redirect(url_for('main.dev_alerts'))


@bp.route('/developer/economy/sinks')
@developer_required
def dev_economy_sinks():
    page = request.args.get('page', 1, type=int)
    user_id = request.args.get('user_id')
    sink_type = request.args.get('sink_type')

    query = MoneySinkLog.query

    if user_id:
        query = query.filter(MoneySinkLog.user_id == user_id)
    if sink_type:
        query = query.filter(MoneySinkLog.sink_type == sink_type)

    pagination = query.order_by(MoneySinkLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    # Calculate total sunk
    total_sunk = db.session.query(func.sum(MoneySinkLog.amount)).scalar() or 0

    # Get distinct sink types for filter
    sink_types = [r[0] for r in db.session.query(
        MoneySinkLog.sink_type).distinct().limit(50).all()]

    return render_template(
        'developer/economy_sinks.html',
        logs=pagination.items,
        pagination=pagination,
        total_sunk=total_sunk,
        sink_types=sink_types,
        title=_('سجلات تصريف الأموال'),
    )
