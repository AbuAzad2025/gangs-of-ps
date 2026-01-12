# Copyright (c) 2025 Gangs of Palestine. All Rights Reserved.
# Developed by Azad

from flask import Flask, request, has_request_context, flash, redirect, url_for, g
from flask_login import current_user
from flask_babel import gettext as _
import os
from config import Config
from extensions import db, migrate, login, admin, babel, csrf, limiter, talisman, mail, seo_manager, socketio, cache

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    def ensure_postgres_database_exists(database_uri: str) -> None:
        from sqlalchemy.engine.url import make_url
        import re

        url = make_url(database_uri)
        if url.drivername not in {"postgresql", "postgresql+psycopg2"}:
            return

        db_name = url.database
        if not db_name:
            raise ValueError("PostgreSQL database name is required.")

        if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
            raise ValueError("Invalid PostgreSQL database name.")

        maintenance_url = url.set(database="postgres")

        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        conn = psycopg2.connect(maintenance_url.render_as_string(hide_password=False))
        try:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            try:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                exists = cur.fetchone() is not None
                if not exists:
                    cur.execute(f'CREATE DATABASE "{db_name}"')
            finally:
                cur.close()
        finally:
            conn.close()

    ensure_postgres_database_exists(app.config["SQLALCHEMY_DATABASE_URI"])

    if app.config.get("TESTING"):
        from sqlalchemy.engine.url import make_url
        from uuid import uuid4

        test_db_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
        if test_db_url.drivername in {"postgresql", "postgresql+psycopg2"}:
            test_schema = f"test_schema_{uuid4().hex}"

            import psycopg2
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            from sqlalchemy.pool import NullPool

            conn = psycopg2.connect(test_db_url.render_as_string(hide_password=False))
            try:
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                cur = conn.cursor()
                try:
                    cur.execute(f'CREATE SCHEMA "{test_schema}"')
                finally:
                    cur.close()
            finally:
                conn.close()

            engine_options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
            connect_args = dict(engine_options.get("connect_args") or {})
            connect_args["options"] = f"-c search_path={test_schema}"
            engine_options["connect_args"] = connect_args
            engine_options["poolclass"] = NullPool
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options
            app.config["TEST_SCHEMA"] = test_schema

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    try:
        admin.init_app(app)
    except Exception as e:
        # Ignore blueprint registration errors during testing
        app.logger.warning(f"Admin init warning: {e}")

    csrf.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    seo_manager.init_app(app)
    cache.init_app(app)
    if socketio:
        socketio.init_app(app, cors_allowed_origins="*")
    
    # Content Security Policy (CSP)
    csp = {
        'default-src': '\'self\'',
        'script-src': [
            '\'self\'',
            '\'unsafe-inline\'', # Required for AdminLTE and some inline JS
            '\'unsafe-eval\'',   # Often required for some complex JS frameworks
            'cdnjs.cloudflare.com',
            'cdn.jsdelivr.net',
            'code.jquery.com',
            'fonts.googleapis.com',
            'www.googletagmanager.com',
            'unpkg.com'
        ],
        'style-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            'fonts.googleapis.com',
            'cdnjs.cloudflare.com',
            'cdn.jsdelivr.net'
        ],
        'img-src': [
            '\'self\'',
            'data:',
            'ui-avatars.com',
            'flagcdn.com',
            'cdnjs.cloudflare.com',
            '*.youtube.com',
            '*.ytimg.com'
        ],
        'media-src': [
            '\'self\'',
            '*.youtube.com'
        ],
        'frame-src': [
            '\'self\'',
            '*.youtube.com',
            '*.youtube-nocookie.com'
        ],
        'font-src': [
            '\'self\'',
            'fonts.gstatic.com',
            'cdnjs.cloudflare.com'
        ],
        'connect-src': [
            '\'self\'',
            'cdn.jsdelivr.net',
            'cdnjs.cloudflare.com',
            'ws://localhost:8000',
            'ws://127.0.0.1:8000',
            'ws://0.0.0.0:8000',
            'ws://localhost:8080',
            'wss:'
        ]
    }
    
    # Initialize Talisman with CSP and other security headers
    is_production = os.environ.get('FLASK_ENV') == 'production'
    force_https = os.environ.get('FORCE_HTTPS', str(is_production)).lower() == 'true'
    
    talisman.init_app(
        app, 
        content_security_policy=csp,
        force_https=force_https,
        strict_transport_security=True,
        session_cookie_secure=app.config['SESSION_COOKIE_SECURE'],
        session_cookie_http_only=True
    )
    
    # Initialize Babel
    def get_locale():
        if not has_request_context():
            return 'ar'
        from flask import session
        lang = request.args.get('lang')
        if lang in app.config.get('LANGUAGES', ['ar', 'en']):
            session['locale'] = lang
            return lang
        # Check if user has a preference in session
        if 'locale' in session:
            return session['locale']
        # Default to Arabic to ensure the site appears in Arabic
        return 'ar'
        # return request.accept_languages.best_match(app.config['LANGUAGES'])

    babel.init_app(app, locale_selector=get_locale)
    
    app.jinja_env.globals['get_locale'] = get_locale

    @app.template_filter('number_format')
    def number_format_filter(value):
        try:
            return "{:,}".format(value)
        except (ValueError, TypeError):
            return value

    def _elite_sync_interval_seconds(now):
        cached_at = getattr(app, "_elite_sync_interval_cached_at", None)
        if cached_at is None or (now - cached_at).total_seconds() >= 300:
            interval = 60
            try:
                from models.system import SystemConfig
                interval = int(SystemConfig.get_value("elite_sync_interval_seconds", "60") or 60)
            except Exception:
                interval = 60
            interval = max(5, interval)
            app._elite_sync_interval_seconds = interval
            app._elite_sync_interval_cached_at = now
        return int(getattr(app, "_elite_sync_interval_seconds", 60))

    def _maybe_sync_elite_titles(now):
        last_run = getattr(app, "_elite_sync_last_run", None)
        interval = _elite_sync_interval_seconds(now)
        if last_run is not None and (now - last_run).total_seconds() < interval:
            return
        from models.user import sync_elite_titles
        sync_elite_titles(now=now)
        app._elite_sync_last_run = now

    def _expire_player_effects(now):
        changed = False
        now_naive = now.replace(tzinfo=None)

        def aware(dt):
            if not dt:
                return None
            if getattr(dt, "tzinfo", None) is None:
                return dt.replace(tzinfo=now.tzinfo)
            return dt

        if current_user.safe_house_until:
            until = aware(current_user.safe_house_until)
            if until and until <= now:
                current_user.is_safe_house_active = False
                current_user.safe_house_until = None
                changed = True

        if current_user.disguise_until:
            until = aware(current_user.disguise_until)
            if until and until <= now:
                current_user.is_disguised = False
                current_user.disguise_until = None
                changed = True

        if current_user.casino_luck_until:
            until = aware(current_user.casino_luck_until)
            if until and until <= now:
                current_user.casino_luck_until = None
                current_user.active_hostess_id = None
                changed = True

        if current_user.jail_until:
            until = aware(current_user.jail_until)
            if until and until <= now:
                current_user.jail_until = None
                changed = True

        if current_user.hospital_until:
            until = aware(current_user.hospital_until)
            if until and until <= now:
                current_user.hospital_until = None
                changed = True

        if current_user.gym_until:
            until = aware(current_user.gym_until)
            if until and until <= now:
                current_user.gym_until = None
                changed = True

        if current_user.crime_cooldown_until:
            until = current_user.crime_cooldown_until
            if getattr(until, "tzinfo", None) is not None:
                until = until.replace(tzinfo=None)
            if until and until <= now_naive:
                current_user.crime_cooldown_until = None
                changed = True

        if current_user.organized_crime_cooldown_until:
            until = current_user.organized_crime_cooldown_until
            if getattr(until, "tzinfo", None) is not None:
                until = until.replace(tzinfo=None)
            if until and until <= now_naive:
                current_user.organized_crime_cooldown_until = None
                changed = True

        if changed:
            try:
                db.session.commit()
            except Exception as e:
                app.logger.error(f"DEBUG: Commit failed in _expire_player_effects: {e}")
                try:
                    db.session.rollback()
                except Exception as rollback_err:
                    app.logger.error(f"DEBUG: Rollback failed in _expire_player_effects: {rollback_err}")

    # Global Status Check (Jail/Hospital)
    @app.before_request
    def check_player_status():
        # Avoid rolling back in tests to prevent DetachedInstanceError with in-memory SQLite
        if app.config.get('TESTING'):
            return

        try:
            db.session.rollback()
        except Exception:
            pass

        if current_user.is_authenticated:
            # Allow developers to access everything
            from models.user import UserRole
            try:
                if current_user.role == UserRole.DEVELOPER:
                    return
            except Exception:
                # If we can't check role (e.g. DetachedInstanceError in tests), assume not developer
                pass

            if not request.endpoint:
                return
                
            # Allowed endpoints (static, logout, admin panel)
            if any(x in request.endpoint for x in ['static', 'logout', 'admin']):
                return
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            g.now_utc = now

            try:
                _maybe_sync_elite_titles(now)
            except Exception as e:
                app.logger.error(f"DEBUG: _maybe_sync_elite_titles failed: {e}")
                try:
                    db.session.rollback()
                except Exception as rollback_err:
                    app.logger.error(f"DEBUG: rollback failed in _maybe_sync_elite_titles: {rollback_err}")
                pass
            
            if not app.config.get('TESTING'):
                if not current_user.is_verified and request.endpoint != 'main.unconfirmed' and 'static' not in request.endpoint:
                    return redirect(url_for('main.unconfirmed'))

            try:
                _expire_player_effects(now)
            except Exception:
                 try:
                     db.session.rollback()
                 except Exception:
                     pass

            def _block_if_busy():
                now_naive = now.replace(tzinfo=None)
                busy_until = None
                busy_kind = None

                if current_user.gym_until:
                    gym_until = current_user.gym_until
                    if gym_until.tzinfo is None:
                        gym_until = gym_until.replace(tzinfo=timezone.utc)
                    if gym_until > now:
                        busy_until = gym_until
                        busy_kind = "gym"

                if not busy_kind and current_user.crime_cooldown_until and current_user.crime_cooldown_until > now_naive:
                    busy_until = current_user.crime_cooldown_until
                    busy_kind = "crime"

                if not busy_kind and current_user.organized_crime_cooldown_until and current_user.organized_crime_cooldown_until > now_naive:
                    busy_until = current_user.organized_crime_cooldown_until
                    busy_kind = "organized_crime"

                if not busy_kind:
                    return None

                action_endpoints = {"main.do_crime", "main.create_lobby"}
                if request.method != "POST" and request.endpoint not in action_endpoints:
                    return None

                endpoint = request.endpoint or ""
                if endpoint == "main.collect_task_reward":
                    return None
                if busy_kind == "gym" and endpoint.startswith("gym."):
                    return None
                if busy_kind == "gym" and endpoint == "main.do_crime":
                    return None
                if busy_kind == "crime" and endpoint in {"main.crimes", "main.story"}:
                    return None
                if busy_kind == "organized_crime" and endpoint in {"main.organized_crimes"}:
                    return None

                if busy_kind == "gym":
                    remaining_seconds = max(1, int((busy_until - now).total_seconds()))
                    redirect_to = url_for("gym.index")
                else:
                    remaining_seconds = max(1, int((busy_until - now_naive).total_seconds()))
                    redirect_to = url_for("main.crimes") if busy_kind == "crime" else url_for("main.organized_crimes")

                flash(_('عليك الانتظار %(seconds)s ثانية قبل القيام بمهمة أخرى!', seconds=remaining_seconds), 'danger')
                return redirect(redirect_to)

            blocked = _block_if_busy()
            if blocked:
                return blocked
            
            # Hospital Check
            hospital_until = current_user.hospital_until
            if hospital_until:
                if hospital_until.tzinfo is None:
                    hospital_until = hospital_until.replace(tzinfo=timezone.utc)

                if hospital_until > now:
                    # Check if Dead (Health <= 0)
                    if current_user.health <= 0:
                        if 'graveyard.' not in request.endpoint:
                            flash(_('لقد قُتلت! أنت الآن في المقبرة.'), 'danger')
                            return redirect(url_for('graveyard.index'))
                    else:
                        # Hospital (Injured but Alive)
                        if 'hospital.' not in request.endpoint:
                            flash(_('أنت في المستشفى! عليك العلاج أو الانتظار.'), 'danger')
                            return redirect(url_for('hospital.index'))

            jail_until = current_user.jail_until
            if jail_until:
                if jail_until.tzinfo is None:
                    jail_until = jail_until.replace(tzinfo=timezone.utc)
                if jail_until > now:
                    if 'jail.' not in request.endpoint:
                        flash(_('أنت في السجن!'), 'danger')
                        return redirect(url_for('jail.index'))

    @app.teardown_request
    def cleanup_db_session(error=None):
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            db.session.remove()
        except Exception:
            pass
    
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        try:
            db.session.remove()
        except Exception:
            pass

    # Context Processor for Social Links
    @app.context_processor
    def inject_social_links():
        from models.system import SystemConfig
        try:
            return dict(
                discord_link=SystemConfig.get_value("discord_invite_link", app.config.get("DISCORD_INVITE_LINK")),
                facebook_link=SystemConfig.get_value("facebook_link", app.config.get("FACEBOOK_LINK")),
                twitter_link=SystemConfig.get_value("twitter_link", app.config.get("TWITTER_LINK")),
                instagram_link=SystemConfig.get_value("instagram_link", app.config.get("INSTAGRAM_LINK"))
            )
        except Exception:
            return dict(
                discord_link=app.config.get("DISCORD_INVITE_LINK"),
                facebook_link=app.config.get("FACEBOOK_LINK"),
                twitter_link=app.config.get("TWITTER_LINK"),
                instagram_link=app.config.get("INSTAGRAM_LINK")
            )

    # Context Processor for Global Data (Announcements & Ticker)
    @app.context_processor
    def inject_global_data():
        from models.system import Announcement
        from models.combat import CombatLog
        from models.user import User
        from sqlalchemy import desc
        from sqlalchemy.orm import joinedload
        from datetime import datetime, timezone, timedelta
        
        now = getattr(g, "now_utc", None) or datetime.now(timezone.utc)
        cache_seconds = 5
        try:
            from models.system import SystemConfig
            cache_seconds = int(SystemConfig.get_value("global_data_cache_seconds", str(cache_seconds)) or cache_seconds)
        except Exception:
            cache_seconds = 5
        cache_seconds = max(1, min(30, cache_seconds))

        cache = getattr(app, "_global_data_cache", None) or {}
        expires_at = cache.get("expires_at")
        if not expires_at or expires_at <= now:
            try:
                latest_announcement_row = (
                    Announcement.query.filter_by(is_active=True)
                    .order_by(Announcement.created_at.desc())
                    .first()
                )
                latest_announcement = None
                if latest_announcement_row:
                    latest_announcement = {
                        "id": latest_announcement_row.id,
                        "title": latest_announcement_row.title,
                        "content": latest_announcement_row.content,
                        "created_at": latest_announcement_row.created_at,
                    }

                recent_combat_rows = (
                    CombatLog.query.options(
                        joinedload(CombatLog.attacker),
                        joinedload(CombatLog.defender),
                    )
                    .order_by(CombatLog.timestamp.desc())
                    .limit(5)
                    .all()
                )
                recent_combat = []
                for combat in recent_combat_rows:
                    attacker_name = _("مجهول")
                    if not getattr(combat, "is_attacker_anonymous", False):
                        attacker_name = combat.attacker.username if combat.attacker else _("مجهول")
                    defender_name = combat.defender.username if combat.defender else _("مجهول")
                    recent_combat.append(
                        {
                            "attacker": attacker_name,
                            "defender": defender_name,
                        }
                    )
                cache = {
                    "expires_at": now.replace(microsecond=0) + timedelta(seconds=cache_seconds),
                    "latest_announcement": latest_announcement,
                    "recent_combat": recent_combat,
                }
                app._global_data_cache = cache
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                latest_announcement = None
                recent_combat = []
        else:
            latest_announcement = cache.get("latest_announcement")
            recent_combat = cache.get("recent_combat") or []
        
        ticker_items = []
        if latest_announcement:
             ticker_items.append({'type': 'announcement', 'text': f"📢 {latest_announcement['title']}: {latest_announcement['content'][:50]}..."})

        for combat in recent_combat:
            try:
                ticker_items.append({'type': 'combat', 'text': _("⚔️ %(attacker)s هاجم %(defender)s", attacker=combat.get("attacker") or _("مجهول"), defender=combat.get("defender") or _("مجهول"))})
            except:
                continue
                
        # Add generic tips if empty
        if not ticker_items:
             ticker_items.append({'type': 'tip', 'text': _("💡 نصيحة: قم بزيارة الجيم لزيادة قوتك!")})
             ticker_items.append({'type': 'announcement', 'text': "📢 اللاعبين الكرام: لا تترددوا في طلب مزايا وتحديثات للعبة، نحن بخدمتكم. | Dear players: Do not hesitate to request game features and updates, we are at your service."})
             ticker_items.append({'type': 'announcement', 'text': "👨‍💻 للتواصل والاقتراحات: يرجى التواصل مع المطور أزاد. | For suggestions and contact: Please reach out to Developer Azad."})

        return dict(
            global_announcement=latest_announcement,
            ticker_news=ticker_items
        )

    # Import Blueprint
    from routes import bp as main_bp
    app.register_blueprint(main_bp)

    from routes.gang import bp as gang_bp
    app.register_blueprint(gang_bp)

    from routes.combat import bp as combat_bp
    app.register_blueprint(combat_bp)

    from routes.gym import bp as gym_bp
    app.register_blueprint(gym_bp)

    from routes.bank import bp as bank_bp
    app.register_blueprint(bank_bp)

    from routes.hospital import bp as hospital_bp
    app.register_blueprint(hospital_bp)

    from routes.jail import bp as jail_bp
    app.register_blueprint(jail_bp)

    from routes.market import bp as market_bp
    app.register_blueprint(market_bp)

    from routes.police_chase import bp as police_chase_bp
    app.register_blueprint(police_chase_bp)

    from routes.travel import bp as travel_bp
    app.register_blueprint(travel_bp)

    from routes.bounties import bp as bounties_bp
    app.register_blueprint(bounties_bp)

    from routes.casino import bp as casino_bp
    app.register_blueprint(casino_bp)

    from routes.black_market import bp as black_market_bp
    app.register_blueprint(black_market_bp)

    from routes.news import bp as news_bp
    app.register_blueprint(news_bp)

    from routes.forum import bp as forum_bp
    app.register_blueprint(forum_bp)

    from routes.economy import bp as economy_bp
    app.register_blueprint(economy_bp)

    from routes.inventory import bp as inventory_bp
    app.register_blueprint(inventory_bp)

    from routes.graveyard import bp as graveyard_bp
    app.register_blueprint(graveyard_bp)

    from routes.racing import bp as racing_bp
    app.register_blueprint(racing_bp)

    from routes.factory import bp as factory_bp
    app.register_blueprint(factory_bp)

    from routes.farm import bp as farm_bp
    app.register_blueprint(farm_bp)

    from routes.entertainment import bp as entertainment_bp
    app.register_blueprint(entertainment_bp)

    from routes.resources import bp as resources_bp
    app.register_blueprint(resources_bp)

    from routes.seo import bp as seo_bp
    app.register_blueprint(seo_bp)

    from routes.youtube import bp as youtube_bp
    app.register_blueprint(youtube_bp)

    # Register Hostess Blueprints
    from routes.hostesses import register_hostess_blueprints
    register_hostess_blueprints(app)

    # Import Models (to ensure they are registered with SQLAlchemy)
    import models
    
    # Register Admin Views
    from flask_admin.contrib.sqla import ModelView
    from flask_admin.menu import MenuLink
    from flask_login import current_user
    from flask_babel import lazy_gettext as _
    from models.user import UserRole
    from admin_views import (
        UserView, ItemView, VehicleView, LocationView, CrimeView, OrganizedCrimeView, 
        GangView, LogView, AssetView, PaymentView, SecureModelView,
        SystemConfigView, UserRankView, ForumCategoryView, ForumTopicView, AnnouncementView,
        UserItemView, BountyView, CombatLogView, GangLogView, GangWarView,
        DailyTaskView, WeeklyWinnerView, ReferralView, MessageView, MarketAssetView,
        UserInvestmentView, ForumPostView, UserVehicleView,
        HostessView, HostessKnowledgeView, LearningLogView, UserLogView
    )

    with app.app_context():
        # Check if views are already registered (only index view exists by default)
        if len(admin._views) <= 1:
            # Seed Ranks
            try:
                # Create tables if not exist (ensures UserRank table exists)
                # db.create_all()
                pass
                # if not models.UserRank.query.first():
                #     default_ranks = [
                #         (1, 'متشرد'), (3, 'نشال'), (5, 'لص'), (10, 'بلطجي'),
                #         (15, 'مجرم'), (20, 'قاتل مأجور'), (25, 'جندي'), (30, 'كابتن'),
                #         (40, 'محترف'), (50, 'مستشار'), (65, 'وكيل'), (80, 'زعيم'), (100, 'عراب')
                #     ]
                #     for min_level, name in default_ranks:
                #         db.session.add(models.UserRank(name=name, min_level=min_level))
                #     db.session.commit()
                
                # Seed Organized Crimes Settings
                # try:
                #     from models.system import SystemConfig
                #     if SystemConfig.get_value('organized_crimes_enabled') is None:
                #         SystemConfig.set_value('organized_crimes_enabled', 'true', str(_('تفعيل الجرائم المنظمة')))
                #     if SystemConfig.get_value('organized_crimes_allow_non_gang') is None:
                #         SystemConfig.set_value('organized_crimes_allow_non_gang', 'true', str(_('السماح لغير الأعضاء في عصابات بالمشاركة')))
                #     if SystemConfig.get_value('organized_crimes_min_creator_rank_level') is None:
                #         SystemConfig.set_value('organized_crimes_min_creator_rank_level', '20', str(_('أقل مستوى لإنشاء جريمة منظمة')))
                #     
                #     # Market Settings
                #     if SystemConfig.get_value('market_enable_spot') is None:
                #         SystemConfig.set_value('market_enable_spot', 'true', str(_('تفعيل تداول السبوت')))
                #     if SystemConfig.get_value('market_enable_futures') is None:
                #         SystemConfig.set_value('market_enable_futures', 'true', str(_('تفعيل تداول الفيوتشر')))
                #     if SystemConfig.get_value('market_enable_limit_orders') is None:
                #         SystemConfig.set_value('market_enable_limit_orders', 'true', str(_('تفعيل أوامر الحد (Limit)')))
                #     if SystemConfig.get_value('market_spot_min_buy_usd') is None:
                #         SystemConfig.set_value('market_spot_min_buy_usd', '10', str(_('أقل مبلغ شراء سبوت (USD)')))
                #     if SystemConfig.get_value('market_futures_leverages') is None:
                #         SystemConfig.set_value('market_futures_leverages', '1,5,10,20,50,100', str(_('الرافعات المسموح بها للفيوتشر')))
                #     if SystemConfig.get_value('market_update_interval_seconds') is None:
                #         SystemConfig.set_value('market_update_interval_seconds', '60', str(_('فاصل تحديث الأسعار بالثواني')))
                #     if SystemConfig.get_value('market_intel_cost') is None:
                #         SystemConfig.set_value('market_intel_cost', '500', str(_('تكلفة شراء المعلومة')))
                #     
                #     # General Settings
                #     if SystemConfig.get_value('maintenance_mode') is None:
                #         SystemConfig.set_value('maintenance_mode', 'false', str(_('وضع الصيانة')))
                #     if SystemConfig.get_value('welcome_message') is None:
                #         SystemConfig.set_value('welcome_message', 'Welcome to Gangs of Palestine!', str(_('رسالة الترحيب')))
                #         
                # except Exception as e:
                #     print(f"Error seeding organized crimes settings: {e}")
            except Exception as e:
                app.logger.error(f"Error seeding ranks: {e}")

            # System & Logs
            admin.add_link(MenuLink(name=_('العودة للحارة'), url='/'))
            admin.add_view(PaymentView(models.PaymentTransaction, db.session, name=_('المدفوعات'), category=_('الإدارة')))
            admin.add_view(LogView(models.GameLog, db.session, name=_('سجل اللعبة'), category=_('الإدارة')))
            admin.add_view(SystemConfigView(models.SystemConfig, db.session, name=_('إعدادات النظام'), category=_('الإدارة')))
            admin.add_view(AnnouncementView(models.Announcement, db.session, name=_('الإعلانات'), category=_('الإدارة')))
            
            # Users & Social
            admin.add_view(UserView(models.User, db.session, name=_('المستخدمين'), category=_('اللاعبين')))
            admin.add_view(UserRankView(models.UserRank, db.session, name=_('رتب اللاعبين'), category=_('اللاعبين')))
            admin.add_view(GangView(models.Gang, db.session, name=_('العصابات'), category=_('اللاعبين'), endpoint='gang_admin'))
            admin.add_view(GangWarView(models.GangWar, db.session, name=_('حروب العصابات'), category=_('اللاعبين')))
            admin.add_view(HostessView(models.Hostess, db.session, name=_('المضيفات'), category=_('اللاعبين')))
            admin.add_view(HostessKnowledgeView(models.HostessKnowledge, db.session, name=_('قاعدة المعرفة'), category=_('اللاعبين')))
            admin.add_view(LearningLogView(models.LearningLog, db.session, name=_('سجل التعلم'), category=_('اللاعبين')))
            
            # Game Content
            admin.add_view(CrimeView(models.Crime, db.session, name=_('الجرائم'), category=_('عالم اللعبة')))
            admin.add_view(OrganizedCrimeView(models.OrganizedCrime, db.session, name=_('الجرائم المنظمة'), category=_('عالم اللعبة')))
            admin.add_view(ItemView(models.Item, db.session, name=_('الأغراض'), category=_('عالم اللعبة')))
            admin.add_view(LocationView(models.Location, db.session, name=_('المناطق'), category=_('عالم اللعبة')))
            admin.add_view(VehicleView(models.Vehicle, db.session, name=_('المركبات'), category=_('عالم اللعبة')))
            admin.add_view(AssetView(models.Asset, db.session, name=_('الممتلكات'), category=_('عالم اللعبة')))
            admin.add_view(DailyTaskView(models.DailyTask, db.session, name=_('المهام اليومية'), category=_('عالم اللعبة')))
            
            # Economy
            admin.add_view(MarketAssetView(models.MarketAsset, db.session, name=_('الأسهم والعملات'), category=_('الاقتصاد')))
            admin.add_view(UserInvestmentView(models.UserInvestment, db.session, name=_('استثمارات اللاعبين'), category=_('الاقتصاد')))
            admin.add_view(SecureModelView(models.SpotOrder, db.session, name=_('أوامر السبوت'), category=_('الاقتصاد')))
            admin.add_view(SecureModelView(models.FuturesPosition, db.session, name=_('صفقات الفيوتشر'), category=_('الاقتصاد')))

            # Monitoring
            admin.add_view(UserItemView(models.UserItem, db.session, name=_('مخزون اللاعبين'), category=_('المراقبة')))
            admin.add_view(BountyView(models.Bounty, db.session, name=_('المكافآت'), category=_('المراقبة')))
            admin.add_view(WeeklyWinnerView(models.WeeklyWinner, db.session, name=_('الفائزين'), category=_('المراقبة')))
            admin.add_view(CombatLogView(models.CombatLog, db.session, name=_('سجل القتال'), category=_('المراقبة')))
            admin.add_view(UserLogView(models.UserLog, db.session, name=_('سجل اللاعبين'), category=_('المراقبة')))
            admin.add_view(GangLogView(models.GangLog, db.session, name=_('سجل العصابات'), category=_('المراقبة')))
            admin.add_view(UserVehicleView(models.UserVehicle, db.session, name=_('مركبات المستخدمين'), category=_('المراقبة')))
            admin.add_view(ReferralView(models.Referral, db.session, name=_('الإحالات'), category=_('المراقبة')))
            admin.add_view(MessageView(models.Message, db.session, name=_('الرسائل'), category=_('المراقبة')))

            # Forum
            admin.add_view(ForumCategoryView(models.ForumCategory, db.session, name=_('أقسام المنتدى'), category=_('المجتمع')))
            admin.add_view(ForumTopicView(models.ForumTopic, db.session, name=_('المواضيع'), category=_('المجتمع')))
            admin.add_view(ForumPostView(models.ForumPost, db.session, name=_('الردود'), category=_('المجتمع')))

    return app
