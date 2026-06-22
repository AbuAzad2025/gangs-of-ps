from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, abort
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter, cache
from models.market import MarketAsset, UserInvestment, FuturesPosition, SpotOrder
from models.user import User
from models.social import Message
from datetime import datetime, timezone
from models.system import SystemConfig
import random
import pandas as pd
from services.resource_service import ResourceService
from services.market_simulation import MarketSimulationService
from utils.decorators import check_player_status
from routes.utils import track_academy_visit

bp = Blueprint('market', __name__, url_prefix='/market')


def check_liquidations(asset):
    """Checks and liquidates positions that hit liquidation price"""
    # Fetch all open positions for this asset
    # This might be heavy if there are thousands, but for now it's fine.
    # Optimization: Filter by liquidation criteria in DB query
    # Long: current_price <= liquidation_price
    # Short: current_price >= liquidation_price

    # 1. Liquidate Longs
    longs = FuturesPosition.query.filter(
        FuturesPosition.asset_id == asset.id,
        FuturesPosition.is_open,
        FuturesPosition.position_type == 'long',
        FuturesPosition.liquidation_price >= asset.current_price
    ).limit(50).all()

    for pos in longs:
        liquidate_position(pos, asset.current_price)

    # 2. Liquidate Shorts
    shorts = FuturesPosition.query.filter(
        FuturesPosition.asset_id == asset.id,
        FuturesPosition.is_open,
        FuturesPosition.position_type == 'short',
        FuturesPosition.liquidation_price <= asset.current_price
    ).limit(50).all()

    for pos in shorts:
        liquidate_position(pos, asset.current_price)


def liquidate_position(position, current_price):
    """Executes liquidation for a single position"""
    try:
        # Lock Position
        # We need to re-fetch with lock to be safe, though we just fetched it.
        # But since we are iterating, another thread might have closed it.
        pos_locked = db.session.query(FuturesPosition).filter_by(
            id=position.id).with_for_update().first()
        if not pos_locked or not pos_locked.is_open:
            return

        # Double check price condition (race condition with price update?)
        # Assume 'current_price' is the source of truth for this liquidation
        # event.

        # Close it
        pos_locked.is_open = False
        pos_locked.exit_price = current_price
        pos_locked.closed_at = datetime.now(timezone.utc)

        # Calculate PnL (Should be roughly -Margin)
        # But we just set it to -Margin effectively (user gets 0 back)
        # Actually calculate it for records
        # User gets nothing back (Liquidation)
        # Or maybe a tiny dust amount if we are generous? No, REKT.

        # Notify User
        msg = Message(
            sender_id=1,  # System
            receiver_id=pos_locked.user_id,
            subject=_('تصفية قسرية: عقد %(sym)s', sym=pos_locked.asset.symbol),
            body=_(
                'للأسف، تم تصفية صفقتك (Liquidation) على سعر %(price)s. خسرت الهامش بالكامل.',
                price=current_price),
            delivery_time=datetime.now(timezone.utc)
        )
        db.session.add(msg)

        # Log it
        current_app.logger.info(
            f"Liquidated Position {pos_locked.id} for User {pos_locked.user_id} at {current_price}")

        # We assume margin is already deducted from user balance when opened.
        # So we simply don't give anything back.

        # Force version update for user to sync client state?
        # Maybe not strictly necessary if they have 0 balance change, but good for consistency.
        # But we don't want to lock user row here if we can avoid it to prevent bottlenecks during mass liquidation.
        # Only lock user if we are modifying balance. Here we are NOT.

        db.session.commit()

    except Exception as e:
        current_app.logger.error(
            f"Error liquidating position {position.id}: {e}")
        db.session.rollback()


