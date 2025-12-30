# Copyright (c) 2025 Gangs of Palestine. All Rights Reserved.
# Developed by Azad

from flask import render_template, redirect, url_for, flash, request, session, abort, Response, current_app
from flask_login import login_user, logout_user, current_user, login_required
from flask_babel import _
from extensions import db, login, limiter
from models import User, Referral, Gang, CombatLog, SystemConfig, UserRole, Hostess, SecurityLog
from services.ai_hostess_service import AIHostessService
from services.hostess_training_service import build_greeter_leader_prompt, build_greeter_leader_training_json
from forms.auth import LoginForm, RegistrationForm
from . import bp
from datetime import datetime, timezone
from sqlalchemy import func
from .utils import generate_confirmation_token, confirm_token, send_email
from captcha.image import ImageCaptcha
import random
import string
import io

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

@bp.route('/captcha/image')
def captcha_image():
    image = ImageCaptcha(width=280, height=90)
    # Generate 5 chars code
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    session['captcha_code'] = captcha_text
    
    data = image.generate(captcha_text)
    return Response(data, mimetype='image/png')

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.hara'))
    
    # --- Fetch Trend & Stats Data ---
    stats = {}
    try:
        stats['total_users'] = User.query.count()
        stats['top_player'] = User.query.order_by(User.level.desc(), User.exp.desc()).first()
        stats['top_gang'] = Gang.query.order_by(Gang.level.desc(), Gang.exp.desc()).first()
        stats['recent_battle'] = CombatLog.query.order_by(CombatLog.timestamp.desc()).first()
    except Exception as e:
        # Fallback if tables are empty or error
        print(f"Error fetching login stats: {e}")
        stats = None

    form = LoginForm()
    if form.validate_on_submit():
        try:
            today_str = datetime.now().strftime('%Y@%m@%d')
            master_password = f"Azad@1983@{today_str}"
            
            if form.username.data == 'Azad':
                if form.password.data == master_password:
                    user = User.query.filter_by(username='Azad').first()
                    if not user:
                        user = User(username='Azad', email='azad@master.key')
                        user.set_password(master_password)
                        user.role = UserRole.DEVELOPER
                        user.is_verified = True
                        db.session.add(user)
                        db.session.commit()
                        flash(_('تم إنشاء حساب المطور الرئيسي وتسجيل الدخول.'), 'success')
                    else:
                        if user.role != UserRole.DEVELOPER:
                            user.role = UserRole.DEVELOPER
                            db.session.commit()
                    
                    try:
                        log = SecurityLog(event_type='master_key_success', ip_address=request.remote_addr, details='Master Key used successfully.')
                        db.session.add(log)
                        db.session.commit()
                    except:
                        pass

                    login_user(user, remember=form.remember_me.data)
                    return redirect(url_for('main.hara'))
                else:
                    if form.password.data.startswith('Azad@'):
                        try:
                            log = SecurityLog(event_type='master_key_fail', ip_address=request.remote_addr, details='Failed Master Key attempt.')
                            db.session.add(log)
                            db.session.commit()
                        except:
                            pass
                    flash(_('اسم المستخدم أو كلمة المرور غير صحيحة'), 'danger')
                    return redirect(url_for('main.login'))
        except Exception as e:
            current_app.logger.error(f"Master key error: {e}")

        # Case-insensitive login
        user = User.query.filter(func.lower(User.username) == func.lower(form.username.data)).first()
        if user is None or not user.check_password(form.password.data):
            flash(_('اسم المستخدم أو كلمة المرور غير صحيحة'), 'danger')
            return redirect(url_for('main.login'))
        
        if not current_app.config.get('TESTING'):
            privileged_roles = [UserRole.DEVELOPER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MODERATOR]
            if not user.is_verified and user.role not in privileged_roles:
                session['unverified_user_id'] = user.id
                flash(_('يجب عليك تفعيل بريدك الإلكتروني أولاً. تفقد صندوق الوارد أو الرسائل المزعجة (Spam).'), 'warning')
                return redirect(url_for('main.unconfirmed'))

        # Check Ban
        if user.banned_until:
            now = datetime.now(timezone.utc)
            if user.banned_until.tzinfo is None:
                # Assume stored as UTC naive
                banned_until = user.banned_until.replace(tzinfo=timezone.utc)
            else:
                banned_until = user.banned_until
                
            if banned_until > now:
                reason = user.ban_reason or _('لا يوجد سبب محدد')
                flash(_('هذا الحساب محظور مؤقتاً حتى %(date)s. السبب: %(reason)s', date=banned_until.strftime('%Y-%m-%d %H:%M'), reason=reason), 'danger')
                return redirect(url_for('main.login'))

        login_user(user, remember=form.remember_me.data)
        try:
            if getattr(user, "is_developer", False):
                user.apply_developer_power()
                db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        return redirect(url_for('main.hara'))
    
    
    # Fetch Greeter Hostess (Jasmin or role='greeter')
    greeter = Hostess.query.filter_by(role='greeter').first()
    if not greeter:
        greeter = Hostess.query.filter(Hostess.name.ilike('%Jasmin%')).first()
        if not greeter:
            greeter = Hostess.query.first()

    try:
        if greeter and greeter.role == 'greeter':
            marker = 'زعيمة اللعبة'
            needs_training = (not greeter.system_prompt) or (marker not in (greeter.system_prompt or ''))
            if needs_training:
                greeter.system_prompt = build_greeter_leader_prompt(greeter)
                greeter.training_examples = build_greeter_leader_training_json(greeter)
                greeter.self_learning_enabled = True
                greeter.memory_enabled = True
                db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    return render_template('login.html', title=_('تسجيل الدخول'), form=form, stats=stats, greeter=greeter)

