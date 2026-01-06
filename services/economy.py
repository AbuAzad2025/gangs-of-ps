from extensions import db
from models.user import User
from models.log import MoneySinkLog, EconomySnapshot, UserLog
from models.system import SystemConfig
from models.facility import UserFacility
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from flask import current_app
from services.resource_service import ResourceService

def get_bank_fee_config():
    """Returns fee configuration (thresholds and percentages)."""
    try:
        tier1_threshold = int(SystemConfig.get_value("bank_fee_tier1_threshold", 50000))
        tier2_threshold = int(SystemConfig.get_value("bank_fee_tier2_threshold", 200000))
        
        tier1_pct = float(SystemConfig.get_value("bank_fee_tier1_pct", 0.005)) # 0.5%
        tier2_pct = float(SystemConfig.get_value("bank_fee_tier2_pct", 0.012)) # 1.2%
        
        return {
            "tier1_threshold": tier1_threshold,
            "tier2_threshold": tier2_threshold,
            "tier1_pct": tier1_pct,
            "tier2_pct": tier2_pct
        }
    except:
        return {
            "tier1_threshold": 50000,
            "tier2_threshold": 200000,
            "tier1_pct": 0.005,
            "tier2_pct": 0.012
        }

def calculate_bank_fee(balance, config):
    if balance < config["tier1_threshold"]:
        return 0, "No Fee"
    elif balance < config["tier2_threshold"]:
        fee = int(balance * config["tier1_pct"])
        return fee, f"Tier 1 ({config['tier1_pct']*100}%)"
    else:
        fee = int(balance * config["tier2_pct"])
        return fee, f"Tier 2 ({config['tier2_pct']*100}%)"

def apply_daily_sinks():
    """
    Applies daily passive sinks (Bank Fees, Maintenance).
    Should be called once per day via scheduler.
    """
    current_app.logger.info("--- Starting Daily Economy Sinks ---")
    
    # 1. Bank Fees
    config = get_bank_fee_config()
    
    # Iterate all users with bank balance > threshold
    # For large scale, this should be batched. For now, we process direct query.
    users = User.query.filter(User.bank_balance >= config["tier1_threshold"]).all()
    
    total_fees = 0
    count = 0
    
    for user in users:
        fee, reason = calculate_bank_fee(user.bank_balance, config)
        if fee > 0:
            try:
                # Use ResourceService for atomic update and locking
                if ResourceService.modify_resources(user.id, {'bank_balance': -fee}, 'bank_fee', auto_commit=False, expected_version=None):
                    log = MoneySinkLog(
                        user_id=user.id,
                        sink_type="bank_fee",
                        amount=fee,
                        details=reason
                    )
                    db.session.add(log)
                    db.session.commit()
                    
                    total_fees += fee
                    count += 1
            except Exception as e:
                current_app.logger.error(f"Error applying fee for user {user.id}: {e}")
                db.session.rollback()
                continue
    
    # Removed bulk commit as we commit per user now
    current_app.logger.info(f"Applied Bank Fees: {total_fees} from {count} users.")
    
    # 2. Property Maintenance (Facilities)
    # Facilities: Houses, Warehouses, etc. stored in UserFacility
    # Logic: Cost = Base * Level * Multiplier
    try:
        maint_multiplier = float(SystemConfig.get_value("maintenance_multiplier", 1.0))
        base_costs = {
            "house": 500,
            "warehouse": 1000,
            "lab": 2000,
            "bunker": 5000
        }
        
        facilities = UserFacility.query.filter(UserFacility.level > 0).all()
        maint_total = 0
        maint_count = 0
        
        for fac in facilities:
            base = base_costs.get(fac.facility_key, 500)
            cost = int(base * fac.level * maint_multiplier)
            
            if cost > 0:
                try:
                    user = db.session.get(User, fac.user_id)
                    if user and user.money >= cost:
                         if ResourceService.modify_resources(user.id, {'money': -cost}, f"maintenance_{fac.facility_key}", auto_commit=False, expected_version=None):
                             log = MoneySinkLog(
                                user_id=user.id,
                                sink_type="maintenance",
                                amount=cost,
                                details=f"{fac.facility_key.title()} Lv{fac.level} Maintenance"
                             )
                             db.session.add(log)
                             db.session.commit()
                             maint_total += cost
                             maint_count += 1
                    elif user:
                        # User cannot pay maintenance!
                        # Logic: Disable facility or downgrade?
                        # For now: Just log warning or maybe downgrade level if repeated (future)
                        # We will just take what they have or 0, and maybe mark facility inactive?
                        # Let's just skip taking money if 0, but maybe track debt?
                        # Simple: If cant pay, facility level drops by 1? (Harsh but effective sink)
                        # Let's be gentle first: Just take what is available up to cost
                        paid = min(user.money, cost)
                        if paid > 0:
                            if ResourceService.modify_resources(user.id, {'money': -paid}, f"maintenance_partial_{fac.facility_key}", auto_commit=False, expected_version=None):
                                log = MoneySinkLog(
                                    user_id=user.id,
                                    sink_type="maintenance_partial",
                                    amount=paid,
                                    details=f"{fac.facility_key.title()} Lv{fac.level} Partial"
                                )
                                db.session.add(log)
                                db.session.commit()
                                maint_total += paid
                                maint_count += 1
                except Exception as e:
                    current_app.logger.error(f"Error processing maintenance for facility {fac.id}: {e}")
                    db.session.rollback()
        
        # Removed bulk commit
        current_app.logger.info(f"Applied Maintenance: {maint_total} from {maint_count} facilities.")
        
    except Exception as e:
        current_app.logger.error(f"Error applying maintenance: {e}")
        db.session.rollback()
    
    return {
        "bank_fees_collected": total_fees,
        "users_charged": count,
        "maintenance_collected": maint_total if 'maint_total' in locals() else 0
    }

