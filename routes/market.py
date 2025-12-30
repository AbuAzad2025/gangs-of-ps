from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models.market import MarketAsset, UserInvestment, FuturesPosition, SpotOrder
from models.user import User
from models.social import Message
from datetime import datetime, timezone, timedelta
from models.system import SystemConfig
import yfinance as yf
import random
import pandas as pd
from .utils import update_daily_task_progress

bp = Blueprint('market', __name__, url_prefix='/market')

def check_limit_orders(asset):
    """Checks and executes limit orders for a given asset"""
    # Buy Orders: Execute if current_price <= limit_price
    buy_orders = SpotOrder.query.filter_by(asset_id=asset.id, status='open', order_type='buy').all()
    for order in buy_orders:
        if asset.current_price <= order.price:
            # User already paid (locked money), so just give assets
            investment = UserInvestment.query.filter_by(user_id=order.user_id, asset_id=asset.id).first()
            if investment:
                # Avg Price update
                total_cost_old = investment.quantity * investment.average_buy_price
                total_cost_new = order.quantity * order.price
                total_qty = investment.quantity + order.quantity
                if total_qty > 0:
                    investment.average_buy_price = (total_cost_old + total_cost_new) / total_qty
                investment.quantity = total_qty
            else:
                investment = UserInvestment(
                    user_id=order.user_id,
                    asset_id=asset.id,
                    quantity=order.quantity,
                    average_buy_price=order.price
                )
                db.session.add(investment)
            
            order.status = 'filled'
            order.filled_quantity = order.quantity
            
    # Sell Orders: Execute if current_price >= limit_price
    sell_orders = SpotOrder.query.filter_by(asset_id=asset.id, status='open', order_type='sell').all()
    for order in sell_orders:
        if asset.current_price >= order.price:
            # Assets already locked, give money
            total_value = order.quantity * order.price
            user = db.session.get(User, order.user_id)
            if user:
                user.money += total_value
            
            order.status = 'filled'
            order.filled_quantity = order.quantity
            try:
                user = db.session.get(User, order.user_id)
                if user:
                    update_daily_task_progress(user, 'buy')
            except Exception:
                pass
            
            db.session.commit()

