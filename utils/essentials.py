from extensions import db
from models import Location, Item, OrganizedCrime, Crime, Vehicle, DailyTask
from models.hostess import Hostess
from flask_babel import _
import json
import os
import random
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
SEEDS_DIR = os.path.join(DATA_DIR, 'seeds')
TRAINING_DIR = os.path.join(DATA_DIR, 'training')

def load_json_seed(filename):
    path = os.path.join(SEEDS_DIR, filename)
    if not os.path.exists(path):
        print(f"Warning: Seed file not found: {path}")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def initialize_essentials(app):
    """Ensures all essential game data exists in the database."""
    with app.app_context():
        print("Checking essential game data...")
        initialize_locations()
        initialize_items()
        initialize_basic_crimes()
        initialize_organized_crimes()
        initialize_vehicles()
        initialize_hostesses()
        initialize_daily_tasks()
        take_economy_snapshot()
        db.session.commit()
        print("Essential game data verification completed.")

def initialize_locations():
    """Seeds initial locations from JSON."""
    locations_data = load_json_seed('locations.json')
    count = 0
    for data in locations_data:
        loc = Location.query.filter_by(name=data['name']).first()
        if not loc:
            loc = Location(
                name=data['name'],
                cost=data['cost'],
                cooldown=data['cooldown'],
                description=data['description'],
                specialty=data['specialty'],
                specialty_value=data['specialty_value'],
                image=data['image']
            )
            db.session.add(loc)
            count += 1
    
    if count > 0:
        print(f"Seeded {count} locations.")

def initialize_items():
    """Seeds basic items and smuggling items from JSON."""
    items_data = []
    items_data.extend(load_json_seed('items.json'))
    items_data.extend(load_json_seed('materials.json'))
    items_data.extend(load_json_seed('farm_products.json'))
    count = 0
    for data in items_data:
        # Check if item exists (handling both types)
        type_filter = data['type']
        item = Item.query.filter_by(name=data['name'], type=type_filter).first()
        
        if not item:
            item = Item(
                name=data['name'],
                description=data['description'],
                type=data['type'],
                cost=data['cost'],
                bonus_strength=data.get('bonus_strength', 0),
                bonus_defense=data.get('bonus_defense', 0),
                bonus_agility=data.get('bonus_agility', 0),
                ammo_needed=data.get('ammo_needed', 0),
                recover_energy=data.get('recover_energy', 0),
                recover_health=data.get('recover_health', 0),
                recover_brave=data.get('recover_brave', 0),
                is_black_market=data.get('is_black_market', True)
            )
            if data.get('image'):
                item.image = data.get('image')
            db.session.add(item)
            count += 1
        else:
            updated = False
            if (not item.image) and data.get('image'):
                item.image = data.get('image')
                updated = True
            if item.is_black_market is None and 'is_black_market' in data:
                item.is_black_market = data.get('is_black_market', True)
                updated = True
            if updated:
                db.session.add(item)
    if count > 0:
        print(f"Seeded {count} items.")