def check_limit_orders(asset):
    """Checks and executes limit orders for a given asset"""
    # Buy Orders: Execute if current_price <= limit_price
    # Optimization: Filter by price in DB query
    buy_orders = SpotOrder.query.filter(
        SpotOrder.asset_id == asset.id,
        SpotOrder.status == 'open',
        SpotOrder.order_type == 'buy',
        SpotOrder.price >= asset.current_price
    ).all()

    for order in buy_orders:
        # Deadlock Prevention: Lock User FIRST, then Investment
        # We must lock the user to safely handle money refunds and consistent
        # ordering
        try:
            # 1. Lock User
            user = db.session.query(User).filter_by(
                id=order.user_id).with_for_update().first()
            if not user:
                continue

            # 2. Lock Investment (to prevent concurrent buy/sell/limit
            # execution)
            investment = UserInvestment.query.filter_by(
                user_id=order.user_id, asset_id=asset.id).with_for_update().first()

            # Optimistic Lock: Try to set status to 'filled' atomically
            # This prevents multiple threads from processing the same order
            rows = SpotOrder.query.filter(
                SpotOrder.id == order.id,
                SpotOrder.status == 'open'
            ).update({
                SpotOrder.status: 'filled',
                SpotOrder.filled_quantity: order.quantity
            }, synchronize_session=False)

            if rows == 0:
                continue  # Already processed by another thread

            # User already paid (locked money) at limit price.
            # If we fill at a better price (current_price < limit_price),
            # refund the difference.
            fill_price = asset.current_price
            refund_amount = 0
            if fill_price < order.price:
                refund_amount = (order.price - fill_price) * order.quantity

            if refund_amount > 0:
                # Refund the difference atomically
                # We already locked the user, so we can update directly or use ResourceService without auto_commit
                # But ResourceService handles logging, so let's use it but careful about double locking if it re-locks?
                # ResourceService.modify_resources uses with_for_update().
                # Nested locks are fine in same transaction.
                if not ResourceService.modify_resources(
                    order.user_id, {
                        'money': refund_amount}, 'spot_limit_buy_refund', auto_commit=False, expected_version=None):
                    db.session.rollback()
                    continue

            if investment:
                # Avg Price update
                total_cost_old = investment.quantity * investment.average_buy_price
                total_cost_new = order.quantity * fill_price  # Use actual fill price
                total_qty = investment.quantity + order.quantity
                if total_qty > 0:
                    investment.average_buy_price = (
                        total_cost_old + total_cost_new) / total_qty
                investment.quantity = total_qty
            else:
                investment = UserInvestment(
                    user_id=order.user_id,
                    asset_id=asset.id,
                    quantity=order.quantity,
                    average_buy_price=fill_price  # Use actual fill price
                )
                db.session.add(investment)

            # Commit immediately to finalize this order
            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                f"Error processing buy order {order.id}: {e}")
            db.session.rollback()

    # Sell Orders: Execute if current_price >= limit_price
    # Optimization: Filter by price in DB query
    sell_orders = SpotOrder.query.filter(
        SpotOrder.asset_id == asset.id,
        SpotOrder.status == 'open',
        SpotOrder.order_type == 'sell',
        SpotOrder.price <= asset.current_price
    ).limit(50).all()

    for order in sell_orders:
        try:
            # Deadlock Prevention: Lock User FIRST
            user = db.session.query(User).filter_by(
                id=order.user_id).with_for_update().first()
            if not user:
                continue

            # Lock Investment (User -> Investment order)
            investment = UserInvestment.query.filter_by(
                user_id=order.user_id, asset_id=asset.id).with_for_update().first()

            # Optimistic Lock
            rows = SpotOrder.query.filter(
                SpotOrder.id == order.id,
                SpotOrder.status == 'open'
            ).update({
                SpotOrder.status: 'filled',
                SpotOrder.filled_quantity: order.quantity
            }, synchronize_session=False)

            if rows == 0:
                continue  # Already processed

            # Assets already locked/deducted at placement, give money
            total_value = order.quantity * order.price

            # Atomic update with logging
            if not ResourceService.modify_resources(
                order.user_id, {
                    'money': total_value}, 'spot_limit_sell_fill', auto_commit=False, expected_version=None):
                db.session.rollback()
                continue

            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                f"Error processing sell order {order.id}: {e}")
            db.session.rollback()


