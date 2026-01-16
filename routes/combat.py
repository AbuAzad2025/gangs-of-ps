from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models import User, UserItem, Item, CombatLog, UserLog
from models.hostess import Hostess
from services.resource_service import ResourceService
from models.combat import ActiveIntel
import random
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_, func
from .utils import update_daily_task_progress

bp = Blueprint('combat', __name__, url_prefix='/combat')


@bp.route('/')
@login_required
def index():
    # Find targets: Users not self, not in hospital, not in jail
    # Matchmaking: +/- 5 levels first, then others
    now = datetime.now(timezone.utc)

    # 1. Search Logic
    search_query = request.args.get('q')
    if search_query:
        targets = User.query.filter(
            User.id != current_user.id,
            User.username.ilike(f'%{search_query}%')
        ).limit(20).all()
    else:
        # 2. Level-based Matchmaking
        min_level = max(1, current_user.level - 5)
        max_level = current_user.level + 5

        # Get targets within level range
        targets = User.query.filter(
            User.id != current_user.id,
            User.level >= min_level,
            User.level <= max_level,
            or_(User.hospital_until is None, User.hospital_until < now),
            or_(User.jail_until is None, User.jail_until < now)
        ).order_by(func.random()).limit(15).all()

        # If not enough targets, fetch random others to fill up to 20
        if len(targets) < 20:
            existing_ids = [t.id for t in targets]
            existing_ids.append(current_user.id)

            more_targets = User.query.filter(
                ~User.id.in_(existing_ids),
                or_(User.hospital_until is None, User.hospital_until < now),
                or_(User.jail_until is None, User.jail_until < now)
            ).order_by(func.random()).limit(20 - len(targets)).all()

            targets.extend(more_targets)

        # Sort by level desc for display
        targets.sort(key=lambda x: x.level, reverse=True)

    # Ensure datetimes are timezone-aware for template comparison
    for target in targets:
        if target.hospital_until and target.hospital_until.tzinfo is None:
            target.hospital_until = target.hospital_until.replace(
                tzinfo=timezone.utc)
        if target.jail_until and target.jail_until.tzinfo is None:
            target.jail_until = target.jail_until.replace(tzinfo=timezone.utc)
        if target.safe_house_until and target.safe_house_until.tzinfo is None:
            target.safe_house_until = target.safe_house_until.replace(
                tzinfo=timezone.utc)

    # Get active intel for these targets
    target_ids = [t.id for t in targets]
    active_intels = ActiveIntel.query.filter(
        ActiveIntel.user_id == current_user.id,
        ActiveIntel.target_id.in_(target_ids),
        ActiveIntel.start_time <= now,
        ActiveIntel.expires_at > now
    ).all()
    intel_target_ids = {intel.target_id for intel in active_intels}

    return render_template(
        'combat/index.html',
        targets=targets,
        search_query=search_query,
        now=now,
        intel_target_ids=intel_target_ids)