def update_market_prices():
    """Updates prices for all tracked assets from Yahoo Finance"""
    assets = MarketAsset.query.all()
    
    # If no assets exist, initialize them
    if not assets:
        initial_assets = [
            {'symbol': 'BTC-USD', 'name': 'Bitcoin (Crypto)', 'type': 'crypto'},
            {'symbol': 'ETH-USD', 'name': 'Ethereum (Crypto)', 'type': 'crypto'},
            {'symbol': 'XRP-USD', 'name': 'XRP (Crypto)', 'type': 'crypto'},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corp', 'type': 'stock'},
            {'symbol': 'TSLA', 'name': 'Tesla Inc', 'type': 'stock'},
            {'symbol': 'AAPL', 'name': 'Apple Inc', 'type': 'stock'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corp', 'type': 'stock'},
            {'symbol': 'GC=F', 'name': 'Gold Futures', 'type': 'commodity'},
            {'symbol': 'SI=F', 'name': 'Silver Futures', 'type': 'commodity'},
        ]
        
        for asset_data in initial_assets:
            new_asset = MarketAsset(
                symbol=asset_data['symbol'],
                name=asset_data['name'],
                asset_type=asset_data['type']
            )
            db.session.add(new_asset)
        db.session.commit()
        assets = MarketAsset.query.all()
    
    # Check if update is needed based on configurable interval
    needs_update = False
    now = datetime.now(timezone.utc)
    try:
        interval = int(SystemConfig.get_value('market_update_interval_seconds', '300') or '300')
    except Exception:
        interval = 300
    for asset in assets:
        last_updated = asset.last_updated
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        if (now - last_updated).total_seconds() > interval or asset.current_price <= 0:
            needs_update = True
            break
            
    if needs_update:
        symbols = [a.symbol for a in assets]
        try:
            # Batch fetch
            print(f"Fetching data for: {symbols}")
            tickers = yf.Tickers(' '.join(symbols))
            
            for asset in assets:
                try:
                    # Accessing tickers.tickers dict safely
                    ticker = tickers.tickers.get(asset.symbol)
                    if not ticker:
                        # Fallback to individual fetch if batch key missing
                        print(f"Key {asset.symbol} not in batch results, trying individual...")
                        ticker = yf.Ticker(asset.symbol)
                    
                    # Try to get fast info, fallback to history
                    price = None
                    prev_close = None
                    
                    try:
                        info = ticker.fast_info
                        price = info.last_price
                        prev_close = info.previous_close
                        
                        # Update 24h stats
                        asset.high_24h = info.day_high
                        asset.low_24h = info.day_low
                        asset.volume_24h = info.last_volume
                        
                        print(f"Got price for {asset.symbol}: {price}")
                    except Exception as e:
                        print(f"fast_info failed for {asset.symbol}: {e}")
                    
                    if not price:
                        # Fallback to history
                        print(f"Fallback to history for {asset.symbol}")
                        hist = ticker.history(period="1d")
                        if not hist.empty:
                            price = hist['Close'].iloc[-1]
                            # Try to get prev close from history if possible (approx)
                            if len(hist) > 1:
                                prev_close = hist['Close'].iloc[-2]
                            else:
                                prev_close = price # Can't calc change accurately
                        else:
                            print(f"History empty for {asset.symbol}")

                    if price:
                        asset.current_price = price
                        if prev_close and prev_close > 0:
                            change = ((price - prev_close) / prev_close) * 100
                            asset.price_change_24h = change
                        asset.last_updated = now
                        
                        # Check Limit Orders
                        check_limit_orders(asset)
                    else:
                        print(f"Could not determine price for {asset.symbol}")

                except Exception as e:
                    print(f"Error processing {asset.symbol}: {e}")
                    
            db.session.commit()
            print("Market update committed.")
        except Exception as e:
            print(f"Global fetch error: {e}")

@bp.route('/')
@login_required
def index():
    # Trigger update (lazy loading)
    update_market_prices()
    
    assets = MarketAsset.query.all()
    
    # User portfolio
    investments = UserInvestment.query.filter_by(user_id=current_user.id).all()
    portfolio_value = sum([inv.current_value() for inv in investments])
    total_invested = sum([inv.quantity * inv.average_buy_price for inv in investments])
    total_profit = portfolio_value - total_invested
    
    return render_template('market/index.html', 
                          title=_('بورصة غسيل الأموال'), 
                          assets=assets, 
                          investments=investments,
                          portfolio_value=portfolio_value,
                          total_profit=total_profit)

@bp.route('/guide')
@login_required
def guide():
    return render_template('market/guide.html', title=_('أكاديمية غسيل الأموال'))

@bp.route('/buy_intel', methods=['POST'])
@login_required
def buy_intel():
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until and current_user.jail_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في السجن!'), 'danger')
        return redirect(url_for('market.index'))
        
    cost = 500
    if current_user.money < cost:
        flash(_('لا تملك كاش كافي لشراء المعلومة!'), 'danger')
        return redirect(url_for('market.index'))
        
    current_user.money -= cost
    
    # Generate random intel
    intels = [
        _("سمعت أن البيتكوين رح يطير اليوم... بس مش أكيد."),
        _("في حيتان ببيعوا أسهم تسلا، دير بالك."),
        _("الذهب هو الملاذ الآمن يا صاحبي."),
        _("الشرطة بتراقب سوق الكريبتو، خليك حذر."),
        _("اشتري في الانخفاض وبيع في الارتفاع... نصيحة بمليون دولار.")
    ]
    intel = random.choice(intels)
    
    flash(_('معلومة مسربة: %(msg)s', msg=intel), 'info')
    db.session.commit()
    return redirect(url_for('market.index'))


@bp.route('/buy/<int:asset_id>', methods=['POST'])
@login_required
def buy(asset_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('gym.index'))

    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)
    
    # Refresh price just in case
    try:
        ticker = yf.Ticker(asset.symbol)
        price = ticker.fast_info.last_price
        if price:
            asset.current_price = price
            asset.last_updated = datetime.now(timezone.utc)
            db.session.commit()
    except:
        pass # Use cached price if fetch fails
        
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
    quantity = amount_to_invest / asset.current_price
    
    # Update User
    current_user.money -= amount_to_invest
    
    # Update/Create Investment
    investment = UserInvestment.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
    
    if investment:
        # Calculate new average price
        total_cost_old = investment.quantity * investment.average_buy_price
        total_cost_new = amount_to_invest
        total_quantity = investment.quantity + quantity
        
        investment.average_buy_price = (total_cost_old + total_cost_new) / total_quantity
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
def sell(asset_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('gym.index'))

    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)
    investment = UserInvestment.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
    
    if not investment or investment.quantity <= 0:
        flash(_('لا تملك أسهم في هذه الشركة!'), 'danger')
        return redirect(url_for('market.index'))
        
    # Percentage to sell (25%, 50%, 100%) or amount? Let's do percentage for simplicity in UI
    percent = int(request.form.get('percent', 0))
    if percent not in [25, 50, 100]:
        flash(_('نسبة بيع غير صحيحة!'), 'danger')
        return redirect(url_for('market.index'))
        
    # Refresh price
    try:
        ticker = yf.Ticker(asset.symbol)
        price = ticker.fast_info.last_price
        if price:
            asset.current_price = price
            asset.last_updated = datetime.now(timezone.utc)
            db.session.commit()
    except:
        pass
        
    quantity_to_sell = investment.quantity * (percent / 100)
    sale_value = quantity_to_sell * asset.current_price
    
    # Calculate Profit
    cost_basis = quantity_to_sell * investment.average_buy_price
    profit = sale_value - cost_basis
    
    # Intelligence Reward (1 IQ per $1000 profit)
    if profit > 0:
        iq_gain = int(profit / 1000)
        if iq_gain > 0:
            current_user.intelligence += iq_gain
            flash(_('ربح ممتاز! اكتسبت %(iq)s نقطة ذكاء.', iq=iq_gain), 'success')

    # Update User
    current_user.money += sale_value
    
    # Update Investment
    investment.quantity -= quantity_to_sell
    
    if investment.quantity < 0.000001: # Floating point fix
        db.session.delete(investment)
    
    db.session.commit()
    
    flash(_('تم تسييل المحفظة بنجاح!'), 'success')
    return redirect(url_for('market.trade', symbol=asset.symbol))

