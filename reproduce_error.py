from factory import create_app, db
from models import User, Item, UserItem
from flask_login import login_user

app = create_app()

with app.app_context():
    # Find a user
    user = User.query.first()
    if not user:
        print("No user found. Creating one.")
        user = User(username='test_user', email='test@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
    
    print(f"Using user: {user.username} (ID: {user.id})")
    
    # Ensure user has Item 20
    item = db.session.get(Item, 20)
    if not item:
        print("Item 20 not found. Creating it.")
        item = Item(id=20, name="Stolen Phone", type="loot", is_black_market=True)
        db.session.add(item)
        db.session.commit()
        
    u_item = UserItem.query.filter_by(user_id=user.id, item_id=20).first()
    if not u_item:
        print("Giving item 20 to user.")
        u_item = UserItem(user_id=user.id, item_id=20, quantity=1)
        db.session.add(u_item)
        db.session.commit()
        
    # Create test client
    with app.test_client() as client:
        # Login
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
            
        # Visit black_market
        try:
            print("Visiting /black_market/ ...")
            resp = client.get('/black_market/')
            print(f"Response status: {resp.status_code}")
            if resp.status_code == 500:
                print("Got 500 error!")
            else:
                print("Success?")
        except Exception as e:
            print(f"Caught exception: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            print("Visiting /empire ...")
            resp2 = client.get('/empire')
            print(f"Empire status: {resp2.status_code}")
        except Exception as e:
            print(f"Caught exception when visiting /empire: {e}")
            import traceback
            traceback.print_exc()