def initialize_basic_crimes():
    """Seeds basic single-player crimes from JSON."""
    crimes_data = load_json_seed('basic_crimes.json')
    count = 0
    for data in crimes_data:
        crime = Crime.query.filter_by(name=data['name']).first()
        if not crime:
            crime = Crime(
                name=data['name'],
                description=data['description'],
                energy_cost=data['energy_cost'],
                money_reward_min=data['money_reward_min'],
                money_reward_max=data['money_reward_max'],
                exp_reward=data['exp_reward'],
                min_level=data['min_level'],
                cooldown=data.get('cooldown', 60),
                min_strength=data.get('min_strength', 0),
                min_agility=data.get('min_agility', 0),
                min_intelligence=data.get('min_intelligence', 0),
                daily_limit=data.get('daily_limit', 0)
            )
            if data.get('image'):
                crime.image = data.get('image')
            if data.get('reward_type'):
                crime.reward_type = data.get('reward_type')
            reward_item_name = data.get('reward_item_name')
            if reward_item_name:
                reward_item = Item.query.filter_by(name=reward_item_name).first()
                if reward_item:
                    crime.reward_item_id = reward_item.id
            db.session.add(crime)
            count += 1
        else:
            updated = False
            seed_cooldown = data.get('cooldown', 60)
            if crime.cooldown in (None, 60) and seed_cooldown != crime.cooldown:
                crime.cooldown = seed_cooldown
                updated = True

            seed_min_level = data.get('min_level', 1)
            if crime.min_level in (None, 1) and seed_min_level != crime.min_level:
                crime.min_level = seed_min_level
                updated = True

            seed_energy_cost = data.get('energy_cost', 10)
            if crime.energy_cost in (None, 10) and seed_energy_cost != crime.energy_cost:
                crime.energy_cost = seed_energy_cost
                updated = True

            seed_money_min = data.get('money_reward_min', 10)
            if crime.money_reward_min in (None, 10) and seed_money_min != crime.money_reward_min:
                crime.money_reward_min = seed_money_min
                updated = True

            seed_money_max = data.get('money_reward_max', 100)
            if crime.money_reward_max in (None, 100) and seed_money_max != crime.money_reward_max:
                crime.money_reward_max = seed_money_max
                updated = True

            seed_exp_reward = data.get('exp_reward', 10)
            if crime.exp_reward in (None, 10) and seed_exp_reward != crime.exp_reward:
                crime.exp_reward = seed_exp_reward
                updated = True

            seed_min_strength = data.get('min_strength', 0)
            if crime.min_strength in (None, 0) and seed_min_strength != crime.min_strength:
                crime.min_strength = seed_min_strength
                updated = True

            seed_min_agility = data.get('min_agility', 0)
            if crime.min_agility in (None, 0) and seed_min_agility != crime.min_agility:
                crime.min_agility = seed_min_agility
                updated = True

            seed_min_intelligence = data.get('min_intelligence', 0)
            if crime.min_intelligence in (None, 0) and seed_min_intelligence != crime.min_intelligence:
                crime.min_intelligence = seed_min_intelligence
                updated = True

            seed_reward_type = data.get('reward_type')
            if crime.reward_type == 'money' and seed_reward_type and seed_reward_type != 'money':
                crime.reward_type = seed_reward_type
                updated = True

            if (not crime.image or crime.image == 'default_crime.jpg') and data.get('image'):
                crime.image = data.get('image')
                updated = True
            if (not crime.description) and data.get('description'):
                crime.description = data.get('description')
                updated = True
                
            seed_daily_limit = data.get('daily_limit', 0)
            if crime.daily_limit is None or seed_daily_limit != crime.daily_limit:
                crime.daily_limit = seed_daily_limit
                updated = True

            if updated:
                db.session.add(crime)
    if count > 0:
        print(f"Seeded {count} basic crimes.")