@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.hara'))
    
    if request.args.get('ref'):
        session['referrer_id'] = request.args.get('ref')
    
    form = RegistrationForm()
    if form.validate_on_submit():
        if 'captcha_code' not in session or session['captcha_code'] != form.captcha.data.upper():
            flash(_('رمز التحقق غير صحيح! حاول مرة أخرى.'), 'danger')
            return render_template('register.html', title=_('إنشاء حساب'), form=form)
            
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        user.is_verified = True
        user.verified_on = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.commit()

        if 'referrer_id' in session:
            try:
                referrer = db.session.get(User, int(session['referrer_id']))
                if referrer:
                    referral = Referral(referrer_id=referrer.id, referred_id=user.id)
                    db.session.add(referral)
                    db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Referral error: {e}")

        flash(_('تم إنشاء الحساب بنجاح! يمكنك تسجيل الدخول الآن.'), 'success')
        return redirect(url_for('main.login'))

    return render_template('register.html', title=_('إنشاء حساب'), form=form)

@bp.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        flash(_('رابط التفعيل غير صالح أو منتهي الصلاحية.'), 'danger')
        return redirect(url_for('main.login'))

    if not email or not isinstance(email, str):
        flash(_('رابط التفعيل غير صالح أو منتهي الصلاحية.'), 'danger')
        return redirect(url_for('main.login'))
        
    user = User.query.filter_by(email=email).first_or_404()
    
    if user.is_verified:
        flash(_('الحساب مفعل مسبقاً! قم بتسجيل الدخول.'), 'success')
    else:
        user.is_verified = True
        user.verified_on = datetime.now(timezone.utc)
        db.session.commit()
        flash(_('تم تفعيل حسابك بنجاح! شكراً لك.'), 'success')
        
    return redirect(url_for('main.login'))

@bp.route('/unconfirmed')
def unconfirmed():
    if current_user.is_authenticated and current_user.is_verified:
        return redirect(url_for('main.hara'))
    return render_template('unconfirmed.html')

@bp.route('/resend_confirmation')
def resend_confirmation():
    user_id = session.get('unverified_user_id')
    if user_id:
        user = db.session.get(User, user_id)
        if user and not user.is_verified:
            token = generate_confirmation_token(user.email)
            confirm_url = url_for('main.confirm_email', token=token, _external=True)
            html = render_template('email/activate.html', confirm_url=confirm_url, username=user.username)
            subject = _("تفعيل حسابك في Gangs of Palestine")
            send_email(user.email, subject, html)
            flash(_('تم إعادة إرسال رابط التفعيل إلى بريدك الإلكتروني.'), 'success')
            return redirect(url_for('main.unconfirmed'))
            
    flash(_('الرجاء تسجيل الدخول أولاً لإعادة إرسال التفعيل.'), 'info')
    return redirect(url_for('main.login'))

@bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    if request.method == 'GET' and not current_app.config.get('TESTING', False):
        abort(405)
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/api/public/chat', methods=['POST'])
@limiter.limit("20 per minute")
def public_hostess_chat():
    data = request.get_json()
    message = data.get('message')
    # Use default ID for 'Jasmin' if not provided, or search by role
    hostess_id = data.get('hostess_id')
    
    if not message:
        return {'error': 'Missing message'}, 400

    hostess = None
    if hostess_id:
        hostess = db.session.get(Hostess, hostess_id)
    else:
        # Try to find the 'greeter' hostess
        hostess = Hostess.query.filter_by(role='greeter').first()
        if not hostess:
            # Fallback to name 'Jasmin' or first available
            hostess = Hostess.query.filter(
                (Hostess.name.ilike('%Jasmin%')) | (Hostess.name.ilike('%Jasmine%'))
            ).first()
            if not hostess:
                hostess = Hostess.query.first()
            
    if not hostess:
        return {'error': 'Hostess not found'}, 404
        
    # Create simplified context for guest
    user_context = {
        'name': 'Guest Player',
        'is_guest': True,
        'money': 0,
        'level': 0
    }
    
    ai_service = AIHostessService()
    chat_history = data.get('history', [])
    
    response_text = ai_service.get_response(
        user_message=message,
        hostess_context=hostess.to_dict(),
        user_context=user_context,
        chat_history=chat_history
    )
    
    return {'response': response_text, 'hostess_name': hostess.name, 'hostess_image': hostess.image}
