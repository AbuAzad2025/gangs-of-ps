from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from flask import redirect, url_for, flash
from flask_babel import lazy_gettext as _
from wtforms import PasswordField
from models import User, UserRank, UserItem, UserVehicle, UserInvestment, Announcement, Hostess, HostessKnowledge, LearningLog

from services.resource_service import ResourceService

class SecureModelView(ModelView):
    def is_accessible(self):
        # Allow ADMIN, SUPER_ADMIN, and DEVELOPER to access
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        flash(_('يجب عليك تسجيل الدخول بصلاحيات المسؤول للوصول إلى هذه الصفحة.'), 'error')
        return redirect(url_for('main.login'))

    page_size = 20
    can_export = True
    can_view_details = True
    create_modal = True
    edit_modal = True
    details_modal = True

class HostessView(SecureModelView):
    column_list = ('name', 'role', 'price', 'dialogue_style', 'is_active')
    column_searchable_list = ('name', 'description')
    column_filters = ('role', 'dialogue_style', 'is_active')
    
    column_labels = {
        'name': _('الاسم'),
        'role': _('الدور'),
        'price': _('السعر'),
        'image': _('الصورة'),
        'description': _('الوصف'),
        'dialogue_style': _('أسلوب الحوار'),
        'intro_message': _('رسالة الترحيب'),
        'buff_type': _('نوع الميزة'),
        'buff_value': _('قيمة الميزة'),
        'system_prompt': _('موجه النظام (Prompt)'),
        'training_examples': _('أمثلة التدريب'),
        'video': _('الفيديو'),
        'video_prompt': _('موجه الفيديو'),
        'voice_config': _('إعدادات الصوت'),
        'personality_config': _('إعدادات الشخصية'),
        'appearance_config': _('إعدادات المظهر'),
        'knowledge_base': _('قاعدة المعرفة (نص)'),
        'is_avatar_active': _('تفعيل الأفاتار'),
        'is_active': _('نشط')
    }

class HostessKnowledgeView(SecureModelView):
    column_list = ('hostess_id', 'question', 'answer', 'category', 'language')
    column_searchable_list = ('question', 'answer', 'keywords')
    column_filters = ('hostess_id', 'category', 'language')
    
    column_labels = {
        'hostess_id': _('المضيفة'),
        'question': _('السؤال'),
        'answer': _('الإجابة'),
        'category': _('التصنيف'),
        'keywords': _('الكلمات المفتاحية'),
        'language': _('اللغة')
    }

class LearningLogView(SecureModelView):
    column_list = ('user_id', 'user_question', 'ai_response', 'was_helpful', 'created_at')
    column_searchable_list = ('user_question', 'ai_response')
    column_filters = ('was_helpful', 'created_at')
    column_default_sort = ('created_at', True)
    
    column_labels = {
        'user_id': _('المستخدم'),
        'user_question': _('سؤال المستخدم'),
        'ai_response': _('رد الذكاء الاصطناعي'),
        'was_helpful': _('مفيد؟'),
        'created_at': _('الوقت')
    }
    
    can_create = False
    can_edit = False

class AnnouncementView(SecureModelView):
    column_list = ('title', 'is_active', 'created_at')
    column_searchable_list = ('title', 'content')
    column_editable_list = ('is_active',)
    column_default_sort = ('created_at', True)
    
    column_labels = {
        'title': _('العنوان'),
        'content': _('المحتوى'),
        'is_active': _('نشط'),
        'created_at': _('تاريخ الإنشاء')
    }