def initialize_organized_crimes():
    """Seeds organized crimes (Heists) from JSON."""
    crimes_data = load_json_seed('organized_crimes.json')
    count = 0
    for data in crimes_data:
        crime = OrganizedCrime.query.filter_by(name=data['name']).first()
        if not crime:
            crime = OrganizedCrime(name=data['name'])
            crime.description = data.get('description')
            crime.min_level = data.get('min_level', 10)
            crime.min_members = data.get('min_members', 2)
            crime.max_members = data.get('max_members', 4)
            crime.duration_minutes = data.get('duration_minutes', 60)
            crime.cooldown_hours = data.get('cooldown_hours', 24)
            crime.energy_cost = data.get('energy_cost', 50)
            crime.money_reward_min = data.get('money_reward_min', 1000)
            crime.money_reward_max = data.get('money_reward_max', 5000)
            crime.exp_reward = data.get('exp_reward', 100)
            crime.min_gang_level = data.get('min_gang_level', 1)
            crime.roles_config = data.get('roles_config', [])
            crime.requirements = json.dumps(data.get('requirements', {}), ensure_ascii=False)
            crime.image = data.get('image', crime.image)
            crime.is_active = True
            db.session.add(crime)
            count += 1
        else:
            updated = False
            if (not crime.image or crime.image == 'default_heist.jpg') and data.get('image'):
                crime.image = data.get('image')
                updated = True
            if data.get('roles_config'):
                needs_role_upgrade = False
                try:
                    if not crime.roles_config:
                        needs_role_upgrade = True
                    else:
                        for r in (crime.roles_config or []):
                            if isinstance(r, dict) and ('min_stats' not in r) and ('req' in r):
                                needs_role_upgrade = True
                                break
                except Exception:
                    needs_role_upgrade = True
                if needs_role_upgrade:
                    crime.roles_config = data.get('roles_config', [])
                    updated = True

            if data.get('requirements') is not None:
                needs_req_upgrade = False
                try:
                    if not crime.requirements or crime.requirements == "{}":
                        needs_req_upgrade = True
                    elif '"required_item"' in json.dumps(data.get('requirements', {}), ensure_ascii=False) and ('required_item' not in (crime.requirements or '')):
                        needs_req_upgrade = True
                except Exception:
                    needs_req_upgrade = True
                if needs_req_upgrade:
                    crime.requirements = json.dumps(data.get('requirements', {}), ensure_ascii=False)
                    updated = True
            if updated:
                db.session.add(crime)
    if count > 0:
        print(f"Seeded {count} organized crimes.")

def initialize_vehicles():
    """Seeds basic vehicles from JSON."""
    vehicles_data = load_json_seed('vehicles.json')
    count = 0
    for data in vehicles_data:
        if not Vehicle.query.filter_by(name=data['name']).first():
            vehicle = Vehicle(
                name=data['name'],
                type=data['type'],
                description=data['description'],
                price=data['price'],
                speed=data['speed'],
                defense=data['defense'],
                risk=data['risk']
            )
            db.session.add(vehicle)
            count += 1
    if count > 0:
        print(f"Seeded {count} vehicles.")