def update_market_prices():
    """Updates market prices using Simulation Service"""
    # Use cache to debounce updates (allow only 1 update every 10 seconds
    # across all threads)
    lock_key = 'market_update_lock'
    if cache.get(lock_key):
        return  # Already updating or recently updated

    cache.set(lock_key, 'locked', timeout=10)  # Lock for 10 seconds

    current_app.logger.info("Ensuring fictional market assets...")
    MarketSimulationService.initialize_assets()

    # 2. Check update interval
    assets = MarketAsset.query.all()
    if not assets:
        return

    # Check if update is needed based on configurable interval
    needs_update = False
    now = datetime.now(timezone.utc)
    try:
        interval = int(
            SystemConfig.get_value(
                'market_update_interval_seconds',
                '300') or '300')
    except Exception:
        interval = 300

    # Check the first asset or any asset to see if time passed
    # Optimization: Just check the first one
    first_asset = assets[0]
    last_updated = first_asset.last_updated
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    if (now - last_updated).total_seconds() > interval:
        needs_update = True

    if needs_update:
        try:
            current_app.logger.info("Updating simulated market prices...")
            MarketSimulationService.update_prices()

            # Check Limit Orders for all assets
            # Reload assets after update
            updated_assets = MarketAsset.query.all()
            for asset in updated_assets:
                check_limit_orders(asset)
                check_liquidations(asset)

            current_app.logger.info("Market update committed.")
        except Exception as e:
            current_app.logger.critical(f"Global simulation error: {e}")


@bp.route('/api/prices')
@login_required
@cache.cached(timeout=60)
def get_prices():
    """API to get current prices for real-time updates"""
    # Trigger lazy update if needed
    update_market_prices()

    allowed = MarketSimulationService.allowed_symbols()
    assets = MarketAsset.query.filter(MarketAsset.symbol.in_(allowed)).all()
    data = {}
    for asset in assets:
        data[asset.id] = {
            'symbol': asset.symbol,
            'price': asset.current_price,
            'change': asset.price_change_24h,
            'volume': asset.volume_24h,
            'high': asset.high_24h,
            'low': asset.low_24h
        }
    return jsonify(data)


@bp.route('/')
@login_required
def index():
    update_market_prices()
    track_academy_visit(current_user, 'market_visit')

    allowed = MarketSimulationService.allowed_symbols()
    assets = MarketAsset.query.filter(MarketAsset.symbol.in_(allowed)).all()

    # User portfolio
    investments = UserInvestment.query.filter_by(user_id=current_user.id).all()
    portfolio_value = sum([inv.current_value() for inv in investments])
    total_invested = sum(
        [inv.quantity * inv.average_buy_price for inv in investments])
    total_profit = portfolio_value - total_invested

    try:
        market_update_interval_seconds = int(
            SystemConfig.get_value(
                'market_update_interval_seconds', '5') or 5)
    except Exception:
        market_update_interval_seconds = 5
    market_update_interval_seconds = max(
        2, min(market_update_interval_seconds, 300))

    return render_template(
        'market/index.html',
        title=_('بورصة غسيل الأموال'),
        assets=assets,
        investments=investments,
        portfolio_value=portfolio_value,
        total_profit=total_profit,
        market_update_interval_ms=market_update_interval_seconds *
        1000)


@bp.route('/guide')
@login_required
def guide():
    return render_template(
        'market/guide.html',
        title=_('أكاديمية غسيل الأموال'))


@bp.route('/trade/<int:asset_id>')
@login_required
def trade(asset_id):
    update_market_prices()

    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)

    investment = UserInvestment.query.filter_by(
        user_id=current_user.id, asset_id=asset.id).first()
    open_orders = SpotOrder.query.filter_by(
        user_id=current_user.id,
        asset_id=asset.id,
        status='open').order_by(
        SpotOrder.created_at.desc()).all()
    futures_positions = FuturesPosition.query.filter_by(
        user_id=current_user.id, asset_id=asset.id, is_open=True).order_by(
        FuturesPosition.opened_at.desc()).all()

    return render_template(
        'market/trade.html',
        title=_('التداول'),
        hide_page_title=True,
        hide_footer=True,
        body_extra_class='',
        page_container_class='container-fluid p-0',
        asset=asset,
        investment=investment,
        open_orders=open_orders,
        futures_positions=futures_positions,
    )