class UserView(SecureModelView):
    column_list = ('id', 'username', 'role', 'level', 'money', 'diamonds', 'location', 'gang', 'inventory', 'banned_until')
    column_searchable_list = ('username',)
    column_filters = ('role', 'level', 'location.name', 'gang.name', 'banned_until')
    column_editable_list = ('role', 'money', 'diamonds', 'banned_until', 'ban_reason')
    form_excluded_columns = ('password_hash', 'items', 'vehicles', 'messages_sent', 'messages_received', 'notifications', 'tasks', 'combat_history_attacker', 'combat_history_defender', 'daily_tasks', 'organized_crimes', 'bounties_placed', 'bounties_claimed', 'topics', 'posts', 'crime_cooldowns')
    
    inline_models = (UserVehicle, UserInvestment, UserItem)

    column_labels = {
        'username': _('اسم المستخدم'),
        'role': _('الرتبة'),
        'level': _('المستوى'),
        'money': _('المال'),
        'diamonds': _('الماس'),
        'location': _('الموقع'),
        'gang': _('العصابة'),
        'is_active': _('نشط'),
        'banned_until': _('محظور حتى'),
        'ban_reason': _('سبب الحظر'),
        'inventory': _('المخزون'),
        'vehicles': _('المركبات'),
        'investments': _('الاستثمارات')
    }

    def _inventory_formatter(view, context, model, name):
        try:
            items = model.inventory.limit(3).all()
            if not items:
                return _('لا يوجد')
            
            item_list = [f"{item.item.name} ({item.quantity})" for item in items]
            if model.inventory.count() > 3:
                item_list.append('...')
            return ", ".join(item_list)
        except:
            return _('خطأ')

    column_formatters = {
        'inventory': _inventory_formatter
    }

    def delete_model(self, model):
        """
        Override delete_model to handle related records cleanup for permanent removal.
        """
        # Check if gang leader
        if model.gang and model.gang.leader_id == model.id:
            flash(_('لا يمكن حذف قائد العصابة. يرجى نقل القيادة أو حذف العصابة أولاً.'), 'error')
            return False
            
        try:
            # Import models locally to avoid circular imports
            from models import (
                UserItem, UserVehicle, UserDailyTask, UserCrimeCooldown, 
                Message, Notification, Bounty, CombatLog, UserInvestment, 
                UserProgress, ResurrectionRequest, PaymentTransaction,
                GangInvite, LobbyParticipant, CrimeLobby, ForumTopic, 
                ForumPost, Referral
            )
            
            # Delete related data
            UserItem.query.filter_by(user_id=model.id).delete()
            UserVehicle.query.filter_by(user_id=model.id).delete()
            UserDailyTask.query.filter_by(user_id=model.id).delete()
            UserCrimeCooldown.query.filter_by(user_id=model.id).delete()
            UserInvestment.query.filter_by(user_id=model.id).delete()
            UserProgress.query.filter_by(user_id=model.id).delete()
            ResurrectionRequest.query.filter_by(user_id=model.id).delete()
            PaymentTransaction.query.filter_by(user_id=model.id).delete()
            GangInvite.query.filter_by(user_id=model.id).delete()
            
            # Forum
            ForumPost.query.filter_by(user_id=model.id).delete()
            ForumTopic.query.filter_by(user_id=model.id).delete()
            
            # Referral
            Referral.query.filter((Referral.referrer_id == model.id) | (Referral.referred_id == model.id)).delete()
            
            # Messages
            Message.query.filter((Message.sender_id == model.id) | (Message.receiver_id == model.id)).delete()
            Notification.query.filter_by(user_id=model.id).delete()
            
            # Combat
            Bounty.query.filter((Bounty.placer_id == model.id) | (Bounty.target_id == model.id)).delete()
            CombatLog.query.filter((CombatLog.attacker_id == model.id) | (CombatLog.defender_id == model.id)).delete()
            
            # Lobby
            # First, delete all participants in lobbies led by this user
            lobbies_led = CrimeLobby.query.filter_by(leader_id=model.id).all()
            for lobby in lobbies_led:
                LobbyParticipant.query.filter_by(lobby_id=lobby.id).delete()
            
            # Then delete the user's participation in other lobbies
            LobbyParticipant.query.filter_by(user_id=model.id).delete()
            
            # Finally delete the lobbies led by user
            CrimeLobby.query.filter_by(leader_id=model.id).delete()
            
            self.session.flush()
            self.session.delete(model)
            self.session.commit()
            return True
        except Exception as ex:
            self.session.rollback()
            flash(_('فشل حذف السجل. %(error)s', error=str(ex)), 'error')
            return False

