import random
import math
import pandas as pd
import json
import re
from datetime import datetime, timezone, timedelta
from models.market import MarketAsset
from models.system import SystemConfig
from extensions import db

class MarketSimulationService:
    # Configuration for simulated assets

    # volatility: max percentage change per update (e.g., 0.02 = 2%)
    # trend_bias: slight bias per update (-0.001 to 0.001)
    BASE_ASSET_CONFIG = {
        'G-COIN': {'name': 'Gangs Coin', 'type': 'crypto', 'volatility': 0.05, 'base_price': 1000, 'enabled': True},
        'B-IRON': {'name': 'BlackIron Arms', 'type': 'stock', 'volatility': 0.02, 'base_price': 150, 'enabled': True},
        'PHRMA': {'name': 'Underground Pharma', 'type': 'stock', 'volatility': 0.015, 'base_price': 80, 'enabled': True},
        'HACK': {'name': 'CyberSec Solutions', 'type': 'stock', 'volatility': 0.03, 'base_price': 220, 'enabled': True},
        'GOLD-X': {'name': 'Conflict Gold', 'type': 'commodity', 'volatility': 0.008, 'base_price': 1900, 'enabled': True},
        'OIL-B': {'name': 'Smuggled Oil', 'type': 'commodity', 'volatility': 0.012, 'base_price': 75, 'enabled': True},
        'CASINO': {'name': 'Royal Casino Corp', 'type': 'stock', 'volatility': 0.025, 'base_price': 45, 'enabled': True},
        'OLIVE': {'name': 'Olive Branch Labs', 'type': 'stock', 'volatility': 0.018, 'base_price': 62, 'enabled': True},
        'KEFFI': {'name': 'Keffiyeh Textiles', 'type': 'stock', 'volatility': 0.022, 'base_price': 38, 'enabled': True},
        'TUNNL': {'name': 'TunnelWorks', 'type': 'stock', 'volatility': 0.028, 'base_price': 91, 'enabled': True},
        'SAFRN': {'name': 'Saffron Routes', 'type': 'commodity', 'volatility': 0.015, 'base_price': 420, 'enabled': True},
        'DUST': {'name': 'Desert Silicon', 'type': 'commodity', 'volatility': 0.02, 'base_price': 12, 'enabled': True},
        'JASM': {'name': 'Jasmin Credit', 'type': 'crypto', 'volatility': 0.06, 'base_price': 6.5, 'enabled': True},
        'AZAD': {'name': 'Azad Index', 'type': 'index', 'volatility': 0.012, 'base_price': 2500, 'enabled': True},

        'BITE': {'name': 'BitCrown', 'type': 'crypto', 'volatility': 0.055, 'base_price': 68000, 'enabled': True},
        'ETRA': {'name': 'Etheria Network', 'type': 'crypto', 'volatility': 0.05, 'base_price': 3600, 'enabled': True},
        'SOLA': {'name': 'Solara Chain', 'type': 'crypto', 'volatility': 0.065, 'base_price': 180, 'enabled': True},
        'RIPL': {'name': 'Rippel Labs', 'type': 'crypto', 'volatility': 0.06, 'base_price': 1.25, 'enabled': True},
        'BNNZ': {'name': 'Binanza Coin', 'type': 'crypto', 'volatility': 0.06, 'base_price': 520, 'enabled': True},
        'CRDN': {'name': 'Cardanium', 'type': 'crypto', 'volatility': 0.055, 'base_price': 2.8, 'enabled': True},
        'PLKD': {'name': 'Polykade', 'type': 'crypto', 'volatility': 0.06, 'base_price': 12.5, 'enabled': True},
        'CHLX': {'name': 'ChainLynx', 'type': 'crypto', 'volatility': 0.06, 'base_price': 24, 'enabled': True},
        'AVLR': {'name': 'AvalancheR', 'type': 'crypto', 'volatility': 0.065, 'base_price': 95, 'enabled': True},
        'LTBY': {'name': 'LiteByte', 'type': 'crypto', 'volatility': 0.055, 'base_price': 140, 'enabled': True},

        'APPLT': {'name': 'Appela Devices', 'type': 'stock', 'volatility': 0.018, 'base_price': 190, 'enabled': True},
        'TSLR': {'name': 'Teslar Mobility', 'type': 'stock', 'volatility': 0.03, 'base_price': 240, 'enabled': True},
        'NVDM': {'name': 'Nvidium Compute', 'type': 'stock', 'volatility': 0.028, 'base_price': 135, 'enabled': True},
        'MSFY': {'name': 'MicroSofy Cloud', 'type': 'stock', 'volatility': 0.017, 'base_price': 420, 'enabled': True},
        'AMZIN': {'name': 'Amazin Bazaar', 'type': 'stock', 'volatility': 0.02, 'base_price': 175, 'enabled': True},
        'GGLX': {'name': 'Gogol Search', 'type': 'stock', 'volatility': 0.019, 'base_price': 160, 'enabled': True},
        'MTTA': {'name': 'Metta Social', 'type': 'stock', 'volatility': 0.021, 'base_price': 310, 'enabled': True},
        'NFLKS': {'name': 'Netflicks Media', 'type': 'stock', 'volatility': 0.024, 'base_price': 485, 'enabled': True},
        'BRKSH': {'name': 'Berkshine Holdings', 'type': 'stock', 'volatility': 0.013, 'base_price': 560, 'enabled': True},
        'JPMRN': {'name': 'JPMorron Bank', 'type': 'stock', 'volatility': 0.015, 'base_price': 155, 'enabled': True},
    }

    @staticmethod
    def get_asset_config():
        base = {}
        for sym, cfg in (MarketSimulationService.BASE_ASSET_CONFIG or {}).items():
            base[sym] = dict(cfg)
            base[sym].setdefault('enabled', True)

        raw = SystemConfig.get_value('market_assets_json')
        if raw:
            try:
                data = json.loads(raw)
            except Exception:
                data = None
            if isinstance(data, dict):
                for k, v in data.items():
                    sym = str(k or '').strip().upper()
                    if not sym or not re.fullmatch(r'[A-Z0-9][A-Z0-9-]{0,9}', sym):
                        continue
                    if not isinstance(v, dict):
                        continue

                    name = str(v.get('name') or base.get(sym, {}).get('name') or sym).strip()
                    atype = str(v.get('type') or base.get(sym, {}).get('type') or 'stock').strip().lower()
                    if atype not in {'stock', 'crypto', 'commodity', 'index'}:
                        atype = 'stock'

                    enabled = v.get('enabled', base.get(sym, {}).get('enabled', True))
                    enabled = bool(enabled)

                    base_price = v.get('base_price', base.get(sym, {}).get('base_price', 100))
                    try:
                        base_price = float(base_price)
                    except Exception:
                        base_price = float(base.get(sym, {}).get('base_price', 100) or 100)
                    if base_price <= 0:
                        base_price = float(base.get(sym, {}).get('base_price', 100) or 100)

                    volatility = v.get('volatility', base.get(sym, {}).get('volatility', 0.02))
                    try:
                        volatility = float(volatility)
                    except Exception:
                        volatility = float(base.get(sym, {}).get('volatility', 0.02) or 0.02)
                    if volatility > 1:
                        volatility = volatility / 100.0
                    volatility = max(0.0001, min(volatility, 0.5))

                    base[sym] = {
                        'name': name,
                        'type': atype,
                        'volatility': volatility,
                        'base_price': base_price,
                        'enabled': enabled,
                    }

        return base

    @staticmethod
    def allowed_symbols():
        cfg = MarketSimulationService.get_asset_config()
        return {sym for sym, meta in cfg.items() if (meta or {}).get('enabled', True)}

    @staticmethod
    def _sanitize_nonfiction_assets():
        allowed = MarketSimulationService.allowed_symbols()
        banned_exact = {
            "BTC-USD", "ETH-USD", "XRP-USD",
            "AAPL", "TSLA", "NVDA", "MSFT",
            "GC=F", "SI=F",
        }

        assets = MarketAsset.query.all()
        for asset in assets:
            sym = (asset.symbol or "").strip()
            name = (asset.name or "").strip()
            if sym in allowed:
                continue

            looks_real = (
                sym in banned_exact or
                sym.endswith("-USD") or
                sym.endswith("=F") or
                name.lower() in {"bitcoin", "ethereum", "ripple", "apple", "tesla", "nvidia", "microsoft"}
            )
            if not looks_real:
                continue

            if sym.endswith("-USD"):
                asset.asset_type = "crypto"
            elif sym.endswith("=F"):
                asset.asset_type = "commodity"
            else:
                asset.asset_type = asset.asset_type or "stock"

            asset.symbol = f"FX{asset.id}"
            asset.name = f"Fictional Asset {asset.id}"

    @staticmethod
    def initialize_assets():
        """Ensures fictional assets exist in the database"""
        existing = {a.symbol: a for a in MarketAsset.query.all()}
        cfg = MarketSimulationService.get_asset_config()
        
        for symbol, config in cfg.items():
            if symbol not in existing:
                asset = MarketAsset(
                    symbol=symbol,
                    name=config['name'],
                    asset_type=config['type'],
                    current_price=config['base_price'],
                    last_updated=datetime.now(timezone.utc)
                )
                db.session.add(asset)
            else:
                asset = existing[symbol]
                asset.name = config.get('name') or asset.name
                asset.asset_type = config.get('type') or asset.asset_type
                if not asset.current_price or asset.current_price <= 0:
                    asset.current_price = float(config.get('base_price') or 1.0)
                asset.last_updated = datetime.now(timezone.utc)
        
        MarketSimulationService._sanitize_nonfiction_assets()
        db.session.commit()

    @staticmethod
    def update_prices():
        """Updates prices using Random Walk with Volatility"""
        assets = MarketAsset.query.all()
        now = datetime.now(timezone.utc)
        cfg = MarketSimulationService.get_asset_config()
        
        # Get global volatility multiplier from config
        try:
            vol_multiplier = float(SystemConfig.get_value('market_volatility_multiplier', '1.0'))
        except:
            vol_multiplier = 1.0
        
        for asset in assets:
            config = cfg.get(asset.symbol)
            if not config:
                continue
            if not config.get('enabled', True):
                continue
            
            # Default volatility if not in config (for old assets if kept)
            base_volatility = config['volatility'] if config else 0.02
            
            # Apply multiplier
            volatility = base_volatility * vol_multiplier
            
            # Random change: -volatility to +volatility
            # Using normal distribution for more natural movement
            change_percent = random.gauss(0, volatility / 2)
            
            # Cap extreme moves
            change_percent = max(min(change_percent, volatility), -volatility)
            
            current_price = asset.current_price
            if current_price <= 0:
                current_price = 1.0 # Reset dead assets
            
            new_price = current_price * (1 + change_percent)
            
            # Ensure minimum price
            if new_price < 0.01:
                new_price = 0.01
                
            # Update Asset
            asset.current_price = new_price
            
            # Calculate 24h change (simplified for simulation)
            # In a real sim, we'd store history. Here we just pretend the change is the daily change
            # or accumulate it. For simplicity, let's just update the price.
            # Ideally, we should track open/close. 
            # Let's approximate price_change_24h as a running average or just the latest move scaled (not accurate but functional)
            # Better: if we have history, use it. If not, just random fluctuation.
            
            # Let's keep existing price_change_24h logic if possible, or simulate it
            # Simulating 24h change: decay old change towards 0 and add new change
            current_change = asset.price_change_24h or 0
            # Decay factor 0.95, add new change * 10
            asset.price_change_24h = (current_change * 0.98) + (change_percent * 100)
            
            # Simulated Volume
            asset.volume_24h = random.randint(10000, 1000000) * new_price
            
            asset.last_updated = now
            
        db.session.commit()
        return True

    @staticmethod
    def get_history_data(symbol, days=180):
        """Generates fake historical data for charting"""
        asset = MarketAsset.query.filter_by(symbol=symbol).first()
        if not asset:
            return pd.DataFrame()
            
        current_price = asset.current_price
        config = MarketSimulationService.get_asset_config().get(symbol)
        volatility = config['volatility'] if config else 0.02
        
        records = []
        price = current_price
        end_date = datetime.now()
        
        for i in range(days):
            date = end_date - timedelta(days=i)
            
            # Generate backwards
            change = random.gauss(0, volatility)
            prev_price = price / (1 + change)
            
            # Intraday moves
            high = max(price, prev_price) * (1 + abs(random.gauss(0, volatility/2)))
            low = min(price, prev_price) * (1 - abs(random.gauss(0, volatility/2)))
            
            records.append({
                'Date': date,
                'Open': prev_price,
                'High': high,
                'Low': low,
                'Close': price,
                'Volume': random.randint(10000, 500000)
            })
            
            price = prev_price
            
        records.reverse()
        return pd.DataFrame(records).set_index('Date')