@bp.route('/futures/open/<int:asset_id>', methods=['POST'])
@login_required
def open_futures(asset_id):
    if SystemConfig.get_value('market_enable_futures', 'true') != 'true':
        flash(_('تم تعطيل تداول الفيوتشر من لوحة المطور'), 'warning')
        return redirect(url_for('market.index'))
    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)
        
    try:
        amount = float(request.form.get('amount', 0))
        leverage = int(request.form.get('leverage', 1))
        position_type = request.form.get('type', 'long') # long or short
    except ValueError:
        flash(_('بيانات غير صحيحة!'), 'danger')
        return redirect(url_for('market.trade', symbol=asset.symbol))
        
    try:
        min_amount = float(SystemConfig.get_value('market_spot_min_buy_usd', '10') or '10')
    except Exception:
        min_amount = 10.0
    if amount < min_amount:
        flash(_('الحد الأدنى للصفقة %(val)s$', val=min_amount), 'danger')
        return redirect(url_for('market.trade', symbol=asset.symbol))
        
    leverages_cfg = SystemConfig.get_value('market_futures_leverages', '1,5,10,20,50,100') or '1,5,10,20,50,100'
    try:
        supported_leverages = [int(x.strip()) for x in leverages_cfg.split(',') if x.strip()]
    except Exception:
        supported_leverages = [1, 5, 10, 20, 50, 100]
    if leverage not in supported_leverages:
        flash(_('رافعة مالية غير مدعومة!'), 'danger')
        return redirect(url_for('market.trade', symbol=asset.symbol))
        
    if position_type not in ['long', 'short']:
        flash(_('نوع صفقة غير صحيح!'), 'danger')
        return redirect(url_for('market.trade', symbol=asset.symbol))
        
    if current_user.money < amount:
        flash(_('لا تملك رصيد كافي!'), 'danger')
        return redirect(url_for('market.trade', symbol=asset.symbol))
        
    # Refresh price
    try:
        ticker = yf.Ticker(asset.symbol)
        price = ticker.fast_info.last_price
        if price:
            asset.current_price = price
            asset.last_updated = datetime.now(timezone.utc)
            db.session.commit()
    except:
        pass
        
    entry_price = asset.current_price
    
    # Calculate Liquidation Price
    # Long: Entry * (1 - 1/Leverage)
    # Short: Entry * (1 + 1/Leverage)
    # Adding a 5% buffer for safety/fees simulation
    if position_type == 'long':
        liquidation_price = entry_price * (1 - (1/leverage) + 0.005) 
    else:
        liquidation_price = entry_price * (1 + (1/leverage) - 0.005)
        
    quantity = (amount * leverage) / entry_price
    
    position = FuturesPosition(
        user_id=current_user.id,
        asset_id=asset.id,
        position_type=position_type,
        entry_price=entry_price,
        margin_amount=amount,
        leverage=leverage,
        quantity=quantity,
        liquidation_price=liquidation_price
    )
    
    current_user.money -= amount
    db.session.add(position)
    db.session.commit()
    
    flash(_('تم فتح الصفقة بنجاح!'), 'success')
    return redirect(url_for('market.trade', symbol=asset.symbol))

