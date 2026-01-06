from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models import Item, UserItem, User, Message, SystemConfig, MoneySinkLog, UserLog, Vehicle, UserVehicle
from models.contract import FarmSupplyContract
from models.facility import UserFacility
from models.location import Location
from models.combat import ActiveIntel
from .utils import update_daily_task_progress
from services.resource_service import ResourceService
from datetime import datetime, timedelta, timezone
import math
import random
import json
from services.requirements import tier_for_user, tier_rank, check_requirements

bp = Blueprint('black_market', __name__, url_prefix='/black_market')

FARM_PRODUCT_NAMES = {
    "زيت زيتون بلدي",
    "زيت زيتون ممتاز",
    "زعتر بلدي",
    "زعتر جبلي فاخر",
    "صابون نابلسي",
    "صابون نابلسي فاخر",
    "تمر أريحا",
    "كوفية فلسطينية",
    "كوفية مطرزة",
    "فخار الخليل",
}


def _best_contract_facility_level(user_id):
    keys = ["olive_press", "zaatar_nursery", "soap_workshop", "keffiyeh_workshop"]
    best_level = 0
    for k in keys:
        uf = UserFacility.query.filter_by(user_id=user_id, facility_key=k).first()
        lvl = int(uf.level) if uf and uf.level is not None else 0
        if lvl >= 2 and lvl > best_level:
            best_level = lvl
    return best_level


def _contract_offer(user):
    tier = tier_for_user(user)
    t = tier_rank(tier)
    best_level = _best_contract_facility_level(user.id)
    if best_level <= 0:
        return None

    duration_minutes = int(SystemConfig.get_value("farm_contract_duration_minutes", "60") or 60)
    base_cost = int(SystemConfig.get_value("farm_contract_base_cost", "25") or 25)
    cost_per_tier = int(SystemConfig.get_value("farm_contract_cost_per_tier", "10") or 10)
    base_bonus = float(SystemConfig.get_value("farm_contract_base_bonus", "0.10") or 0.10)
    bonus_per_level = float(SystemConfig.get_value("farm_contract_bonus_per_facility_level", "0.03") or 0.03)
    max_bonus = float(SystemConfig.get_value("farm_contract_max_bonus", "0.25") or 0.25)

    bonus = min(max_bonus, base_bonus + bonus_per_level * max(0, best_level - 1) + 0.01 * max(0, t - 1))
    cost = max(1, base_cost + cost_per_tier * max(0, t - 1))

    return {"duration_minutes": duration_minutes, "bonus_percent": bonus, "cost_diamonds": cost}

# --- Smuggling Helpers ---
def get_smuggling_price(item, location_id=None):
    """Calculates dynamic price based on location and time (hourly)"""
    if not location_id:
        return item.cost
        
    # Seed based on hour, location, and item to ensure consistent prices for everyone in that hour/loc
    now = datetime.now(timezone.utc)
    hour_seed = int(now.timestamp() / 3600) 
    seed = hour_seed + location_id + item.id
    
    # Use a local random instance to not affect global state
    rng = random.Random(seed)
    
    # Multiplier between 0.7 and 1.6
    multiplier = rng.uniform(0.7, 1.6)
    
    # Specific location biases (optional, can be added later)
    
    return int(item.cost * multiplier)
 
def _get_black_market_event():
    raw_key = SystemConfig.get_value('black_market_event', 'none') or 'none'
    key = (raw_key or 'none').strip()
    raw_loc = SystemConfig.get_value('black_market_event_location_id', None)
    try:
        loc_id = int(raw_loc) if raw_loc not in (None, '', 'none') else None
    except Exception:
        loc_id = None
    event = {
        "key": key,
        "location_id": loc_id,
        "title": None,
        "description": None,
        "type": "neutral",
    }
    if key == 'smuggling_boost':
        event["title"] = _('فوضى على الحدود')
        event["description"] = _('أسعار شراء وبيع بضائع التهريب أعلى من المعتاد في المناطق المتأثرة.')
        event["type"] = "buff"
    elif key == 'smuggling_crackdown':
        event["title"] = _('حملة تفتيش على المعابر')
        event["description"] = _('الأسعار أقل من المعتاد وخطر الخسارة أعلى في المناطق المتأثرة.')
        event["type"] = "nerf"
    else:
        event["key"] = "none"
    return event

def _apply_black_market_event(price, location_id, event):
    if not event:
        return price
    key = event.get("key") or "none"
    if key == "none":
        return price
    target_loc = event.get("location_id")
    if target_loc and location_id and location_id != target_loc:
        return price
    if key == "smuggling_boost":
        return int(price * 1.25)
    if key == "smuggling_crackdown":
        return int(price * 0.75)
    return price

from sqlalchemy import text

from models.market import Auction, AuctionBid

def _sweep_auction_refunds(auction_id):
    """
    Ensures only the highest bidder holds the money. 
    Refunds all other outbid users atomically.
    """
    try:
        # Get all unrefunded bids
        bids = AuctionBid.query.filter_by(auction_id=auction_id, is_refunded=False)\
            .order_by(AuctionBid.amount.desc(), AuctionBid.timestamp.asc()).all()
        
        if not bids:
            return None
            
        # Highest bid keeps money (Winner)
        winner = bids[0]
        
        # Others get refunded
        for b in bids[1:]:
            # Atomic check-and-update to prevent double refunds
            rows = AuctionBid.query.filter(AuctionBid.id == b.id, AuctionBid.is_refunded == False).update({
                AuctionBid.is_refunded: True
            }, synchronize_session=False)
            
            if rows > 0:
                # Refund Money
                ResourceService.modify_resources(b.bidder_id, {'money': b.amount}, 'auction_refund_sweep', auto_commit=False)
        
        db.session.commit()
        return winner
    except Exception as e:
        current_app.logger.error(f"Error in sweep refunds: {e}")
        return None

