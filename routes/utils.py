from flask import current_app, flash, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os
import random
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
        current_app.logger.error(f"Error sending email: {e}")
        # In development, we might not have a real SMTP server
        if current_app.debug:
            current_app.logger.debug(f"--- DEBUG EMAIL ---\nTo: {to}\nSubject: {subject}\n{template}\n-------------------")

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
        current_app.logger.error(f"Error sending notification: {e}")
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
        current_app.logger.error(f"Image validation failed: {e}")
        return None
            
    return None

def update_daily_task_progress(user, target_type):
    """
    Updates progress for daily tasks based on target_type.
    """
    try:
        # Ensure tasks exist for today
        sync_daily_tasks(user)
        
        today = datetime.now(timezone.utc).date()
        
        # Map specific types to generic categories
        target_types = [target_type]
        if target_type == 'organized_crime':
            target_types.append('crime')
            
        # Debug Log
        if current_app.debug:
            current_app.logger.debug(f"Updating daily task for user {user.id}, type: {target_type} -> {target_types}")

        # Find incomplete tasks for today matching the types
        # Note: We join DailyTask to filter by target_type
        tasks = UserDailyTask.query.join(DailyTask).filter(
            UserDailyTask.user_id == user.id,
            UserDailyTask.date == today,
            UserDailyTask.is_completed == False,
            DailyTask.target_type.in_(target_types)
        ).with_for_update().all() # Lock rows to prevent race conditions
        
        updated_count = 0
        for user_task in tasks:
            user_task.progress += 1
            updated_count += 1
            
            # Auto-complete logic if needed, but usually user collects reward manually
            if user_task.progress >= user_task.task.target_count:
                user_task.progress = user_task.task.target_count
                # Optional: Mark as completed immediately if no manual collection is required
                # But here we wait for collection.
                
        db.session.commit()
        
        if current_app.debug and updated_count > 0:
            current_app.logger.debug(f"Updated {updated_count} tasks for user {user.id}")
            
        return True
    except Exception as e:
        current_app.logger.error(f"Error updating daily task: {e}")
        db.session.rollback()
        return False

def sync_daily_tasks(user):
    """
    Synchronizes daily tasks for the user.
    Ensures the user has tasks assigned for the current day.
    """
    try:
        today = datetime.now(timezone.utc).date()
        
        # Check if user already has tasks for today
        user_tasks = UserDailyTask.query.filter_by(user_id=user.id, date=today).all()
        if user_tasks:
            return user_tasks

        current_app.logger.info(f"Synchronizing daily tasks for user {user.id}")

        # Fetch available tasks
        all_tasks = DailyTask.query.filter(
            DailyTask.is_active == True,
            DailyTask.min_level <= user.level
        ).all()

        # If no tasks exist in DB, try to initialize them (fallback)
        if not all_tasks:
            current_app.logger.warning("No daily tasks found in DB. Attempting initialization.")
            try:
                from utils.essentials import initialize_daily_tasks
                initialize_daily_tasks()
                db.session.commit()
                # Re-fetch
                all_tasks = DailyTask.query.filter(
                    DailyTask.is_active == True,
                    DailyTask.min_level <= user.level
                ).all()
            except Exception as e:
                current_app.logger.error(f"Failed to initialize daily tasks: {e}")
                db.session.rollback()
        
        if not all_tasks:
            current_app.logger.error("Still no daily tasks available after initialization attempt.")
            return []

        # Selection Logic
        preferred_specs = [
            ("buy", 3),
            ("crime", 3),
            ("crime", 6),
        ]
        selected_tasks = []
        selected_ids = set()

        # 1. Try to match preferred specs
        for target_type, target_count in preferred_specs:
            task = next(
                (t for t in all_tasks if t.target_type == target_type and int(t.target_count or 0) == int(target_count)),
                None
            )
            if task and task.id not in selected_ids:
                selected_tasks.append(task)
                selected_ids.add(task.id)

        # 2. Fill remaining slots with random tasks
        remaining = [t for t in all_tasks if t.id not in selected_ids]
        if len(selected_tasks) < 3 and remaining:
            needed = min(3 - len(selected_tasks), len(remaining))
            selected_tasks.extend(random.sample(remaining, needed))

        # Create UserDailyTask entries
        new_tasks = []
        for task in selected_tasks:
            user_task = UserDailyTask(
                user_id=user.id,
                task_id=task.id,
                date=today
            )
            db.session.add(user_task)
            new_tasks.append(user_task)
        
        db.session.commit()
        current_app.logger.info(f"Assigned {len(new_tasks)} daily tasks to user {user.id}")
        
        return new_tasks

    except Exception as e:
        current_app.logger.error(f"Error in sync_daily_tasks: {e}")
        db.session.rollback()
        return []
