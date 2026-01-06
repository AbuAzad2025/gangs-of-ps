from flask import render_template, redirect, url_for, flash, request, abort, session, current_app
from flask_login import login_required, current_user
from extensions import db, limiter
from models import Crime, Item, WeeklyWinner, UserItem, DailyTask, UserDailyTask, Gang, GangLog, User, Announcement, SystemConfig, OrganizedCrime, CrimeLobby, LobbyParticipant, HeistHistory, UserCrimeCooldown, Vehicle, UserVehicle, InvestigationLog, Location, FactoryJob, FarmSupplyContract, UserLog, UserOrganizedCrimeCooldown
from models.hostess import Hostess
from . import bp
import random
from datetime import datetime, timedelta, timezone
from flask_babel import _
from .utils import update_daily_task_progress, send_notification, sync_daily_tasks
from services.requirements import check_requirements
from services.resource_service import ResourceService
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from decorators import check_maintenance, player_only

_broadcast_cache = {}


@bp.route('/organized_crimes')
@limiter.limit("30 per minute")
def organized_crimes():
    if not current_user.is_authenticated:
        enabled = SystemConfig.get_value('organized_crimes_enabled', 'true') == 'true'
        if not enabled:
            flash(_('الجرائم المنظمة غير مفعلة حالياً.'), 'warning')
            return redirect(url_for('main.index'))
            
        crimes = OrganizedCrime.query.filter_by(is_active=True).order_by(OrganizedCrime.min_level).all()
        meta_description = _("سيناريوهات الجرائم المنظمة في عصابات فلسطين. خطط ونفذ عمليات سطو مسلح مع فريقك.")
        
        crime_access = {}
        crime_meta = {}
        for c in crimes:
             crime_access[c.id] = {"unlocked": False, "reason": _("يجب تسجيل الدخول للعب"), "hint_text": _("سجل دخولك الآن"), "hint_url": url_for('main.login')}
             # Basic meta
             reqs = {}
             try:
                 import json
                 reqs = json.loads(c.requirements) if c.requirements else {}
             except:
                 pass
             crime_meta[c.id] = {
                'required_item': reqs.get('required_item'),
                'heat_window_hours': reqs.get('heat_window_hours'),
                'double_patrol_pct': reqs.get('double_patrol_pct'),
                'lucky_event_pct': reqs.get('lucky_event_pct')
             }

        return render_template('organized_crimes.html', crimes=crimes, allow_non_gang=True, can_create=False, 
                               min_creator_rank_level=0, active_lobbies=[], crime_meta=crime_meta, 
                               crime_access=crime_access, lobby_counts={}, meta_description=meta_description)

    try:
        existing_participation = LobbyParticipant.query.join(CrimeLobby).filter(
            LobbyParticipant.user_id == current_user.id,
            CrimeLobby.status.in_(['recruiting', 'in_progress'])
        ).first()
    except Exception:
        existing_participation = None
        try:
            db.session.rollback()
        except Exception:
            pass
    if existing_participation:
        lobby = db.session.get(CrimeLobby, existing_participation.lobby_id)
        if lobby and not _expire_lobby_if_needed(lobby) and lobby.status in ['recruiting', 'in_progress']:
            return redirect(url_for('main.lobby', lobby_id=lobby.id))

    try:
        db.session.rollback()
    except Exception:
        pass

    enabled = SystemConfig.get_value('organized_crimes_enabled', 'true') == 'true'
    allow_non_gang = SystemConfig.get_value('organized_crimes_allow_non_gang', 'true') == 'true'
    min_creator_rank_level = int(SystemConfig.get_value('organized_crimes_min_creator_rank_level', '20'))

    if OrganizedCrime.query.count() < 6:
        from utils.essentials import initialize_items, initialize_organized_crimes
        initialize_items()
        initialize_organized_crimes()
        db.session.commit()
    
    if not enabled:
        flash(_('الجرائم المنظمة غير مفعلة حالياً.'), 'warning')
        return redirect(url_for('main.hara'))
    
    crimes = OrganizedCrime.query.filter_by(is_active=True).order_by(OrganizedCrime.min_level).all()

    # Fetch User Cooldowns
    user_cooldowns = UserOrganizedCrimeCooldown.query.filter_by(user_id=current_user.id).all()
    cooldowns_map = {uc.crime_id: uc.cooldown_until for uc in user_cooldowns}

    crime_meta = {}
    crime_access = {}
    for c in crimes:
        reqs = {}
        try:
            import json
            reqs = json.loads(c.requirements) if c.requirements else {}
        except Exception:
            reqs = {}
        crime_meta[c.id] = {
            'required_item': reqs.get('required_item'),
            'heat_window_hours': reqs.get('heat_window_hours'),
            'double_patrol_pct': reqs.get('double_patrol_pct'),
            'lucky_event_pct': reqs.get('lucky_event_pct')
        }

        is_ok = True
        reason = None
        hint_text = None
        hint_url = None

        # Check Cooldown
        if c.id in cooldowns_map:
            ends_at = cooldowns_map[c.id]
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            if ends_at > datetime.now(timezone.utc):
                is_ok = False
                remaining = ends_at - datetime.now(timezone.utc)
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                reason = _('انتظار: %(h)sس %(m)sد', h=hours, m=minutes)
                crime_meta[c.id]['cooldown_until'] = ends_at

        if is_ok:
            chk = check_requirements(current_user, {"min_level": c.min_level})
        if not chk["ok"]:
            is_ok = False
            reason = chk["reason"]
            hint_text = chk.get("hint_text")
            hint_url = url_for('main.daily_tasks') if chk.get("hint_key") == "daily_tasks" else None

        if is_ok and (not allow_non_gang) and (not current_user.gang_id):
            is_ok = False
            reason = _('انضم لعصابة لفتحها.')
            hint_text = _('نصيحة: افتح صفحة العصابات وانضم لواحدة.')
            hint_url = url_for('gang.index')

        if is_ok and c.min_gang_level and current_user.gang:
            try:
                if int(current_user.gang.level) < int(c.min_gang_level):
                    is_ok = False
                    reason = _('تحتاج مستوى عصابة %(n)s.', n=c.min_gang_level)
                    hint_text = _('نصيحة: طوّر عصابتك عبر التبرعات والنشاط.')
                    hint_url = url_for('gang.index')
            except Exception:
                pass

        if is_ok:
            role_ok = False
            best_reason = None
            role_reqs = reqs if isinstance(reqs, dict) else {}
            roles = c.roles_config or []
            if roles:
                for role in roles:
                    role_name = role.get("name") if isinstance(role, dict) else None
                    role_key = role.get("key") if isinstance(role, dict) else None
                    r = {}
                    if role_name and role_name in role_reqs:
                        r = role_reqs.get(role_name) or {}
                    elif role_key and role_key in role_reqs:
                        r = role_reqs.get(role_key) or {}
                    if isinstance(r, dict):
                        req_map = {}
                        if "strength" in r: req_map["min_strength"] = r.get("strength")
                        if "agility" in r: req_map["min_agility"] = r.get("agility")
                        if "intelligence" in r: req_map["min_intelligence"] = r.get("intelligence")
                        chk_role = check_requirements(current_user, req_map)
                        if chk_role["ok"]:
                            role_ok = True
                            break
                        if not best_reason and chk_role["reason"]:
                            best_reason = chk_role["reason"]
            else:
                role_ok = True

            if not role_ok:
                is_ok = False
                reason = best_reason or _('طور مهاراتك لفتحها.')
                hint_text = _('نصيحة: روح الجيم وطور مهاراتك.')
                hint_url = url_for('gym.index')

        crime_access[c.id] = {"unlocked": bool(is_ok), "reason": reason, "hint_text": hint_text, "hint_url": hint_url}
    
    effective_level = current_user.level
    try:
        effective_level = current_user.level + (current_user.rank_points_value // 50)
    except:
        pass
    
    can_create = effective_level >= min_creator_rank_level
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    try:
        active_lobbies = (
            CrimeLobby.query.options(
                joinedload(CrimeLobby.crime),
                joinedload(CrimeLobby.leader),
                selectinload(CrimeLobby.participants),
            )
            .filter(
                CrimeLobby.status == 'recruiting',
                CrimeLobby.created_at >= cutoff,
            )
            .order_by(CrimeLobby.created_at.desc())
            .all()
        )
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        active_lobbies = []

    lobby_counts = {}
    for lobby in active_lobbies:
        try:
            lobby_counts[lobby.id] = len(lobby.participants or [])
        except Exception:
            lobby_counts[lobby.id] = 0
            try:
                db.session.rollback()
            except Exception:
                pass

    return render_template('organized_crimes.html', crimes=crimes, allow_non_gang=allow_non_gang, can_create=can_create, min_creator_rank_level=min_creator_rank_level, active_lobbies=active_lobbies, crime_meta=crime_meta, crime_access=crime_access, lobby_counts=lobby_counts)


def _expire_lobby_if_needed(lobby):
    if not lobby:
        return False
    try:
        created = lobby.created_at
        if not created:
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now - created > timedelta(hours=24) and lobby.status == 'recruiting':
            lobby.status = 'expired'
            db.session.commit()
            return True
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return False
@bp.route('/daily_tasks')
@login_required
def daily_tasks():
    user_tasks = sync_daily_tasks(current_user)
    return render_template('daily_tasks.html', tasks=user_tasks)

@bp.route('/collect_task_reward/<int:task_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def collect_task_reward(task_id):
    # Lock the row for update to prevent double claiming
    user_task = UserDailyTask.query.filter_by(id=task_id).with_for_update().first()
    
    if not user_task:
        abort(404)
    
    if user_task.user_id != current_user.id:
        flash(_('هذه المهمة ليست لك!'), 'danger')
        return redirect(url_for('main.daily_tasks'))
        
    if user_task.is_completed:
        flash(_('تم استلام المكافأة مسبقاً.'), 'warning')
        return redirect(url_for('main.daily_tasks'))
        
    if user_task.progress < user_task.task.target_count:
        flash(_('لم تكمل المهمة بعد!'), 'warning')
        return redirect(url_for('main.daily_tasks'))
        
    # Grant Reward using atomic update via ResourceService
    changes = {
        'money': user_task.task.reward_money,
        'exp': user_task.task.reward_exp
    }
    
    if not ResourceService.modify_resources(current_user.id, changes, 'daily_task_reward', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء استلام المكافأة.'), 'danger')
        return redirect(url_for('main.daily_tasks'))
    
    # Check Level Up
    if current_user.check_level_up():
        ref_url = url_for('main.register', ref=current_user.referral_code, _external=True)
        share_text = _("أصبحت زعيم مستوى %(level)s في عصابات فلسطين! هل تجرؤ على تحديي؟ %(url)s", level=current_user.level, url=ref_url)
        wa_link = f"https://wa.me/?text={share_text}"
        flash(_('مبروك! وصلت للمستوى %(level)s! <a href="%(url)s" target="_blank" class="btn btn-sm btn-success ml-2"><i class="fab fa-whatsapp"></i> شارك</a>', level=current_user.level, url=wa_link), 'success')

    user_task.is_completed = True
    db.session.commit()
    
    flash(_('مبروك! حصلت على المكافأة: %(money)s شيكل و %(exp)s خبرة.', money=user_task.task.reward_money, exp=user_task.task.reward_exp), 'success')
    return redirect(url_for('main.daily_tasks'))

@bp.route('/daily_reward')
@login_required
@limiter.limit("1 per minute") # Strict limit for daily reward
def daily_reward():
    now = datetime.now(timezone.utc)
    
    # Lock User Row
    user = db.session.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    ).scalar_one()
    
    if user.last_daily_reward:
        # Check if 24 hours have passed
        last_claim_at = user.last_daily_reward
        if last_claim_at.tzinfo is None:
             last_claim_at = last_claim_at.replace(tzinfo=timezone.utc)
             
        if now - last_claim_at < timedelta(hours=24):
            remaining = timedelta(hours=24) - (now - last_claim_at)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, remaining_seconds = divmod(remainder, 60)
            db.session.rollback() # Release lock
            flash(_('لسه بدري يا كبير! ارجع بعد %(hours)s ساعة و %(minutes)s دقيقة.', hours=hours, minutes=minutes), 'warning')
            return redirect(url_for('main.hara'))
            
        delta_days = (now.date() - last_claim_at.date()).days
        if delta_days == 1:
            user.daily_streak = int(user.daily_streak or 0) + 1
        else:
            user.daily_streak = 1
    else:
        user.daily_streak = 1

    user.daily_streak = max(1, min(30, int(user.daily_streak or 1)))

    base_money = user.level * 50
    base_energy = 20
    base_exp = 10

    streak = int(user.daily_streak or 1)
    streak_multiplier = 1.0 + (min(6, streak - 1) * 0.10)

    money_reward = int(base_money * streak_multiplier)
    energy_reward = int(min(40, base_energy + (min(10, streak - 1) * 2)))
    exp_reward = int(base_exp * streak_multiplier)
    diamonds_reward = 0
    if streak % 7 == 0:
        diamonds_reward = 1
        money_reward += user.level * 200
    
    user.last_daily_reward = now.replace(tzinfo=None)
    
    # Atomic Resource Update
    changes = {
        'money': money_reward,
        'energy': energy_reward,
        'exp': exp_reward
    }
    if diamonds_reward:
        changes['diamonds'] = diamonds_reward
    
    set_fields = {
        'last_daily_reward': now.replace(tzinfo=None),
        'daily_streak': streak
    }
        
    if not ResourceService.modify_resources(user.id, changes, 'daily_reward', auto_commit=False, expected_version=None, set_fields=set_fields):
        flash(_('حدث خطأ أثناء استلام المكافأة. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('main.hara'))

    # Update non-resource fields (ResourceService holds the lock now)
    # Re-fetch user to ensure we are working on the locked instance in this session
    locked_user = db.session.get(User, user.id)
    # Fields already set by ResourceService via set_fields

    db.session.commit()
    
    if diamonds_reward:
        flash(_('أخذت مكافأتك اليومية (ستريك %(streak)s): %(money)s شيكل و %(energy)s طاقة و %(d)s ماس!', streak=streak, money=money_reward, energy=energy_reward, d=diamonds_reward), 'success')
    else:
        flash(_('أخذت مكافأتك اليومية (ستريك %(streak)s): %(money)s شيكل و %(energy)s طاقة!', streak=streak, money=money_reward, energy=energy_reward), 'success')
    return redirect(url_for('main.hara'))

@bp.route('/hara')
@login_required
def hara():
    announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).limit(3).all()
    now = datetime.now(timezone.utc)
    can_claim = True
    remaining_text = None
    last_claim_at = current_user.last_daily_reward
    if last_claim_at:
        if last_claim_at.tzinfo is None:
            last_claim_at = last_claim_at.replace(tzinfo=timezone.utc)
        if now - last_claim_at < timedelta(hours=24):
            can_claim = False
            remaining = timedelta(hours=24) - (now - last_claim_at)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, remaining_seconds = divmod(remainder, 60)
            remaining_text = _('%(hours)s ساعة و %(minutes)s دقيقة', hours=hours, minutes=minutes)

    base_money = current_user.level * 50
    base_energy = 20
    base_exp = 10

    current_streak = int(getattr(current_user, "daily_streak", 0) or 0)
    next_streak = 1
    if current_user.last_daily_reward:
        lc = current_user.last_daily_reward
        if lc.tzinfo is None:
            lc = lc.replace(tzinfo=timezone.utc)
        delta_days = (now.date() - lc.date()).days
        if delta_days == 1:
            next_streak = max(1, current_streak + 1)
        elif delta_days == 0:
            next_streak = max(1, current_streak)
        else:
            next_streak = 1
    else:
        next_streak = 1
    next_streak = max(1, min(30, int(next_streak)))

    streak_multiplier = 1.0 + (min(6, next_streak - 1) * 0.10)
    next_money = int(base_money * streak_multiplier)
    next_energy = int(min(40, base_energy + (min(10, next_streak - 1) * 2)))
    next_exp = int(base_exp * streak_multiplier)
    next_diamonds = 1 if (next_streak % 7 == 0) else 0
    if next_diamonds:
        next_money += current_user.level * 200

    daily_reward_meta = {
        "can_claim": bool(can_claim),
        "remaining_text": remaining_text,
        "streak": max(0, current_streak),
        "next_streak": next_streak,
        "next_money": next_money,
        "next_energy": next_energy,
        "next_exp": next_exp,
        "next_diamonds": next_diamonds,
    }

    return render_template('hara.html', user=current_user, announcements=announcements, daily_reward_meta=daily_reward_meta)

@bp.route('/empire')
@login_required
def empire():
    now = datetime.now(timezone.utc)

    try:
        active_factory_job = FactoryJob.query.filter_by(user_id=current_user.id, status='running').order_by(FactoryJob.ends_at.desc()).first()
        factory_jobs_count = FactoryJob.query.filter_by(user_id=current_user.id).count()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        active_factory_job = None
        factory_jobs_count = 0

    try:
        contracts = FarmSupplyContract.query.filter_by(user_id=current_user.id).order_by(FarmSupplyContract.ends_at.desc()).all()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        contracts = []

    active_contracts = [c for c in contracts if getattr(c, "is_active", False)]

    current_location = None
    if current_user.location_id:
        try:
            current_location = db.session.get(Location, current_user.location_id)
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_location = None

    try:
        smuggling_items = UserItem.query.join(Item).filter(UserItem.user_id == current_user.id, Item.type == 'smuggling').all()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        smuggling_items = []

    try:
        current_heat = current_user.heat_value(now=now)
    except Exception:
        current_heat = 0

    gang = current_user.gang

    return render_template(
        'empire.html',
        user=current_user,
        active_factory_job=active_factory_job,
        factory_jobs_count=factory_jobs_count,
        contracts=contracts,
        active_contracts=active_contracts,
        current_location=current_location,
        smuggling_items=smuggling_items,
        current_heat=current_heat,
        gang=gang,
        title=_('إمبراطوريتك'),
    )

@bp.route('/guide')
def guide():
    return render_template('guide.html')

@bp.route('/crimes')
@login_required
def crimes():
    if not Crime.query.filter_by(name='سرقة سيارة').first():
        from utils.essentials import initialize_items, initialize_basic_crimes
        initialize_items()
        initialize_basic_crimes()
        db.session.commit()
    else:
        now = datetime.now(timezone.utc)
        last_check = getattr(current_app, "_basic_crimes_seed_last_check", None)
        if last_check is None or (now - last_check).total_seconds() >= 300:
            try:
                if Crime.query.filter(Crime.cooldown == 60).count() > 0:
                    from utils.essentials import initialize_basic_crimes
                    initialize_basic_crimes()
                    db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
            current_app._basic_crimes_seed_last_check = now

    # Show all active crimes to let users see what's coming (motivation)
    all_crimes = Crime.query.filter_by(is_active=True).order_by(Crime.min_level).all()

    reward_previews = {}
    crime_rewards = {
        'سرقة كشك': ['رزمة دخان مهرب'],
        'سرقة هاتف': ['هاتف مسروق'],
        'سرقة دراجة': ['دراجة هوائية مسروقة'],
        'سطو على محل مجوهرات': ['مجوهرات مسروقة', 'ساعة يد فاخرة مسروقة'],
        'تجارة أسلحة صغيرة': ['سكينة مطبخ', 'عصا بيسبول', 'شفرة', 'جنزير', 'هراوة شرطة', 'مسدس حلوان']
    }

    for crime in all_crimes:
        if getattr(crime, 'reward_type', 'money') == 'item':
            items = []
            if getattr(crime, 'reward_item_id', None):
                reward_item = db.session.get(Item, crime.reward_item_id)
                if reward_item:
                    items = [reward_item]
            if not items:
                names = crime_rewards.get(crime.name) or []
                if names:
                    items = Item.query.filter(Item.name.in_(names)).all()
            reward_previews[crime.id] = items[:3]

    # Get user cooldowns
    cooldowns = UserCrimeCooldown.query.filter_by(user_id=current_user.id).all()
    cooldown_map = {}
    now = datetime.now(timezone.utc)
    
    # Global Cooldown Logic
    global_cooldown_until_ms = None
    if current_user.crime_cooldown_until:
        until = current_user.crime_cooldown_until
        # Ensure 'until' is timezone-aware (UTC) for comparison and timestamp calculation
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
            
        if until > now:
            global_cooldown_until_ms = int(until.timestamp() * 1000)
    
    for c in cooldowns:
        # Check if still active
        if c.cooldown_until:
            c_until = c.cooldown_until
            if c_until.tzinfo is None:
                c_until = c_until.replace(tzinfo=timezone.utc)
                
            if c_until > now:
                cooldown_map[c.crime_id] = c_until

    return render_template('crimes.html', crimes=all_crimes, user=current_user, cooldown_map=cooldown_map, now=now, reward_previews=reward_previews, global_cooldown_until_ms=global_cooldown_until_ms)

@bp.route('/story')
@login_required
def story():
    story = session.pop('story', None)
    if not story:
        return redirect(url_for('main.index'))
    if isinstance(story, dict):
        if 'title' in story:
            story.setdefault('title_msgid', story.get('title'))
        if 'subtitle' in story:
            story.setdefault('subtitle_msgid', story.get('subtitle'))
        if 'badge' in story:
            story.setdefault('badge_msgid', story.get('badge'))
        if 'alt_label' in story:
            story.setdefault('alt_label_msgid', story.get('alt_label'))
    return render_template('story.html', story=story)

@bp.route('/do_crime/<int:crime_id>')
@login_required
@check_maintenance('crimes')
@player_only
@limiter.limit("5 per second")
def do_crime(crime_id):
    # 1. Anti-Bot Check
    # if 'check_bot_activity' in globals() and not check_bot_activity():
    #      return redirect(url_for('main.crimes'))
    
    # 2. Status Check (Jail/Hospital)
    now = datetime.now(timezone.utc)
    db.session.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    ).scalar_one()
    now_naive = now.replace(tzinfo=None)

    if current_user.crime_cooldown_until:
        # DISABLED Global Cooldown Check per user request
        # This was causing timezone issues (6618 seconds block) and users want independent cooldowns.
        pass
        # until = current_user.crime_cooldown_until
        # if getattr(until, "tzinfo", None) is not None:
        #     until = until.replace(tzinfo=None)
        # if until and until > now_naive:
        #     remaining_seconds = max(1, int((until - now_naive).total_seconds()))
        #     flash(_('عليك الانتظار %(seconds)s ثانية قبل القيام بمهمة أخرى!', seconds=remaining_seconds), 'danger')
        #     return redirect(url_for('main.crimes'))
    
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك القيام بجرائم!'), 'danger')
            return redirect(url_for('jail.index'))

    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك القيام بجرائم!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب في الجيم ولا يمكنك القيام بجرائم!'), 'danger')
            return redirect(url_for('gym.index'))

    crime = db.session.get(Crime, crime_id)
    if not crime:
        abort(404)
    
    # Requirements Check
    effective_strength = current_user.strength
    effective_agility = current_user.agility

    equipped_items = UserItem.query.join(Item).filter(
        UserItem.user_id == current_user.id,
        UserItem.is_equipped == True
    ).all()

    for ui in equipped_items:
        mult = 1.0
        if ui.condition is not None and ui.condition < 100:
            mult = ui.condition / 100
        effective_strength += int(ui.item.bonus_strength * mult)
        effective_agility += int(ui.item.bonus_agility * mult)

    if current_user.level < crime.min_level:
        flash(_('مستواك لا يسمح بتنفيذ هذه الجريمة بعد!'), 'danger')
        return redirect(url_for('main.crimes'))
        
    if effective_strength < crime.min_strength:
        flash(_('عضلاتك ضعيفة! تحتاج قوة %(str)s (مع العتاد) لتنفيذ هذه الجريمة', str=crime.min_strength), 'danger')
        return redirect(url_for('main.crimes'))
        
    if effective_agility < crime.min_agility:
        flash(_('حركتك بطيئة! تحتاج خفة حركة %(agl)s (مع العتاد) لتنفيذ هذه الجريمة', agl=crime.min_agility), 'danger')
        return redirect(url_for('main.crimes'))

    # Energy Check
    if current_user.energy < crime.energy_cost:
        flash(_('ما عندك طاقة كافية!'), 'danger')
        return redirect(url_for('main.crimes'))

    # Daily Limit Check
    daily_limit = getattr(crime, 'daily_limit', None) or 0
    
    # Pre-fetch cooldown record
    user_cooldown = UserCrimeCooldown.query.filter_by(user_id=current_user.id, crime_id=crime.id).first()

    if daily_limit > 0:
        if user_cooldown and user_cooldown.last_reset_date == now.date():
            if user_cooldown.daily_count >= daily_limit:
                flash(_('لقد وصلت للحد اليومي لهذه الجريمة! (%(limit)s مرة يومياً)', limit=daily_limit), 'danger')
                return redirect(url_for('main.crimes'))
        
    # Cooldown Check (Specific Crime)
    if user_cooldown:
        cooldown_until = user_cooldown.cooldown_until
        # Ensure aware UTC for comparison
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
            
        if cooldown_until > now:
            remaining = (cooldown_until - now).total_seconds()
            flash(_('عليك الانتظار %(time)s ثانية قبل القيام بهذه الجريمة مرة أخرى!', time=int(remaining)), 'danger')
            return redirect(url_for('main.crimes'))

    # Execute
    # Atomic deduction for energy
    if not ResourceService.modify_resources(current_user.id, {'energy': -crime.energy_cost}, 'crime_cost', auto_commit=False, expected_version=None):
        db.session.rollback()
        flash(_('لا تملك طاقة كافية!'), 'danger')
        return redirect(url_for('main.crimes'))
    
    # Set Cooldown (Specific Crime) & Update Daily Count
    new_cooldown_time = (datetime.now(timezone.utc) + timedelta(seconds=crime.cooldown)).replace(tzinfo=None)
    
    if user_cooldown:
        user_cooldown.cooldown_until = new_cooldown_time
        if user_cooldown.last_reset_date != now.date():
            user_cooldown.daily_count = 1
            user_cooldown.last_reset_date = now.date()
        else:
            user_cooldown.daily_count += 1
    else:
        new_record = UserCrimeCooldown(
            user_id=current_user.id, 
            crime_id=crime.id, 
            cooldown_until=new_cooldown_time,
            daily_count=1,
            last_reset_date=now.date()
        )
        db.session.add(new_record)

    base_global_cd_seconds = 20
    try:
        base_global_cd_seconds = int(SystemConfig.get_value("crime_global_cooldown_seconds", str(base_global_cd_seconds)) or base_global_cd_seconds)
    except Exception:
        base_global_cd_seconds = 10
    base_global_cd_seconds = max(1, min(300, base_global_cd_seconds))

    max_global_cd_seconds = 240
    try:
        max_global_cd_seconds = int(SystemConfig.get_value("crime_global_cooldown_max_seconds", str(max_global_cd_seconds)) or max_global_cd_seconds)
    except Exception:
        max_global_cd_seconds = 120
    max_global_cd_seconds = max(5, min(600, max_global_cd_seconds))

    crime_cd = int(getattr(crime, "cooldown", 0) or 0)
    crime_min_level = int(getattr(crime, "min_level", 1) or 1)
    reward_max = int(getattr(crime, "money_reward_max", 0) or 0)
    reward_bump = min(25, int(reward_max / 5000))

    # Simplified Global Cooldown to respect "Each crime has its own counter"
    # Just a small breathing room between actions
    global_cd_seconds = 1
    
    if current_user.is_suspicious:
        # Soft Anti-Cheat: Increase global cooldown
        global_cd_seconds = int(global_cd_seconds * 1.5)
    
    # DISABLED Global Cooldown Setting per user request
    # current_user.crime_cooldown_until = now + timedelta(seconds=global_cd_seconds)
    
    # Success/Fail Logic
    # Dynamic Success Chance
    base_chance = 60
    
    # Bonus for stats exceeding minimums
    str_ratio = effective_strength / max(1, crime.min_strength)
    agl_ratio = effective_agility / max(1, crime.min_agility)
    
    # Up to 20% bonus for having stats above required
    bonus_chance = min(30, (str_ratio + agl_ratio - 2) * 15)
    # Intelligence bonus (smart criminals plan better)
    intel_bonus = min(10, current_user.intelligence / 10)
    
    if current_user.is_suspicious:
        # Soft Anti-Cheat: Reduce base chance silently
        intel_bonus = 0
        bonus_chance = bonus_chance / 2

    hostess_bonus = 0
    hostess = None
    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > now:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'crime_success':
                hostess_bonus = (hostess.buff_value if hostess.buff_value else 0.1) * 100

    final_chance = min(95, base_chance + bonus_chance + intel_bonus + hostess_bonus)
    try:
        heat = current_user.heat_value(now=now)
    except Exception:
        heat = 0
    try:
        heat_penalty_per_point = float(SystemConfig.get_value("heat_success_penalty_per_point", "0.15") or 0.15)
    except Exception:
        heat_penalty_per_point = 0.15
        
    # Smart Ceiling: As heat approaches 100, success drops drastically but never hits 0 purely by heat (min 5%)
    heat_penalty = heat * heat_penalty_per_point
    
    # Nonlinear penalty at high heat (>80)
    if heat > 80:
        heat_penalty += (heat - 80) * 0.5
        
    final_chance = max(5, int(final_chance - heat_penalty))
    
    # --- OCCUPATION MECHANICS (Smart Flavor) ---
    # 1. Collaborator (Al-Jasoos)
    # If heat is high (>40), risk of betrayal increases.
    if heat > 40 and random.random() < 0.05:
         jail_time = 60
         # Atomic update handled by direct assignment here since we commit immediately
         current_user.jail_until = datetime.now(timezone.utc) + timedelta(minutes=jail_time)
         # We might want to clear the cooldown to let them suffer in jail but not wait after? No, keep CD.
         db.session.commit()
         
         flash(_('🕵️ جاسوس بلغ عنك! قوات خاصة حاصرتك قبل ما تبدأ. أخذوك تحقيق 60 دقيقة.'), 'danger')
         return redirect(url_for('jail.index'))

    # 2. Random Arrest (E'teqal A'shwa'i)
    # 1% chance regardless of skill/heat/luck - The reality of occupation.
    if random.random() < 0.01:
         jail_time = random.randint(30, 90)
         current_user.jail_until = datetime.now(timezone.utc) + timedelta(minutes=jail_time)
         db.session.commit()
         
         flash(_('👮 كنت ماشي في حالك، وقفتك دورية واعتقلوك عشوائياً (اعتقال إداري).'), 'danger')
         return redirect(url_for('jail.index'))

    # 3. Wall Smuggling Risk (Specific to "Tehreeb Ommal")
    if crime.name == 'تهريب عمال' and random.random() < 0.15:
         jail_time = random.randint(20, 45)
         current_user.jail_until = datetime.now(timezone.utc) + timedelta(minutes=jail_time)
         db.session.commit()
         flash(_('🧗 علقت بالسلك وأجت دورية حرس حدود لقطتك. "تهريب عمال؟ تعال هون!"'), 'danger')
         return redirect(url_for('jail.index'))

    roll = random.randint(1, 100)
    
    if roll <= final_chance:
        try:
            level_mult_factor = float(SystemConfig.get_value("crime_level_money_multiplier", "0.02") or 0.02)
        except:
            level_mult_factor = 0.02
        level_multiplier = 1 + (current_user.level * level_mult_factor)
        base_money = random.randint(crime.money_reward_min, crime.money_reward_max)
        money = int(base_money * level_multiplier)
        xp_reward = int(crime.exp_reward * level_multiplier)
        
        if current_user.is_suspicious:
            # Soft Anti-Cheat: Reduce rewards
            money = int(money * 0.6)
            xp_reward = int(xp_reward * 0.5)

        story_item_name = None
        story_item_condition = None
        story_vehicle_name = None
        story_vehicle_condition = None

        if hostess:
            if hostess.buff_type == 'crime_money':
                money = int(money * (1 + (hostess.buff_value or 0.1)))
            elif hostess.buff_type == 'crime_xp':
                xp_reward = int(xp_reward * (1 + (hostess.buff_value or 0.1)))
        
        # Vehicle Theft Reward Logic
        if hasattr(crime, 'reward_type') and crime.reward_type == 'vehicle':
             # Filter vehicles by price (approximate tier) based on user level
             # Logic: Max price = User Level * 20000 + 5000
             max_price = current_user.level * 20000 + 5000
             available_vehicles = Vehicle.query.filter(Vehicle.price <= max_price, Vehicle.is_active == True).all()
             
             if available_vehicles:
                 # Pick one random vehicle
                 stolen_vehicle = random.choice(available_vehicles)
                 
                 # Condition: Damaged (20% to 50%)
                 condition = random.randint(20, 50)
                 
                 new_user_vehicle = UserVehicle(
                     user_id=current_user.id,
                     vehicle_id=stolen_vehicle.id,
                     condition=condition,
                     is_active=False
                 )
                 db.session.add(new_user_vehicle)
                 story_vehicle_name = stolen_vehicle.name
                 story_vehicle_condition = condition
                 
                 # Minimal cash found in the car
                 money = random.randint(10, 100) 
             else:
                 pass
        
        # Item Theft Reward Logic
        elif hasattr(crime, 'reward_type') and crime.reward_type == 'item':
             item_reward = None
             item_condition = 100
             
             # 1. Check if specific item is assigned in DB
             if hasattr(crime, 'reward_item_id') and crime.reward_item_id:
                 item_reward = db.session.get(Item, crime.reward_item_id)
             
             # 2. Fallback to hardcoded map (Legacy support)
             if not item_reward:
                 crime_rewards = {
                     'سرقة كشك': ['رزمة دخان مهرب'],
                     'سرقة هاتف': ['هاتف مسروق'],
                     'سرقة دراجة': ['دراجة هوائية مسروقة'],
                     'سطو على محل مجوهرات': ['مجوهرات مسروقة', 'ساعة يد فاخرة مسروقة'],
                     'تجارة أسلحة صغيرة': ['سكينة مطبخ', 'عصا بيسبول', 'شفرة', 'جنزير', 'هراوة شرطة', 'مسدس حلوان']
                 }
                 potential_items = crime_rewards.get(crime.name)
                 if potential_items:
                     item_name = random.choice(potential_items)
                     item_reward = Item.query.filter_by(name=item_name).first()
             
             if item_reward:
                 if not current_app.config.get('TESTING', False):
                     if random.random() < 0.15:
                         item_condition = 100
                     else:
                         item_condition = random.randint(55, 90) if item_reward.type == 'loot' else random.randint(70, 95)

                 new_user_item = UserItem(user_id=current_user.id, item_id=item_reward.id, quantity=1, condition=item_condition)
                 existing_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item_reward.id).first()
                 if existing_item:
                     existing_item.quantity += 1
                     if existing_item.condition is not None:
                         existing_item.condition = min(existing_item.condition, item_condition)
                 else:
                     db.session.add(new_user_item)
                 story_item_name = item_reward.name
                 story_item_condition = item_condition

        # Add Money using ResourceService for atomicity
        changes = {
            'money': money,
            'exp': xp_reward
        }
        ResourceService.modify_resources(current_user.id, changes, 'crime_success', auto_commit=False, expected_version=current_user.version)
        current_user.add_rank_points(1)
        try:
            try:
                heat_base = int(SystemConfig.get_value("crime_heat_gain_base", "2") or 2)
            except:
                heat_base = 2
            heat_gain = heat_base + int(crime.min_level / 10) + int(crime.energy_cost / 20)
            if getattr(crime, "reward_type", "money") in {"item", "vehicle"}:
                heat_gain += 1
            current_user.add_heat(heat_gain, now=now)
        except Exception:
            pass
        leveled_up = False
        try:
            if current_user.check_level_up():
                leveled_up = True
        except Exception:
            pass
            
        log = UserLog(
            user_id=current_user.id, 
            action='CRIME_SUCCESS', 
            details=f"Crime: {crime.name}, Money: {money}, XP: {xp_reward}", 
            result='success', 
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log)
        db.session.commit()
        
        update_daily_task_progress(current_user, 'crime')

        action_lines = [
            'تسللت بهدوء…',
            'راقبت المكان دقيقة…',
            'خططت بسرعة ونفّذت…',
            'قلّبتها مزبوط وما خليت أثر…',
        ]
        extra_lines = [
            '💨 رميت عليهم قنبلة دخانية!',
            '🚧 قفزت فوق حاجز بسرعة!',
            '🕶️ غيّرت مسارك من الزحمة!',
            '⚡ كانت حركة سريعة وخاطفة!',
            '🔇 اشتغلت بصمت…',
        ]
        action = random.choice(action_lines)
        extra = random.choice(extra_lines)

        animation = 'spark'
        badge = 'نجاح'
        image = crime.image or 'crimes/wallet.jpg'

        if getattr(crime, 'reward_type', 'money') == 'vehicle':
            animation = 'speed'
            extra = random.choice(['🚗 دعست بنزين وطلعت زي الرصاصة!', '🛞 لفّيت الدركسيون وهربت!', '💨 غيّرت شارع بآخر لحظة!'])
        elif getattr(crime, 'reward_type', 'money') == 'item':
            animation = 'spark'
            extra = random.choice(['🧤 لبست كفوف وخطفت الغنيمة!', '🧰 فتحت القفل بحركة سريعة!', '🕳️ خبّيتها قبل ما ينتبهوا!'])

        parts = [
            {'msgid': 'كفو! نفذت الجريمة.'},
            {'msgid': action},
            {'msgid': extra},
            {'msgid': 'ونجحت!'},
        ]

        stats = {
            'money': money,
            'exp': xp_reward
        }

        next_url = url_for('main.crimes')
        alt_url = None
        alt_label = None

        if story_vehicle_name:
            parts.append({'msgid': 'سرقت %(name)s.', 'params': {'name': story_vehicle_name}})
            parts.append({'msgid': 'بس حالتها %(cond)s%% وبدها تصليح بالمرآب.', 'params': {'cond': story_vehicle_condition}})
            stats['vehicle'] = story_vehicle_name
            stats['vehicle_condition'] = story_vehicle_condition
            alt_url = url_for('garage.index')
            alt_label = 'المرآب'

        if story_item_name:
            parts.append({'msgid': 'لقيت %(item)s.', 'params': {'item': story_item_name}})
            if story_item_condition is not None and story_item_condition < 100:
                parts.append({'msgid': 'كانت حالتها %(cond)s%%، بدها تصليح قبل البيع.', 'params': {'cond': story_item_condition}})
            stats['item'] = story_item_name
            stats['item_condition'] = story_item_condition
            alt_url = url_for('black_market.index')
            alt_label = 'السوق السوداء'

        parts.append({'msgid': 'وكسبت %(money)s شيكل و %(exp)s خبرة.', 'params': {'money': money, 'exp': xp_reward}})
        
        # Calculate gang bonus percent for display if it was applied
        gang_bonus_percent = 0
        if current_user.gang_id:
            gang_bonus_percent = 5  # Default or fetch from Gang logic if complex
            
        if gang_bonus_percent > 0:
             parts.append({'msgid': '(بونص عصابة +%(bonus)s%%)', 'params': {'bonus': gang_bonus_percent}})
        if leveled_up:
            parts.append({'msgid': 'مبروك! وصلت للمستوى %(level)s.', 'params': {'level': current_user.level}})
            stats['level'] = current_user.level

        session['story'] = {
            'title_msgid': crime.name,
            'subtitle_msgid': crime.description if crime.description else None,
            'text_parts': parts,
            'image': image,
            'animation': animation,
            'status': 'success',
            'badge_msgid': badge,
            'next_url': next_url,
            'alt_url': alt_url,
            'alt_label_msgid': alt_label,
            'stats': stats
        }

        return redirect(url_for('main.story'))
        
    else:
        # FAILED CRIME -> POLICE CHASE
        # Instead of simple fail, we trigger a chase
        try:
            heat_gain = 6 + int(crime.min_level / 5)
            
            # Gang Buff (Security Detail) - Reduce Heat Gain
            try:
                from services.gang_service import GangService
                gang_buff = GangService.get_gang_buff(current_user.gang_id, 'security_detail')
                if gang_buff > 0:
                     heat_gain = int(heat_gain * (1 - gang_buff / 100))
            except Exception:
                pass
                
            current_user.add_heat(heat_gain, now=now)
        except Exception:
            pass
        
        log = UserLog(
            user_id=current_user.id, 
            action='CRIME_FAIL', 
            details=f"Crime: {crime.name} failed, started chase", 
            result='fail', 
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log)
        db.session.commit() # Save cooldown/energy usage
        
        # Setup Chase Session
        session['active_chase'] = True
        
        # Critical Fail Logic (High Roll)
        is_critical_fail = roll > 95
        difficulty_mult = 2 if is_critical_fail else 1
        
        session['chase_difficulty'] = max(1, (crime.min_level // 5) * difficulty_mult) 
        
        if is_critical_fail:
            text = '😱 كارثة! فشلت الجريمة بشكل مريع والشرطة مستنفرة جداً!'
        else:
            text = 'فشلت الجريمة والشرطة تلاحقك! اهرب بسرعة!'

        session['story'] = {
            'title_msgid': crime.name,
            'subtitle_msgid': crime.description if crime.description else None,
            'text_parts': [
                {'msgid': text},
                {'msgid': '🔥 جهّز خطة هروب بسرعة…'},
            ],
            'image': crime.image or 'crimes/wallet.jpg',
            'animation': 'smoke',
            'status': 'danger',
            'badge_msgid': 'مطاردة',
            'next_url': url_for('police_chase.index'),
            'alt_url': url_for('main.crimes'),
            'alt_label_msgid': 'رجوع للجرائم',
            'stats': None
        }

        return redirect(url_for('main.story'))
        
    return redirect(url_for('main.crimes'))

@bp.route('/inventory')
@login_required
def inventory():
    user_items = UserItem.query.filter_by(user_id=current_user.id).all()
    return render_template('inventory.html', items=user_items)

@bp.route('/equip_item/<int:item_id>')
@login_required
@limiter.limit("20 per minute")
def equip_item(item_id):
    # Lock the item to prevent concurrent equip/unequip
    user_item = db.session.query(UserItem).filter_by(id=item_id).with_for_update().first()
    if not user_item:
        abort(404)
    
    if user_item.user_id != current_user.id:
        flash(_('هذا الغرض ليس ملكك!'), 'danger')
        return redirect(url_for('main.inventory'))
        
    # Unequip current item of same type
    # We also need to lock the currently equipped item to prevent race conditions there
    current_equipped = UserItem.query.join(Item).filter(
        UserItem.user_id == current_user.id,
        UserItem.is_equipped == True,
        Item.type == user_item.item.type
    ).with_for_update().first()
    
    if current_equipped:
        current_equipped.is_equipped = False
        
    user_item.is_equipped = True
    db.session.commit()
    
    flash(_('تم تجهيز %(item)s.', item=user_item.item.name), 'success')
    return redirect(url_for('main.inventory'))

@bp.route('/unequip_item/<int:item_id>')
@login_required
@limiter.limit("20 per minute")
def unequip_item(item_id):
    user_item = db.session.get(UserItem, item_id)
    if not user_item:
        abort(404)
    
    if user_item.user_id != current_user.id:
        flash(_('هذا الغرض ليس ملكك!'), 'danger')
        return redirect(url_for('main.inventory'))
        
    if not user_item.is_equipped:
        flash(_('هذا الغرض غير مجهز أصلاً.'), 'warning')
        return redirect(url_for('main.inventory'))
        
    user_item.is_equipped = False
    db.session.commit()
    
    flash(_('تم خلع %(name)s.', name=user_item.item.name), 'success')
    return redirect(url_for('main.inventory'))

# --- Intel & Hacking Routes ---

@bp.route('/intel_center')
@login_required
def intel_center():
    return render_template('intel_center.html', user=current_user)

@bp.route('/investigate', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def investigate():
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك إجراء تحريات!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك إجراء تحريات!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك إجراء تحريات!'), 'danger')
            return redirect(url_for('gym.index'))

    target_username = request.form.get('username')
    target = User.query.filter_by(username=target_username).first()
    
    if not target:
        flash(_('لم يتم العثور على هذا اللاعب!'), 'danger')
        return redirect(url_for('main.intel_center'))
        
    if target.id == current_user.id:
        flash(_('بدك تتجسس على حالك يا عبيط؟'), 'warning')
        return redirect(url_for('main.intel_center'))
        
    # Cost
    energy_cost = 10
    money_cost = 500
    
    if current_user.energy < energy_cost:
        flash(_('ما عندك طاقة كافية!'), 'danger')
        return redirect(url_for('main.intel_center'))
        
    if current_user.money < money_cost:
        flash(_('ما معك كاش كافي! العملية بدها 500 شيكل.'), 'danger')
        return redirect(url_for('main.intel_center'))
        
    # Process
    if not ResourceService.modify_resources(current_user.id, {'energy': -energy_cost, 'money': -money_cost}, 'investigate_cost', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء العملية.'), 'danger')
        return redirect(url_for('main.intel_center'))
    
    # Success Chance
    # Base 50% + (My Intel - Target Intel) * 2
    chance = 50 + (current_user.intelligence - target.intelligence) * 2
    chance = min(90, max(10, chance)) # Cap between 10% and 90%
    
    if random.randint(1, 100) <= chance:
        # Success
        report = {
            'user_id': target.id, # Added ID for Attack Link
            'username': target.username,
            'level': target.level,
            'strength': target.strength,
            'agility': target.agility,
            'defense': target.defense,
            'intelligence': target.intelligence,
            'money': target.money, # Spy on cash!
            'health': target.health
        }
        
        # Log the investigation
        log = InvestigationLog(
            investigator_id=current_user.id,
            target_id=target.id,
            success=True,
            details=str(report)
        )
        db.session.add(log)

        # Chance to improve intelligence
        if random.random() < 0.2: # 20% chance
            ResourceService.modify_resources(current_user.id, {'intelligence': 1}, 'investigate_skill_gain', auto_commit=False, expected_version=current_user.version)
            flash(_('تطورت مهاراتك الاستخباراتية! (+1 ذكاء)'), 'success')

        db.session.commit()
        flash(_('تمت العملية بنجاح! جاري عرض التقرير...'), 'success')
        return render_template('intel_report.html', report=report, user=current_user)
    else:
        # Fail
        log = InvestigationLog(
            investigator_id=current_user.id,
            target_id=target.id,
            success=False,
            details="Failed investigation attempt"
        )
        db.session.add(log)
        
        db.session.commit()
        flash(_('فشلت العملية! كشفوك وهربت بصعوبة.'), 'danger')
        return redirect(url_for('main.intel_center'))

@bp.route('/hack_player', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def hack_player():
    target_username = request.form.get('username')
    target = User.query.filter_by(username=target_username).first()
    
    if not target:
        flash(_('لم يتم العثور على هذا اللاعب!'), 'danger')
        return redirect(url_for('main.intel_center'))
        
    if target.id == current_user.id:
        flash(_('بدك تسرق حالك؟'), 'warning')
        return redirect(url_for('main.intel_center'))
    
    # Cost
    energy_cost = 20
    
    # Atomic Deduction
    if not ResourceService.modify_resources(current_user.id, {'energy': -energy_cost}, 'hack_player_cost', auto_commit=False, expected_version=current_user.version):
        flash(_('ما عندك طاقة كافية!'), 'danger')
        return redirect(url_for('main.intel_center'))
        
    # Logic
    
    # Must have higher intel to even try effectively
    if current_user.intelligence < target.intelligence:
        flash(_('نظام الحماية عنده قوي جداً! فشلت العملية.'), 'danger')
        db.session.commit()
        return redirect(url_for('main.intel_center'))
        
    # Success Chance based on intel difference
    chance = 40 + (current_user.intelligence - target.intelligence) * 2
    chance = min(80, max(5, chance))
    
    if random.randint(1, 100) <= chance:
        # Steal 1-5% of cash
        percent = random.randint(1, 5) / 100
        stolen = int(target.money * percent)
        if stolen < 10:
            stolen = 10 # Minimum
            
        if target.money < stolen:
            stolen = target.money
            
        # Atomic Transfer
        try:
            # Deduct from target
            if not ResourceService.modify_resources(target.id, {'money': -stolen}, f'hacked_by_{current_user.id}', auto_commit=False, expected_version=target.version):
                raise Exception("Failed to deduct from target")
            
            # Add to hacker
            changes = {'money': stolen, 'exp': 20}
            if random.random() < 0.1: # 10% chance to gain intel
                changes['intelligence'] = 1
                flash(_('تطورت مهارتك في القرصنة! (+1 ذكاء)'), 'success')
                
            if not ResourceService.modify_resources(current_user.id, changes, f'hack_player_success_{target.id}', auto_commit=False, expected_version=current_user.version):
                raise Exception("Failed to add to hacker")
                
            log = UserLog(
                user_id=current_user.id,
                action='HACK_PLAYER_SUCCESS',
                details=f"Hacked {target.username} for {stolen} money",
                result='success',
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            flash(_('تم اختراق الحساب! سرقت %(amount)s شيكل من %(user)s', amount=stolen, user=target.username), 'success')
        except Exception:
            db.session.rollback()
            flash(_('حدث خطأ أثناء العملية.'), 'danger')
            return redirect(url_for('main.intel_center'))
    else:
        # Fail
        log = UserLog(
            user_id=current_user.id,
            action='HACK_PLAYER_FAIL',
            details=f"Failed to hack {target.username}",
            result='fail',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        flash(_('فشل الاختراق! الحماية كشفتك.'), 'danger')
        db.session.commit()
        
    return redirect(url_for('main.intel_center'))

@bp.route('/hack_bank', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def hack_bank():
    # PvE Hacking
    # High risk, High reward
    energy_cost = 50
    if current_user.energy < energy_cost:
        flash(_('تحتاج 50 طاقة لقرصنة البنك!'), 'danger')
        return redirect(url_for('main.intel_center'))
        
    # Atomic Deduction
    if not ResourceService.modify_resources(current_user.id, {'energy': -energy_cost}, 'hack_bank_cost', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء العملية.'), 'danger')
        return redirect(url_for('main.intel_center'))
    
    # Required Intel
    if current_user.intelligence < 50:
        db.session.rollback()
        flash(_('ذكاؤك لا يكفي لاختراق البنك المركزي! تحتاج 50 ذكاء على الأقل.'), 'danger')
        return redirect(url_for('main.intel_center'))
        
    # Chance
    chance = 30 + (current_user.intelligence - 50) # Base 30% + 1% per intel over 50
    chance = min(70, chance)
    
    if random.randint(1, 100) <= chance:
        # Success
        reward = random.randint(10000, 50000)
        
        # Atomic Reward
        changes = {
            'money': reward,
            'exp': 500,
            'intelligence': 2
        }
        
        # Refresh user to get latest version after cost deduction
        db.session.refresh(current_user)
        
        if not ResourceService.modify_resources(current_user.id, changes, 'hack_bank_success', auto_commit=False, expected_version=current_user.version):
            db.session.rollback()
            flash(_('حدث خطأ أثناء إضافة المكافأة. اتصل بالدعم الفني.'), 'error')
            return redirect(url_for('main.intel_center'))

        log = UserLog(
            user_id=current_user.id,
            action='HACK_BANK_SUCCESS',
            details=f"Hacked Central Bank for {reward} money",
            result='success',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log)
        db.session.commit()
        flash(_('عملية أسطورية! اخترقت البنك وسرقت %(amt)s شيكل!', amt=reward), 'success')
    else:
        # Fail -> Jail? For now just fail and lose energy
        log = UserLog(
            user_id=current_user.id,
            action='HACK_BANK_FAIL',
            details="Failed to hack Central Bank",
            result='fail',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log)
        flash(_('نظام الحماية كشفك! هربت بأعجوبة ولم تحصل على شيء.'), 'danger')
        db.session.commit()
        
    return redirect(url_for('main.intel_center'))

@bp.route('/create_lobby/<int:crime_id>')
@login_required
@limiter.limit("5 per minute")
def create_lobby(crime_id):
    if not current_user.is_verified:
        flash(_('يجب تفعيل الحساب قبل المشاركة في الجرائم المنظمة.'), 'warning')
        return redirect(url_for('main.unconfirmed'))
    
    # Lock User to prevent multiple lobby creations
    # We use a dummy update or select for update on User to serialize requests for this user
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    # 0. Status Check (Jail/Hospital)
    now = datetime.now(timezone.utc)
    
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك المشاركة في الجرائم!'), 'danger')
            return redirect(url_for('jail.index'))

    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك المشاركة في الجرائم!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب في الجيم ولا يمكنك المشاركة في الجرائم!'), 'danger')
            return redirect(url_for('gym.index'))

    # 1. Check Cooldown
    cooldown = UserOrganizedCrimeCooldown.query.filter_by(user_id=current_user.id, crime_id=crime_id).first()
    if cooldown:
        ends_at = cooldown.cooldown_until
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        if ends_at > datetime.now(timezone.utc):
            remaining = ends_at - datetime.now(timezone.utc)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            flash(_('عليك الانتظار %(hours)s ساعة و %(minutes)s دقيقة قبل تكرار هذه الجريمة!', hours=hours, minutes=minutes), 'danger')
            return redirect(url_for('main.organized_crimes'))

    # 2. Check Active Lobby
    existing_participation = LobbyParticipant.query.join(CrimeLobby).filter(
        LobbyParticipant.user_id == current_user.id,
        CrimeLobby.status.in_(['recruiting', 'in_progress'])
    ).first()
    
    if existing_participation:
        flash(_('أنت مشارك بالفعل في جريمة منظمة أخرى!'), 'warning')
        return redirect(url_for('main.lobby', lobby_id=existing_participation.lobby_id))

    crime = db.session.get(OrganizedCrime, crime_id)
    if not crime or not crime.is_active:
        abort(404)
        
    # Check Rank/Level for creator
    min_creator_rank_level = int(SystemConfig.get_value('organized_crimes_min_creator_rank_level', '20'))
    effective_level = current_user.level + (current_user.rank_points_value // 50) if hasattr(current_user, 'rank_points_value') else current_user.level
    
    if effective_level < min_creator_rank_level:
        flash(_('رتبتك لا تسمح بإنشاء مجموعة!'), 'danger')
        return redirect(url_for('main.organized_crimes'))

    if current_user.energy < crime.energy_cost:
        flash(_('لا تملك طاقة كافية لبدء العملية.'), 'danger')
        return redirect(url_for('main.organized_crimes'))

    # Create Lobby
    lobby = CrimeLobby(
        crime_id=crime.id,
        leader_id=current_user.id,
        status='recruiting'
    )
    db.session.add(lobby)
    db.session.flush() # Get ID
    
    # Add Leader as Participant (Role needs to be selected? Default to first role or let them choose later?)
    # Usually leader picks role first. Let's say "Leader" or just None for now and they pick in lobby.
    # But LobbyParticipant requires role_name (nullable=False in model?). 
    # Let's check model.
    # Line 53: role_name = db.Column(db.String(50), nullable=False)
    # We'll assign the first role available as default, or "Leader" if not defined.
    first_role = crime.roles_config[0]['name'] if crime.roles_config else 'Leader'
    
    participant = LobbyParticipant(
        lobby_id=lobby.id,
        user_id=current_user.id,
        role_name=first_role,
        is_ready=True
    )
    db.session.add(participant)
    
    # Atomic Energy Deduction
    if not ResourceService.modify_resources(current_user.id, {'energy': -crime.energy_cost}, 'create_lobby_cost', auto_commit=False, expected_version=current_user.version):
        db.session.rollback()
        flash(_('فشلت العملية! ربما تغيرت بياناتك أو لا تملك طاقة كافية.'), 'danger')
        return redirect(url_for('main.organized_crimes'))
    
    db.session.commit()
    
    flash(_('تم إنشاء المجموعة بنجاح!'), 'success')
    return redirect(url_for('main.lobby', lobby_id=lobby.id))

@bp.route('/lobby/<int:lobby_id>')
@login_required
def lobby(lobby_id):
    if not current_user.is_verified:
        flash(_('يجب تفعيل الحساب قبل المشاركة في الجرائم المنظمة.'), 'warning')
        return redirect(url_for('main.unconfirmed'))
    lobby = db.session.get(CrimeLobby, lobby_id)
    if not lobby:
        abort(404)

    if _expire_lobby_if_needed(lobby):
        flash(_('انتهت صلاحية هذه العملية المنظمة لعدم اكتمال الفريق خلال 24 ساعة.'), 'warning')
        return redirect(url_for('main.organized_crimes'))

    roles_config = lobby.crime.roles_config or []
    lobby_roles = []
    for role_def in roles_config:
        role_name = role_def.get('name') if isinstance(role_def, dict) else None
        participant = None
        if role_name:
            participant = next((p for p in lobby.participants if p.role_name == role_name), None)
        lobby_roles.append({'def': role_def, 'participant': participant})

    if not lobby_roles:
        for p in lobby.participants:
            lobby_roles.append({
                'def': {'name': p.role_name, 'description': '', 'min_stats': {}},
                'participant': p
            })

    current_participant = next((p for p in lobby.participants if p.user_id == current_user.id), None)
    is_leader = lobby.leader_id == current_user.id
        
    # Dynamic penalties preview
    try:
        money_penalty = max(100, int((lobby.crime.money_reward_min or 0) * 0.05))
    except:
        money_penalty = 100
    try:
        xp_penalty = max(50, int((lobby.crime.exp_reward or 0) * 0.1))
    except:
        xp_penalty = 50
    try:
        en_penalty_calc = (lobby.crime.energy_cost or 10) // 2
        energy_penalty = max(5, min(20, en_penalty_calc))
    except:
        energy_penalty = 10
    
    # Override from requirements JSON if configured
    required_item = None
    required_item_obj = None
    has_required_item = False
    
    try:
        import json
        reqs = json.loads(lobby.crime.requirements) if lobby.crime.requirements else {}
        
        # Check for required item
        if 'required_item' in reqs:
            required_item_name = reqs['required_item']
            required_item_obj = Item.query.filter_by(name=required_item_name).first()
            if required_item_obj:
                required_item = required_item_obj
                # Check if anyone in lobby has it
                for p in lobby.participants:
                    user_has = UserItem.query.filter_by(user_id=p.user_id).join(Item).filter(Item.name == required_item_name).first()
                    if user_has:
                        has_required_item = True
                        break
        
        pct_money = float(reqs.get('penalty_money_pct', 0))
        min_money = int(reqs.get('penalty_money_min_abs', 0))
        if pct_money and pct_money > 0:
            base_min = int((lobby.crime.money_reward_min or 0) * pct_money)
            money_penalty = max(money_penalty, base_min)
        if min_money and min_money > 0:
            money_penalty = max(money_penalty, min_money)
        
        pct_xp = float(reqs.get('penalty_xp_pct', 0))
        min_xp = int(reqs.get('penalty_xp_min_abs', 0))
        if pct_xp and pct_xp > 0:
            base_xp = int((lobby.crime.exp_reward or 0) * pct_xp)
            xp_penalty = max(xp_penalty, base_xp)
        if min_xp and min_xp > 0:
            xp_penalty = max(xp_penalty, min_xp)
        
        min_en = int(reqs.get('penalty_energy_min', 0))
        max_en = int(reqs.get('penalty_energy_max', 0))
        if min_en and min_en > 0:
            energy_penalty = max(energy_penalty, min_en)
        if max_en and max_en > 0:
            energy_penalty = min(energy_penalty, max_en)
    except Exception:
        pass
        
    return render_template('lobby.html', lobby=lobby, user=current_user,
                           money_penalty=money_penalty, xp_penalty=xp_penalty, energy_penalty=energy_penalty,
                           lobby_roles=lobby_roles, current_participant=current_participant, is_leader=is_leader,
                           required_item=required_item, has_required_item=has_required_item)


@bp.route('/broadcast_lobby_invites/<int:lobby_id>', methods=['POST'])
@login_required
@limiter.limit("2 per minute")
def broadcast_lobby_invites(lobby_id):
    lobby = db.session.get(CrimeLobby, lobby_id)
    if not lobby:
        abort(404)
    if lobby.leader_id != current_user.id:
        abort(403)
    if _expire_lobby_if_needed(lobby):
        flash(_('انتهت صلاحية هذه العملية المنظمة.'), 'warning')
        return redirect(url_for('main.organized_crimes'))
    if lobby.status != 'recruiting':
        flash(_('المجموعة غير متاحة!'), 'warning')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))

    now = datetime.now(timezone.utc)
    last = _broadcast_cache.get(lobby.id)
    if last:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last < timedelta(hours=1):
            remaining = timedelta(hours=1) - (now - last)
            minutes = int(remaining.total_seconds() // 60) or 1
            flash(_('تم إرسال الدعوات بالفعل. انتظر حوالي %(m)d دقيقة قبل التجديد.', m=minutes), 'info')
            return redirect(url_for('main.lobby', lobby_id=lobby.id))

    recipients = User.query.filter(User.id != current_user.id).all()
    join_link = url_for('main.lobby', lobby_id=lobby.id)
    for u in recipients:
        try:
            send_notification(
                user_id=u.id,
                title=str(_('دعوة للمشاركة في جريمة منظمة')),
                message=str(_('القائد %(leader)s دعاك للمشاركة في "%(crime)s". سارع لاختيار دورك!', leader=current_user.username, crime=lobby.crime.name)),
                type='info',
                link=join_link
            )
        except Exception:
            continue

    _broadcast_cache[lobby.id] = now
    flash(_('تم إرسال الدعوات لجميع اللاعبين. صلاحية الدعوات ساعة واحدة تقريباً.'), 'success')
    return redirect(url_for('main.lobby', lobby_id=lobby.id))

@bp.route('/toggle_ready/<int:lobby_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def toggle_ready(lobby_id):
    lobby = db.session.get(CrimeLobby, lobby_id)
    if not lobby:
        abort(404)
    participant = LobbyParticipant.query.filter_by(lobby_id=lobby.id, user_id=current_user.id).first()
    if not participant:
        abort(403)
    if lobby.status != 'recruiting':
        flash(_('المجموعة غير متاحة!'), 'warning')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))

    participant.is_ready = not participant.is_ready
    db.session.commit()
    return redirect(url_for('main.lobby', lobby_id=lobby.id))

@bp.route('/kick_member/<int:lobby_id>/<int:user_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def kick_member(lobby_id, user_id):
    lobby = db.session.get(CrimeLobby, lobby_id)
    if not lobby:
        abort(404)
    if lobby.leader_id != current_user.id:
        abort(403)
    if user_id == current_user.id:
        flash(_('لا يمكنك طرد نفسك.'), 'warning')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))

    participant = LobbyParticipant.query.filter_by(lobby_id=lobby.id, user_id=user_id).first()
    if not participant:
        abort(404)

    db.session.delete(participant)
    db.session.commit()
    flash(_('تم طرد العضو من المجموعة.'), 'success')
    return redirect(url_for('main.lobby', lobby_id=lobby.id))

@bp.route('/join_lobby/<int:lobby_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def join_lobby(lobby_id):
    if not current_user.is_verified:
        flash(_('يجب تفعيل الحساب قبل المشاركة في الجرائم المنظمة.'), 'warning')
        return redirect(url_for('main.unconfirmed'))
    # 0. Status Check (Jail/Hospital)
    now = datetime.now(timezone.utc)
    
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك المشاركة في الجرائم!'), 'danger')
            return redirect(url_for('jail.index'))

    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك المشاركة في الجرائم!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب في الجيم ولا يمكنك المشاركة في الجرائم!'), 'danger')
            return redirect(url_for('gym.index'))

    # 2. Check Active Lobby
    existing_participation = LobbyParticipant.query.join(CrimeLobby).filter(
        LobbyParticipant.user_id == current_user.id,
        CrimeLobby.status.in_(['recruiting', 'in_progress'])
    ).first()
    
    if existing_participation:
        flash(_('أنت مشارك بالفعل في جريمة منظمة أخرى!'), 'warning')
        return redirect(url_for('main.lobby', lobby_id=existing_participation.lobby_id))

    lobby = db.session.query(CrimeLobby).filter_by(id=lobby_id).with_for_update().first()
    if not lobby:
        flash(_('المجموعة غير متاحة!'), 'danger')
        return redirect(url_for('main.organized_crimes'))

    # Check Specific Cooldown
    cooldown = UserOrganizedCrimeCooldown.query.filter_by(user_id=current_user.id, crime_id=lobby.crime_id).first()
    if cooldown:
        ends_at = cooldown.cooldown_until
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        if ends_at > datetime.now(timezone.utc):
            remaining = ends_at - datetime.now(timezone.utc)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            flash(_('عليك الانتظار %(hours)s ساعة و %(minutes)s دقيقة قبل تكرار هذه الجريمة!', hours=hours, minutes=minutes), 'danger')
            return redirect(url_for('main.organized_crimes'))

    if _expire_lobby_if_needed(lobby):
        flash(_('انتهت صلاحية هذه العملية المنظمة.'), 'warning')
        return redirect(url_for('main.organized_crimes'))

    if lobby.status != 'recruiting':
        flash(_('المجموعة غير متاحة!'), 'danger')
        return redirect(url_for('main.organized_crimes'))

    roles_config = lobby.crime.roles_config or []
    max_slots = max(int(lobby.crime.min_members or 0), int(getattr(lobby.crime, 'max_members', 0) or 0), len(roles_config))
    max_slots = max(1, max_slots)
    if len(lobby.participants) >= max_slots:
        flash(_('المجموعة ممتلئة!'), 'danger')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))
        
    # Check Role
    role_name = request.form.get('role') or request.form.get('role_name')
    if not role_name:
        flash(_('يجب اختيار دور للانضمام.'), 'warning')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))

    if roles_config:
        valid_roles = [r.get('name') for r in roles_config if isinstance(r, dict)]
        if role_name not in valid_roles:
            flash(_('هذا الدور غير متاح.'), 'warning')
            return redirect(url_for('main.lobby', lobby_id=lobby.id))

    # Check if role is already taken
    if any(p.role_name == role_name for p in lobby.participants):
        flash(_('هذا الدور مأخوذ بالفعل!'), 'warning')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))
        
    # Strict Role Requirement Check (Fair Play)
    role_def = next((r for r in roles_config if isinstance(r, dict) and r.get('name') == role_name), None)
    if role_def:
        min_stats = role_def.get('min_stats') or role_def.get('req') or {}
        for stat, req_val in min_stats.items():
            user_val = getattr(current_user, stat, 0)
            if user_val < req_val:
                flash(_('مهاراتك لا تسمح بهذا الدور! مطلوب %(stat)s: %(req)s وأنت لديك %(val)s.', 
                      stat=_(stat), req=req_val, val=user_val), 'danger')
                return redirect(url_for('main.lobby', lobby_id=lobby.id))
        
    participant = LobbyParticipant(
        lobby_id=lobby.id,
        user_id=current_user.id,
        role_name=role_name,
        is_ready=False
    )
    db.session.add(participant)
    db.session.commit()
    
    flash(_('تم الانضمام للمجموعة!'), 'success')
    return redirect(url_for('main.lobby', lobby_id=lobby.id))
    
@bp.route('/leave_lobby/<int:lobby_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def leave_lobby(lobby_id):
    lobby = db.session.query(CrimeLobby).filter_by(id=lobby_id).with_for_update().first()
    if not lobby:
        abort(404)
        
    participant = LobbyParticipant.query.filter_by(lobby_id=lobby.id, user_id=current_user.id).first()
    if not participant:
        abort(403)
        
    if lobby.leader_id == current_user.id:
        # If leader leaves, destroy lobby? or pass leadership?
        # Simple: Destroy lobby
        db.session.delete(lobby)
        flash(_('تم حل المجموعة لأن القائد غادر.'), 'warning')
        db.session.commit()
        return redirect(url_for('main.organized_crimes'))
    else:
        # Penalties on leaving (dynamic based on crime difficulty)
        try:
            money_penalty = max(100, int((lobby.crime.money_reward_min or 0) * 0.05))
        except:
            money_penalty = 100
        try:
            exp_penalty = max(50, int((lobby.crime.exp_reward or 0) * 0.1))
        except:
            exp_penalty = 50
        try:
            energy_penalty = max(5, min(20, ((lobby.crime.energy_cost or 10) // 2)))
        except:
            energy_penalty = 10
        
        # Override from requirements JSON if configured
        try:
            import json
            reqs = json.loads(lobby.crime.requirements) if lobby.crime.requirements else {}
            pct_money = float(reqs.get('penalty_money_pct', 0))
            min_money = int(reqs.get('penalty_money_min_abs', 0))
            if pct_money and pct_money > 0:
                base_min = int((lobby.crime.money_reward_min or 0) * pct_money)
                money_penalty = max(money_penalty, base_min)
            if min_money and min_money > 0:
                money_penalty = max(money_penalty, min_money)
            
            pct_xp = float(reqs.get('penalty_xp_pct', 0))
            min_xp = int(reqs.get('penalty_xp_min_abs', 0))
            if pct_xp and pct_xp > 0:
                base_xp = int((lobby.crime.exp_reward or 0) * pct_xp)
                exp_penalty = max(exp_penalty, base_xp)
            if min_xp and min_xp > 0:
                exp_penalty = max(exp_penalty, min_xp)
            
            min_en = int(reqs.get('penalty_energy_min', 0))
            max_en = int(reqs.get('penalty_energy_max', 0))
            if min_en and min_en > 0:
                energy_penalty = max(energy_penalty, min_en)
            if max_en and max_en > 0:
                energy_penalty = min(energy_penalty, max_en)
        except Exception:
            pass
        
        changes = {}
        if money_penalty > 0:
            changes['money'] = -money_penalty
        if exp_penalty > 0:
            changes['exp'] = -exp_penalty
        if energy_penalty > 0:
            changes['energy'] = -energy_penalty

        if changes:
            ResourceService.modify_resources(current_user.id, changes, 'organized_crime_leave_penalty', auto_commit=False, expected_version=current_user.version)
        
        db.session.delete(participant)
        db.session.commit()
        
        flash(_('انسحبت من المجموعة وتكبدت خسائر: -%(m)s$، -%(xp)s XP، -%(en)s طاقة.', m=money_penalty, xp=exp_penalty, en=energy_penalty), 'warning')
        return redirect(url_for('main.organized_crimes'))

@bp.route('/start_heist/<int:lobby_id>', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def start_heist(lobby_id):
    if not current_user.is_verified:
        flash(_('يجب تفعيل الحساب قبل المشاركة في الجرائم المنظمة.'), 'warning')
        return redirect(url_for('main.unconfirmed'))
    
    # Lock lobby to prevent race conditions (joining/leaving during start)
    lobby = db.session.query(CrimeLobby).filter_by(id=lobby_id).with_for_update().first()
    if not lobby:
        abort(404)
    if lobby.leader_id != current_user.id:
        abort(403)

    if _expire_lobby_if_needed(lobby):
        flash(_('انتهت صلاحية هذه العملية المنظمة.'), 'warning')
        return redirect(url_for('main.organized_crimes'))
        
    # Validate
    participants = lobby.participants
    if len(participants) < lobby.crime.min_members:
        flash(_('العدد غير مكتمل!'), 'danger')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))
        
    if not all(p.is_ready for p in participants):
        flash(_('جميع الأعضاء يجب أن يكونوا مستعدين!'), 'warning')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))

    # Check Participants Status (Jail/Hospital/Gym)
    now = datetime.now(timezone.utc)
    for p in participants:
        user = p.user
        
        # Jail Check
        if user.jail_until:
            jail_until = user.jail_until
            if jail_until.tzinfo is None:
                jail_until = jail_until.replace(tzinfo=timezone.utc)
            if jail_until > now:
                flash(_('لا يمكن بدء العملية! العضو %(user)s في السجن.', user=user.username), 'danger')
                return redirect(url_for('main.lobby', lobby_id=lobby.id))
        
        # Hospital Check
        if user.hospital_until:
            hospital_until = user.hospital_until
            if hospital_until.tzinfo is None:
                hospital_until = hospital_until.replace(tzinfo=timezone.utc)
            if hospital_until > now:
                flash(_('لا يمكن بدء العملية! العضو %(user)s في المستشفى.', user=user.username), 'danger')
                return redirect(url_for('main.lobby', lobby_id=lobby.id))
                
        # Gym Check
        if user.gym_until:
            gym_until = user.gym_until
            if gym_until.tzinfo is None:
                gym_until = gym_until.replace(tzinfo=timezone.utc)
            if gym_until > now:
                flash(_('لا يمكن بدء العملية! العضو %(user)s يتدرب في الجيم.', user=user.username), 'danger')
                return redirect(url_for('main.lobby', lobby_id=lobby.id))

    # Strict Role Requirement Check (Final Gate - Fair Play)
    crime = lobby.crime
    roles_config = crime.roles_config or []
    for p in participants:
        role_def = next((r for r in roles_config if isinstance(r, dict) and r.get('name') == p.role_name), None)
        if role_def:
            min_stats = role_def.get('min_stats') or role_def.get('req') or {}
            for stat, req_val in min_stats.items():
                user_val = getattr(p.user, stat, 0)
                if user_val < req_val:
                    flash(_('لا يمكن بدء العملية! العضو %(user)s لا يملك المهارات الكافية لدور %(role)s (مطلوب %(stat)s: %(req)s).', 
                          user=p.user.username, role=_(p.role_name), stat=_(stat), req=req_val), 'danger')
                    return redirect(url_for('main.lobby', lobby_id=lobby.id))

    # 1. Planning Time (Patience & Integration)
    planning_seconds = int(lobby.crime.planning_time_seconds or 10)
    
    created_at = lobby.created_at
    if created_at.tzinfo is None:
        # Heuristic to handle Naive DateTimes (Local vs UTC)
        # If created_at is significantly in the future relative to UTC, it's likely Local Time stored as Naive.
        if created_at > datetime.utcnow() + timedelta(minutes=10):
             now_ref = datetime.now() # Local Naive
        else:
             now_ref = datetime.utcnow() # UTC Naive
        elapsed_seconds = (now_ref - created_at).total_seconds()
    else:
        elapsed_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
        
    if elapsed_seconds < 0:
        elapsed_seconds = 0 # Prevent negative elapsed time due to clock skew

    if elapsed_seconds < planning_seconds:
        remaining = planning_seconds - elapsed_seconds
        flash(_('يجب التخطيط جيداً! انتظروا %(sec)s ثانية للمراجعة قبل البدء.', sec=int(remaining)), 'warning')
        return redirect(url_for('main.lobby', lobby_id=lobby.id))

    # 2. Item Requirements (Capabilities)
    import json
    try:
        if lobby.crime.requirements:
            reqs = json.loads(lobby.crime.requirements)
            if 'required_item' in reqs:
                item_name = reqs['required_item']
                # Check if anyone has it
                has_item = False
                for p in participants:
                    # Check UserItem
                    # Note: This query inside loop is not optimal but fine for small team size (max 4)
                    user_has = UserItem.query.filter_by(user_id=p.user_id).join(Item).filter(Item.name == item_name).first()
                    if user_has:
                        has_item = True
                        break
                
                if not has_item:
                     flash(_('تحتاجون إلى "%(item)s" لتنفيذ هذه العملية! يمكنكم شراؤها من السوق السوداء.', item=item_name), 'danger')
                     return redirect(url_for('main.lobby', lobby_id=lobby.id))
    except Exception:
        pass
        
    # --- Strategic Heist Logic ---
    crime = lobby.crime
    roles_config = crime.roles_config or []
    story_log = []
    story_log.append(_("بدأت عملية {crime} بقيادة {leader}...").format(crime=_(crime.name), leader=lobby.leader.username))
    
    # --- Strategic Heist Logic ---

    # 1. Consume Required Items
    requirements = json.loads(crime.requirements) if crime.requirements else {}
    
    # Global Item Deduction
    if 'required_item' in requirements:
        item_name = requirements['required_item']
        item = Item.query.filter_by(name=item_name).first()
        if item and item.type == 'consumable':
            # Find a donor
            for p in participants:
                user_item = UserItem.query.filter_by(user_id=p.user_id, item_id=item.id).with_for_update().first()
                if user_item and user_item.quantity > 0:
                    user_item.quantity -= 1
                    if user_item.quantity <= 0:
                        db.session.delete(user_item)
                    story_log.append(_("تم استخدام {item} من قبل {user}.").format(item=item.name, user=p.user.username))
                    break # Deduct once per heist

    # Per-Role Item Deduction
    for p in participants:
        role_def = next((r for r in roles_config if r['name'] == p.role_name), None)
        role_key = None
        if role_def and isinstance(role_def, dict):
            role_key = role_def.get('key')

        role_reqs = requirements.get(p.role_name, {})
        if (not role_reqs) and role_key:
            role_reqs = requirements.get(role_key, {})

        if 'item' in role_reqs:
             r_item_name = role_reqs['item']
             r_item = Item.query.filter_by(name=r_item_name).first()
             if r_item and r_item.type == 'consumable':
                 u_item = UserItem.query.filter_by(user_id=p.user_id, item_id=r_item.id).with_for_update().first()
                 if u_item and u_item.quantity > 0:
                     u_item.quantity -= 1
                     if u_item.quantity <= 0:
                         db.session.delete(u_item)
                     story_log.append(_("استهلك {user} أداة {item} للدور.").format(user=p.user.username, item=r_item.name))

    # 2. Base Probability & Setup
    success_probability = 50 # Start with 50/50
    participant_performance = {}
    
    # 3. Evaluate Each Role (Capabilities & Stats)
    for p in participants:
        role_def = next((r for r in roles_config if r['name'] == p.role_name), None)
        if not role_def:
            continue
            
        user = p.user
        role_performance = 0 # -10 to +10
        
        # Check Stats
        min_stats = {}
        if isinstance(role_def, dict):
            min_stats = role_def.get('min_stats') or role_def.get('req') or {}
        
        # Intelligence (Planning/Hacking)
        if 'intelligence' in min_stats:
            req = min_stats['intelligence']
            diff = user.intelligence - req
            if diff >= 0:
                role_performance += 5 + (diff // 10)
                story_log.append(_("✅ {role} ({user}): أدى دوره بذكاء خارق! (+{bonus}%)").format(role=_(p.role_name), user=user.username, bonus=5 + (diff // 10)))
            else:
                role_performance -= 10
                story_log.append(_("⚠️ {role} ({user}): واجه صعوبات تقنية. (-10%)").format(role=_(p.role_name), user=user.username))
                
        # Strength (Enforcer/Breacher)
        if 'strength' in min_stats:
            req = min_stats['strength']
            diff = user.strength - req
            if diff >= 0:
                role_performance += 5 + (diff // 10)
                story_log.append(_("💪 {role} ({user}): سيطر على الوضع بقوة! (+{bonus}%)").format(role=_(p.role_name), user=user.username, bonus=5 + (diff // 10)))
            else:
                role_performance -= 10
                story_log.append(_("⚠️ {role} ({user}): لم يستطع كسر الدفاعات بسرعة. (-10%)").format(role=_(p.role_name), user=user.username))
                
        # Agility (Driver/Runner)
        if 'agility' in min_stats:
            req = min_stats['agility']
            diff = user.agility - req
            if diff >= 0:
                role_performance += 5 + (diff // 10)
                story_log.append(_("🚗 {role} ({user}): قاد الفريق ببراعة وسرعة! (+{bonus}%)").format(role=_(p.role_name), user=user.username, bonus=5 + (diff // 10)))
            else:
                role_performance -= 10
                story_log.append(_("⚠️ {role} ({user}): تأخر في الوصول لنقطة الهروب. (-10%)").format(role=_(p.role_name), user=user.username))
        
        if 'defense' in min_stats:
            req = min_stats['defense']
            diff = user.defense - req
            if diff >= 0:
                role_performance += 4 + (diff // 10)
                story_log.append(_("🛡️ {role} ({user}): صدّ الضغط وحمى الفريق! (+{bonus}%)").format(role=_(p.role_name), user=user.username, bonus=4 + (diff // 10)))
            else:
                role_performance -= 8
                story_log.append(_("⚠️ {role} ({user}): انهك من الضغط وتباطأ. (-8%)").format(role=_(p.role_name), user=user.username))

        # Cap performance impact per user
        role_performance = max(-15, min(15, role_performance))
        participant_performance[p.user_id] = role_performance
        success_probability += role_performance
        
    # 4. Vehicle / Garage Integration
    # Check if a Driver exists or if the crime implies a need for speed
    driver_participant = next((p for p in participants if 'driver' in p.role_name.lower() or 'سائق' in p.role_name), None)
    
    if driver_participant:
        # Check their active vehicle
        active_vehicle = UserVehicle.query.filter_by(user_id=driver_participant.user_id, is_active=True).first()
        if active_vehicle:
            # Check vehicle stats (price as proxy for quality)
            vehicle_quality = active_vehicle.vehicle.price / 10000 
            vehicle_bonus = min(15, int(vehicle_quality))
            
            success_probability += vehicle_bonus
            story_log.append(_("🏎️ السائق {user} يستخدم سيارة {car} المعدلة! (+{bonus}%)").format(
                user=driver_participant.user.username, 
                car=active_vehicle.vehicle.name,
                bonus=vehicle_bonus
            ))
        else:
            success_probability -= 10
            story_log.append(_("⚠️ السائق {user} لا يملك سيارة مجهزة! الهروب سيكون صعباً. (-10%)").format(user=driver_participant.user.username))
    else:
        # No specific driver, check if anyone has a high-end vehicle to help
        best_vehicle_bonus = 0
        owner_name = ""
        vehicle_name = ""
        
        for p in participants:
             active_vehicle = UserVehicle.query.filter_by(user_id=p.user_id, is_active=True).first()
             if active_vehicle:
                 bonus = min(10, int(active_vehicle.vehicle.price / 15000))
                 if bonus > best_vehicle_bonus:
                     best_vehicle_bonus = bonus
                     owner_name = p.user.username
                     vehicle_name = active_vehicle.vehicle.name
        
        if best_vehicle_bonus > 0:
            success_probability += best_vehicle_bonus
            story_log.append(_("🚗 الفريق يستخدم سيارة {user} ({car}) للهروب! (+{bonus}%)").format(
                user=owner_name, car=vehicle_name, bonus=best_vehicle_bonus
            ))

    # 5. Random Events & Health Risks (The "Chaos" Factor)
    chaos_roll = random.randint(1, 20)
    injuries = {} # Store injuries to apply transactionally
    if chaos_roll <= 5:
        success_probability -= 15
        story_log.append(_("🚨 كارثة! الشرطة نصبت كميناً محكماً! (-15%)"))
        # High risk of injury
        for p in participants:
            if random.random() < 0.3: # 30% chance of injury
                hospital_time = 30 # 30 minutes
                injuries[p.user_id] = (datetime.now(timezone.utc) + timedelta(minutes=hospital_time)).replace(tzinfo=None)
                story_log.append(_("🚑 {user} أصيب بطلق ناري! تم نقله للمستشفى.").format(user=p.user.username))

    elif chaos_roll >= 18:
        success_probability += 15
        story_log.append(_("🍀 حظ لا يصدق: وجدتم باباً خلفياً مفتوحاً! (+15%)"))
        
    # 5. Final Roll
    success_probability = min(95, max(5, success_probability))
    try:
        import json
        reqs_heat = json.loads(lobby.crime.requirements) if lobby.crime.requirements else {}
        heat_window = int(reqs_heat.get('heat_window_hours', 6))
        heat_success_penalty = float(reqs_heat.get('heat_success_penalty_pct', 5.0))
        heat_jail_boost = float(reqs_heat.get('heat_jail_boost_pct', 10.0))
        recent_ops = 0
        now_ts = datetime.now(timezone.utc)
        for p in participants:
            lc = p.user.last_crime
            if lc:
                if lc.tzinfo is None:
                    lc = lc.replace(tzinfo=timezone.utc)
                if (now_ts - lc) <= timedelta(hours=heat_window):
                    recent_ops += 1
        if recent_ops > 0:
            success_penalty_total = heat_success_penalty * min(recent_ops, len(participants))
            success_probability = max(5, success_probability - success_penalty_total)
            story_log.append(_("🚨 حرارة الساحة مرتفعة: فرص النجاح انخفضت بنسبة {pct}%").format(pct=int(success_penalty_total)))
    except Exception:
        pass
    try:
        import json
        reqs_patrol = json.loads(lobby.crime.requirements) if lobby.crime.requirements else {}
        dp_chance = float(reqs_patrol.get('double_patrol_pct', 3.0))
        dp_success_penalty = float(reqs_patrol.get('double_patrol_success_penalty_pct', 7.5))
        dp_jail_boost = float(reqs_patrol.get('double_patrol_jail_boost_pct', 15.0))
        double_patrol_active = False
        if random.random() * 100 <= dp_chance:
            success_probability = max(5, success_probability - dp_success_penalty)
            double_patrol_active = True
            story_log.append(_("🚓 دورية مزدوجة في المنطقة! انخفضت فرص النجاح وزادت المخاطر."))
    except Exception:
        double_patrol_active = False
    roll = random.randint(1, 100)
    is_success = roll <= success_probability
    
    story_log.append(_("--- النتيجة النهائية: نسبة النجاح {prob}% (الرقم العشوائي: {roll}) ---").format(prob=success_probability, roll=roll))
    
    # Calculate Cooldown
    # User requested 23h 59m cooldown
    cooldown_until = (datetime.now(timezone.utc) + timedelta(hours=23, minutes=59)).replace(tzinfo=None)
    
    total_reward = 0
    participants_snapshot = []
    
    if is_success:
        reward_money = random.randint(crime.money_reward_min, crime.money_reward_max)
        reward_exp = crime.exp_reward
        try:
            import json
            reqs2 = json.loads(lobby.crime.requirements) if lobby.crime.requirements else {}
            lucky_chance = float(reqs2.get('lucky_event_pct', 5.0))
            lucky_money_pct = float(reqs2.get('lucky_money_pct', 25.0))
            lucky_exp_pct = float(reqs2.get('lucky_exp_pct', 50.0))
            if random.random() * 100 <= lucky_chance:
                reward_money = int(reward_money * (1 + lucky_money_pct / 100.0))
                reward_exp = int(reward_exp * (1 + lucky_exp_pct / 100.0))
                story_log.append(_("🎁 مفاجأة نادرة! حصل الفريق على مكافآت إضافية بفضل فرصة ذهبية."))
        except Exception:
            pass
        total_reward = reward_money
        
        # Distribute
        share = reward_money // len(participants)
        
        story_log.append(_("💰 نجحت العملية! الغنيمة الكلية: {money} شيكل.").format(money=reward_money))
        
        # Determine MVP
        mvp_user_id = None
        if participant_performance:
            mvp_user_id = max(participant_performance, key=participant_performance.get)

        for p in participants:
            # Skip if hospitalized (no reward if unconscious? No, let's give them reward but they are in hospital)
            bonus_money = 0
            bonus_exp = 0
            
            # --- Role Bonuses ---
            try:
                import json
                reqs_roles = json.loads(lobby.crime.requirements) if lobby.crime.requirements else {}
                role_bonuses = reqs_roles.get('role_bonuses', {})
                rb = role_bonuses.get(p.role_name, {})
                money_pct = float(rb.get('money_pct', 0))
                exp_bonus = int(rb.get('exp_bonus', 0))
                rank_pts = int(rb.get('rank_points', 0))
                if money_pct:
                    bonus_money += int(share * (money_pct / 100.0))
                if exp_bonus:
                    bonus_exp += exp_bonus
                if rank_pts:
                    p.user.add_rank_points(rank_pts)
                if money_pct or exp_bonus:
                    story_log.append(_("🏅 دور {role} منح مكافأة خاصة لعضو: +{m} مال، +{e} خبرة").format(role=p.role_name, m=int(share * (money_pct / 100.0)), e=exp_bonus))
                
                # Streak bonus
                streak_step = float(reqs_roles.get('streak_step_pct', 2.0))
                streak_max = float(reqs_roles.get('streak_max_pct', 10.0))
                # Calculate consecutive success streak from history
                try:
                    recent_histories = HeistHistory.query.order_by(HeistHistory.created_at.desc()).limit(10).all()
                    streak = 0
                    for h in recent_histories:
                        names = [ps.get('name') for ps in (h.participants_snapshot or [])]
                        if p.user.username in names:
                            if h.success:
                                streak += 1
                            else:
                                break
                    if streak > 0:
                        streak_pct = min(streak_step * streak, streak_max)
                        sm = int((share + bonus_money) * (streak_pct / 100.0))
                        se = int((reward_exp + bonus_exp) * (streak_pct / 100.0))
                        bonus_money += sm
                        bonus_exp += se
                        story_log.append(_("🔥 سلسلة انتصارات: مكافآت إضافية بنسبة {pct}% للاعب {user}").format(pct=int(streak_pct), user=p.user.username))
                except Exception:
                    pass
            except Exception:
                pass
            
            # --- Fair Play Improvements ---
            
            # 1. MVP Bonus (Performance Based)
            if p.user_id == mvp_user_id and len(participants) > 1:
                mvp_bonus_money = int(share * 0.05) # 5% Bonus
                mvp_bonus_exp = 50
                bonus_money += mvp_bonus_money
                bonus_exp += mvp_bonus_exp
                story_log.append(_("🌟 {user} كان الأفضل أداءً! (+{m} مال، +{e} خبرة)").format(user=p.user.username, m=mvp_bonus_money, e=mvp_bonus_exp))
            
            # 2. Leader Bonus (Consolidated)
            if p.user_id == lobby.leader_id:
                leader_bonus = int(reward_money * 0.1) # 10% of total
                bonus_money += leader_bonus
                story_log.append(_("👑 القائد {user} حصل على مكافأة القيادة: {bonus} شيكل.").format(user=p.user.username, bonus=leader_bonus))

            # Atomic update via ResourceService
            changes = {
                'money': (share + bonus_money),
                'exp': (reward_exp + bonus_exp)
            }
            
            set_fields_dict = {}
            
            # Update Specific Cooldown
            cooldown_rec = UserOrganizedCrimeCooldown.query.filter_by(user_id=p.user_id, crime_id=crime.id).first()
            if not cooldown_rec:
                cooldown_rec = UserOrganizedCrimeCooldown(user_id=p.user_id, crime_id=crime.id)
                db.session.add(cooldown_rec)
            cooldown_rec.cooldown_until = cooldown_until
            
            if p.user_id in injuries:
                set_fields_dict['hospital_until'] = injuries[p.user_id]
            
            # Note: Using expected_version to ensure data consistency.
            # ResourceService.modify_resources uses with_for_update() for locking.
            
            # Add last_crime to set_fields to ensure atomic update
            set_fields_dict['last_crime'] = datetime.now(timezone.utc).replace(tzinfo=None)
            
            if not ResourceService.modify_resources(
                p.user_id, 
                changes, 
                'organized_crime_reward', 
                auto_commit=False,
                expected_version=p.user.version,
                set_fields=set_fields_dict
            ):
                 db.session.rollback()
                 flash(_('حدث خطأ أثناء توزيع الجوائز. حاول مرة أخرى.'), 'error')
                 return redirect(url_for('main.lobby', lobby_id=lobby.id))

            # Refresh user object to reflect DB changes made by ResourceService (important for check_level_up)
            db.session.refresh(p.user)

            # Manually update rank points to avoid rollback in add_rank_points
            try:
                from models.gameplay import UserProgress
                # Lock the progress row to prevent race conditions
                progress = UserProgress.query.filter_by(user_id=p.user_id).with_for_update().first()
                if progress:
                    progress.rank_points += 5
                else:
                    progress = UserProgress(user_id=p.user_id, rank_points=5)
                    db.session.add(progress)
            except Exception:
                pass

            try:
                p.user.check_level_up()
            except Exception:
                pass
            # last_crime updated via ResourceService
            update_daily_task_progress(p.user, 'organized_crime')
            
            participants_snapshot.append({
                'name': p.user.username,
                'role': p.role_name,
                'reward': share + bonus_money,
                'exp': reward_exp + bonus_exp,
                'status': 'success'
            })
        
    else:
        story_log.append(_("❌ فشلت العملية! الفوضى عارمة."))
        
        # Fail Consequences
        for p in participants:
            # Update Specific Cooldown
            cooldown_rec = UserOrganizedCrimeCooldown.query.filter_by(user_id=p.user_id, crime_id=crime.id).first()
            if not cooldown_rec:
                cooldown_rec = UserOrganizedCrimeCooldown(user_id=p.user_id, crime_id=crime.id)
                db.session.add(cooldown_rec)
            cooldown_rec.cooldown_until = cooldown_until

            set_fields_dict = {}
            try:
                set_fields_dict['last_crime'] = datetime.now(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
            
            # Check if already hospitalized from chaos
            status = 'failed'
            if p.user_id in injuries:
                status = 'hospitalized'
                set_fields_dict['hospital_until'] = injuries[p.user_id]
            elif p.user.hospital_until and p.user.hospital_until > datetime.now(timezone.utc).replace(tzinfo=None):
                 # Already hospitalized before heist (should not happen due to check, but safe to keep)
                 status = 'hospitalized'
            
            participants_snapshot.append({
                'name': p.user.username,
                'role': p.role_name,
                'reward': 0,
                'exp': 0,
                'status': status
            })

            # Jail Logic (if not hospitalized)
            if status != 'hospitalized':
                # --- Getaway Vehicle Check ---
                active_vehicle = UserVehicle.query.filter_by(user_id=p.user_id, is_active=True).first()
                vehicle_escape_bonus = 0
                if active_vehicle:
                     # e.g., 5% chance to escape per 10k price, max 50%
                     vehicle_escape_bonus = min(0.5, active_vehicle.vehicle.price / 200000.0)
                
                # 40% chance jail per person
                jail_chance = 0.4 - vehicle_escape_bonus
                try:
                    # Apply heat and double patrol boosts
                    if 'heat_jail_boost' in locals():
                        jail_chance += (heat_jail_boost / 100.0)
                    if 'double_patrol_active' in locals() and double_patrol_active:
                        if 'dp_jail_boost' in locals():
                            jail_chance += (dp_jail_boost / 100.0)
                except Exception:
                    pass
                if random.random() < min(0.9, max(0.05, jail_chance)):
                    jail_time = 10 * crime.min_gang_level # Minutes
                    jail_until_dt = (datetime.now(timezone.utc) + timedelta(minutes=jail_time)).replace(tzinfo=None)
                    set_fields_dict['jail_until'] = jail_until_dt
                    story_log.append(_("👮 {user} تم القبض عليه! ({time} دقيقة سجن)").format(user=p.user.username, time=jail_time))
                else:
                    # Trigger Chase for Leader ONLY (others just escape)
                    if p.user.id == current_user.id:
                        # Set session for chase
                        session['active_chase'] = True
                        session['chase_difficulty'] = crime.min_gang_level + 1
                        story_log.append(_("🚔 {user} الشرطة تطاردك! استعد للهروب!").format(user=p.user.username))
                    else:
                        story_log.append(_("🏃 {user} تمكن من الهروب بأعجوبة.").format(user=p.user.username))
            
            # Apply updates via ResourceService
            if not ResourceService.modify_resources(
                p.user_id, 
                {}, 
                'organized_crime_fail', 
                auto_commit=False,
                expected_version=p.user.version,
                set_fields=set_fields_dict
            ):
                db.session.rollback()
                flash(_('حدث خطأ أثناء معالجة النتائج. حاول مرة أخرى.'), 'error')
                return redirect(url_for('main.lobby', lobby_id=lobby.id))

    # 6. Save History
    history = HeistHistory(
        crime_name=crime.name,
        leader_name=lobby.leader.username,
        participants_snapshot=participants_snapshot,
        log_details="\n".join(story_log),
        success=is_success,
        money_earned=total_reward,
        exp_earned=0 # Total exp not tracked per se, but per user
    )
    db.session.add(history)
    
    # 7. Clean up Lobby
    db.session.delete(lobby)
    db.session.commit()
    
    # Redirect based on outcome
    if not is_success and session.get('active_chase'):
         return redirect(url_for('police_chase.index'))
    
    return redirect(url_for('main.heist_report', history_id=history.id))

@bp.route('/heist_report/<int:history_id>')
@login_required
def heist_report(history_id):
    history = db.session.get(HeistHistory, history_id)
    if not history:
        abort(404)
    crime_image = 'crimes/bank_heist.jpg'
    try:
        oc = OrganizedCrime.query.filter_by(name=history.crime_name).first()
        if oc and oc.image:
            crime_image = oc.image
    except Exception:
        pass

    lines = []
    try:
        lines = (history.log_details or "").splitlines()
    except Exception:
        lines = []

    animation = 'spark' if history.success else 'smoke'
    if any('🚗' in (l or '') or '🏎️' in (l or '') for l in lines):
        animation = 'speed'

    return render_template('heist_report.html', history=history, crime_image=crime_image, lines=lines, animation=animation)

@bp.route('/heist_history')
@login_required
def heist_history():
    # Show last 20 heists
    history = HeistHistory.query.order_by(HeistHistory.created_at.desc()).limit(20).all()
    return render_template('heist_history.html', history=history)