class UserRankView(SecureModelView):
    column_list = ('id', 'name', 'min_level', 'resurrection_cost', 'user_count', 'sample_users')
    column_editable_list = ('name', 'min_level', 'resurrection_cost')
    column_labels = {
        'name': _('اسم الرتبة'),
        'min_level': _('المستوى الأدنى'),
        'resurrection_cost': _('تكلفة الإحياء (الماس)'),
        'user_count': _('عدد اللاعبين'),
        'sample_users': _('لاعبين في هذه الرتبة')
    }
    
    def _user_count_formatter(view, context, model, name):
        next_rank = UserRank.query.filter(UserRank.min_level > model.min_level).order_by(UserRank.min_level.asc()).first()
        query = User.query.filter(User.level >= model.min_level)
        if next_rank:
            query = query.filter(User.level < next_rank.min_level)
        return query.count()

    def _users_list_formatter(view, context, model, name):
        next_rank = UserRank.query.filter(UserRank.min_level > model.min_level).order_by(UserRank.min_level.asc()).first()
        query = User.query.filter(User.level >= model.min_level)
        if next_rank:
            query = query.filter(User.level < next_rank.min_level)
        
        users = query.limit(5).all()
        names = [u.username for u in users]
        if query.count() > 5:
            names.append('...')
        return ", ".join(names) if names else _('لا يوجد')

    def _cost_formatter(view, context, model, name):
        try:
            return f"{int(model.resurrection_cost)} 💎"
        except Exception:
            return f"{model.resurrection_cost} 💎"

    column_formatters = {
        'user_count': _user_count_formatter,
        'sample_users': _users_list_formatter,
        'resurrection_cost': _cost_formatter
    }

class ItemView(SecureModelView):
    column_list = ('id', 'name', 'type', 'cost', 'bonus_strength', 'bonus_defense', 'is_black_market')
    column_searchable_list = ('name', 'description')
    column_filters = ('type', 'is_black_market')
    column_editable_list = ('cost', 'is_black_market')
    
    column_labels = {
        'name': _('الاسم'),
        'type': _('النوع'),
        'cost': _('السعر'),
        'bonus_strength': _('قوة إضافية'),
        'bonus_defense': _('دفاع إضافي'),
        'is_black_market': _('سوق سوداء')
    }

class UserItemView(SecureModelView):
    column_list = ('user', 'item', 'quantity', 'is_equipped')
    column_filters = ('user.username', 'item.name', 'is_equipped')
    column_editable_list = ('quantity', 'is_equipped')
    
    column_labels = {
        'user': _('المستخدم'),
        'item': _('الغرض'),
        'quantity': _('الكمية'),
        'is_equipped': _('مجهز')
    }

class VehicleView(SecureModelView):
    column_list = ('id', 'name', 'type', 'price', 'speed', 'defense', 'risk')
    column_searchable_list = ('name',)
    column_filters = ('type',)
    
    column_labels = {
        'name': _('الاسم'),
        'type': _('النوع'),
        'price': _('السعر'),
        'speed': _('السرعة'),
        'defense': _('الدفاع'),
        'risk': _('نسبة الخطر')
    }

class UserVehicleView(SecureModelView):
    column_list = ('user', 'vehicle', 'is_active', 'condition')
    column_filters = ('user.username', 'vehicle.name', 'is_active')
    column_editable_list = ('is_active', 'condition')
    
    column_labels = {
        'user': _('المستخدم'),
        'vehicle': _('المركبة'),
        'is_active': _('مستخدمة حالياً'),
        'condition': _('الحالة')
    }

class LocationView(SecureModelView):
    column_list = ('id', 'name', 'cost', 'cooldown', 'specialty')
    column_labels = {
        'name': _('الاسم'),
        'cost': _('تكلفة السفر'),
        'cooldown': _('وقت الانتظار'),
        'specialty': _('الميزة الخاصة')
    }

class CrimeView(SecureModelView):
    column_list = ('id', 'name', 'min_level', 'energy_cost', 'cooldown', 'money_reward_min', 'money_reward_max', 'is_active')
    column_filters = ('min_level', 'energy_cost', 'cooldown', 'is_active')
    column_editable_list = ('name', 'min_level', 'energy_cost', 'cooldown', 'money_reward_min', 'money_reward_max', 'is_active')
    column_labels = {
        'name': _('اسم الجريمة'),
        'min_level': _('المستوى المطلوب'),
        'energy_cost': _('الطاقة المطلوبة'),
        'cooldown': _('وقت الانتظار (ثواني)'),
        'money_reward_min': _('أقل مكافأة'),
        'money_reward_max': _('أعلى مكافأة'),
        'is_active': _('نشط')
    }