@bp.route('/history/<symbol>')
@login_required
@cache.cached(timeout=300)
def history(symbol):
    update_market_prices()
    allowed = MarketSimulationService.allowed_symbols()
    if symbol not in allowed:
        abort(404)

    try:
        days = int(request.args.get('days', 180) or 180)
    except Exception:
        days = 180
    days = max(30, min(days, 365))

    df = MarketSimulationService.get_history_data(symbol, days=days)
    if df is None or df.empty:
        return jsonify([])

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    close = df['Close'].astype(float)
    sma_20 = close.rolling(20).mean()
    ema_50 = close.ewm(span=50, adjust=False).mean()
    std_20 = close.rolling(20).std()
    bb_upper = sma_20 + (2 * std_20)
    bb_lower = sma_20 - (2 * std_20)

    out = []
    for idx, row in df.iterrows():
        ts = idx.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        i = df.index.get_loc(idx)
        v_sma = sma_20.iloc[i]
        v_ema = ema_50.iloc[i]
        v_bbu = bb_upper.iloc[i]
        v_bbl = bb_lower.iloc[i]

        out.append({
            'time': int(ts.timestamp()),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': float(row.get('Volume', 0) or 0),
            'sma_20': None if pd.isna(v_sma) else float(v_sma),
            'ema_50': None if pd.isna(v_ema) else float(v_ema),
            'bb_upper': None if pd.isna(v_bbu) else float(v_bbu),
            'bb_lower': None if pd.isna(v_bbl) else float(v_bbl),
        })

    return jsonify(out)