def process_expired_auctions():
    """Checks for expired auctions and processes them."""
    now = datetime.now(timezone.utc)
    
    # 1. Fetch potential expired auctions (dirty read is fine here)
    expired_ids = [a.id for a in Auction.query.filter(
        Auction.status == 'active',
        Auction.end_time <= now
    ).all()]
    
    if not expired_ids:
        return

    for auc_id in expired_ids:
        # 2. Atomic claim: Try to set status to 'processing'
        # This ensures only ONE thread/process handles this specific auction
        rows_updated = Auction.query.filter(
            Auction.id == auc_id, 
            Auction.status == 'active'
        ).update({
            Auction.status: 'processing'
        }, synchronize_session=False)
        
        if rows_updated == 0:
            continue # Another thread claimed it or it's already done
            
        try:
            # Commit the claim so other threads see it immediately
            db.session.commit()
            
            # Now we have exclusive rights to process this auction
            auc = Auction.query.get(auc_id)
            if not auc: 
                continue

            # First, ensure refunds are clean
            _sweep_auction_refunds(auc.id)
            
            # Get highest active bid
            highest_bid = AuctionBid.query.filter_by(auction_id=auc.id, is_refunded=False).order_by(AuctionBid.amount.desc()).first()
            
            if highest_bid:
                # Lock Winner and Seller to prevent deadlocks
                users_to_lock = sorted(list(set(filter(None, [highest_bid.bidder_id, auc.seller_id]))))
                for uid in users_to_lock:
                    db.session.query(User).filter_by(id=uid).with_for_update().first()

                winner = User.query.get(highest_bid.bidder_id)
                if winner:
                    # Distribute Item
                    if auc.item_type == 'item':
                        try:
                            item_id = int(auc.item_id)
                            u_item = UserItem.query.filter_by(user_id=winner.id, item_id=item_id).first()
                            
                            old_qty = u_item.quantity if u_item else 0
                            
                            if u_item:
                                u_item.quantity += 1
                            else:
                                u_item = UserItem(user_id=winner.id, item_id=item_id, quantity=1, is_equipped=False)
                                db.session.add(u_item)
                            
                            # Log Item Gain
                            log = UserLog(
                                user_id=winner.id,
                                action='AUCTION_WIN_ITEM',
                                details=json.dumps({'item_id': item_id, 'auction_id': auc.id}),
                                result='success',
                                before_state={'quantity': old_qty},
                                after_state={'quantity': old_qty + 1},
                                ip_address='System',
                                user_agent='System'
                            )
                            db.session.add(log)
                            
                            # Notify Winner
                            msg = Message(
                                sender_id=None,
                                recipient_id=winner.id,
                                subject=_("مبروك! لقد فزت بالمزاد"),
                                body=_("لقد فزت بمزاد %(item)s بسعر %(price)s", item=auc.item_id, price=highest_bid.amount)
                            )
                            db.session.add(msg)
                        except Exception as e:
                            current_app.logger.error(f"Error distributing auction item: {e}")

                    elif auc.item_type == 'vehicle':
                        try:
                            vehicle_id = int(auc.item_id)
                            
                            existing_count = UserVehicle.query.filter_by(user_id=winner.id, vehicle_id=vehicle_id).count()
                            
                            new_uv = UserVehicle(
                                user_id=winner.id,
                                vehicle_id=vehicle_id,
                                is_active=False,
                                condition=100
                            )
                            db.session.add(new_uv)
                            
                            # Log Vehicle Gain
                            log = UserLog(
                                user_id=winner.id,
                                action='AUCTION_WIN_VEHICLE',
                                details=json.dumps({'vehicle_id': vehicle_id, 'auction_id': auc.id}),
                                result='success',
                                before_state={'vehicle_count': existing_count},
                                after_state={'vehicle_count': existing_count + 1},
                                ip_address='System',
                                user_agent='System'
                            )
                            db.session.add(log)
                            
                            msg = Message(
                                sender_id=None,
                                recipient_id=winner.id,
                                subject=_("مبروك! لقد فزت بالمزاد"),
                                body=_("لقد فزت بمركبة جديدة من المزاد!")
                            )
                            db.session.add(msg)
                        except Exception as e:
                            current_app.logger.error(f"Error distributing auction vehicle: {e}")
                    
                    elif auc.item_type == 'title':
                         # Titles might be handled differently or just advisory here
                         pass

                # Transfer money to seller if exists
                if auc.seller_id:
                    seller = db.session.get(User, auc.seller_id)
                    if seller:
                        # Apply Market Tax (15%) - Economy Sink
                        tax_rate = 0.15
                        tax_amount = int(highest_bid.amount * tax_rate)
                        net_amount = highest_bid.amount - tax_amount
                        
                        # Atomic Update with logging
                        ResourceService.modify_resources(seller.id, {'money': net_amount}, 'auction_sale', auto_commit=False, expected_version=seller.version)
                        
                        # Log to MoneySinkLog
                        if tax_amount > 0:
                            sink_log = MoneySinkLog(
                                user_id=seller.id,
                                sink_type='market_tax',
                                amount=tax_amount,
                                details=f"Auction ID: {auc.id}, Item Type: {auc.item_type}, Price: {highest_bid.amount}"
                            )
                            db.session.add(sink_log)
                        
                        msg = Message(
                            sender_id=None,
                            recipient_id=seller.id,
                            subject=_("تم بيع الغرض في المزاد"),
                            body=_("تم بيع غرضك بسعر %(price)s. تم خصم ضريبة سوق %(tax)s (%(rate)s%%). صافي الربح: %(net)s", 
                                   price=highest_bid.amount, tax=tax_amount, rate=int(tax_rate*100), net=net_amount)
                        )
                        db.session.add(msg)

                auc.status = 'completed'
                auc.winner_id = highest_bid.bidder_id
                auc.current_price = highest_bid.amount

            else:
                # No bids - Return item to seller
                auc.status = 'expired'
                
                if auc.seller_id:
                    # Lock Seller
                    db.session.query(User).filter_by(id=auc.seller_id).with_for_update().first()
                    
                    seller = User.query.get(auc.seller_id)
                    if seller:
                        if auc.item_type == 'item':
                            try:
                                item_id = int(auc.item_id)
                                u_item = UserItem.query.filter_by(user_id=seller.id, item_id=item_id).first()
                                old_qty = u_item.quantity if u_item else 0
                                
                                if u_item:
                                    u_item.quantity += 1
                                else:
                                    u_item = UserItem(user_id=seller.id, item_id=item_id, quantity=1, is_equipped=False)
                                    db.session.add(u_item)
                                    
                                # Log Return
                                log = UserLog(
                                    user_id=seller.id,
                                    action='AUCTION_RETURN_ITEM',
                                    details=json.dumps({'item_id': item_id, 'auction_id': auc.id}),
                                    result='success',
                                    before_state={'quantity': old_qty},
                                    after_state={'quantity': old_qty + 1},
                                    ip_address='System',
                                    user_agent='System'
                                )
                                db.session.add(log)
                                
                                msg = Message(
                                    sender_id=None,
                                    recipient_id=seller.id,
                                    subject=_("انتهى المزاد"),
                                    body=_("انتهى المزاد دون عروض. تم إعادة الغرض إلى مخزونك.")
                                )
                                db.session.add(msg)
                            except Exception as e:
                                current_app.logger.error(f"Error returning auction item: {e}")

                        elif auc.item_type == 'vehicle':
                             try:
                                vehicle_id = int(auc.item_id)
                                existing_count = UserVehicle.query.filter_by(user_id=seller.id, vehicle_id=vehicle_id).count()
                                
                                new_uv = UserVehicle(
                                    user_id=seller.id,
                                    vehicle_id=vehicle_id,
                                    is_active=False,
                                    condition=100
                                )
                                db.session.add(new_uv)
                                
                                log = UserLog(
                                    user_id=seller.id,
                                    action='AUCTION_RETURN_VEHICLE',
                                    details=json.dumps({'vehicle_id': vehicle_id, 'auction_id': auc.id}),
                                    result='success',
                                    before_state={'vehicle_count': existing_count},
                                    after_state={'vehicle_count': existing_count + 1},
                                    ip_address='System',
                                    user_agent='System'
                                )
                                db.session.add(log)
                                
                                msg = Message(
                                    sender_id=None,
                                    recipient_id=seller.id,
                                    subject=_("انتهى المزاد"),
                                    body=_("انتهى المزاد دون عروض. تم إعادة المركبة إلى كراجك.")
                                )
                                db.session.add(msg)
                             except Exception as e:
                                current_app.logger.error(f"Error returning auction vehicle: {e}")
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing expired auction {auc_id}: {e}")
            # Reset status so it can be retried? Or mark as error?
            # For now, maybe reset to active to retry, or leave as processing/error
            # Let's set to active to retry, but with caution
            try:
                Auction.query.filter_by(id=auc_id).update({Auction.status: 'active'})
                db.session.commit()
            except: pass

