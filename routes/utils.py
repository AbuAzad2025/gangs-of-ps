from flask import current_app, flash, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os
from extensions import db, mail
from models import DailyTask, UserDailyTask, Notification
from PIL import Image
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message

def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-confirm-salt')

def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt='email-confirm-salt',
            max_age=expiration
        )
    except:
        return False
    return email

def send_email(to, subject, template):
    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Error sending email: {e}")
        # In development, we might not have a real SMTP server
        if current_app.debug:
            print(f"--- DEBUG EMAIL ---\nTo: {to}\nSubject: {subject}\n{template}\n-------------------")

def send_notification(user_id, title, message, type='info', link=None):
    """
    Send a notification to a user.
    """
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link
        )
        db.session.add(notif)
        db.session.commit()
    except Exception as e:
        print(f"Error sending notification: {e}")
        db.session.rollback()

def save_image(form_image, folder):
    if not form_image:
        return None
        
    # Handle case where form_image is a string (e.g. existing filename from obj)
    if isinstance(form_image, str):
        return None
        
    if not hasattr(form_image, 'filename'):
        return None
        
    filename = secure_filename(form_image.filename)
    if not filename:
        return None
        
    # Check Allowed Extensions
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif'}
        ext = os.path.splitext(filename)[1].lower()
        if ext not in allowed_extensions:
            return None
            
        # Add timestamp to filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_filename = f"{timestamp}_{os.urandom(8).hex()}{ext}" # Add random string for extra safety
        
        # Ensure directory exists
        upload_path = os.path.join(current_app.root_path, 'static', 'uploads', folder)
        os.makedirs(upload_path, exist_ok=True)
        
        filepath = os.path.join(upload_path, new_filename)
        
        try:
            # Validate and Strip using Pillow
            img = Image.open(form_image)
            img.verify() # Verify it's an image
            
            # Re-open to save (verify closes the file)
            form_image.seek(0)
            img = Image.open(form_image)
            
            # Remove metadata (EXIF) by creating a new image
            data = list(img.getdata())
            image_without_exif = Image.new(img.mode, img.size)
            image_without_exif.putdata(data)
            
            image_without_exif.save(filepath)
            
            return f"uploads/{folder}/{new_filename}"
        except Exception as e:
            print(f"Image validation failed: {e}")
            return None
            
    return None

def update_daily_task_progress(user, target_type):
    today = datetime.now(timezone.utc).date()
    # Find incomplete tasks for today matching the type
    tasks = UserDailyTask.query.join(DailyTask).filter(
        UserDailyTask.user_id == user.id,
        UserDailyTask.date == today,
        UserDailyTask.is_completed == False,
        DailyTask.target_type == target_type
    ).all()
    
    for user_task in tasks:
        user_task.progress += 1
        if user_task.progress >= user_task.task.target_count:
            # Cap progress at goal; reward is granted via collect_task_reward
            user_task.progress = user_task.task.target_count
            
    db.session.commit()
