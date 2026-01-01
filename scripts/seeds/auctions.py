import os
import sys
from datetime import datetime, timedelta, timezone

# Add parent directory to path (scripts/seeds -> scripts -> root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from factory import create_app
from extensions import db
from models.market import Auction
from models.item import Item
from models.vehicle import Vehicle

def seed_auctions():
    app = create_app()
    with app.app_context():
        print("Seeding auctions...")
        
        # Ensure we have an item
        item = Item.query.filter_by(name="سلاح كلاشينكوف ذهبي").first()
        if not item:
            item = Item(
                name="سلاح كلاشينكوف ذهبي", 
                type="weapon", 
                cost=50000, 
                is_black_market=True, 
                description="نسخة نادرة جداً مطلية بالذهب.", 
                bonus_strength=50, 
                ammo_needed=10,
                image="images/items/golden_ak47.svg"
            )
            db.session.add(item)
            db.session.commit()
            print(f"Created dummy item: {item.name}")
        else:
            item.image = "images/items/golden_ak47.svg"
            db.session.commit()
            print(f"Updated existing item image: {item.name}")
            
        # Ensure we have a vehicle
        vehicle = Vehicle.query.filter_by(name="جيب مرسيدس G-Class").first()
        if not vehicle:
            vehicle = Vehicle(
                name="جيب مرسيدس G-Class", 
                type="mushtuba", 
                price=150000, 
                description="وحش الطرق الوعرة.", 
                speed=80, 
                defense=90, 
                risk=20,
                image="images/vehicles/mercedes_g_class.svg"
            )
            db.session.add(vehicle)
            db.session.commit()
            print(f"Created dummy vehicle: {vehicle.name}")
        else:
            vehicle.image = "images/vehicles/mercedes_g_class.svg"
            db.session.commit()
            print(f"Updated existing vehicle image: {vehicle.name}")

        # Check for existing active auctions to avoid duplicates
        existing_item_auction = Auction.query.filter_by(item_type='item', item_id=str(item.id), status='active').first()
        if not existing_item_auction:
            # Create Active Auction for Item
            auc1 = Auction(
                item_type='item',
                item_id=str(item.id),
                start_price=10000,
                current_price=10000,
                min_bid_increment=1000,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(hours=2),
                status='active'
            )
            db.session.add(auc1)
            print("Created auction for item.")
        
        existing_veh_auction = Auction.query.filter_by(item_type='vehicle', item_id=str(vehicle.id), status='active').first()
        if not existing_veh_auction:
            # Create Active Auction for Vehicle
            auc2 = Auction(
                item_type='vehicle',
                item_id=str(vehicle.id),
                start_price=50000,
                current_price=50000,
                min_bid_increment=5000,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(hours=4),
                status='active'
            )
            db.session.add(auc2)
            print("Created auction for vehicle.")
        
        try:
            db.session.commit()
            print("Auctions seeded successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error seeding auctions: {e}")

if __name__ == '__main__':
    seed_auctions()
