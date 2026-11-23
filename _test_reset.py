import os
os.environ['USE_TEST_DB']='1'
os.environ['TEST_DATABASE_URL']='sqlite:///C:/Users/azad1/AppData/Local/Temp/opencode/gop_reset.db'
os.environ['SECRET_KEY']='gop-reset-local-key'
os.environ['ENABLE_DEBUG_LOGIN']='1'
from run import app
from routes.utils import generate_password_reset_token, verify_password_reset_token
from models import User
from extensions import db
with app.app_context():
    db.create_all()
    # create user with email
    u = User(username='resetuser', email='reset@test.com')
    u.set_password('OldPass123!')
    db.session.add(u)
    db.session.commit()
    print('user created, hash:', u.password_hash[:30])
    # generate token
    token = generate_password_reset_token(u.email, u.password_hash)
    print('token:', token[:40], '...')
    # verify (should work)
    email = verify_password_reset_token(token)
    print('verify before reset:', email)
    # reset password
    u.set_password('NewPass123!')
    db.session.commit()
    print('password reset done')
    # verify same token (should be None now - single use)
    email2 = verify_password_reset_token(token)
    print('verify after reset (should be None):', email2)
    # invalid token
    print('verify invalid:', verify_password_reset_token('garbage'))
    # expired simulation: can't easily, skip
    # test login with new password
    from werkzeug.security import check_password_hash
    u2 = User.query.filter_by(username='resetuser').first()
    print('check new password:', u2.check_password('NewPass123!'))
    print('check old password:', u2.check_password('OldPass123!'))