@bp.route('/place_order/<int:asset_id>', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
@check_player_status
def place_order(asset_id):
    update_market_prices()
    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)

    trade_type = (request.form.get('trade_type') or 'limit').strip().lower()
    order_type = (request.form.get('type') or '').strip().lower()

    if order_type not in {'buy', 'sell'}:
        flash(_('نوع عملية غير صحيح.'), 'danger')
        return redirect(url_for('market.trade', asset_id=asset.id))

    try:
        amount = float(request.form.get('amount', 0) or 0)
    except Exception:
        amount = 0.0

    if amount <= 0:
        flash(_('كمية/مبلغ غير صحيح.'), 'danger')
        return redirect(url_for('market.trade', asset_id=asset.id))

    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    if not user:
        abort(404)

    if trade_type == 'market':
        if asset.current_price <= 0:
            flash(_('سعر غير صالح حالياً.'), 'danger')
            return redirect(url_for('market.trade', asset_id=asset.id))

        if order_type == 'buy':
            usd_to_spend = amount
            if user.money < usd_to_spend:
                flash(_('لا تملك كاش كافي.'), 'danger')
                return redirect(url_for('market.trade', asset_id=asset.id))

            quantity = usd_to_spend / asset.current_price
            if not ResourceService.modify_resources(
                user.id, {
                    'money': -usd_to_spend}, 'spot_market_buy', auto_commit=False, expected_version=None):
                db.session.rollback()
                flash(_('لا تملك كاش كافي.'), 'danger')
                return redirect(url_for('market.trade', asset_id=asset.id))

            investment = UserInvestment.query.filter_by(
                user_id=user.id, asset_id=asset.id).with_for_update().first()
            if investment:
                total_cost_old = investment.quantity * investment.average_buy_price
                total_cost_new = usd_to_spend
                total_qty = investment.quantity + quantity
                if total_qty > 0:
                    investment.average_buy_price = (
                        total_cost_old + total_cost_new) / total_qty
                investment.quantity = total_qty
            else:
                investment = UserInvestment(
                    user_id=user.id,
                    asset_id=asset.id,
                    quantity=quantity,
                    average_buy_price=asset.current_price)
                db.session.add(investment)

            db.session.commit()
            flash(_('تم تنفيذ شراء Market بنجاح.'), 'success')
            return redirect(url_for('market.trade', asset_id=asset.id))

        if order_type == 'sell':
            qty_to_sell = amount
            investment = UserInvestment.query.filter_by(
                user_id=user.id, asset_id=asset.id).with_for_update().first()
            if not investment or investment.quantity < qty_to_sell:
                db.session.rollback()
                flash(_('لا تملك كمية كافية للبيع.'), 'danger')
                return redirect(url_for('market.trade', asset_id=asset.id))

            sell_value = qty_to_sell * asset.current_price
            investment.quantity -= qty_to_sell
            if investment.quantity <= 0:
                db.session.delete(investment)

            if not ResourceService.modify_resources(
                user.id, {
                    'money': sell_value}, 'spot_market_sell', auto_commit=False, expected_version=None):
                db.session.rollback()
                flash(_('حدث خطأ أثناء البيع.'), 'danger')
                return redirect(url_for('market.trade', asset_id=asset.id))

            db.session.commit()
            flash(_('تم تنفيذ بيع Market بنجاح.'), 'success')
            return redirect(url_for('market.trade', asset_id=asset.id))

    if trade_type == 'limit':
        try:
            price = float(request.form.get('price', 0) or 0)
        except Exception:
            price = 0.0

        quantity = amount
        if price <= 0 or quantity <= 0:
            flash(_('السعر/الكمية غير صحيحين.'), 'danger')
            return redirect(url_for('market.trade', asset_id=asset.id))

        if order_type == 'buy':
            total_cost = price * quantity
            if user.money < total_cost:
                flash(_('لا تملك كاش كافي.'), 'danger')
                return redirect(url_for('market.trade', asset_id=asset.id))

            if not ResourceService.modify_resources(
                user.id, {
                    'money': -total_cost}, 'spot_limit_buy_place', auto_commit=False, expected_version=None):
                db.session.rollback()
                flash(_('لا تملك كاش كافي.'), 'danger')
                return redirect(url_for('market.trade', asset_id=asset.id))

            order = SpotOrder(
                user_id=user.id,
                asset_id=asset.id,
                order_type='buy',
                price=price,
                quantity=quantity,
                status='open')
            db.session.add(order)
            db.session.commit()
            flash(_('تم وضع أمر Limit شراء.'), 'success')
            return redirect(url_for('market.trade', asset_id=asset.id))

        investment = UserInvestment.query.filter_by(
            user_id=user.id, asset_id=asset.id).with_for_update().first()
        if not investment or investment.quantity < quantity:
            db.session.rollback()
            flash(_('لا تملك كمية كافية للبيع.'), 'danger')
            return redirect(url_for('market.trade', asset_id=asset.id))

        investment.quantity -= quantity
        if investment.quantity <= 0:
            db.session.delete(investment)

        order = SpotOrder(
            user_id=user.id,
            asset_id=asset.id,
            order_type='sell',
            price=price,
            quantity=quantity,
            status='open')
        db.session.add(order)
        db.session.commit()
        flash(_('تم وضع أمر Limit بيع.'), 'success')
        return redirect(url_for('market.trade', asset_id=asset.id))

    flash(_('نوع تداول غير مدعوم.'), 'danger')
    return redirect(url_for('market.trade', asset_id=asset.id))


