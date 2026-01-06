
from flask import Flask
from flask_babel import Babel
try:
    from flask_babel import _
    print("Imported _ from flask_babel successfully")
except ImportError:
    print("Could not import _ from flask_babel directly")
    from flask_babel import gettext as _

app = Flask(__name__)
babel = Babel(app)

with app.app_context():
    s = _('إدارة الجرائم المنظمة')
    print(f"String: {s}")
    print(f"Type: {type(s)}")
    
    # Try to reproduce error
    try:
        # Simulate % formatting with a bad string
        bad = "01234567%/"
        print(bad % ())
    except ValueError as e:
        print(f"Caught expected error: {e}")

    try:
        # Check if s has %
        if '%' in str(s):
            print("String has %")
        else:
            print("String has no %")
    except Exception as e:
        print(f"Error checking string: {e}")