@bp.route('/attack/<int:target_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def attack(target_id):
    # Deadlock Prevention: Lock both users in ID order
    # This prevents deadlocks when two users attack each other simultaneously
    first_id, second_id = sorted([current_user.id, target_id])

    u1 = db.session.query(User).filter_by(
        id=first_id).with_for_update().first()
    u2 = db.session.query(User).filter_by(
        id=second_id).with_for_update().first()

    target = u1 if u1 and u1.id == target_id else u2

    if not target:
        abort(404)

    if target.id == current_user.id:
        flash(_('لا يمكنك مهاجمة نفسك!'), 'danger')
        return redirect(url_for('combat.index'))

    # Status Check for Attacker
    now = datetime.now(timezone.utc)

    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك القتال!'), 'danger')
            return redirect(url_for('jail.index'))

    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك القتال!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك القتال!'), 'danger')
            return redirect(url_for('gym.index'))

    # Anti-Spam Cooldown (5 seconds)
    if current_user.last_attack:
        last_attack = current_user.last_attack
        if last_attack.tzinfo is None:
            last_attack = last_attack.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) - last_attack < timedelta(seconds=5):
            flash(_('انتظر قليلاً قبل الهجوم التالي!'), 'warning')
            return redirect(url_for('combat.index'))

    # Target is already fetched and locked at the start of the function
    # to prevent deadlocks.

    if current_user.health < 10:
        flash(_('صحتك منخفضة جداً للقتال!'), 'danger')
        return redirect(url_for('main.hospital'))

    now = datetime.now(timezone.utc)

    # --- Newbie Protection ---
    if getattr(
        target,
        "is_admin_protected",
        False) and not getattr(
        current_user,
        "is_developer",
            False):
        flash(_('هذا اللاعب تحت حماية الإدارة ولا يمكن مهاجمته!'), 'warning')
        return redirect(url_for('combat.index'))

    if target.created_at:
        target_created_at = target.created_at
        if target_created_at.tzinfo is None:
            target_created_at = target_created_at.replace(tzinfo=timezone.utc)
        if (now - target_created_at).days < 7:
            flash(
                _('هذا اللاعب تحت حماية "العراب" (لاعب جديد لمدة أسبوع) ولا يمكن مهاجمته!'),
                'warning')
            return redirect(url_for('combat.index'))

    if not current_app.config.get('TESTING', False):
        # --- Intel Check ---
        active_intel = ActiveIntel.query.filter(
            ActiveIntel.user_id == current_user.id,
            ActiveIntel.target_id == target.id,
            ActiveIntel.start_time <= now,
            ActiveIntel.expires_at > now
        ).first()

        if not active_intel:
            flash(
                _('لا يمكنك الهجوم على هذا اللاعب دون معلومات استخباراتية! استأجر مخبراً من السوق السوداء أولاً.'),
                'warning')
            return redirect(url_for('black_market.index'))

    if not current_app.config.get('TESTING', False):
        # --- Location Check ---
        if current_user.location_id != target.location_id:
            target_location = target.location.name if target.location else _(
                "غير معروف")
            flash(_('يجب أن تكون في نفس المدينة لتنفيذ الهجوم! الهدف متواجد في %(city)s.',
                  city=target_location), 'warning')
            return redirect(url_for('travel.index'))

    # --- Safe House Protection & Breach Logic ---
    if target.is_safe_house_active and target.safe_house_until:
        safe_house_until = target.safe_house_until
        if safe_house_until.tzinfo is None:
            safe_house_until = safe_house_until.replace(tzinfo=timezone.utc)

        if safe_house_until > now:
            # Check if attempting to breach
            action = request.form.get('action')
            if action == 'breach':
                # Check for C4
                c4_item = UserItem.query.join(Item).filter(
                    UserItem.user_id == current_user.id,
                    Item.name.ilike('%C4%')  # Flexible search for C4
                ).first()

                if not c4_item or c4_item.quantity < 1:
                    flash(
                        _('تحتاج إلى متفجرات C4 لتفجير المنزل الآمن!'),
                        'danger')
                    return redirect(url_for('combat.index'))

                # Atomic Consume C4
                rows = UserItem.query.filter(
                    UserItem.user_id == current_user.id,
                    UserItem.id == c4_item.id,
                    UserItem.quantity >= 1
                ).update({
                    UserItem.quantity: UserItem.quantity - 1
                }, synchronize_session=False)

                if rows == 0:
                    flash(_('حدث خطأ أثناء استخدام C4!'), 'danger')
                    return redirect(url_for('combat.index'))

                # Destroy Safe House
                target.is_safe_house_active = False
                target.safe_house_until = None
                # Removed premature commit to ensure atomicity with combat
                # transaction

                flash(
                    _('تم تفجير المنزل الآمن بنجاح! الهدف مكشوف الآن.'),
                    'success')
                # Proceed to combat

            else:
                flash(
                    _('الهدف يحتمي داخل منزل آمن! تحتاج لتفجيره أولاً باستخدام C4.'),
                    'warning')
                return redirect(url_for('combat.index'))

    if target.hospital_until:
        hospital_until = target.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)

        if hospital_until > now:
            flash(_('هذا اللاعب في المستشفى حالياً'), 'warning')
            return redirect(url_for('combat.index'))

    if target.jail_until:
        jail_until = target.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)

        if jail_until > now:
            flash(_('هذا اللاعب في السجن حالياً'), 'warning')
            return redirect(url_for('combat.index'))

    current_user.last_attack = now.replace(tzinfo=None)
    # db.session.commit() # Keep transaction open to maintain locks for combat
    # calculation

    # Check Gang Affiliation & Alliances
    if current_user.gang_id and target.gang_id:
        if current_user.gang_id == target.gang_id:
            flash(_('لا يمكنك مهاجمة عضو في نفس العصابة!'), 'warning')
            return redirect(url_for('combat.index'))

        # Check Alliance
        from models.social import GangAlliance
        alliance = GangAlliance.query.filter(
            ((GangAlliance.gang1_id == current_user.gang_id) & (
                GangAlliance.gang2_id == target.gang_id)) | (
                (GangAlliance.gang1_id == target.gang_id) & (
                    GangAlliance.gang2_id == current_user.gang_id)),
            GangAlliance.status == 'active').first()
        if alliance:
            flash(_('لا يمكنك مهاجمة حليف! بينكما معاهدة سلام.'), 'warning')
            return redirect(url_for('combat.index'))

    # Combat Logic
    # Get Equipped Weapon & Armor for Attacker
    equipped_weapon = UserItem.query.join(Item).filter(
        UserItem.user_id == current_user.id,
        UserItem.is_equipped,
        Item.type == 'weapon'
    ).first()

    # Calculate Total Attack
    attacker_strength = current_user.strength

    if equipped_weapon:
        # Bullet Check
        if equipped_weapon.item.ammo_needed > 0:
            if current_user.bullets < equipped_weapon.item.ammo_needed:
                flash(_('ما معك رصاص كافي لسلاحك! تحتاج %(ammo)s رصاصة.',
                      ammo=equipped_weapon.item.ammo_needed), 'danger')
                return redirect(url_for('combat.index'))

            # Deduct Bullets
            # We hold the lock, so expected_version=None
            if not ResourceService.modify_resources(
                current_user.id,
                {
                    'bullets': -equipped_weapon.item.ammo_needed},
                'combat_ammo_use',
                auto_commit=False,
                    expected_version=None):
                flash(_('ما معك رصاص كافي لسلاحك!'), 'danger')
                return redirect(url_for('combat.index'))

        mult = 1.0
        if equipped_weapon.condition is not None and equipped_weapon.condition < 100:
            mult = equipped_weapon.condition / 100
        attacker_strength += int(equipped_weapon.item.bonus_strength * mult)

    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > now:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.combat_skill > 0:
                attacker_strength += hostess.combat_skill

    is_berserk = False
    if current_user.health < 30:
        is_berserk = True
        attacker_strength *= 1.3

    crit_chance = 5 + (current_user.intelligence / 20)
    is_crit = False
    if random.randint(1, 100) <= crit_chance:
        attacker_strength *= 1.5
        is_crit = True

    attacker_total = attacker_strength * random.uniform(0.8, 1.2)

    # Calculate Total Defense
    defender_defense = target.defense

    # Get Target's Equipped Armor
    target_armor = UserItem.query.join(Item).filter(
        UserItem.user_id == target.id,
        UserItem.is_equipped,
        Item.type == 'armor'
    ).first()

    if target_armor:
        mult = 1.0
        if target_armor.condition is not None and target_armor.condition < 100:
            mult = target_armor.condition / 100
        defender_defense += int(target_armor.item.bonus_defense * mult)

    defender_total = defender_defense * random.uniform(0.8, 1.2)

    dodge_chance = 5 + (target.agility / 20)
    is_dodge = False
    if random.randint(1, 100) <= dodge_chance:
        defender_total *= 2.0
        is_dodge = True

    # Check for Gang War
    is_war = False
    war = None
    if current_user.gang_id and target.gang_id:
        from models.social import GangWar
        from sqlalchemy import or_
        war = GangWar.query.filter(
            or_(
                (GangWar.gang1_id == current_user.gang_id) & (
                    GangWar.gang2_id == target.gang_id),
                (GangWar.gang1_id == target.gang_id) & (
                    GangWar.gang2_id == current_user.gang_id)),
            GangWar.status == 'active').first()
        if war:
            is_war = True

    # Determine Disguise Status
    is_anonymous = False
    if current_user.is_disguised and current_user.disguise_until:
        disguise_until = current_user.disguise_until
        if disguise_until.tzinfo is None:
            disguise_until = disguise_until.replace(tzinfo=timezone.utc)

        if disguise_until > now:
            is_anonymous = True

    # Determine Winner
    if attacker_total > defender_total:
        # Win
        damage_reduction_mult = 0.5
        damage = int((attacker_total - defender_total) * damage_reduction_mult)

        steal_percent = 0.2 if is_war else 0.1
        # Steal 10% or 20% in war
        money_stolen = int(target.money * steal_percent)

        loot_msg = ""
        if not current_app.config.get('TESTING', False):
            if random.random() < 0.3:
                # Loot bullets from target (Steal, not generate)
                available_bullets = target.bullets
                if available_bullets > 0:
                    bullets_looted = min(
                        available_bullets, random.randint(5, 20))

                    # Atomic Transfer
                    if ResourceService.modify_resources(
                        target.id, {
                            'bullets': -bullets_looted}, f'combat_loot_loss_{current_user.id}', auto_commit=False):
                        # We hold the lock on current_user, so we don't need
                        # expected_version check
                        ResourceService.modify_resources(
                            current_user.id, {
                                'bullets': bullets_looted}, 'combat_loot_win', auto_commit=False, expected_version=None)
                        loot_msg = _(
                            ' ووجدت في جيوبه %(bullets)s رصاصة!',
                            bullets=bullets_looted)

        exp_gain = 100 if is_war else 50

        # Atomic Steal Logic via ResourceService
        real_stolen = 0
        if money_stolen > 0:
            # Try to deduct from target
            if ResourceService.modify_resources(
                target.id,
                {'money': -money_stolen},
                f'combat_loss_vs_{current_user.id}',
                auto_commit=False,
            ):
                real_stolen = money_stolen
            else:
                real_stolen = 0  # Failed to steal (maybe insufficient funds)

        money_stolen = real_stolen  # Sync for display

        # Apply Attacker Rewards (Money + Exp)
        attacker_changes = {'exp': exp_gain}
        if real_stolen > 0:
            attacker_changes['money'] = real_stolen

        ResourceService.modify_resources(
            current_user.id,
            attacker_changes,
            'combat_win',
            auto_commit=False,
            expected_version=None)

        current_user.add_rank_points(5 if is_war else 3)

        if current_user.check_level_up():
            ref_url = url_for(
                'main.register',
                ref=current_user.referral_code,
                _external=True)
            share_text = _(
                "أصبحت زعيم مستوى %(level)s في عصابات فلسطين! هل تجرؤ على تحديي؟ %(url)s",
                level=current_user.level,
                url=ref_url)
            wa_link = f"https://wa.me/?text={share_text}"
            flash(
                _(
                    'مبروك! وصلت للمستوى %(level)s! '
                    '<a href="%(url)s" target="_blank" class="btn btn-sm btn-success ml-2">'
                    '<i class="fab fa-whatsapp"></i> شارك</a>',
                    level=current_user.level,
                    url=wa_link),
                'success')

        # Damage target health
        damage_val = max(5, int(damage / 10))
        # Ensure we don't go below 0 (ResourceService check_balance=True by default for negative values,
        # but here we want to clamp, not fail. So we calculate exact
        # deduction.)
        current_target_health = target.health
        actual_damage = min(current_target_health, damage_val)

        target_changes = {'health': -actual_damage}
        target_set_fields = {}

        # Check if dead
        if current_target_health - actual_damage <= 0:
            target_set_fields['hospital_until'] = (
                datetime.now(
                    timezone.utc) +
                timedelta(
                    days=3650)).replace(
                tzinfo=None)
            flash(_('لقد قضيت على خصمك وأرسلته للمقبرة!'), 'success')
            try:
                from models.user import reserve_elite_titles_for_death
                reserve_elite_titles_for_death(target.id, now=now)
            except Exception:
                pass

            # --- CLAIM BOUNTY ---
            from models import Bounty
            # Lock bounties to prevent race conditions
            bounties = Bounty.query.filter_by(
                target_id=target.id).with_for_update().all()
            if bounties:
                total_bounty = 0
                for bounty in bounties:
                    total_bounty += bounty.amount
                    db.session.delete(bounty)

                # Atomic Update for Bounty
                ResourceService.modify_resources(
                    current_user.id, {
                        'money': total_bounty}, 'combat_bounty_claim', auto_commit=False, expected_version=None)

                # Commit handled at end of transaction

                current_user.add_rank_points(10)
                flash(
                    _(
                        'مبروك! لقد قبضت على مكافآت بقيمة %(amount)s$ كانت على رأس هذا اللاعب!',
                        amount=total_bounty),
                    'success')

            # --- Gang War Trigger Logic ---
            # If attacker is high rank and no war exists, start war
            if current_user.gang_id and target.gang_id and not is_war:
                from models.social import Gang

                # Lock both gangs to prevent race conditions (Sorted by ID)
                g1_id, g2_id = sorted([current_user.gang_id, target.gang_id])
                g1 = db.session.query(Gang).filter_by(
                    id=g1_id).with_for_update().first()
                g2 = db.session.query(Gang).filter_by(
                    id=g2_id).with_for_update().first()

                if g1 and g2:
                    attacker_gang = g1 if g1.id == current_user.gang_id else g2
                    target_gang = g1 if g1.id == target.gang_id else g2

                    # Double check war status after locking
                    existing_war = GangWar.query.filter(
                        or_(
                            (GangWar.gang1_id == current_user.gang_id) & (
                                GangWar.gang2_id == target.gang_id),
                            (GangWar.gang1_id == target.gang_id) & (
                                GangWar.gang2_id == current_user.gang_id)),
                        GangWar.status == 'active').first()

                    if existing_war:
                        is_war = True
                        war = existing_war
                    else:
                        # High rank criteria: Leader, Underboss, or Level 50+
                        is_high_rank = (
                            current_user.id == attacker_gang.leader_id) or (
                            current_user.id == attacker_gang.underboss_id) or (
                            current_user.level >= 50)

                        if is_high_rank:
                            # --- Fair Play Checks ---

                            # 1. Power Balance Check
                            # Prevent bullying: Attacker level shouldn't be
                            # overwhelmingly higher
                            is_unfair = False
                            if attacker_gang.level > (
                                    target_gang.level * 2 + 5):
                                is_unfair = True

                            # 2. Cooldown Check (No war in last 24h)
                            recent_war = GangWar.query.filter(
                                or_(
                                    (GangWar.gang1_id == current_user.gang_id) & (
                                        GangWar.gang2_id == target.gang_id),
                                    (GangWar.gang1_id == target.gang_id) & (
                                        GangWar.gang2_id == current_user.gang_id)),
                                GangWar.end_time > (
                                    now -
                                    timedelta(
                                        days=1))).first()

                            if not is_unfair and not recent_war:
                                new_war = GangWar(
                                    gang1_id=current_user.gang_id, gang2_id=target.gang_id)
                                db.session.add(new_war)
                                flash(
                                    _('لقد تسببت هجمتك في اندلاع حرب عصابات!'), 'danger')
                                is_war = True
                                war = new_war
                            elif is_unfair:
                                flash(
                                    _('تجنبت اندلاع حرب لأن عصابتك أقوى بكثير من الخصم (نظام اللعب النظيف).'),
                                    'info')
                            elif recent_war:
                                flash(
                                    _('لم تندلع حرب جديدة لوجود هدنة مؤقتة بعد الحرب الأخيرة.'), 'info')

        # Apply Target Damage & Status
        ResourceService.modify_resources(
            target.id,
            target_changes,
            'combat_damage',
            auto_commit=False,
            set_fields=target_set_fields)

        # Gang EXP Logic
        if current_user.gang_id:
            from models.social import Gang, GangLog
            # Lock Gang Row
            gang = db.session.query(Gang).filter_by(
                id=current_user.gang_id).with_for_update().first()
            if gang:
                exp_amount = 20 if is_war else 10
                gang.exp += exp_amount

                log_action = _(
                    'هاجم %(target)s وكسب %(exp)s خبرة',
                    target=target.username,
                    exp=exp_amount)
                if is_anonymous:
                    log_action += " " + _('(متخفي)')

                log = GangLog(
                    gang_id=gang.id,
                    user_id=current_user.id,
                    action=log_action)
                db.session.add(log)

                # Update War Score (Weighted by Role)
                if is_war and war:
                    # Lock war row for atomic update
                    try:
                        war = db.session.query(GangWar).filter_by(
                            id=war.id).with_for_update().first()
                    except Exception:
                        war = None

                    if war:
                        # Determine points based on target role
                        points = 1
                        target_gang_role = None
                        if target_gang:
                            if target.id == target_gang.leader_id:
                                points = 5
                                target_gang_role = _('الزعيم')
                            elif target.id == target_gang.underboss_id:
                                points = 3
                                target_gang_role = _('النائب')
                            else:
                                points = 1
                                target_gang_role = _('عضو')

                        if war.gang1_id == gang.id:
                            war.score_gang1 += points
                        else:
                            war.score_gang2 += points

                        flash(_('انتصار في حرب العصابات! +%(points)s نقطة (إسقاط %(role)s)',
                              points=points, role=target_gang_role), 'success')

                # Level up logic
                if gang.exp >= gang.level * 1000:
                    gang.exp -= gang.level * 1000
                    gang.level += 1
                    log_levelup = GangLog(
                        gang_id=gang.id,
                        action=_(
                            'ترقت العصابة للمستوى %(level)s!',
                            level=gang.level))
                    db.session.add(log_levelup)
                    flash(_('مبروك! ترقت عصابتك للمستوى %(level)s!',
                          level=gang.level), 'success')

        # Create Combat Log (Win)
        combat_log = CombatLog(
            attacker_id=current_user.id,
            defender_id=target.id,
            winner_id=current_user.id,
            money_stolen=money_stolen,
            exp_gain=exp_gain,
            is_attacker_anonymous=is_anonymous
        )
        db.session.add(combat_log)

        # Create detailed User Log for combat win
        log = UserLog(
            user_id=current_user.id,
            action='COMBAT_WIN',
            details=json.dumps({
                'target_id': target.id,
                'target_username': target.username,
                'money_stolen': money_stolen,
                'exp_gain': exp_gain,
                'is_war': is_war,
                'is_anonymous': is_anonymous,
                'is_berserk': is_berserk,
                'is_critical': is_crit,
                'is_dodge': is_dodge,
                'bullets_looted': bullets_looted if 'bullets_looted' in locals() else 0,
                'bounty_claimed': total_bounty if 'total_bounty' in locals() else 0
            }),
            result='success',
            before_state={
                'money': current_user.money - money_stolen,
                'exp': current_user.exp - exp_gain,
                'health': target.health + actual_damage if 'actual_damage' in locals() else target.health
            },
            after_state={
                'money': current_user.money,
                'exp': current_user.exp,
                'health': target.health
            },
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log)

        # Update Daily Task Progress
        update_daily_task_progress(current_user, 'combat')

        db.session.commit()

        msg = _(
            'لقد انتصرت! سرقت %(money)s$ وحصلت على %(exp)s خبرة.',
            money=money_stolen,
            exp=exp_gain)
        msg += loot_msg

        if is_berserk:
            msg += " " + _('😡 حالة هيجان (Berserk)!')
        if is_crit:
            msg += " " + _('🎯 ضربة حرجة (Critical Hit)!')
        if is_dodge:
            msg += " " + _('الخصم حاول يتفادى الضربة لكنك جبت أجله!')

        flash(msg, 'success')
        return render_template(
            'combat/result.html',
            result='win',
            target=target,
            money=money_stolen,
            exp=exp_gain)

    else:
        # Lose
        damage = int(defender_total - attacker_total)
        money_lost = int(current_user.money * 0.1)
        money_lost = max(0, money_lost)  # Ensure no negative money loss

        # Atomic Loss
        if money_lost > 0:
            # Deduct from loser (current_user)
            # We hold the lock, so expected_version=None (Using
            # current_user.version here is risky if it was updated by ammo
            # usage earlier in transaction)
            if ResourceService.modify_resources(
                current_user.id, {
                    'money': -money_lost}, 'combat_loss_penalty', auto_commit=False, expected_version=None):
                # Add to winner (target) - no expected_version
                ResourceService.modify_resources(
                    target.id, {
                        'money': money_lost}, 'combat_win_defense', auto_commit=False, expected_version=None)
            else:
                money_lost = 0  # Could not take money

        # Apply Damage to Loser (Current User)
        loser_damage_val = max(5, int(damage / 10))
        loser_actual_damage = min(current_user.health, loser_damage_val)

        loser_changes = {'health': -loser_actual_damage}
        loser_set_fields = {}

        if current_user.health - loser_actual_damage <= 0:
            loser_set_fields['hospital_until'] = (
                datetime.now(
                    timezone.utc) +
                timedelta(
                    minutes=10)).replace(
                tzinfo=None)
            flash(_('لقد قُضي عليك وذهبت للمستشفى!'), 'danger')

        ResourceService.modify_resources(
            current_user.id,
            loser_changes,
            'combat_loss_damage',
            auto_commit=False,
            set_fields=loser_set_fields)

        # Create Combat Log (Lose)
        combat_log = CombatLog(
            attacker_id=current_user.id,
            defender_id=target.id,
            winner_id=target.id,
            money_stolen=money_lost,
            exp_gain=0,
            is_attacker_anonymous=is_anonymous
        )
        db.session.add(combat_log)

        # User Log
        log = UserLog(
            user_id=current_user.id,
            action='COMBAT_LOSE',
            details=json.dumps({
                'target_id': target.id,
                'target_username': target.username,
                'money_lost': money_lost,
                'health_damage': loser_actual_damage,
                'is_anonymous': is_anonymous,
                'hospitalized': 'hospital_until' in loser_set_fields
            }),
            result='fail',
            before_state={
                'money': current_user.money + money_lost,
                'health': current_user.health + loser_actual_damage
            },
            after_state={
                'money': current_user.money,
                'health': current_user.health - loser_actual_damage
            },
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log)

        db.session.commit()

        msg = _('لقد خسرت المعركة! خسرت %(money)s$.', money=money_lost)
        flash(msg, 'danger')
        return render_template(
            'combat/result.html',
            result='lose',
            target=target,
            money=money_lost)


@bp.route('/history')
@login_required
def history():
    from sqlalchemy import or_
    logs = CombatLog.query.filter(
        or_(CombatLog.attacker_id == current_user.id, CombatLog.defender_id == current_user.id)
    ).order_by(CombatLog.timestamp.desc()).limit(50).all()

    return render_template('combat/history.html', logs=logs)
