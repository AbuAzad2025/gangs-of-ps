from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    current_app,
)
from flask_login import login_required, current_user
from extensions import db
from flask_babel import _
from models import Location, UserItem, Item
from models.system import SystemConfig
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from models import User
import random
from services.resource_service import ResourceService

bp = Blueprint('travel', __name__, url_prefix='/travel')


@bp.route('/')
@login_required
def index():
    if Location.query.filter(Location.name != 'Default City').count() == 0:
        from utils.essentials import initialize_locations
        initialize_locations()
        db.session.commit()

    locations = Location.query.filter(
        Location.id != current_user.location_id).limit(50).all()
    current_location = db.session.get(
        Location, current_user.location_id) if current_user.location_id else None

    # Calculate remaining cooldown
    remaining_time = 0
    if current_user.last_travel and current_user.location_id:
        # Assuming cooldown is based on the current location (the one we traveled TO)
        # If user has no location (e.g. initial), cooldown is 0
        if current_location:
            elapsed = datetime.now(
                timezone.utc) - current_user.last_travel.replace(
                tzinfo=timezone.utc) if current_user.last_travel.tzinfo is None else datetime.now(
                timezone.utc) - current_user.last_travel
            cooldown_duration = current_location.cooldown
            if elapsed.total_seconds() < cooldown_duration:
                remaining_time = int(
                    cooldown_duration - elapsed.total_seconds())

    return render_template(
        'travel.html',
        locations=locations,
        current_location=current_location,
        remaining_time=remaining_time)