class OrganizedCrimeView(SecureModelView):
    column_list = ('id', 'name', 'min_members', 'energy_cost', 'money_reward_min', 'money_reward_max', 'exp_reward', 'cooldown_hours', 'is_active', 'roles_config', 'requirements')
    column_filters = ('min_members', 'energy_cost', 'cooldown_hours', 'is_active')
    column_editable_list = ('name', 'min_members', 'energy_cost', 'money_reward_min', 'money_reward_max', 'exp_reward', 'cooldown_hours', 'is_active', 'roles_config', 'requirements')
    column_labels = {
        'name': _('اسم الجريمة المنظمة'),
        'min_members': _('عدد الأعضاء المطلوب'),
        'energy_cost': _('تكلفة الطاقة'),
        'money_reward_min': _('أقل مكافأة'),
        'money_reward_max': _('أعلى مكافأة'),
        'exp_reward': _('مكافأة الخبرة'),
        'cooldown_hours': _('الهدنة (ساعات)'),
        'is_active': _('نشط'),
        'roles_config': _('إعدادات الأدوار (JSON)'),
        'requirements': _('المتطلبات (JSON)')
    }

class GangView(SecureModelView):
    column_list = ('id', 'name', 'leader', 'level', 'points', 'money')
    column_labels = {
        'name': _('اسم العصابة'),
        'leader': _('القائد'),
        'level': _('المستوى'),
        'points': _('النقاط'),
        'money': _('خزينة العصابة')
    }

class CombatLogView(SecureModelView):
    can_create = False
    can_edit = False
    can_delete = False
    column_list = ('timestamp', 'attacker', 'defender', 'winner', 'money_stolen', 'exp_gain')
    column_filters = ('attacker.username', 'defender.username', 'winner.username')
    column_default_sort = ('timestamp', True)
    column_labels = {
        'timestamp': _('الوقت'),
        'attacker': _('المهاجم'),
        'defender': _('المدافع'),
        'winner': _('الفائز'),
        'money_stolen': _('المال المسروق'),
        'exp_gain': _('الخبرة المكتسبة')
    }

class GangLogView(SecureModelView):
    can_create = False
    can_edit = False
    can_delete = False
    column_list = ('timestamp', 'gang', 'user', 'action')
    column_filters = ('gang.name', 'user.username', 'action')
    column_default_sort = ('timestamp', True)
    column_labels = {
        'timestamp': _('الوقت'),
        'gang': _('العصابة'),
        'user': _('العضو'),
        'action': _('الحدث')
    }

    def _action_formatter(view, context, model, name):
        translations = {
            "Joined the gang via invite": _('انضم للعصابة عبر دعوة'),
            "Left the gang": _('غادر العصابة'),
            "Created the gang": _('أنشأ العصابة'),
            "Kicked from gang": _('طُرد من العصابة'),
            "Promoted to leader": _('ترقى لزعيم'),
            "Demoted": _('تم تنزيل رتبته')
        }
        return translations.get(model.action, model.action)

    column_formatters = {
        'action': _action_formatter
    }

class GangWarView(SecureModelView):
    column_list = ('gang1', 'gang2', 'score_gang1', 'score_gang2', 'status', 'start_time')
    column_filters = ('gang1.name', 'gang2.name', 'status')
    column_labels = {
        'gang1': _('العصابة 1'),
        'gang2': _('العصابة 2'),
        'score_gang1': _('نقاط 1'),
        'score_gang2': _('نقاط 2'),
        'status': _('الحالة'),
        'start_time': _('وقت البدء')
    }

class LogView(SecureModelView):
    can_create = False
    can_edit = False
    can_delete = False
    column_list = ('timestamp', 'admin', 'action', 'details')
    column_default_sort = ('timestamp', True)
    column_filters = ('admin.username', 'action')
    column_labels = {
        'timestamp': _('الوقت'),
        'admin': _('المسؤول'),
        'action': _('الحدث'),
        'details': _('التفاصيل')
    }