@bp.route('/auctions/create', methods=['GET', 'POST'])
@login_required
def create_auction():
    if request.method == 'POST':
        user_item_id = request.form.get('user_item_id', type=int)
        start_price = request.form.get('start_price', type=int)
        duration = request.form.get('duration', type=int)

        if not user_item_id or not start_price or not duration:
            flash(_('يرجى ملء جميع الحقول!'), 'danger')
            return redirect(url_for('black_market.create_auction'))
        
        if start_price < 1000:
            flash(_('سعر البداية يجب أن يكون 1000 على الأقل!'), 'danger')
            return redirect(url_for('black_market.create_auction'))
            
        valid_durations = [1, 6, 12, 24]
        if duration not in valid_durations:
            flash(_('مدة غير صالحة!'), 'danger')
            return redirect(url_for('black_market.create_auction'))

        try:
            # Lock User first to prevent deadlocks
            db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

            # Lock UserItem
            user_item = UserItem.query.filter_by(id=user_item_id, user_id=current_user.id).with_for_update().first()
            
            if not user_item or user_item.quantity < 1:
                flash(_('الغرض غير موجود أو نفدت الكمية!'), 'danger')
                return redirect(url_for('black_market.create_auction'))
                
            if user_item.is_equipped:
                flash(_('لا يمكن بيع غرض مجهز!'), 'danger')
                return redirect(url_for('black_market.create_auction'))

            # Check max price limit (Anti-Cheating)
            max_price = user_item.item.cost * 3
            if start_price > max_price:
                flash(_('سعر البداية يتجاوز الحد المسموح به (3 أضعاف السعر الأصلي)! الحد الأقصى: %(max)s ₪', max=max_price), 'danger')
                return redirect(url_for('black_market.create_auction'))
                
            # Deduct Item
            if user_item.quantity == 1:
                db.session.delete(user_item)
            else:
                user_item.quantity -= 1
                
            # Create Auction
            now = datetime.now(timezone.utc)
            end_time = now + timedelta(hours=duration)
            
            new_auction = Auction(
                item_type='item',
                item_id=str(user_item.item_id), # Store Item ID as string
                seller_id=current_user.id,
                start_price=start_price,
                current_price=start_price,
                min_bid_increment=max(100, int(start_price * 0.05)), # 5% increment
                start_time=now,
                end_time=end_time,
                status='active'
            )
            
            db.session.add(new_auction)
            db.session.commit()
            
            flash(_('تم إنشاء المزاد بنجاح!'), 'success')
            return redirect(url_for('black_market.auctions'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating auction: {e}")
            flash(_('حدث خطأ أثناء إنشاء المزاد.'), 'danger')
            return redirect(url_for('black_market.create_auction'))

    # GET
    user_items = UserItem.query.join(Item).filter(
        UserItem.user_id == current_user.id,
        UserItem.quantity > 0,
        UserItem.is_equipped == False
    ).all()
    
    return render_template('black_market/create_auction.html', user_items=user_items)

@bp.route('/auctions')
@login_required
def auctions():
    """List active auctions."""
    process_expired_auctions()
    now = datetime.now(timezone.utc)
    active_auctions = Auction.query.filter(
        Auction.status == 'active',
        Auction.end_time > now
    ).order_by(Auction.end_time.asc()).all()
    
    # Process auction display data
    display_auctions = []
    for auc in active_auctions:
        # Get highest bid
        highest_bid = AuctionBid.query.filter_by(auction_id=auc.id).order_by(AuctionBid.amount.desc()).first()
        current_bid = highest_bid.amount if highest_bid else auc.start_price
        bidder_name = highest_bid.bidder.username if highest_bid else _("لا أحد")
        
        # Get Item Name and Image
        item_name = auc.item_id # Default fallback
        item_image = None
        
        if auc.item_type == 'item':
             # item_id is int ID for Item table
             try:
                 item_obj = Item.query.get(int(auc.item_id))
                 if item_obj: 
                     item_name = item_obj.name
                     item_image = item_obj.image
             except: pass
        elif auc.item_type == 'vehicle':
             try:
                 veh_obj = Vehicle.query.get(int(auc.item_id))
                 if veh_obj: 
                     item_name = veh_obj.name
                     item_image = veh_obj.image
             except: pass
        elif auc.item_type == 'title':
            item_name = f"Title: {auc.item_id}" 
        
        # Ensure auc.end_time is offset-aware for comparison
        auc_end_time = auc.end_time
        if auc_end_time.tzinfo is None:
            auc_end_time = auc_end_time.replace(tzinfo=timezone.utc)
            
        display_auctions.append({
            'obj': auc,
            'current_bid': current_bid,
            'bidder_name': bidder_name,
            'item_name': item_name,
            'item_image': item_image,
            'item_type': auc.item_type,
            'time_left': auc_end_time - now,
            'end_time_iso': auc_end_time.isoformat()
        })
        
    return render_template('black_market/auctions.html', auctions=display_auctions)

@bp.route('/auctions/<int:auction_id>/bid', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def place_bid(auction_id):
    """Place a bid on an auction."""
    amount = request.form.get('amount', type=int)
    if not amount or amount <= 0:
        flash(_("مبلغ غير صالح"), "danger")
        return redirect(url_for('black_market.auctions'))
        
    # Optimistic Locking: We don't lock the row, we check version/state on update
    auction = Auction.query.filter_by(id=auction_id).first()
    if not auction:
        abort(404)
    
    if not auction.is_active:
        flash(_("المزاد منتهي"), "danger")
        return redirect(url_for('black_market.auctions'))

    # Prevent self-bidding (Anti-Shill Bidding)
    if auction.seller_id == current_user.id:
        flash(_("لا يمكنك المزايدة على غرضك الخاص!"), "danger")
        return redirect(url_for('black_market.auctions'))

    highest_bid = AuctionBid.query.filter_by(auction_id=auction.id).order_by(AuctionBid.amount.desc()).first()
    current_highest = highest_bid.amount if highest_bid else auction.start_price
    current_winner_id = highest_bid.bidder_id if highest_bid else None
    
    min_req = current_highest + auction.min_bid_increment
    if highest_bid is None:
        min_req = auction.start_price # First bid can be start price
    
    if amount < min_req:
        flash(_("يجب أن يكون العرض أعلى من %(amount)s", amount=min_req), "danger")
        return redirect(url_for('black_market.auctions'))
        
    if current_user.money < amount:
        flash(_("ليس لديك كاش كافي!"), "danger")
        return redirect(url_for('black_market.auctions'))
        
    try:
        # 1. Attempt to update Auction with Optimistic Locking
        # We check that current_price and winner_id haven't changed since we read them
        
        # Anti-Sniping calculation
        new_end_time = auction.end_time
        if new_end_time.tzinfo is None:
            new_end_time = new_end_time.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        time_left = new_end_time - now
        extended = False
        if time_left.total_seconds() < 300: # 5 mins
            new_end_time += timedelta(minutes=5)
            extended = True

        # Perform the update
        # We use auction.current_price and auction.winner_id as the "version"
        update_criteria = [
            Auction.id == auction_id,
            Auction.current_price == (current_highest if highest_bid else auction.start_price),
             # Note: If no bids, current_price might be start_price, but winner_id is None.
             # If bids exist, current_price is highest bid.
             # We should rely on what we read: current_highest
        ]
        
        # However, auction.current_price column stores the current price.
        # If no bids, it stores start_price? Yes, typically initialized to start_price.
        # But let's use the DB value we read.
        
        # Refined Criteria:
        # We match strictly what we saw.
        # If highest_bid is None, we expect auction.winner_id to be None.
        # If highest_bid exists, we expect auction.winner_id to be highest_bid.bidder_id.
        
        # Construct filter conditions explicitly
        filter_conditions = [
            Auction.id == auction_id,
            Auction.current_price == auction.current_price,
            Auction.winner_id == auction.winner_id
        ]
        
        updates = {
            Auction.current_price: amount,
            Auction.winner_id: current_user.id,
            Auction.end_time: new_end_time
        }
        
        rows_updated = Auction.query.filter(*filter_conditions).update(updates)
        
        if rows_updated == 0:
            db.session.rollback()
            flash(_("تغير سعر المزاد أثناء محاولتك. حاول مرة أخرى."), "warning")
            return redirect(url_for('black_market.auctions'))

        # Deadlock Prevention: Lock Current Bidder and Previous Bidder in ID order
        users_to_lock = [current_user.id]
        if highest_bid:
            users_to_lock.append(highest_bid.bidder_id)
        
        # Remove duplicates and sort
        users_to_lock = sorted(list(set(users_to_lock)))
        
        for uid in users_to_lock:
            db.session.query(User).filter_by(id=uid).with_for_update().first()

        # 2. Deduct money from current bidder
        if not ResourceService.modify_resources(current_user.id, {'money': -amount}, 'auction_bid', auto_commit=False, expected_version=None):
            # If deduction fails, we MUST rollback the auction update
            raise Exception("Insufficient funds or deduction failed")
        
        # 3. Refund previous bidder if exists
        if highest_bid:
            prev_bidder = User.query.get(highest_bid.bidder_id)
            if prev_bidder:
                if not ResourceService.modify_resources(prev_bidder.id, {'money': highest_bid.amount}, 'auction_refund', auto_commit=False, expected_version=None):
                    raise Exception("Failed to refund previous bidder")

        # 4. Create Bid Record
        new_bid = AuctionBid(
            auction_id=auction.id,
            bidder_id=current_user.id,
            amount=amount
        )
        db.session.add(new_bid)
        
        if extended:
            flash(_("تم تمديد المزاد 5 دقائق!"), "info")
            
        db.session.commit()
        flash(_("تم تقديم عرضك بنجاح!"), "success")
        
    except Exception as e:
        db.session.rollback()
        flash(_("حدث خطأ أثناء تقديم العرض: %(error)s", error=str(e)), "danger")
        
    return redirect(url_for('black_market.auctions'))

@bp.route('/')
@login_required
def index():
    # Smuggling items are initialized in utils/essentials.py
    
    now = datetime.now(timezone.utc)
    current_loc_id = current_user.location_id
    black_market_event = _get_black_market_event()

    changed_status = False
    if current_user.safe_house_until:
        safe_until = current_user.safe_house_until
        if safe_until.tzinfo is None:
            safe_until = safe_until.replace(tzinfo=timezone.utc)
        if safe_until <= now:
            current_user.is_safe_house_active = False
            current_user.safe_house_until = None
            changed_status = True

    if current_user.disguise_until:
        disguise_until = current_user.disguise_until
        if disguise_until.tzinfo is None:
            disguise_until = disguise_until.replace(tzinfo=timezone.utc)
        if disguise_until <= now:
            current_user.is_disguised = False
            current_user.disguise_until = None
            changed_status = True

    if changed_status:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    try:
        weapons = Item.query.filter_by(type='weapon', is_black_market=True).all()
        armors = Item.query.filter_by(type='armor', is_black_market=True).all()
        consumables = Item.query.filter_by(type='consumable', is_black_market=True).all()
        loot_items = UserItem.query.filter_by(user_id=current_user.id).join(Item).filter(Item.type == 'loot').all()
    except Exception:
        db.session.rollback()
        weapons = []
        armors = []
        consumables = []
        loot_items = []
    
    # Smuggling Items with dynamic prices
    try:
        smuggling_items_query = Item.query.filter_by(type='smuggling').all()
        smuggling_items = []
        
        for item in smuggling_items_query:
            price = get_smuggling_price(item, current_loc_id)
            price = _apply_black_market_event(price, current_loc_id, black_market_event)
            
            # Check user inventory
            user_qty = 0
            u_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()
            if u_item:
                user_qty = u_item.quantity
                
            smuggling_items.append({
                'item': item,
                'current_price': price,
                'user_quantity': user_qty,
                'trend': 'up' if price > item.cost else 'down' # Simple trend indicator
            })
        
        # Sort by user quantity descending
        smuggling_items.sort(key=lambda x: x['user_quantity'], reverse=True)
    except Exception:
        db.session.rollback()
        smuggling_items = []
        
    bullets_factory_only = SystemConfig.get_value('economy_bullets_only_from_factory', 'false') == 'true'

    try:
        active_contract = FarmSupplyContract.query.filter_by(
            user_id=current_user.id,
            location_id=current_loc_id,
            status='active'
        ).order_by(FarmSupplyContract.ends_at.desc()).first()
        if active_contract and not active_contract.is_active:
            active_contract.status = 'expired'
            db.session.add(active_contract)
            db.session.commit()
            active_contract = None
    except Exception:
        db.session.rollback()
        active_contract = None

    contract_offer = _contract_offer(current_user)
    
    current_location = db.session.get(Location, current_loc_id) if current_loc_id else None


    services_requirements = {
        "safe_house": {"min_tier": "t2", "min_intelligence": 8},
        "disguise": {"min_tier": "t1", "min_intelligence": 6},
        "spy": {"min_tier": "t2", "min_intelligence": 12},
        "cool_off": {"min_tier": "t1", "min_intelligence": 5},
    }
    services_access = {}
    for k, req in services_requirements.items():
        chk = check_requirements(current_user, req)
        hint_url = None
        if chk.get("hint_key") == "gym":
            hint_url = url_for('gym.index')
        elif chk.get("hint_key") == "daily_tasks":
            hint_url = url_for('main.daily_tasks')
        services_access[k] = {"unlocked": bool(chk["ok"]), "reason": chk["reason"], "hint_text": chk.get("hint_text"), "hint_url": hint_url}

    return render_template('black_market.html', 
                           weapons=weapons, 
                           armors=armors, 
                           consumables=consumables, 
                           loot_items=loot_items, 
                           smuggling_items=smuggling_items,
                           user=current_user,
                           bullets_factory_only=bullets_factory_only,
                           active_contract=active_contract,
                           contract_offer=contract_offer,
                           current_location=current_location,
                           services_access=services_access,
                           black_market_event=black_market_event)

@bp.route('/buy_smuggling/<int:item_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def buy_smuggling(item_id):
    # Lock User to prevent race conditions (especially for UserItem creation)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Status Check (Copy-paste standard checks or use decorator if available)
    now = datetime.now(timezone.utc)
    if current_user.jail_until and current_user.jail_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في السجن!'), 'danger')
        return redirect(url_for('black_market.index'))
    if current_user.hospital_until and current_user.hospital_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في المستشفى!'), 'danger')
        return redirect(url_for('hospital.index'))
        
    item = db.session.get(Item, item_id)
    if not item or item.type != 'smuggling':
        abort(404)
        
    quantity = int(request.form.get('quantity', 0))
    if quantity <= 0:
        flash(_('كمية غير صحيحة!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    black_market_event = _get_black_market_event()
    price = get_smuggling_price(item, current_user.location_id)
    price = _apply_black_market_event(price, current_user.location_id, black_market_event)
    total_cost = price * quantity
    
    # Gang Buff (Bazaar Connections)
    try:
        from services.gang_service import GangService
        gang_buff = GangService.get_gang_buff(current_user.gang_id, 'bazaar_connections')
        if gang_buff > 0:
            total_cost = int(total_cost * (1 - gang_buff / 100))
    except Exception as e:
        current_app.logger.error(f"Error applying gang buff: {e}")
    
    if current_user.money < total_cost:
        flash(_('ليس لديك مال كافي!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    # Atomic deduction with logging
    if not ResourceService.modify_resources(current_user.id, {'money': -total_cost}, 'buy_smuggling', auto_commit=False, expected_version=None):
        flash(_('حدث خطأ أثناء الشراء. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))
    
    user_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()
    old_qty = user_item.quantity if user_item else 0
    
    if user_item:
        user_item.quantity += quantity
    else:
        user_item = UserItem(user_id=current_user.id, item_id=item.id, quantity=quantity)
        db.session.add(user_item)
        
    # Log Item Gain
    log = UserLog(
        user_id=current_user.id,
        action='BUY_SMUGGLING_ITEM',
        details=json.dumps({'item_id': item.id, 'item_name': item.name, 'quantity': quantity, 'price_per_unit': price}),
        result='success',
        before_state={'quantity': old_qty},
        after_state={'quantity': old_qty + quantity},
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    db.session.add(log)
        
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    flash(_('تم شراء %(qty)s من %(name)s بسعر %(price)s للقطعة.', qty=quantity, name=item.name, price=price), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/sell_smuggling/<int:item_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def sell_smuggling(item_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until and current_user.jail_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في السجن!'), 'danger')
        return redirect(url_for('black_market.index'))
    if current_user.hospital_until and current_user.hospital_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في المستشفى!'), 'danger')
        return redirect(url_for('hospital.index'))

    item = db.session.get(Item, item_id)
    if not item or item.type != 'smuggling':
        abort(404)
        
    # Lock User first to prevent deadlocks with buy_smuggling (User -> Item)
    # This ensures consistent locking order (User -> UserItem)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
        
    # Lock the item row to prevent double selling
    user_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item.id).with_for_update().first()
    if not user_item or user_item.quantity <= 0:
        flash(_('لا تملك هذا الغرض!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    quantity = int(request.form.get('quantity', 0))
    if quantity <= 0 or quantity > user_item.quantity:
        flash(_('كمية غير صحيحة!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    black_market_event = _get_black_market_event()
    price = get_smuggling_price(item, current_user.location_id)
    price = _apply_black_market_event(price, current_user.location_id, black_market_event)
    total_value = price * quantity

    bonus_pct = 0.0
    if item.name in FARM_PRODUCT_NAMES:
        contract = FarmSupplyContract.query.filter_by(
            user_id=current_user.id,
            location_id=current_user.location_id,
            status='active'
        ).order_by(FarmSupplyContract.ends_at.desc()).first()
        if contract and contract.is_active:
            try:
                bonus_pct = float(contract.bonus_percent or 0.0)
            except Exception:
                bonus_pct = 0.0
            total_value = int(total_value * (1 + bonus_pct))
    
    # Atomic Update with logging
    if not ResourceService.modify_resources(current_user.id, {'money': total_value}, 'sell_smuggling', auto_commit=False, expected_version=None):
        flash(_('حدث خطأ أثناء البيع. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))

    old_qty = user_item.quantity
    user_item.quantity -= quantity
    
    # Log Item Loss
    log = UserLog(
        user_id=current_user.id,
        action='SELL_SMUGGLING_ITEM',
        details=json.dumps({'item_id': item.id, 'item_name': item.name, 'quantity': quantity, 'price_per_unit': price, 'total_value': total_value}),
        result='success',
        before_state={'quantity': old_qty},
        after_state={'quantity': user_item.quantity},
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    db.session.add(log)
    
    if user_item.quantity == 0:
        db.session.delete(user_item)
        
    db.session.commit()
    if bonus_pct > 0:
        flash(_('تم بيع %(qty)s من %(name)s بسعر %(price)s للقطعة. عقد توريد +%(pct)s%%. الربح: %(val)s', qty=quantity, name=item.name, price=price, pct=int(bonus_pct * 100), val=total_value), 'success')
    else:
        flash(_('تم بيع %(qty)s من %(name)s بسعر %(price)s للقطعة. الربح: %(val)s', qty=quantity, name=item.name, price=price, val=total_value), 'success')
    return redirect(url_for('black_market.index'))


@bp.route('/buy_service/<service_type>', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def buy_service(service_type):
    # Lock user to prevent race conditions
    # We use the ID to query, ensuring we get the session object attached to this transaction
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك التعامل مع السوق السوداء!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك التعامل مع السوق السوداء!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك التعامل مع السوق السوداء!'), 'danger')
            return redirect(url_for('gym.index'))

    service_requirements = {
        "safe_house": {"min_tier": "t2", "min_intelligence": 8},
        "disguise": {"min_tier": "t1", "min_intelligence": 6},
        "cool_off": {"min_tier": "t1", "min_intelligence": 5},
    }
    if service_type in service_requirements:
        chk = check_requirements(current_user, service_requirements[service_type])
        if not chk["ok"]:
            flash(_('طور نفسك لفتحها: %(reason)s', reason=chk["reason"]), 'warning')
            return redirect(url_for('black_market.index'))

    if service_type == 'safe_house':
        cost = 50000
        duration = 24 # hours
        
        # Gang Buff (Bazaar Connections)
        try:
            from services.gang_service import GangService
            gang_buff = GangService.get_gang_buff(current_user.gang_id, 'bazaar_connections')
            if gang_buff > 0:
                cost = int(cost * (1 - gang_buff / 100))
        except Exception as e:
            current_app.logger.error(f"Error applying gang buff: {e}")

        if current_user.money < cost:
            flash(_('تحتاج إلى %(cost)s$ لاستئجار منزل آمن!', cost="{:,}".format(cost)), 'danger')
            return redirect(url_for('black_market.index'))
            
        # Atomic deduction with logging
        if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'buy_service_safehouse', auto_commit=False, expected_version=current_user.version):
            flash(_('حدث خطأ أثناء الشراء. حاول مرة أخرى.'), 'danger')
            return redirect(url_for('black_market.index'))

        current_user.is_safe_house_active = True
        
        # Extend if already active, else set new
        safe_house_until = current_user.safe_house_until
        if safe_house_until and safe_house_until.tzinfo is None:
            safe_house_until = safe_house_until.replace(tzinfo=timezone.utc)
            
        if safe_house_until and safe_house_until > now:
            current_user.safe_house_until = safe_house_until + timedelta(hours=duration)
        else:
            current_user.safe_house_until = now + timedelta(hours=duration)
            
        flash(_('تم استئجار المنزل الآمن لمدة 24 ساعة! لا يمكن لأحد مهاجمتك الآن.'), 'success')
        
    elif service_type == 'disguise':
        cost = 10000
        duration = 1 # hours
        
        # Gang Buff (Bazaar Connections)
        try:
            from services.gang_service import GangService
            gang_buff = GangService.get_gang_buff(current_user.gang_id, 'bazaar_connections')
            if gang_buff > 0:
                cost = int(cost * (1 - gang_buff / 100))
        except Exception as e:
            current_app.logger.error(f"Error applying gang buff: {e}")

        if current_user.money < cost:
            flash(_('تحتاج إلى %(cost)s$ لشراء تنكر!', cost="{:,}".format(cost)), 'danger')
            return redirect(url_for('black_market.index'))
            
        # Atomic deduction with logging
        if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'buy_service_disguise', auto_commit=False, expected_version=current_user.version):
            flash(_('حدث خطأ أثناء الشراء. حاول مرة أخرى.'), 'danger')
            return redirect(url_for('black_market.index'))

        current_user.is_disguised = True
        
        if current_user.disguise_until and current_user.disguise_until > now:
            current_user.disguise_until += timedelta(hours=duration)
        else:
            current_user.disguise_until = now + timedelta(hours=duration)
            
        flash(_('تم تفعيل التخفي لمدة ساعة! سيظهر اسمك كمجهول عند الهجوم.'), 'success')
    elif service_type == 'cool_off':
        heat = 0
        try:
            heat = current_user.heat_value(now=now)
        except Exception:
            heat = 0
        if heat <= 0:
            flash(_('حرارتك صفر… خليك هادي.'), 'info')
            return redirect(url_for('black_market.index'))

        cost = 5000 + (heat * 700)
        if current_user.money < cost:
            flash(_('تحتاج إلى %(cost)s$ لتخفيف الحرارة الحالية.', cost=cost), 'danger')
            return redirect(url_for('black_market.index'))

        # Atomic deduction with logging
        if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'buy_service_cool_off', auto_commit=False, expected_version=None):
            db.session.rollback()
            flash(_('حدث خطأ أثناء العملية. حاول مرة أخرى.'), 'danger')
            return redirect(url_for('black_market.index'))

        try:
            current_user.add_heat(-40, now=now)
        except Exception:
            pass
        flash(_('دفعت رشوة ونظفت آثارك. الحرارة انخفضت.'), 'success')
        
    else:
        flash(_('خدمة غير معروفة!'), 'danger')
        
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    return redirect(url_for('black_market.index'))

@bp.route('/buy_bullets', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def buy_bullets():
    quantity = request.form.get('quantity', type=int)
    payment_method = request.form.get('payment_method', 'money') # money or diamonds

    if not quantity or quantity <= 0:
        flash(_('الكمية غير صحيحة!'), 'danger')
        return redirect(url_for('black_market.index'))

    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك شراء الرصاص!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك شراء الرصاص!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك شراء الرصاص!'), 'danger')
            return redirect(url_for('gym.index'))

    changes = {}
    cost_log_key = ''
    set_fields = {}

    if payment_method == 'diamonds':
        # 1 Diamond = 10 Bullets
        diamonds_cost = math.ceil(quantity / 10)
        if current_user.diamonds < diamonds_cost:
             flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=diamonds_cost), 'danger')
             return redirect(url_for('black_market.index'))
        
        changes = {'diamonds': -diamonds_cost, 'bullets': quantity}
        cost_log_key = 'buy_bullets_diamonds'
        flash_msg = _('تم شراء %(qty)s رصاصة مقابل %(cost)s ماسة!', qty=quantity, cost=diamonds_cost)

    else:
        # Default: Money
        if SystemConfig.get_value('economy_bullets_only_from_factory', 'false') == 'true':
            flash(_('الذخيرة يتم إنتاجها من المصانع فقط (أو شراؤها بالماس).'), 'info')
            return redirect(url_for('factory.index'))

        # Daily Limit Check (Only for Cash)
        today = datetime.now(timezone.utc).date()
        effective_daily_purchased = current_user.daily_bullets_purchased or 0
        
        if current_user.daily_money_date != today:
            effective_daily_purchased = 0
            set_fields['daily_money_date'] = today
            set_fields['daily_money_earned'] = 0
            
        # Formula: 250 + (Level - 1) * 7.58, max 1000
        # Level 1: 250
        # Level 100: 250 + 99 * 7.58 = 1000
        limit = min(1000, int(250 + (max(1, current_user.level) - 1) * 7.58))
        
        if effective_daily_purchased + quantity > limit:
            remaining = max(0, limit - effective_daily_purchased)
            flash(_('لقد تجاوزت الحد اليومي لشراء الرصاص بالكاش! (%(limit)s). المتبقي لك اليوم: %(rem)s', limit=limit, rem=remaining), 'danger')
            return redirect(url_for('black_market.index'))

        cost_per_bullet = 10
        total_cost = quantity * cost_per_bullet
        
        if current_user.money < total_cost:
            flash(_('معكش مصاري كفاية!'), 'danger')
            return redirect(url_for('black_market.index'))
            
        changes = {'money': -total_cost, 'bullets': quantity}
        cost_log_key = 'buy_bullets_money'
        flash_msg = _('تم شراء %(qty)s رصاصة بنجاح!', qty=quantity)
        
        set_fields['daily_bullets_purchased'] = effective_daily_purchased + quantity

    # Atomic deduction with logging
    if not ResourceService.modify_resources(current_user.id, changes, cost_log_key, auto_commit=True, expected_version=current_user.version, set_fields=set_fields):
        flash(_('حدث خطأ أثناء الشراء. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))
    
    update_daily_task_progress(current_user, 'buy')
    
    flash(flash_msg, 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/spy', methods=['POST'])
@login_required
@limiter.limit("3 per minute")
def spy():
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك إرسال مخبرين!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك إرسال مخبرين!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك إرسال مخبرين!'), 'danger')
            return redirect(url_for('gym.index'))

    chk = check_requirements(current_user, {"min_tier": "t2", "min_intelligence": 12})
    if not chk["ok"]:
        flash(_('طور نفسك لفتحها: %(reason)s', reason=chk["reason"]), 'warning')
        return redirect(url_for('black_market.index'))

    target_username = request.form.get('username')
    if not target_username:
        flash(_('يرجى إدخال اسم اللاعب!'), 'danger')
        return redirect(url_for('black_market.index'))

    target = User.query.filter_by(username=target_username).first()
    if not target:
        flash(_('اللاعب غير موجود!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    if target.id == current_user.id:
        flash(_('لا يمكنك التجسس على نفسك!'), 'warning')
        return redirect(url_for('black_market.index'))

    # Logic: Cost and Time depend on level difference
    # If target is higher level -> More expensive, takes longer
    # If I have high intelligence -> Cheaper, faster
    
    level_diff = target.level - current_user.level
    intel_factor = current_user.intelligence / 10.0  # Higher intel reduces cost/time
    
    base_cost = 5000
    base_time = 10 # minutes
    
    # Cost Multiplier: +10% per level diff (if target is higher), reduced by Intel
    cost_multiplier = 1.0 + (max(0, level_diff) * 0.1) - (intel_factor * 0.05)
    cost_multiplier = max(0.5, cost_multiplier) # Min 50% cost
    
    final_cost = int(base_cost * cost_multiplier)
    
    # Check Money
    if current_user.money < final_cost:
        flash(_('تحتاج إلى %(cost)s$ لعملية التجسس هذه!', cost=final_cost), 'danger')
        return redirect(url_for('black_market.index'))
        
    # Time Multiplier: Similar logic
    time_multiplier = 1.0 + (max(0, level_diff) * 0.05) - (intel_factor * 0.1)
    time_multiplier = max(0.2, time_multiplier) # Min 20% time (2 mins)
    
    final_time_minutes = int(base_time * time_multiplier)
    delivery_time = datetime.now(timezone.utc) + timedelta(minutes=final_time_minutes)
    
    # Deduct Money
    # Atomic deduction with logging
    if not ResourceService.modify_resources(current_user.id, {'money': -final_cost}, 'spy', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء العملية. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))
    
    # Prepare Report Data
    # Estimated bullets to kill (Assuming avg player dmg = 20 for calculation)
    # Formula: (HP + Defense) / Dmg
    estimated_hp = target.health
    estimated_def = target.defense
    avg_dmg = 5 # Conservative estimate (min damage)
    bullets_needed = math.ceil((estimated_hp + (estimated_def * 0.5)) / avg_dmg) # Simple formula
    
    location_name = target.location.name if target.location else _("غير معروف")
    safe_house_until = target.safe_house_until
    if safe_house_until and safe_house_until.tzinfo is None:
        safe_house_until = safe_house_until.replace(tzinfo=timezone.utc)
    safe_house_status = _("نشط") if (target.is_safe_house_active and safe_house_until and safe_house_until > now) else _("غير نشط")
    
    report_body = f"""
    <strong>{_('تقرير استخباراتي عن الهدف:')} {target.username}</strong><br><br>
    <ul>
        <li><strong>{_('الموقع الحالي:')}</strong> {location_name}</li>
        <li><strong>{_('المنزل الآمن:')}</strong> {safe_house_status}</li>
        <li><strong>{_('المستوى:')}</strong> {target.level}</li>
        <li><strong>{_('الصحة المقدرة:')}</strong> {estimated_hp} / {target.max_health}</li>
        <li><strong>{_('الدفاع:')}</strong> {estimated_def}</li>
        <li><strong>{_('رصاصات للقتل (تقريبي):')}</strong> {bullets_needed} {_('رصاصة')}</li>
        <li><strong>{_('الكاش:')}</strong> ${target.money:,}</li>
    </ul>
    <br>
    <small>{_('ملاحظة: هذه المعلومات دقيقة وقت طلب التقرير وقد تتغير.')}</small>
    """
    
    # Create Message
    msg = Message(
        sender_id=current_user.id, # From "Self" or "System"
        receiver_id=current_user.id,
        subject=_('تقرير سري: %(name)s', name=target.username),
        body=report_body,
        delivery_time=delivery_time
    )
    
    db.session.add(msg)
    
    # Create Active Intel (Valid from delivery time for 24 hours)
    intel = ActiveIntel(
        user_id=current_user.id,
        target_id=target.id,
        start_time=delivery_time,
        expires_at=delivery_time + timedelta(hours=24)
    )
    db.session.add(intel)
    
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    
    flash(_('بدأ المخبر العمل. التكلفة: %(cost)s$. سيصل التقرير خلال %(time)s دقيقة.', cost=final_cost, time=final_time_minutes), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/buy/<int:item_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def buy(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        abort(404)
    
    if not item.is_black_market:
        flash(_('هذا الغرض غير متوفر في السوق السوداء!'), 'danger')
        return redirect(url_for('black_market.index'))

    cost = item.cost
    # Gang Buff (Bazaar Connections)
    try:
        from services.gang_service import GangService
        gang_buff = GangService.get_gang_buff(current_user.gang_id, 'bazaar_connections')
        if gang_buff > 0:
            cost = int(cost * (1 - gang_buff / 100))
    except Exception as e:
        current_app.logger.error(f"Error applying gang buff: {e}")

    if current_user.money < cost:
        flash(_('معكش مصاري كفاية يا معلم!'), 'danger')
        return redirect(url_for('black_market.index'))
    
    # Atomic deduction with logging
    if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'buy_black_market_item', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء الشراء. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))
    
    # Check if user already has this item
    user_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()
    
    old_qty = user_item.quantity if user_item else 0
    
    if user_item:
        user_item.quantity += 1
    else:
        user_item = UserItem(user_id=current_user.id, item_id=item.id, quantity=1)
        db.session.add(user_item)
    
    # Log Item Gain
    log = UserLog(
        user_id=current_user.id,
        action='BUY_BLACK_MARKET_ITEM',
        details=json.dumps({'item_id': item.id, 'item_name': item.name, 'cost': item.cost}),
        result='success',
        before_state={'quantity': old_qty},
        after_state={'quantity': old_qty + 1},
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    db.session.add(log)
    
    db.session.commit()
    
    update_daily_task_progress(current_user, 'buy')
    
    flash(_('تم شراء %(name)s من السوق السوداء بنجاح!', name=item.name), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/sell_loot/<int:user_item_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def sell_loot(user_item_id):
    user_item = db.session.get(UserItem, user_item_id)
    if not user_item:
        abort(404)
        
    if user_item.user_id != current_user.id:
        flash(_('هذا الغرض ليس ملكك!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    if user_item.item.type != 'loot':
        flash(_('لا يمكنك بيع هذا الغرض هنا! فقط المسروقات.'), 'warning')
        return redirect(url_for('black_market.index'))
        
    if user_item.condition is not None and user_item.condition < 100:
        flash(_('لا يمكن بيع مسروقات متضررة! قم بإصلاحها أولاً.'), 'danger')
        return redirect(url_for('black_market.index'))
        
    # Sell Price: 60% of original cost
    sell_price = int(user_item.item.cost * 0.6)
    
    # Atomic Update with logging
    if not ResourceService.modify_resources(current_user.id, {'money': sell_price}, 'sell_loot', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء البيع. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))
    
    old_qty = user_item.quantity
    
    if user_item.quantity > 1:
        user_item.quantity -= 1
    else:
        db.session.delete(user_item)
        
    # Log Item Loss
    log = UserLog(
        user_id=current_user.id,
        action='SELL_LOOT',
        details=json.dumps({'item_id': user_item.item.id, 'item_name': user_item.item.name, 'sell_price': sell_price}),
        result='success',
        before_state={'quantity': old_qty},
        after_state={'quantity': old_qty - 1},
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    db.session.add(log)
        
    db.session.commit()
    
    flash(_('تم بيع %(name)s مقابل %(price)s شيكل.', name=user_item.item.name, price=sell_price), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/repair_loot/<int:user_item_id>', methods=['POST'])
@login_required
def repair_loot(user_item_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك إصلاح المسروقات!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك إصلاح المسروقات!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك إصلاح المسروقات!'), 'danger')
            return redirect(url_for('gym.index'))

    user_item = db.session.get(UserItem, user_item_id)
    if not user_item:
        abort(404)
    if user_item.user_id != current_user.id:
        flash(_('هذا الغرض ليس ملكك!'), 'danger')
        return redirect(url_for('black_market.index'))
    if user_item.item.type != 'loot':
        flash(_('فقط المسروقات يمكن إصلاحها هنا.'), 'warning')
        return redirect(url_for('black_market.index'))
    
    if user_item.condition is None or user_item.condition >= 100:
        flash(_('الغرض سليم ولا يحتاج لإصلاح.'), 'info')
        return redirect(url_for('black_market.index'))
    
    damage = 100 - user_item.condition
    base_cost = user_item.item.cost
    # Repair cost: 0.5% of value per 1% damage
    # Total repair from 0% to 100% costs 50% of item value
    # Sell price is 60% of value, ensuring profit margin
    cost = int(damage * (base_cost * 0.005) * user_item.quantity)
    
    if current_user.money < cost:
        flash(_('تحتاج %(cost)s شيكل لإصلاح المسروقات!', cost=cost), 'danger')
        return redirect(url_for('black_market.index'))
    
    # Atomic deduction with logging
    if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'repair_loot', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء الإصلاح. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))

    user_item.condition = 100
    db.session.commit()
    
    flash(_('تم إصلاح المسروقات وأصبحت جاهزة للبيع.'), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/repair_all_loot', methods=['POST'])
@login_required
def repair_all_loot():
    # Find all damaged loot items for the user
    damaged_items = []
    user_items = UserItem.query.filter_by(user_id=current_user.id).all()
    
    for ui in user_items:
        if ui.item.type == 'loot' and ui.condition is not None and ui.condition < 100:
            damaged_items.append(ui)
            
    if not damaged_items:
        flash(_('لا يوجد مسروقات متضررة لإصلاحها.'), 'info')
        return redirect(url_for('black_market.index'))
        
    total_cost = 0
    for ui in damaged_items:
        damage = 100 - ui.condition
        item_cost = int(damage * (ui.item.cost * 0.005) * ui.quantity)
        total_cost += item_cost
        
    if current_user.money < total_cost:
        flash(_('تحتاج %(cost)s شيكل لإصلاح كل المسروقات! لديك %(money)s فقط.', cost=total_cost, money=current_user.money), 'danger')
        return redirect(url_for('black_market.index'))
        
    # Process repair
    # Atomic deduction with logging
    if not ResourceService.modify_resources(current_user.id, {'money': -total_cost}, 'repair_all_loot', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء الإصلاح. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))

    for ui in damaged_items:
        ui.condition = 100
        
    db.session.commit()
    
    flash(_('تم إصلاح كل المسروقات (%(count)d قطعة) بتكلفة %(cost)s شيكل.', count=len(damaged_items), cost=total_cost), 'success')
    return redirect(url_for('black_market.index'))


@bp.route('/extend_contract', methods=['POST'])
@login_required
@limiter.limit("3 per minute")
def extend_contract():
    offer = _contract_offer(current_user)
    if not offer:
        flash(_('طور مرافقك لفتح عقد التوريد.'), 'warning')
        return redirect(url_for('farm.index'))

    cost = int(offer["cost_diamonds"])
    duration_minutes = int(offer["duration_minutes"])
    bonus = float(offer["bonus_percent"])

    if current_user.diamonds < cost:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=cost), 'danger')
        return redirect(url_for('black_market.index'))

    # Atomic deduction with logging
    if not ResourceService.modify_resources(current_user.id, {'diamonds': -cost}, 'extend_farm_contract', auto_commit=False, expected_version=current_user.version):
        flash(_('حدث خطأ أثناء التمديد. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('black_market.index'))

    # current_user.diamonds = max(0, int(current_user.diamonds) - cost) # Removed

    now = datetime.now(timezone.utc)
    location_id = current_user.location_id
    contract = FarmSupplyContract.query.filter_by(
        user_id=current_user.id,
        location_id=location_id,
        status='active'
    ).order_by(FarmSupplyContract.ends_at.desc()).first()
    if contract and not contract.is_active:
        contract.status = 'expired'
        db.session.add(contract)
        db.session.commit()
        contract = None

    if contract:
        ends = contract.ends_at
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        if ends and ends > now:
            contract.ends_at = (ends + timedelta(minutes=duration_minutes)).replace(tzinfo=None)
        else:
            contract.ends_at = (now + timedelta(minutes=duration_minutes)).replace(tzinfo=None)
        contract.bonus_percent = bonus
        db.session.add(contract)
    else:
        contract = FarmSupplyContract(
            user_id=current_user.id,
            location_id=location_id,
            bonus_percent=bonus,
            status='active',
            created_at=now,
            ends_at=(now + timedelta(minutes=duration_minutes)).replace(tzinfo=None),
        )
        db.session.add(contract)

    db.session.commit()
    flash(_('تم تمديد عقد التوريد. +%(pct)s%% لمدة %(min)s دقيقة.', pct=int(bonus * 100), min=duration_minutes), 'success')
    return redirect(url_for('black_market.index'))