@bp.route('/fly/<int:location_id>', methods=['POST'])
@login_required
def fly(location_id):
    target_location = db.session.get(Location, location_id)
    if not target_location:
        abort(404)

    user = db.session.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    ).scalar_one()

    # Check Status (Jail/Hospital/Gym)
    now = datetime.now(timezone.utc)

    if user.jail_until:
        jail_until = user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك السفر!'), 'danger')
            return redirect(url_for('jail.index'))

    if user.hospital_until:
        hospital_until = user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك السفر!'), 'danger')
            return redirect(url_for('hospital.index'))

    if user.gym_until:
        gym_until = user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب في الجيم ولا يمكنك السفر!'), 'danger')
            return redirect(url_for('gym.index'))

    # Check if already there
    if user.location_id == target_location.id:
        flash(_('أنت موجود هنا بالفعل!'), 'warning')
        return redirect(url_for('travel.index'))

    # Check Cooldown
    if user.last_travel and user.location_id:
        current_loc = db.session.get(Location, user.location_id)
        if current_loc:
            elapsed = datetime.now(
                timezone.utc) - user.last_travel.replace(
                tzinfo=timezone.utc) if user.last_travel.tzinfo is None else datetime.now(
                timezone.utc) - user.last_travel
            if elapsed.total_seconds() < current_loc.cooldown:
                flash(_('عليك الانتظار قبل السفر مرة أخرى!'), 'danger')
                return redirect(url_for('travel.index'))

    # Check Money
    if user.money < target_location.cost:
        flash(_('ليس لديك مال كافٍ للسفر!'), 'danger')
        return redirect(url_for('travel.index'))

    # --- SMUGGLING CHECK ---
    # Check if user has smuggling items
    smuggling_items = UserItem.query.filter_by(
        user_id=user.id).join(Item).filter(
        Item.type == 'smuggling').all()
    smuggling_risk_base = 0
    total_smuggling_qty = 0

    if smuggling_items:
        for ui in smuggling_items:
            total_smuggling_qty += ui.quantity

        # Risk: 15% base + 2% per item
        smuggling_risk_base = 15 + (total_smuggling_qty * 2)

        # Intelligence reduces risk
        intel_factor = user.intelligence * 0.1
        smuggling_risk = max(
            5,
            smuggling_risk_base -
            intel_factor)  # Min 5% risk always

        risk_roll = random.randint(1, 100)

        if risk_roll <= smuggling_risk:
            # BUSTED!
            jail_time = 30  # minutes
            fine_amount = int(user.money * 0.2)  # 20% fine

            # Confiscate items
            for ui in smuggling_items:
                db.session.delete(ui)

            # Atomic Fine via ResourceService
            ResourceService.modify_resources(user.id,
                                             {'money': -fine_amount},
                                             'smuggling_bust_fine',
                                             auto_commit=False,
                                             expected_version=None)

            # current_user.money -= fine_amount # Removed
            user.jail_until = datetime.now(
                timezone.utc) + timedelta(minutes=jail_time)

            db.session.commit()

            flash(
                random.choice([
                    _('🚔 كبسة! فتشوا السيارة ولقوا تهريب. مصادرة + سجن 30 دقيقة + غرامة %(fine)s$.',
                      fine=fine_amount),
                    _('🚔 انمسكت! تفتيش مفاجئ وتهريب مكشوف. سجن 30 دقيقة وغرامة %(fine)s$.',
                      fine=fine_amount),
                    _('🚔 وقفوّك للتفتيش… ولقوا تهريب. سجن 30 دقيقة + غرامة %(fine)s$.',
                      fine=fine_amount),
                ]),
                'danger')
            return redirect(url_for('jail.index'))

    # --- FLYING CHECKPOINT (Tayyar) ---
    # 8% Chance: Stops you, takes your money (travel cost), and sends you back.
    if random.random() < 0.08:
        # Deduct cost (Gas/Taxi money lost)
        if ResourceService.modify_resources(user.id,
                                            {'money': -target_location.cost},
                                            'travel_tayyar_cost',
                                            auto_commit=False,
                                            expected_version=None):
            db.session.commit()
            flash(
                random.choice([
                    _('🚧 حاجز طيار فجأة طلعلك! وقفوك نص ساعة وفي الآخر رجعوك. راحت عليك أجرة الطريق.'),
                    _('🚧 حاجز طيار! لفّوك على جنب وتدقيق… وبعدها رجّعوك. أجرة الطريق راحت.'),
                    _('🚧 طلّعوك على حاجز طيار وتفتيش مطوّل… آخر شي رجّعوك. خسرت أجرة الطريق.'),
                ]),
                'danger')
            return redirect(url_for('travel.index'))

    # Process Travel

    # --- REGIONAL AUTHORITY CHECKS ---
    target_name = target_location.name

    # 1. Gaza Strip - Hamas Internal Security (Al-Amn Al-Dakhili)
    if target_name == 'غزة':
        if random.random() < 0.08:  # 8% Chance
            # Strict Checkpoint
            flash(
                random.choice([
                    _('🚧 حاجز للأمن الداخلي (حماس): "هات هويتك وشو بتعمل هون؟" تحقيق سريع ومضيت.'),
                    _('🚧 نقطة تفتيش للأمن الداخلي: "وين رايح؟" كم سؤال وكم دقيقة ومرقت.'),
                    _('🚧 وقفوك حاجز للأمن الداخلي… تدقيق بسيط وبعدين مشّوك.'),
                ]),
                'warning')
            # Potential for future expansion: Check for specific "immoral"
            # items

    # 2. West Bank - PA Security Forces (Al-Sulta)
    elif target_name in ['رام الله', 'نابلس', 'الخليل', 'جنين', 'أريحا', 'بيت لحم', 'طولكرم']:
        if random.random() < 0.08:  # 8% Chance
            security_branch = random.choice([_('الوقائي'), _('المخابرات')])
            flash(
                random.choice([
                    _('🚓 دورية للأمن %(branch)s وقفتك: "ممنوع التجول بالسلاح هون يا شب". تفتيش وتدقيق أمني.',
                      branch=security_branch),
                    _('🚓 طلعلك حاجز للأمن %(branch)s: تدقيق أسماء وتفتيش خفيف… وبالأخير مشّوك.',
                      branch=security_branch),
                    _('🚓 الأمن %(branch)s وقفك على جنب: "افتح الشنطة". تدقيق سريع وبعدين طريقك.',
                      branch=security_branch),
                ]),
                'warning')
            # Potential: Confiscate weapons if we want to be harsh, but for now
            # just flavor/delay.

    # 3. Jerusalem - Separation Wall (Jidar Al-Fasl)
    if target_name == 'القدس':
        # The Wall is the main obstacle to Jerusalem
        if random.random() < 0.12:  # 12% Chance
            flash(
                random.choice([
                    _('🧱 جدار الفصل العنصري مسكر المنطقة. اضطريت تلف طريق طويلة وتستنى "الفتحة" لتمر.'),
                    _('🧱 سكروا الطريق باتجاه القدس… لفيت لفّة طويلة واستنيت لحد ما فتحت.'),
                    _('🧱 على بوابة الجدار… ازدحام وتأخير. بالأخير مرقت بعد لفّة طويلة.'),
                ]),
                'danger')
            # Maybe add delay?

    # --- OCCUPATION OBSTACLES (Before Travel) ---

    travel_cost = target_location.cost

    # Fetch Occupation Alert Level (1: Normal, 2: Tense, 3: Closure)
    try:
        alert_level = int(
            SystemConfig.get_value(
                'occupation_alert_level', '1'))
    except BaseException:
        alert_level = 1

    # Base Probability (Normal: 15%)
    checkpoint_prob = 15
    if alert_level == 2:
        checkpoint_prob = 40  # Tense: 40%
    elif alert_level == 3:
        checkpoint_prob = 80  # Closure: 80%

    # Random Events Logic (Occupation Flavor)
    event_roll = 50 if current_app.config.get(
        'TESTING') else random.randint(1, 100)
    msg_extra = ""

    # 1. Occupation Checkpoint (HajeZ)
    if event_roll <= checkpoint_prob:
        # Determine type: Flying (60%) or Permanent (40%)
        # In Closure (Level 3), mostly Permanent/Iron Gates (80%)
        permanent_chance = 0.4 if alert_level < 3 else 0.8
        is_permanent = random.random() < permanent_chance

        if not is_permanent:
            # Flying Checkpoint
            if random.random() > 0.4:  # 60% chance to pass
                msg_extra = random.choice([
                    _(' 🚧 صادفك حاجز طيار، لكن الجندي كان ملتهي بالجوال ومرقت عخير.'),
                    _(' 🚧 حاجز طيار… الجندي مشغول وخلصتها بسرعة.'),
                    _(' 🚧 وقفوك لحظة على حاجز طيار وبعدين مشّوك.'),
                ])
            else:
                # Bribe logic
                bribe = int(travel_cost * 0.5)
                if user.money >= (travel_cost + bribe):
                    if ResourceService.modify_resources(
                        user.id, {
                            'money': -bribe}, 'travel_bribe', auto_commit=False, expected_version=None):
                        msg_extra = random.choice([
                            _(' 🛑 حاجز طيار! الجندي طلب هويتك وتصريح، دفعت %(bribe)s رشوة لتمشي.',
                              bribe=bribe),
                            _(' 🛑 حاجز طيار… شدّوا عليك شوي. دفعت %(bribe)s وكمّلت طريقك.',
                              bribe=bribe),
                            _(' 🛑 طلبوا تصريح/هوية… حلّيتها برشوة %(bribe)s ومشيت.',
                              bribe=bribe),
                        ])
                    else:
                        flash(_('حدث خطأ أثناء دفع الرشوة!'), 'danger')
                        return redirect(url_for('travel.index'))
                else:
                    # Jail
                    jail_time = 15
                    ResourceService.modify_resources(
                        user.id, {
                            'money': -travel_cost}, 'travel_cost_jail', auto_commit=False, expected_version=None)
                    user.jail_until = datetime.now(
                        timezone.utc) + timedelta(minutes=jail_time)
                    db.session.commit()
                    flash(
                        random.choice([
                            _('👮 مسكوك عالمانع! معكش تدفع الرشوة. 15 دقيقة تحقيق ميداني.'),
                            _('👮 ما معكش ترشي… سحبوك عالتحقيق 15 دقيقة.'),
                            _('👮 "وين تصريحك؟" ما قدرت تدفع… 15 دقيقة تحقيق ميداني.'),
                        ]),
                        'danger')
                    return redirect(url_for('jail.index'))
        else:
            # Permanent Checkpoint (More dangerous)
            if random.random() < 0.2:  # 20% Administrative Detention
                jail_time = random.randint(30, 60)
                ResourceService.modify_resources(
                    user.id, {
                        'money': -travel_cost}, 'travel_cost_jail', auto_commit=False, expected_version=None)
                user.jail_until = datetime.now(
                    timezone.utc) + timedelta(minutes=jail_time)
                db.session.commit()
                flash(
                    random.choice([
                        _('👮 الجندي عالحاجز شاف اسمك بالقائمة السوداء! تحولت للاعتقال الإداري لمدة %(time)s دقيقة.',
                          time=jail_time),
                        _('👮 على الحاجز: "اسمك طالع!" أخذوك اعتقال إداري %(time)s دقيقة.',
                          time=jail_time),
                        _('👮 تدقيق طويل… وبالأخير طلع اسمك. اعتقال إداري %(time)s دقيقة.',
                          time=jail_time),
                    ]),
                    'danger')
                return redirect(url_for('jail.index'))
            else:
                # Just delay/annoyance
                msg_extra = random.choice([
                    _(' 🛂 أزمة عالحاجز وتفتيش دقيق، بس مرقت بعد ما طلعوا روحك.'),
                    _(' 🛂 طابور وتفتيش… أخذ وقت، بس بالنهاية مشيت.'),
                    _(' 🛂 دقّقوا عليك كثير وتأخرت… بس عدّت.'),
                ])

    # 2. Settler Attack (5% chance) -> 16-20
    elif 16 <= event_roll <= 20:
        damage_percent = random.randint(5, 15)
        damage = int(user.max_health * (damage_percent / 100))
        current_health = user.health
        real_damage = min(current_health, damage)

        if real_damage >= current_health:
            # Critical injury -> Hospital
            hospital_time = 10
            # ResourceService.modify_resources(user.id, {'health': -real_damage}, ...) might not set exact 0 if race.
            # Close enough.
            # Better to set explicitly if dying.
            ResourceService.modify_resources(user.id,
                                             {'money': -travel_cost},
                                             'travel_cost_hospital',
                                             auto_commit=False,
                                             expected_version=None)
            user.hospital_until = datetime.now(
                timezone.utc) + timedelta(minutes=hospital_time)
            user.health = 0
            db.session.commit()
            flash(
                _('🚑 هاجم المستوطنون سيارتك! إصابتك خطيرة وتم نقلك للمستشفى.'),
                'danger')
            return redirect(url_for('hospital.index'))
        else:
            ResourceService.modify_resources(user.id,
                                             {'health': -real_damage},
                                             'settler_attack',
                                             auto_commit=False,
                                             expected_version=None)
            msg_extra = _(
                " 🧱 طلعولك مستوطنين ورموا حجار عالسيارة! انصبت وخسرت %(dmg)s من صحتك.",
                dmg=real_damage)

    # 3. Occupation Raid (Iqtiham) - 5% chance (21-25)
    elif 21 <= event_roll <= 25:
        # Determine outcome: Clash (30%), Arrest (30%), Escape (40%)
        raid_outcome = random.random()

        if raid_outcome < 0.3:  # Clash - 30%
            # User gets involved in clashes
            damage_percent = random.randint(10, 25)
            damage = int(user.max_health * (damage_percent / 100))
            xp_gain = random.randint(50, 150)  # Good XP reward

            current_health = user.health
            real_damage = min(current_health, damage)

            if real_damage >= current_health:
                # Critical -> Hospital
                hospital_time = 15
                user.hospital_until = datetime.now(
                    timezone.utc) + timedelta(minutes=hospital_time)
                user.health = 0
                ResourceService.modify_resources(user.id,
                                                 {'money': -travel_cost},
                                                 'travel_raid_hospital',
                                                 auto_commit=False,
                                                 expected_version=None)
                db.session.commit()
                flash(
                    _('🚑 الجيش مقتحم المدينة! تصاوبت خلال المواجهات وتم نقلك للمستشفى.'),
                    'danger')
                return redirect(url_for('hospital.index'))
            else:
                ResourceService.modify_resources(user.id,
                                                 {'health': -real_damage,
                                                  'exp': xp_gain},
                                                 'travel_raid_clash',
                                                 auto_commit=False,
                                                 expected_version=None)
                msg_extra = _(
                    " 💥 المدينة تتعرض لاقتحام! شاركت في المواجهات، تصاوبت (%(dmg)s-) بس كسبت خبرة مقاومة (%(xp)s+).",
                    dmg=real_damage,
                    xp=xp_gain)

        elif raid_outcome < 0.6:  # Arrest - 30%
            # Administrative Detention
            jail_time = random.randint(45, 120)  # Longer than usual
            user.jail_until = datetime.now(
                timezone.utc) + timedelta(minutes=jail_time)
            ResourceService.modify_resources(user.id,
                                             {'money': -travel_cost},
                                             'travel_raid_jail',
                                             auto_commit=False,
                                             expected_version=None)
            db.session.commit()
            flash(
                random.choice([
                    _('🚔 اقتحام واسع! حاصروك في الحارة وأخذوك اعتقال إداري لمدة %(time)s دقيقة.',
                      time=jail_time),
                    _('🚔 اقتحام بالمدينة… لقطوك من الشارع واعتقلوك إداريًا %(time)s دقيقة.',
                      time=jail_time),
                    _('🚔 الجيش مقتحم… ما لحقت تهرب. اعتقال إداري %(time)s دقيقة.',
                      time=jail_time),
                ]),
                'danger')
            return redirect(url_for('jail.index'))

        else:  # Escape - 40%
            msg_extra = _(
                " 🔦 الجيش مقتحم البلد! بس أنت ابن بلد وعارف الطرق المختصرة، نفذت منهم.")

    # 4. Mashboob Cars Campaign (5% chance) - 26-30
    elif 26 <= event_roll <= 30:
        # Check if user has an active vehicle
        from models import UserVehicle
        active_vehicle = UserVehicle.query.filter_by(
            user_id=user.id, is_active=True).first()

        if active_vehicle:
            # 50% chance to lose the car if this event triggers
            if random.random() < 0.5:
                vehicle_name = active_vehicle.vehicle.name
                db.session.delete(active_vehicle)
                # No refund, just loss. Occupation is brutal.
                # Maybe give some scrap metal money? No, total loss fits the
                # theme.

                # Atomic deduction for travel only
                ResourceService.modify_resources(user.id,
                                                 {'money': -travel_cost},
                                                 'travel_mashboob_loss',
                                                 auto_commit=False,
                                                 expected_version=None)
                # Removed premature commit to ensure atomicity with location
                # update

                # Prevent double billing
                travel_cost = 0

                flash(
                    _(
                        '🚜 حملة على السيارات المشطوبة! الجيش صادر سيارتك (%(car)s) ودمرها لأنها "غير قانونية". '
                        'راحت عليك!',
                        car=vehicle_name),
                    'danger')
                # User is stranded at target location (or source? code says they move at end).
                # Logic continues below to move user, which implies they found another way or walked.
                # But let's say they are stuck? No, better to just lose car and
                # arrive angry.
            else:
                msg_extra = _(
                    " 🚓 دورية شرطة بتلم السيارات المشطوبة، بس نمرتك صفرا ومشيت.")
        else:
            # No car, just saw the campaign
            msg_extra = _(
                " 🚜 الجيش بيلم السيارات المشطوبة بالشارع، منيح أنك مش سايق.")

    # 5. Surprise Inspection (Fahs Mofaje') - 5% chance - 31-35
    elif 31 <= event_roll <= 35:
        # Check for illegal items (Drugs/Weapons)
        # Assuming 'smuggling' type items are illegal
        illegal_items = UserItem.query.filter_by(user_id=user.id).join(
            Item).filter(Item.type.in_(['smuggling', 'weapon'])).all()

        has_contraband = False
        if illegal_items:
            # If equipped weapon, maybe okay? Smuggling is definitely bad.
            for ui in illegal_items:
                if ui.item.type == 'smuggling':
                    has_contraband = True
                    break

        if has_contraband:
            jail_time = 45
            ResourceService.modify_resources(user.id,
                                             {'money': -travel_cost},
                                             'travel_inspection_jail',
                                             auto_commit=False,
                                             expected_version=None)
            user.jail_until = datetime.now(
                timezone.utc) + timedelta(minutes=jail_time)
            db.session.commit()
            flash(
                random.choice([
                    _('👮 تفتيش مفاجئ! لقوا معك مهربات. "عوفر" بانتظارك لمدة %(time)s دقيقة.',
                      time=jail_time),
                    _('👮 فتشوا السيارة ولِقوا تهريب… حولّوك عالتحقيق %(time)s دقيقة.',
                      time=jail_time),
                    _('👮 تفتيش دقيق… والتهريب مكشوف. سجن %(time)s دقيقة.',
                      time=jail_time),
                ]),
                'danger')
            return redirect(url_for('jail.index'))
        else:
            msg_extra = random.choice([
                _(' 🔍 تفتيش مفاجئ ودقيق للسيارات، بس وضعك بالسليم.'),
                _(' 🔍 فتشوا الكل… الحمد لله وضعك نظيف.'),
                _(' 🔍 تدقيق وتفتيش… مرقت بدون مشاكل.'),
            ])

    # 6. Cousin Driver (5% chance)
    elif event_roll >= 96:
        travel_cost = 0
        msg_extra = _(" 🚕 طلع الشوفير ابن عمك! التوصيلة ببلاش.")

    # Atomic deduction
    # Note: travel_cost might be 0.
    if travel_cost > 0:
        if not ResourceService.modify_resources(
            user.id, {
                'money': -travel_cost}, 'travel_cost', auto_commit=False, expected_version=None):
            # Should not happen if checks passed and no intervening deductions,
            # but possible.
            flash(_('ليس لديك مال كافٍ للسفر!'), 'danger')
            return redirect(url_for('travel.index'))

    # current_user.money -= travel_cost # Removed
    user.location_id = target_location.id
    user.last_travel = datetime.now(timezone.utc)

    db.session.commit()

    flash(_('وصلت إلى %(name)s بنجاح!', name=target_location.name) +
          msg_extra, 'success')
    return redirect(url_for('travel.index'))