@bp.route('/cancel_order/<int:order_id>', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
@check_player_status
def cancel_order(order_id):
    order = db.session.query(SpotOrder).filter_by(
        id=order_id).with_for_update().first()
    if not order or order.user_id != current_user.id:
        abort(404)

    if order.status != 'open':
        flash(_('الطلب ليس مفتوحاً.'), 'warning')
        return redirect(url_for('market.trade', asset_id=order.asset_id))

    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    if not user:
        abort(404)

    if order.order_type == 'buy':
        refund = (order.quantity - (order.filled_quantity or 0)) * order.price
        if refund > 0:
            ResourceService.modify_resources(user.id,
                                             {'money': refund},
                                             'spot_limit_buy_cancel_refund',
                                             auto_commit=False,
                                             expected_version=None)
    else:
        qty = order.quantity - (order.filled_quantity or 0)
        if qty > 0:
            investment = UserInvestment.query.filter_by(
                user_id=user.id, asset_id=order.asset_id).with_for_update().first()
            if investment:
                investment.quantity += qty
            else:
                investment = UserInvestment(
                    user_id=user.id,
                    asset_id=order.asset_id,
                    quantity=qty,
                    average_buy_price=order.price)
                db.session.add(investment)

    order.status = 'cancelled'
    db.session.commit()
    flash(_('تم إلغاء الطلب.'), 'success')
    return redirect(url_for('market.trade', asset_id=order.asset_id))


@bp.route('/open_futures/<int:asset_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
@check_player_status
def open_futures(asset_id):
    update_market_prices()
    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)

    pos_type = (request.form.get('type') or '').strip().lower()
    if pos_type not in {'long', 'short'}:
        flash(_('نوع صفقة غير صحيح.'), 'danger')
        return redirect(url_for('market.trade', asset_id=asset.id))

    leverage = request.form.get('leverage', type=int) or 10
    if leverage not in {10, 20, 50, 100}:
        leverage = 10

    try:
        margin = float(request.form.get('amount', 0) or 0)
    except Exception:
        margin = 0.0

    if margin <= 0:
        flash(_('الهامش غير صحيح.'), 'danger')
        return redirect(url_for('market.trade', asset_id=asset.id))

    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    if not user:
        abort(404)

    if user.money < margin:
        flash(_('لا تملك كاش كافي.'), 'danger')
        return redirect(url_for('market.trade', asset_id=asset.id))

    if asset.current_price <= 0:
        flash(_('سعر غير صالح حالياً.'), 'danger')
        return redirect(url_for('market.trade', asset_id=asset.id))

    if not ResourceService.modify_resources(
        user.id, {
            'money': -margin}, 'futures_open_margin', auto_commit=False, expected_version=None):
        db.session.rollback()
        flash(_('لا تملك كاش كافي.'), 'danger')
        return redirect(url_for('market.trade', asset_id=asset.id))

    entry_price = asset.current_price
    quantity = (margin * leverage) / entry_price
    if pos_type == 'long':
        liquidation_price = entry_price * (1 - (1 / leverage))
    else:
        liquidation_price = entry_price * (1 + (1 / leverage))

    pos = FuturesPosition(
        user_id=user.id,
        asset_id=asset.id,
        position_type=pos_type,
        entry_price=entry_price,
        margin_amount=margin,
        leverage=leverage,
        quantity=quantity,
        liquidation_price=liquidation_price,
        is_open=True,
    )
    db.session.add(pos)
    db.session.commit()
    flash(_('تم فتح صفقة Futures بنجاح.'), 'success')
    return redirect(url_for('market.trade', asset_id=asset.id))


@bp.route('/close_futures/<int:position_id>', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
@check_player_status
def close_futures(position_id):
    pos = db.session.query(FuturesPosition).filter_by(
        id=position_id).with_for_update().first()
    if not pos or pos.user_id != current_user.id:
        abort(404)

    if not pos.is_open:
        flash(_('الصفقة مغلقة بالفعل.'), 'warning')
        return redirect(url_for('market.trade', asset_id=pos.asset_id))

    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    if not user:
        abort(404)

    update_market_prices()
    pnl = float(pos.calculate_pnl() or 0.0)
    payout = float(pos.margin_amount or 0.0) + pnl
    if payout < 0:
        payout = 0.0

    pos.is_open = False
    pos.closed_at = datetime.now(timezone.utc)

    if payout > 0:
        ResourceService.modify_resources(user.id,
                                         {'money': payout},
                                         'futures_close_payout',
                                         auto_commit=False,
                                         expected_version=None)

    db.session.commit()
    flash(_('تم إغلاق الصفقة.'), 'success')
    return redirect(url_for('market.trade', asset_id=pos.asset_id))


@bp.route('/buy_intel', methods=['POST'])
@login_required
@check_player_status
def buy_intel():
    try:
        cost = int(SystemConfig.get_value('market_intel_cost', '500') or 500)
    except Exception:
        cost = 500
    if current_user.money < cost:
        flash(_('لا تملك كاش كافي لشراء المعلومة!'), 'danger')
        return redirect(url_for('market.index'))

    # Atomic Deduction with logging
    if not ResourceService.modify_resources(
            current_user.id, {
            'money': -cost}, 'buy_intel_market', auto_commit=False, expected_version=None):
        flash(_('لا تملك كاش كافي لشراء المعلومة!'), 'danger')
        return redirect(url_for('market.index'))

    update_market_prices()

    def _fmt_money(x):
        try:
            return f"{float(x):,.2f}"
        except Exception:
            return "0.00"

    allowed = MarketSimulationService.allowed_symbols()
    assets = MarketAsset.query.filter(MarketAsset.symbol.in_(allowed)).all()
    asset = random.choice(assets) if assets else None

    if asset:
        sym = asset.symbol
        name = asset.name
        price = float(asset.current_price or 0.0)
        chg = float(asset.price_change_24h or 0.0)
        vol = float(asset.volume_24h or 0.0)
        up = chg >= 0

        pivot_up = price * (1 + random.uniform(0.008, 0.02)
                            ) if price > 0 else 0
        pivot_down = price * \
            (1 - random.uniform(0.008, 0.02)) if price > 0 else 0
        liq_level = price * (1 + (0.03 if up else -0.03)) if price > 0 else 0
        funding = random.choice(
            ["-0.02%", "-0.01%", "+0.01%", "+0.02%", "+0.03%"])

        vol_text = _fmt_money(vol)
        pivot_up_text = _fmt_money(pivot_up)
        pivot_down_text = _fmt_money(pivot_down)
        liq_level_text = _fmt_money(liq_level)

        intel_pool = []
        if asset.asset_type == 'crypto':
            intel_pool.extend([
                _(
                    f"معلومة مسربة: فيه نشاط غير طبيعي على {name} ({sym}). "
                    f"حجم 24س: {vol_text}. انتبه للذبذبة."
                ),
                _(
                    f"معلومة مسربة: إذا {sym} اخترق {pivot_up_text} ممكن نشوف تسارع قوي. "
                    f"لو كسر {pivot_down_text} خفف مخاطرة."
                ),
                _(
                    f"معلومة مسربة: تمويل الفيوتشر على {sym} حوالي {funding}. "
                    f"خليك واعي من تصفيات الرافعة قرب {liq_level_text}."
                ),
                _(
                    "معلومة مسربة: مراقبة أمنية مشددة على تداولات الكريبتو اليوم… "
                    "لا تفتح صفقات كبيرة دفعة وحدة."
                ),
            ])
        elif asset.asset_type == 'stock':
            intel_pool.extend([
                _(
                    f"معلومة مسربة: في صانع سوق عم يلمّ سيولة على {name} ({sym}). "
                    f"إذا ثبت فوق {pivot_up_text} بيصير الاختراق أقرب."
                ),
                _(
                    f"معلومة مسربة: {sym} عليه تذبذب {abs(chg):.2f}% خلال 24س. "
                    "إذا بتشتغل فيوتشر خفف الرافعة."
                ),
                _(
                    f"معلومة مسربة: في أوامر معلّقة كبيرة حوالين {pivot_down_text} على {sym}… "
                    "ممكن يعمل ارتداد سريع."
                ),
            ])
        elif asset.asset_type == 'commodity':
            intel_pool.extend([
                _(
                    f"معلومة مسربة: شحنة جديدة أثرت على {name} ({sym}). "
                    f"توقع حركة سريعة حوالين {pivot_up_text} و{pivot_down_text}."
                ),
                _(
                    f"معلومة مسربة: سيولة {sym} اليوم أعلى من المعتاد. "
                    "لو بتدخل، ادخل تدريجي وخلي وقف خسارة واضح."
                ),
            ])
        elif asset.asset_type == 'index':
            intel_pool.extend([
                _(f"معلومة مسربة: مؤشر {name} ({sym}) عم يعطي مزاج السوق. إذا ظل أخضر، فرص السبوت أحسن من الفيوتشر."),
                _(f"معلومة مسربة: تحرك {sym} اليوم هادي… بس ممكن يصير دفع مفاجئ إذا زاد الحجم.")
            ])

        intel_pool.extend([
            _("معلومة مسربة: لا تلحق الشمعة… خليك مع الخطة ووزّع دخولك."),
            _("معلومة مسربة: إذا فتحت فيوتشر، خلي إدارة المخاطر أولاً… الرافعة بتكبر الربح والخسارة."),
        ])
        intel = random.choice(intel_pool)
    else:
        intel = _(
            "معلومة مسربة: السوق اليوم حساس… اشتغل بحذر ولا تفتح صفقات كبيرة.")

    if intel.startswith("معلومة مسربة:"):
        flash(_('%(msg)s', msg=intel), 'info')
    else:
        flash(_('معلومة مسربة: %(msg)s', msg=intel), 'info')
    db.session.commit()
    return redirect(url_for('market.index'))


@bp.route('/buy/<int:asset_id>', methods=['POST'])
@login_required
@check_player_status
def buy(asset_id):
    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)

    # Refresh price
    # Handled by simulation service
    pass

    try:
        amount_to_invest = float(request.form.get('amount', 0))
    except ValueError:
        amount_to_invest = 0

    if amount_to_invest <= 0:
        flash(_('مبلغ غير صحيح!'), 'danger')
        return redirect(url_for('market.index'))

    if current_user.money < amount_to_invest:
        flash(_('لا تملك كاش كافي للعملية!'), 'danger')
        return redirect(url_for('market.index'))

    # Calculate quantity
    if asset.current_price <= 0:
        flash(_('سعر السهم غير صالح للتداول حالياً!'), 'danger')
        return redirect(url_for('market.index'))

    quantity = amount_to_invest / asset.current_price

    # Atomic Deduction with logging
    if not ResourceService.modify_resources(
            current_user.id, {
            'money': -amount_to_invest}, 'buy_asset_spot', auto_commit=False, expected_version=None):
        flash(_('لا تملك كاش كافي للعملية!'), 'danger')
        return redirect(url_for('market.index'))

    # Update/Create Investment
    investment = UserInvestment.query.filter_by(
        user_id=current_user.id,
        asset_id=asset.id).with_for_update().first()

    if investment:
        # Calculate new average price
        total_cost_old = investment.quantity * investment.average_buy_price
        total_cost_new = amount_to_invest
        total_quantity = investment.quantity + quantity

        investment.average_buy_price = (
            total_cost_old + total_cost_new) / total_quantity
        investment.quantity = total_quantity
    else:
        investment = UserInvestment(
            user_id=current_user.id,
            asset_id=asset.id,
            quantity=quantity,
            average_buy_price=asset.current_price
        )
        db.session.add(investment)

    db.session.commit()

    flash(_('تم شراء (غسيل) الأسهم بنجاح!'), 'success')
    return redirect(url_for('market.index'))


@bp.route('/sell/<int:asset_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
@check_player_status
def sell(asset_id):
    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)

    # Deadlock Prevention: Lock User FIRST, then Investment
    # We must ensure consistent locking order (User -> Investment) to avoid
    # deadlocks with 'buy' and 'check_limit_orders'
    try:
        # 1. Lock User
        # We lock the user row to establish the lock order.
        db.session.query(User).filter_by(
            id=current_user.id).with_for_update().first()

        # 2. Lock Investment
        investment = UserInvestment.query.filter_by(
            user_id=current_user.id, asset_id=asset.id).with_for_update().first()

        if not investment or investment.quantity <= 0:
            db.session.rollback()
            flash(_('لا تملك أسهم لبيعها!'), 'danger')
            return redirect(url_for('market.index'))

        # Calculate Value
        sell_value = investment.quantity * asset.current_price

        # 3. Add Money
        # ResourceService.modify_resources uses the same transaction and will
        # re-verify user lock (safe re-entrant)
        if not ResourceService.modify_resources(
            current_user.id, {
                'money': sell_value}, 'sell_asset_spot', auto_commit=False, expected_version=None):
            db.session.rollback()
            flash(_('خطأ في العملية!'), 'danger')
            return redirect(url_for('market.index'))

        # 4. Remove Investment
        db.session.delete(investment)
        db.session.commit()

        flash(_('تم بيع الأسهم بنجاح وربح %(val)s', val=int(sell_value)), 'success')

    except Exception as e:
        current_app.logger.error(f"Sell Error: {e}")
        db.session.rollback()
        flash(_('حدث خطأ أثناء البيع!'), 'danger')

    return redirect(url_for('market.index'))
