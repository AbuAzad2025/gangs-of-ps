import random
import math
import pandas as pd
from datetime import datetime, timezone, timedelta
from models.market import MarketAsset
from models.system import SystemConfig
from extensions import db

class MarketSimulationService:
    # Configuration for simulated assets

    # volatility: max percentage change per update (e.g., 0.02 = 2%)
    # trend_bias: slight bias per update (-0.001 to 0.001)
    ASSET_CONFIG = {
        'G-COIN': {'name': 'Gangs Coin', 'type': 'crypto', 'volatility': 0.05, 'base_price': 1000},
        'B-IRON': {'name': 'BlackIron Arms', 'type': 'stock', 'volatility': 0.02, 'base_price': 150},
        'PHRMA': {'name': 'Underground Pharma', 'type': 'stock', 'volatility': 0.015, 'base_price': 80},
        'HACK': {'name': 'CyberSec Solutions', 'type': 'stock', 'volatility': 0.03, 'base_price': 220},
        'GOLD-X': {'name': 'Conflict Gold', 'type': 'commodity', 'volatility': 0.008, 'base_price': 1900},
        'OIL-B': {'name': 'Smuggled Oil', 'type': 'commodity', 'volatility': 0.012, 'base_price': 75},
        'CASINO': {'name': 'Royal Casino Corp', 'type': 'stock', 'volatility': 0.025, 'base_price': 45},
    }

    @staticmethod
    def initialize_assets():
        """Ensures fictional assets exist in the database"""
        existing = {a.symbol: a for a in MarketAsset.query.all()}
        
        for symbol, config in MarketSimulationService.ASSET_CONFIG.items():
            if symbol not in existing:
                asset = MarketAsset(
                    symbol=symbol,
                    name=config['name'],
                    asset_type=config['type'],
                    current_price=config['base_price'],
                    last_updated=datetime.now(timezone.utc)
                )
                db.session.add(asset)
        
        # Optionally deactivate real world assets or leave them?
        # For now, let's just add the new ones. User can delete old ones manually or we can clean up.
        db.session.commit()

    @staticmethod
    def update_prices():
        """Updates prices using Random Walk with Volatility"""
        assets = MarketAsset.query.all()
        now = datetime.now(timezone.utc)
        
        # Get global volatility multiplier from config
        try:
            vol_multiplier = float(SystemConfig.get_value('market_volatility_multiplier', '1.0'))
        except:
            vol_multiplier = 1.0
        
        for asset in assets:
            config = MarketSimulationService.ASSET_CONFIG.get(asset.symbol)
            
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
        config = MarketSimulationService.ASSET_CONFIG.get(symbol)
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