class UserLogView(SecureModelView):
    can_create = False
    can_edit = False
    can_delete = False
    column_list = ('timestamp', 'user', 'action', 'details', 'result', 'before_state', 'after_state', 'ip_address')
    column_default_sort = ('timestamp', True)
    column_filters = ('user.username', 'action', 'result', 'ip_address')
    column_searchable_list = ('action', 'details', 'ip_address')
    column_labels = {
        'timestamp': _('الوقت'),
        'user': _('المستخدم'),
        'action': _('الحدث'),
        'details': _('التفاصيل'),
        'result': _('النتيجة'),
        'before_state': _('قبل'),
        'after_state': _('بعد'),
        'ip_address': _('IP')
    }

class AssetView(SecureModelView):
    column_list = ('id', 'name', 'type', 'base_price', 'income_per_day')
    column_labels = {
        'name': _('اسم العقار'),
        'type': _('النوع'),
        'base_price': _('السعر الأساسي'),
        'income_per_day': _('الدخل اليومي')
    }

class PaymentView(SecureModelView):
    can_create = False
    column_list = ('id', 'user', 'amount_usd', 'diamonds_amount', 'status', 'created_at', 'is_verified')
    column_editable_list = ('status', 'is_verified')
    column_filters = ('status', 'is_verified')
    column_default_sort = ('created_at', True)
    column_labels = {
        'user': _('المستخدم'),
        'amount_usd': _('المبلغ (دولار)'),
        'diamonds_amount': _('الماس'),
        'status': _('الحالة'),
        'created_at': _('تاريخ الطلب'),
        'is_verified': _('تم التحقق')
    }

    def on_model_change(self, form, model, is_created):
        if is_created:
            return

        from sqlalchemy import inspect
        from models import User
        
        ins = inspect(model)
        status_hist = ins.attrs.status.history
        verified_hist = ins.attrs.is_verified.history
        
        new_status = model.status
        new_verified = model.is_verified
        
        # We only care if the transaction is becoming "completed" and "verified"
        if new_status == 'completed' and new_verified:
            # Check if it was ALREADY completed and verified before this change
            # If no changes to status/verified, it was already effectively in this state (or came from DB that way)
            # But on_model_change only fires if form validates. 
            
            status_changed = status_hist.has_changes()
            verified_changed = verified_hist.has_changes()
            
            was_already_valid = False
            
            if not status_changed and not verified_changed:
                # No relevant fields changed, so if it is valid now, it was valid before.
                was_already_valid = True
            else:
                # Reconstruct previous state
                # If changed, 'deleted' contains the old value. If not changed, current value is the old value.
                prev_status = status_hist.deleted[0] if status_changed and status_hist.deleted else model.status
                prev_verified = verified_hist.deleted[0] if verified_changed and verified_hist.deleted else model.is_verified
                
                if prev_status == 'completed' and prev_verified:
                    was_already_valid = True
            
            if not was_already_valid:
                # It just became valid. Award diamonds.
                user = db.session.get(User, model.user_id)
                if user and ResourceService.modify_resources(model.user_id, {'diamonds': model.diamonds_amount}, 'payment_verified', auto_commit=False, expected_version=user.version):
                    flash(_('تم إضافة %(amount)s ماسة للمستخدم بنجاح.', amount=model.diamonds_amount), 'success')
                else:
                    flash(_('فشل إضافة الماسات. لم يتم العثور على المستخدم أو حدث خطأ في البيانات.', amount=model.diamonds_amount), 'error')


class SystemConfigView(SecureModelView):
    column_list = ('key', 'value', 'description')
    column_editable_list = ('value', 'description')
    column_labels = {
        'key': _('المفتاح'),
        'value': _('القيمة'),
        'description': _('الوصف')
    }

class BountyView(SecureModelView):
    column_list = ('id', 'placer', 'target', 'amount', 'is_anonymous', 'created_at')
    column_filters = ('placer.username', 'target.username', 'is_anonymous')
    column_labels = {
        'placer': _('واضع المكافأة'),
        'target': _('المستهدف'),
        'amount': _('المبلغ'),
        'is_anonymous': _('مجهول'),
        'created_at': _('تاريخ الإنشاء')
    }