@bp.route('/futures/close/<int:position_id>', methods=['POST'])
@login_required
def close_futures(position_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك التداول!'), 'danger')
            return redirect(url_for('gym.index'))

    position = db.session.get(FuturesPosition, position_id)
    if not position or position.user_id != current_user.id or not position.is_open:
        abort(404)
        
    asset = position.asset
    
    # Refresh price
    try:
        ticker = yf.Ticker(asset.symbol)
        price = ticker.fast_info.last_price
        if price:
            asset.current_price = price
            asset.last_updated = datetime.now(timezone.utc)
            db.session.commit()
    except:
        pass
        
    pnl = position.calculate_pnl()
    
    # Return margin + pnl
    return_amount = position.margin_amount + pnl
    
    # If liquidated logic (simplified check here, though should be background task)
    if return_amount <= 0:
        return_amount = 0
        flash(_('تم تصفية الصفقة (ليكويديشن)! خسرت كل المبلغ.'), 'danger')
    else:
        # Intelligence Reward
        if pnl > 0:
            iq_gain = int(pnl / 1000)
            if iq_gain > 0:
                current_user.intelligence += iq_gain
                flash(_('ربح ممتاز! اكتسبت %(iq)s نقطة ذكاء.', iq=iq_gain), 'success')
                
        flash(_('تم إغلاق الصفقة. الربح/الخسارة: %(val).2f$', val=pnl), 'success' if pnl >= 0 else 'warning')
        
    current_user.money += return_amount
    
    # Mark as closed (or delete? let's delete to keep DB clean for game, or keep for history)
    # For game simplicity, let's delete or mark closed. Let's delete to avoid clutter.
    # Actually, better to keep history but for now delete to match spot logic style
    db.session.delete(position)
    db.session.commit()
    
    return redirect(url_for('market.trade', symbol=asset.symbol))

@bp.route('/intel/buy', methods=['POST'])
@login_required
def purchase_intel_report():
    try:
        cost = int(SystemConfig.get_value('market_intel_cost', '500') or '500')
    except Exception:
        cost = 500
    if current_user.money < cost:
        flash(_('لا تملك كاش كافي لشراء المعلومة! (المطلوب %(c)s$)', c=cost), 'danger')
        return redirect(url_for('market.index'))
    
    # Pick random asset
    assets = MarketAsset.query.all()
    if not assets:
        flash(_('لا يوجد معلومات متاحة حالياً.'), 'warning')
        return redirect(url_for('market.index'))
        
    asset = random.choice(assets)
    
    # Analyze (Do this BEFORE deducting money to avoid refund logic)
    try:
        ticker = yf.Ticker(asset.symbol)
        # Get enough history for SMA20
        hist = ticker.history(period="1mo")
        
        trend = "neutral" # Default
        
        if hist.empty or len(hist) < 20:
            # Fallback simple analysis
            if asset.price_change_24h > 2:
                trend = "bullish"
            elif asset.price_change_24h < -2:
                trend = "bearish"
        else:
            # Calculate SMA 20
            sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            current_price = hist['Close'].iloc[-1]
            
            if current_price > sma_20:
                trend = "bullish"
            else:
                trend = "bearish"
                
        # Generate Message
        flavor_texts = {
            "bullish": [
                _("مصادري في وول ستريت تؤكد: الحيتان يشترون {symbol} بجنون! السعر فوق المتوسط."),
                _("تسريب سري: تقارير الأرباح لـ {symbol} ستكون خيالية. اشترِ قبل الانفجار!"),
                _("المافيا الروسية تغسل أموالها في {symbol}. السعر سيرتفع حتماً."),
            ],
            "bearish": [
                _("انتبه! المدير التنفيذي لـ {symbol} يبيع أسهمه سراً. الانهيار قادم."),
                _("هناك تلاعب في {symbol} لتخفيض السعر. اهرب فوراً!"),
                _("سمعت أن الحكومة ستحظر {symbol} قريباً. بيع كل شيء!"),
            ],
            "neutral": [
                _("السوق هادئ جداً حول {symbol}. الهدوء الذي يسبق العاصفة؟"),
                _("لا توجد حركة واضحة على {symbol}. وفر فلوسك لفرصة أخرى."),
            ]
        }
        
        msg_template = random.choice(flavor_texts.get(trend, flavor_texts['neutral']))
        msg = msg_template.format(symbol=asset.symbol)
        
        # Now deduct money and commit
        current_user.money -= cost
        
        # Create delayed message
        delivery_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        # Use current user as sender (Note to self)
        intel_msg = Message(
            sender_id=current_user.id,
            receiver_id=current_user.id,
            subject=_('تقرير استخباراتي: {symbol}').format(symbol=asset.symbol),
            body=msg,
            delivery_time=delivery_time
        )
        db.session.add(intel_msg)
        db.session.commit()
        
        flash(_('تم استلام طلبك. سيصلك التقرير في بريدك الوارد خلال 10 دقائق.'), 'success')
        
    except Exception as e:
        print(f"Intel Error: {e}")
        # No money deducted yet, so just rollback to be safe (though nothing changed)
        db.session.rollback()
        flash(_('حدث خطأ أثناء جلب المعلومات. حاول مرة أخرى لاحقاً.'), 'danger')
        
    return redirect(url_for('market.index'))


@bp.route('/trade/<symbol>')
@login_required
def trade(symbol):
    # Trigger update
    update_market_prices()
    
    asset = MarketAsset.query.filter_by(symbol=symbol).first_or_404()
    investment = UserInvestment.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
    futures_positions = FuturesPosition.query.filter_by(user_id=current_user.id, asset_id=asset.id, is_open=True).all()
    open_orders = SpotOrder.query.filter_by(user_id=current_user.id, asset_id=asset.id, status='open').order_by(SpotOrder.created_at.desc()).all()
    
    return render_template('market/trade.html',
                          title=f"{asset.name} | Trade",
                          asset=asset,
                          investment=investment,
                          futures_positions=futures_positions,
                          open_orders=open_orders)

@bp.route('/spot/order/<int:asset_id>', methods=['POST'])
@login_required
def place_order(asset_id):
    if SystemConfig.get_value('market_enable_spot', 'true') != 'true':
        flash(_('تم تعطيل التداول الفوري من لوحة المطور'), 'warning')
        return redirect(url_for('market.index'))
    asset = db.session.get(MarketAsset, asset_id)
    if not asset:
        abort(404)
        
    try:
        order_type = request.form.get('type') # buy, sell
        trade_type = request.form.get('trade_type') # market, limit
        amount = float(request.form.get('amount', 0))
        price = float(request.form.get('price', 0)) # Only for limit
    except ValueError:
        flash(_('بيانات غير صحيحة!'), 'danger')
        return redirect(url_for('market.trade', symbol=asset.symbol))
        
    if amount <= 0:
        flash(_('الكمية يجب أن تكون أكبر من صفر'), 'danger')
        return redirect(url_for('market.trade', symbol=asset.symbol))

    # MARKET ORDERS
    if trade_type == 'market':
        if order_type == 'buy':
            # Amount is Total USDT
            if current_user.money < amount:
                flash(_('لا تملك كاش كافي!'), 'danger')
                return redirect(url_for('market.trade', symbol=asset.symbol))
            try:
                min_buy = float(SystemConfig.get_value('market_spot_min_buy_usd', '10') or '10')
            except Exception:
                min_buy = 10.0
            if amount < min_buy:
                flash(_('أقل مبلغ شراء سبوت هو %(val)s$', val=min_buy), 'danger')
                return redirect(url_for('market.trade', symbol=asset.symbol))
            
            quantity = amount / asset.current_price
            current_user.money -= amount
            
            investment = UserInvestment.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
            if investment:
                total_cost_old = investment.quantity * investment.average_buy_price
                total_cost_new = amount
                investment.quantity += quantity
                investment.average_buy_price = (total_cost_old + total_cost_new) / investment.quantity
            else:
                investment = UserInvestment(user_id=current_user.id, asset_id=asset.id, quantity=quantity, average_buy_price=asset.current_price)
                db.session.add(investment)
                
            db.session.commit()
            flash(_('تم شراء الأسهم بنجاح!'), 'success')
            try:
                update_daily_task_progress(current_user, 'buy')
            except Exception:
                pass
            
        elif order_type == 'sell':
            # Amount is Quantity (Shares)
            investment = UserInvestment.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
            if not investment or investment.quantity < amount:
                flash(_('لا تملك أسهم كافية!'), 'danger')
                return redirect(url_for('market.trade', symbol=asset.symbol))
                
            sale_value = amount * asset.current_price
            
            # Profit logic
            cost_basis = amount * investment.average_buy_price
            profit = sale_value - cost_basis
            if profit > 0:
                iq = int(profit/1000)
                if iq > 0: current_user.intelligence += iq
                
            current_user.money += sale_value
            investment.quantity -= amount
            if investment.quantity < 1e-6: db.session.delete(investment)
            
            db.session.commit()
            flash(_('تم بيع الأسهم بنجاح!'), 'success')

    # LIMIT ORDERS
    elif trade_type == 'limit':
        if SystemConfig.get_value('market_enable_limit_orders', 'true') != 'true':
            flash(_('أوامر الحد (Limit) معطلة من لوحة المطور'), 'warning')
            return redirect(url_for('market.trade', symbol=asset.symbol))
        if price <= 0:
             flash(_('سعر غير صحيح!'), 'danger')
             return redirect(url_for('market.trade', symbol=asset.symbol))
             
        if order_type == 'buy':
            # Amount is Quantity (Shares) for Limit
            total_cost = amount * price
            
            if current_user.money < total_cost:
                flash(_('لا تملك كاش كافي! (المطلوب: %(cost).2f$)', cost=total_cost), 'danger')
                return redirect(url_for('market.trade', symbol=asset.symbol))
                
            current_user.money -= total_cost
            
            order = SpotOrder(
                user_id=current_user.id,
                asset_id=asset.id,
                order_type='buy',
                price=price,
                quantity=amount,
                status='open'
            )
            db.session.add(order)
            db.session.commit()
            flash(_('تم وضع أمر الشراء!'), 'success')
            
        elif order_type == 'sell':
            # Amount is Quantity (Shares)
            investment = UserInvestment.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
            if not investment or investment.quantity < amount:
                flash(_('لا تملك أسهم كافية!'), 'danger')
                return redirect(url_for('market.trade', symbol=asset.symbol))
                
            # Lock assets
            investment.quantity -= amount
            if investment.quantity < 1e-6: db.session.delete(investment)
            
            order = SpotOrder(
                user_id=current_user.id,
                asset_id=asset.id,
                order_type='sell',
                price=price,
                quantity=amount,
                status='open'
            )
            db.session.add(order)
            db.session.commit()
            flash(_('تم وضع أمر البيع!'), 'success')
            
    return redirect(url_for('market.trade', symbol=asset.symbol))

@bp.route('/spot/cancel/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = db.session.get(SpotOrder, order_id)
    if not order or order.user_id != current_user.id or order.status != 'open':
        abort(404)
        
    # Refund
    if order.order_type == 'buy':
        refund = (order.quantity - order.filled_quantity) * order.price
        current_user.money += refund
    else:
        # Return shares
        asset = order.asset
        investment = UserInvestment.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
        qty_back = order.quantity - order.filled_quantity
        if investment:
            investment.quantity += qty_back
        else:
            investment = UserInvestment(
                user_id=current_user.id,
                asset_id=asset.id,
                quantity=qty_back,
                average_buy_price=order.price
            )
            db.session.add(investment)
            
    order.status = 'cancelled'
    db.session.commit()
    flash(_('تم إلغاء الأمر.'), 'info')
    return redirect(url_for('market.trade', symbol=order.asset.symbol))

@bp.route('/history/<symbol>')
@login_required
def history(symbol):
    try:
        ticker = yf.Ticker(symbol)
        # Fetch history - fetch more to allow for MA calculation
        hist = ticker.history(period="6mo", interval="1d")
        
        # Calculate Indicators
        # SMA 20
        hist['SMA_20'] = hist['Close'].rolling(window=20).mean()
        # EMA 50
        hist['EMA_50'] = hist['Close'].ewm(span=50, adjust=False).mean()
        
        # Bollinger Bands (20, 2)
        hist['BB_Middle'] = hist['Close'].rolling(window=20).mean()
        hist['BB_Std'] = hist['Close'].rolling(window=20).std()
        hist['BB_Upper'] = hist['BB_Middle'] + (2 * hist['BB_Std'])
        hist['BB_Lower'] = hist['BB_Middle'] - (2 * hist['BB_Std'])

        # Drop NaN values created by rolling windows (optional, or just handle in loop)
        # We'll just slice the last month for display to keep it clean but accurate
        display_hist = hist.tail(30) # Last 30 days for view

        data = []
        for index, row in display_hist.iterrows():
            # lightweight-charts expects time in seconds (unix timestamp) or string YYYY-MM-DD
            item = {
                'time': index.strftime('%Y-%m-%d'),
                'open': row['Open'],
                'high': row['High'],
                'low': row['Low'],
                'close': row['Close'],
                # Indicators (handle NaN if any remain)
                'sma_20': row['SMA_20'] if not pd.isna(row['SMA_20']) else None,
                'ema_50': row['EMA_50'] if not pd.isna(row['EMA_50']) else None,
                'bb_upper': row['BB_Upper'] if not pd.isna(row['BB_Upper']) else None,
                'bb_lower': row['BB_Lower'] if not pd.isna(row['BB_Lower']) else None,
            }
            data.append(item)
            
        return jsonify(data)
    except Exception as e:
        print(f"History error: {e}")
        return jsonify({'error': str(e)})