def create_daily_snapshot():
    """
    Creates a snapshot of the economy for today.
    """
    current_app.logger.info("--- Creating Economy Snapshot ---")
    today = datetime.now(timezone.utc).date()
    
    # Check if snapshot already exists
    existing = EconomySnapshot.query.filter_by(date=today).first()
    if existing:
        current_app.logger.info(f"Snapshot for {today} already exists. Updating...")
        snapshot = existing
    else:
        snapshot = EconomySnapshot(date=today)
        db.session.add(snapshot)
    
    # Calculate stats
    total_money = db.session.query(func.sum(User.money)).scalar() or 0
    total_bank = db.session.query(func.sum(User.bank_balance)).scalar() or 0
    user_count = User.query.count()
    
    snapshot.total_money = total_money
    snapshot.total_bank = total_bank
    total_wealth = total_money + total_bank
    snapshot.avg_wealth = int(total_wealth / user_count) if user_count > 0 else 0
    
    # Top 1% Share
    if user_count > 0:
        top_count = max(1, int(user_count * 0.01))
        top_users = User.query.with_entities(User.money + User.bank_balance).order_by((User.money + User.bank_balance).desc()).limit(top_count).all()
        top_wealth = sum([u[0] for u in top_users])
        
        snapshot.top_1_percent_share = (top_wealth / total_wealth * 100) if total_wealth > 0 else 0
    
    # Active Users (using UserLog)
    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    snapshot.active_users_24h = db.session.query(UserLog.user_id).filter(
        UserLog.timestamp >= one_day_ago
    ).distinct().count()
    
    db.session.commit()
    current_app.logger.info(f"Snapshot Created: Total Wealth={total_wealth}, Top 1%={snapshot.top_1_percent_share:.2f}%")
    return snapshot

def adjust_economy_policy():
    """
    Checks EconomySnapshot and adjusts SystemConfig automatically.
    The 'Smart' Economy Logic.
    """
    today = datetime.now(timezone.utc).date()
    snapshot = EconomySnapshot.query.filter_by(date=today).first()
    
    if not snapshot:
        return "No snapshot found for today."
        
    changes = []
    
    # Inflation Trigger: Top 1% holds too much wealth
    if snapshot.top_1_percent_share > 45.0:
        # Increase Tier 2 Fee
        current_pct = float(SystemConfig.get_value("bank_fee_tier2_pct", 0.012))
        if current_pct < 0.025: # Cap at 2.5%
            new_pct = current_pct + 0.002
            SystemConfig.set_value("bank_fee_tier2_pct", str(new_pct), "Auto-adjusted due to high inequality")
            changes.append(f"Increased Tier 2 Fee to {new_pct:.3f}")
    
    # Deflation Trigger: Average wealth dropping too fast (TODO)
    
    if changes:
        return f"Economy Policy Adjusted: {', '.join(changes)}"
    else:
        return "Economy stable. No policy changes."

def process_daily_economy_checks():
    """
    Master function to run all daily economy tasks.
    """
    current_app.logger.info("\n=== PROCESSING DAILY ECONOMY CHECKS ===")
    
    # 1. Apply Sinks (Remove money first)
    apply_daily_sinks()
    
    # 2. Create Snapshot (Record state after sinks)
    create_daily_snapshot()
    
    # 3. Adjust Policy (React to new state)
    result = adjust_economy_policy()
    current_app.logger.info(result)
    
    current_app.logger.info("=== DAILY ECONOMY CHECKS COMPLETE ===\n")