class ForumCategoryView(SecureModelView):
    column_list = ('id', 'title', 'order', 'min_rank')
    column_editable_list = ('title', 'order', 'min_rank')
    column_labels = {
        'title': _('العنوان'),
        'description': _('الوصف'),
        'order': _('الترتيب'),
        'min_rank': _('أقل رتبة')
    }

class ForumTopicView(SecureModelView):
    column_list = ('id', 'title', 'category', 'user', 'is_pinned', 'is_locked', 'created_at')
    column_filters = ('category', 'is_pinned', 'is_locked')
    column_editable_list = ('is_pinned', 'is_locked')
    column_labels = {
        'title': _('العنوان'),
        'category': _('القسم'),
        'user': _('الكاتب'),
        'is_pinned': _('مثبت'),
        'is_locked': _('مغلق'),
        'created_at': _('تاريخ الإنشاء')
    }

class ForumPostView(SecureModelView):
    column_list = ('id', 'topic', 'user', 'content', 'created_at')
    column_filters = ('topic.title', 'user.username')
    column_labels = {
        'topic': _('الموضوع'),
        'user': _('الكاتب'),
        'content': _('المحتوى'),
        'created_at': _('تاريخ الإنشاء')
    }

class DailyTaskView(SecureModelView):
    column_list = ('id', 'description', 'target_type', 'target_count', 'reward_money', 'reward_exp', 'is_active')
    column_filters = ('target_type', 'is_active')
    column_editable_list = ('description', 'target_type', 'target_count', 'reward_money', 'reward_exp', 'is_active')
    column_labels = {
        'description': _('الوصف'),
        'target_type': _('النوع'),
        'target_count': _('العدد المطلوب'),
        'reward_money': _('مكافأة مالية'),
        'reward_exp': _('مكافأة خبرة'),
        'is_active': _('نشط')
    }

class WeeklyWinnerView(SecureModelView):
    column_list = ('id', 'user', 'week_number', 'year', 'amount_won', 'created_at')
    column_filters = ('user.username', 'year')
    column_labels = {
        'user': _('الفائز'),
        'week_number': _('الأسبوع'),
        'year': _('السنة'),
        'amount_won': _('المبلغ'),
        'created_at': _('تاريخ الفوز')
    }

class ReferralView(SecureModelView):
    column_list = ('id', 'referrer', 'referred', 'status', 'created_at')
    column_filters = ('referrer.username', 'referred.username', 'status')
    column_labels = {
        'referrer': _('المرسل'),
        'referred': _('المستلم'),
        'status': _('الحالة'),
        'created_at': _('تاريخ الدعوة')
    }

class MessageView(SecureModelView):
    column_list = ('id', 'sender', 'receiver', 'subject', 'is_read', 'timestamp')
    column_filters = ('sender.username', 'receiver.username', 'is_read')
    column_labels = {
        'sender': _('المرسل'),
        'receiver': _('المستلم'),
        'subject': _('العنوان'),
        'body': _('المحتوى'),
        'is_read': _('مقرؤة'),
        'timestamp': _('الوقت')
    }

class MarketAssetView(SecureModelView):
    column_list = ('id', 'symbol', 'name', 'asset_type', 'current_price', 'price_change_24h', 'last_updated')
    column_editable_list = ('symbol', 'name', 'asset_type', 'current_price', 'price_change_24h')
    column_labels = {
        'symbol': _('الرمز'),
        'name': _('الاسم'),
        'asset_type': _('النوع'),
        'current_price': _('السعر الحالي'),
        'price_change_24h': _('التغير (24س)'),
        'last_updated': _('آخر تحديث')
    }

class UserInvestmentView(SecureModelView):
    column_list = ('id', 'user', 'asset', 'quantity', 'average_buy_price')
    column_filters = ('user.username', 'asset.symbol')
    column_labels = {
        'user': _('المستثمر'),
        'asset': _('الأصل'),
        'quantity': _('الكمية'),
        'average_buy_price': _('متوسط الشراء')
    }