def initialize_hostesses():
    """Seeds casino hostesses from Deep Training folders."""
    hostesses_dir = os.path.join(TRAINING_DIR, 'hostesses')
    if not os.path.exists(hostesses_dir):
        print("Warning: Hostesses training directory not found.")
        return

    # Iterate over subdirectories (jasmin, layla, etc.)
    count = 0
    for name in os.listdir(hostesses_dir):
        hostess_path = os.path.join(hostesses_dir, name)
        if os.path.isdir(hostess_path):
            profile_file = os.path.join(hostess_path, 'profile.json')
            prompt_file = os.path.join(hostess_path, 'system_prompt.txt')
            
            if os.path.exists(profile_file) and os.path.exists(prompt_file):
                try:
                    with open(profile_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        system_prompt = f.read()
                    
                    hostess = Hostess.query.filter_by(name=data['name']).first()
                    if not hostess:
                        hostess = Hostess(name=data['name'])
                        db.session.add(hostess)
                        count += 1
                    
                    # Update fields
                    hostess.role = data['role']
                    hostess.price = data['price']
                    hostess.description = data['description']
                    hostess.dialogue_style = data['dialogue_style']
                    hostess.intro_message = data['intro_message']
                    hostess.buff_type = data['buff_type']
                    hostess.buff_value = data['buff_value']
                    hostess.image = data['image']
                    hostess.video = data.get('video')
                    vp = data.get('video_prompt')
                    if vp:
                        try:
                            hostess.video_prompt = json.dumps(vp, ensure_ascii=False)
                        except Exception:
                            hostess.video_prompt = None
                    hostess.personality_config = json.dumps(data['personality_config'])
                    hostess.system_prompt = system_prompt
                    hostess.is_public = data.get('is_public', False)
                    
                    # Max Stats
                    hostess.level = data.get('level', 1)
                    hostess.exp = data.get('exp', 0)
                    hostess.charm = data.get('charm', 10)
                    hostess.intelligence = data.get('intelligence', 10)
                except Exception as e:
                    print(f"ERROR loading hostess {name}: {e}")

    if count > 0:
        print(f"Seeded/Updated {count} hostesses from deep training data.")


def initialize_daily_tasks():
    defaults = load_json_seed('daily_tasks.json')
    if not defaults:
        defaults = [
            {
                "description": "نفّذ 3 جرائم",
                "target_type": "crime",
                "target_count": 3,
                "reward_money": 450,
                "reward_exp": 35,
                "min_level": 1,
                "is_active": True,
            }
        ]

    inserted = 0
    updated = 0
    deactivated = 0
    for data in defaults:
        description = data.get("description")
        target_type = data.get("target_type")
        target_count = int(data.get("target_count", 1))
        min_level = int(data.get("min_level", 1))
        reward_money = int(data.get("reward_money", 0))
        reward_exp = int(data.get("reward_exp", 0))
        is_active = bool(data.get("is_active", True))

        if not description or not target_type:
            continue

        candidates = DailyTask.query.filter_by(
            target_type=target_type,
            target_count=target_count,
            min_level=min_level,
        ).all()

        task = next((t for t in candidates if t.description == description), None)
        if not task and candidates:
            task = candidates[0]

        if not task:
            task = DailyTask(
                description=description,
                target_type=target_type,
                target_count=target_count,
                reward_money=reward_money,
                reward_exp=reward_exp,
                min_level=min_level,
                is_active=is_active,
            )
            db.session.add(task)
            inserted += 1
            continue

        for other in candidates:
            if other.id == task.id:
                continue
            if other.description == description:
                continue
            if other.is_active:
                other.is_active = False
                db.session.add(other)
                deactivated += 1

        changed = False
        if task.description != description:
            task.description = description
            changed = True
        if task.reward_money != reward_money:
            task.reward_money = reward_money
            changed = True
        if task.reward_exp != reward_exp:
            task.reward_exp = reward_exp
            changed = True
        if task.is_active != is_active:
            task.is_active = is_active
            changed = True
        if changed:
            db.session.add(task)
            updated += 1

    if inserted > 0 or updated > 0:
        print(f"Seeded {inserted} daily tasks.")
    if deactivated > 0:
        print(f"Deactivated {deactivated} duplicate daily tasks.")

def take_economy_snapshot():
    """Takes a daily snapshot of the economy for analysis."""
    from models.user import User
    from models.log import EconomySnapshot
    from sqlalchemy import func

    today = datetime.now(timezone.utc).date()
    
    # Check if snapshot exists for today
    if EconomySnapshot.query.filter_by(date=today).first():
        return

    # Calculate stats
    total_money = db.session.query(func.sum(User.money)).scalar() or 0
    total_bank = db.session.query(func.sum(User.bank_balance)).scalar() or 0
    user_count = User.query.count()
    
    if user_count == 0:
        avg_wealth = 0
    else:
        avg_wealth = (total_money + total_bank) // user_count

    # Top 1% share
    limit = max(1, int(user_count * 0.01))
    top_users = User.query.with_entities(User.money, User.bank_balance).order_by((User.money + User.bank_balance).desc()).limit(limit).all()
    
    top_wealth = sum([(u.money + u.bank_balance) for u in top_users])
    total_wealth = total_money + total_bank
    
    top_1_percent_share = (top_wealth / total_wealth * 100) if total_wealth > 0 else 0

    snapshot = EconomySnapshot(
        date=today,
        total_money=total_money,
        total_bank=total_bank,
        avg_wealth=avg_wealth,
        top_1_percent_share=top_1_percent_share,
        active_users_24h=0 # Placeholder
    )
    db.session.add(snapshot)
    db.session.commit()
    print(f"Economy Snapshot taken for {today}")
