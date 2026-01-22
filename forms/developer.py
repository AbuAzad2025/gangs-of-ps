from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, IntegerField, SelectField, SubmitField, BooleanField, TextAreaField, DateTimeField
from wtforms.validators import DataRequired, Optional
from flask_babel import lazy_gettext as _l


class VehicleForm(FlaskForm):
    name = StringField('Vehicle Name', validators=[DataRequired()])
    type = SelectField('Type', choices=[
        ('legal_il', _l('Yellow Plate (Legal IL)')),
        ('legal_pal', _l('White/Green Plate (Legal PAL)')),
        ('mushtuba', _l('Mushtuba (Illegal)'))
    ], validators=[DataRequired()])
    description = TextAreaField('Description')
    price = IntegerField('Price', validators=[DataRequired()])
    speed = IntegerField('Speed (0-100)', validators=[DataRequired()])
    defense = IntegerField('Defense (0-100)', validators=[DataRequired()])
    risk = IntegerField('Seizure Risk % (0-100)', validators=[Optional()])
    image = FileField('Vehicle Image', validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Vehicle')


class ItemForm(FlaskForm):
    name = StringField('Item Name', validators=[DataRequired()])
    type = SelectField('Type', choices=[
        ('weapon', _l('Weapon')),
        ('armor', _l('Armor')),
        ('consumable', _l('Consumable')),
        ('loot', _l('Loot (Stealable)'))
    ], validators=[DataRequired()])
    description = TextAreaField('Description')
    cost = IntegerField('Cost', validators=[DataRequired()])
    bonus_strength = IntegerField('Strength Bonus', validators=[Optional()])
    bonus_defense = IntegerField('Defense Bonus', validators=[Optional()])
    bonus_agility = IntegerField('Agility Bonus', validators=[Optional()])
    ammo_needed = IntegerField(
        'Ammo Needed (per attack)',
        validators=[
            Optional()])
    recover_energy = IntegerField('Recover Energy', validators=[Optional()])
    recover_health = IntegerField('Recover Health', validators=[Optional()])
    recover_brave = IntegerField('Recover Brave', validators=[Optional()])
    image = FileField('Item Image', validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    is_black_market = BooleanField('Black Market Item')
    submit = SubmitField('Save Item')


class CrimeForm(FlaskForm):
    name = StringField('Crime Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    energy_cost = IntegerField('Energy Cost', validators=[DataRequired()])
    min_level = IntegerField('Min Level', validators=[DataRequired()])
    money_reward_min = IntegerField(
        'Min Money Reward', validators=[
            DataRequired()])
    money_reward_max = IntegerField(
        'Max Money Reward', validators=[
            DataRequired()])
    exp_reward = IntegerField('EXP Reward', validators=[DataRequired()])
    reward_type = SelectField('Reward Type', choices=[
        ('money', _l('Money Only')),
        ('vehicle', _l('Vehicle (Random Rank)')),
        ('item', _l('Specific Item'))
    ], default='money', validators=[DataRequired()])
    reward_item_id = SelectField(
        'Reward Item (If Item Type)',
        coerce=int,
        validators=[
            Optional()])
    image = FileField('Crime Image', validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Crime')


class AssetForm(FlaskForm):
    name = StringField('Property Name', validators=[DataRequired()])
    type = SelectField('Type', choices=[
        ('house', _l('House')),
        ('business', _l('Business'))
    ], validators=[DataRequired()])
    description = TextAreaField('Description')
    value = IntegerField('Price/Value', validators=[DataRequired()])
    income = IntegerField('Daily Income/Benefit', validators=[DataRequired()])
    maintenance_cost = IntegerField('Daily Maintenance Cost', default=0)
    image = FileField('Property Image', validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Property')


class TaskForm(FlaskForm):
    description = StringField('Description', validators=[DataRequired()])
    target_type = SelectField('Type', choices=[
        ('crime', _l('Crime')),
        ('gym', _l('Gym')),
        ('buy', _l('Buy Item')),
        ('combat', _l('Combat')),
        ('intel', _l('Intel')),
        ('gang', _l('Gang'))
    ], validators=[DataRequired()])
    target_count = IntegerField('Target Count', validators=[DataRequired()])
    reward_money = IntegerField('Reward Money', validators=[DataRequired()])
    reward_exp = IntegerField('Reward XP', validators=[DataRequired()])
    image = FileField('Task Image', validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Task')


class AnnouncementForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Announcement')


class ForumCategoryForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description')
    order = IntegerField('Order', default=0)
    min_rank = IntegerField('Min Rank (0=All)', default=0)
    submit = SubmitField('Save Category')


class OrganizedCrimeForm(FlaskForm):
    name = StringField('Crime Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    min_members = IntegerField(
        'Min Members',
        default=3,
        validators=[
            DataRequired()])
    min_gang_level = IntegerField(
        'Min Gang Level',
        default=1,
        validators=[
            DataRequired()])
    energy_cost = IntegerField(
        'Energy Cost (Leader)',
        default=50,
        validators=[
            DataRequired()])
    min_level = IntegerField(
        'Min Level',
        default=10,
        validators=[
            DataRequired()])
    cooldown_hours = IntegerField(
        'Cooldown Hours',
        default=24,
        validators=[
            DataRequired()])
    money_reward_min = IntegerField(
        'Min Money Reward',
        default=1000,
        validators=[
            DataRequired()])
    money_reward_max = IntegerField(
        'Max Money Reward',
        default=5000,
        validators=[
            DataRequired()])
    exp_reward = IntegerField(
        'EXP Reward',
        default=100,
        validators=[
            DataRequired()])
    image = FileField('Crime Image', validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    is_active = BooleanField('Active')
    submit = SubmitField('Save OC')


class HostessForm(FlaskForm):
    name = StringField(_l('الاسم'), validators=[DataRequired()])
    role = SelectField(_l('الدور'), choices=[
        ('luck', _l('حظ (Luck)')),
        ('spy', _l('تجسس (Spy)')),
        ('support', _l('دعم نفسي (Support)')),
        ('companion', _l('مرافقة (Companion)')),
        ('greeter', _l('موظفة استقبال (Greeter)'))
    ], validators=[DataRequired()])
    price = IntegerField(_l('سعر الاستئجار'), validators=[DataRequired()])
    description = TextAreaField(_l('الوصف'))
    dialogue_style = SelectField(_l('أسلوب الحديث'), choices=[
        ('friendly', _l('ودود (Friendly)')),
        ('mysterious', _l('غامض (Mysterious)')),
        ('flirty', _l('مغازل (Flirty)')),
        ('energetic', _l('حيوي (Energetic)')),
        ('supportive', _l('داعم (Supportive)'))
    ], default='friendly')
    intro_message = TextAreaField(_l('رسالة الترحيب'))
    system_prompt = TextAreaField(_l('تلقين الذكاء الاصطناعي (System Prompt)'))
    knowledge_base = TextAreaField(
        _l('قاعدة المعرفة (دليل المستخدم)'),
        render_kw={
            "rows": 10})
    training_examples = TextAreaField(
        _l('أمثلة تدريب (JSON)'),
        render_kw={
            "rows": 10,
            "placeholder": '[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]'})

    # Video Configuration
    video_choice = SelectField(
        _l('اختيار أفاتار موجود'), choices=[
            ('', _l('بدون'))], validators=[
            Optional()])
    video = FileField(_l('أفاتار متحرك (MP4/WebM/GIF)'),
                      validators=[FileAllowed(['mp4', 'webm', 'gif'], 'Videos only!')])
    video_prompt = TextAreaField(
        _l('سيناريو الفيديو (JSON)'),
        render_kw={
            "rows": 10,
            "placeholder": '{"title": "...", "description": "...", "shots": [...]}'})

    # Voice & Personality
    voice_config = TextAreaField(
        _l('إعدادات الصوت (JSON)'),
        render_kw={
            "rows": 5,
            "placeholder": '{"provider": "browser", "pitch": 1.0, "rate": 1.0}'})
    personality_config = TextAreaField(
        _l('إعدادات الشخصية (JSON)'), render_kw={
            "rows": 5, "placeholder": '{"flirt_level": 5, "shyness": 2}'})

    # Appearance & Style (New)
    clothing_style = SelectField(_l('ستايل الملابس'), choices=[
        ('casual', _l('كاجوال (Casual)')),
        ('formal', _l('رسمي / فستان سهرة (Evening Gown)')),
        ('lingerie', _l('لانجري / مثير (Lingerie/Sexy)')),
        ('street', _l('ستريت وير / شورت جينز (Street/Shorts)')),
        ('traditional', _l('تقليدي / مطرز (Traditional)')),
        ('cyberpunk', _l('سايبر بانك (Cyberpunk)')),
        ('bikini', _l('ملابس سباحة (Bikini)'))
    ], default='casual')

    clothing_custom = StringField(
        _l('وصف الملابس (تخصيص)'), render_kw={
            "placeholder": "مثال: فستان أحمر قصير ضيق..."})
    hair_style = StringField(
        _l('ستايل الشعر'), render_kw={
            "placeholder": "مثال: شعر أسود طويل مموج..."})
    body_features = StringField(
        _l('مواصفات الجسم'), render_kw={
            "placeholder": "مثال: قوام رياضي، عيون عسلية..."})

    appearance_config = TextAreaField(
        _l('تكوين المظهر الكامل (JSON)'), render_kw={
            "rows": 5, "readonly": True})

    is_avatar_active = BooleanField(_l('تفعيل وضع الافاتار الحقيقي (فيديو)'))

    # RPG Stats
    level = IntegerField(_l('المستوى (Level)'), default=1)
    exp = IntegerField(_l('الخبرة (EXP)'), default=0)
    charm = IntegerField(_l('الجاذبية (Charm)'), default=10)
    intelligence = IntegerField(_l('الذكاء (Intelligence)'), default=10)
    combat_skill = IntegerField(_l('المهارة القتالية (Combat)'), default=0)
    loyalty = IntegerField(_l('الولاء (Loyalty)'), default=50)
    reset_special_cooldown = BooleanField(_l('تصفير وقت انتظار الحركة الخاصة'))

    image = FileField(_l('صورة المضيفة'), validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    is_active = BooleanField(_l('نشط'))
    submit = SubmitField(_l('حفظ المضيفة'))


class SystemConfigForm(FlaskForm):
    key = StringField(_l('مفتاح الإعداد (Key)'), validators=[DataRequired()])
    value = TextAreaField(_l('القيمة (Value)'), validators=[DataRequired()])
    description = StringField(_l('الوصف (Description)'))
    submit = SubmitField(_l('حفظ الإعداد'))


class AchievementForm(FlaskForm):
    key = StringField(_l('المعرف (Key)'), validators=[DataRequired()])
    title = StringField(_l('العنوان'), validators=[DataRequired()])
    description = TextAreaField(_l('الوصف'), validators=[Optional()])
    points = IntegerField(_l('النقاط'), validators=[Optional()])
    submit = SubmitField(_l('حفظ الإنجاز'))


class GangForm(FlaskForm):
    name = StringField(_l('اسم العصابة'), validators=[DataRequired()])
    description = TextAreaField(_l('الوصف'))
    leader_id = IntegerField(_l('معرف القائد'), validators=[DataRequired()])
    level = IntegerField(_l('المستوى'), validators=[Optional()])
    money = IntegerField(_l('مال الخزينة'), validators=[Optional()])
    bullets = IntegerField(_l('ذخيرة الخزينة'), validators=[Optional()])
    max_members = IntegerField(
        _l('الحد الأقصى للأعضاء'),
        validators=[
            Optional()])
    image = FileField(_l('شعار العصابة'), validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    submit = SubmitField(_l('حفظ العصابة'))


class LocationForm(FlaskForm):
    name = StringField(_l('اسم المدينة/الموقع'), validators=[DataRequired()])
    description = TextAreaField(_l('الوصف'))
    cost = IntegerField(_l('تكلفة السفر'), validators=[DataRequired()])
    cooldown = IntegerField(_l('وقت الانتظار (ثانية)'), default=300)
    specialty = StringField(_l('التخصص (commerce, defense, etc.)'))
    specialty_value = IntegerField(_l('قيمة التخصص'), default=0)
    image = FileField(_l('صورة الموقع'), validators=[
                      FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    submit = SubmitField(_l('حفظ الموقع'))


class HostessKnowledgeForm(FlaskForm):
    question = TextAreaField(
        _l('السؤال / الموضوع'),
        validators=[
            DataRequired()])
    answer = TextAreaField(
        _l('الإجابة / المعلومات'),
        validators=[
            DataRequired()])
    category = StringField(_l('التصنيف'), default='general')
    keywords = StringField(_l('كلمات مفتاحية (مفصولة بفاصلة)'))
    language = SelectField(
        _l('اللغة'), choices=[
            ('ar', 'العربية'), ('en', 'English')], default='ar')
    hostess_id = SelectField(
        _l('مخصص لمضيفة (اختياري)'),
        coerce=int,
        validators=[
            Optional()])
    submit = SubmitField(_l('حفظ المعرفة'))


class VideoScenarioForm(FlaskForm):
    title = StringField(_l('عنوان السيناريو'), validators=[DataRequired()])
    description = TextAreaField(_l('الوصف'))
    script_content = TextAreaField(
        _l('محتوى السيناريو (JSON)'), validators=[
            DataRequired()], render_kw={
            "rows": 10})
    trigger_keywords = StringField(_l('كلمات مفتاحية للتفعيل'))
    is_active = BooleanField(_l('نشط'), default=True)
    submit = SubmitField(_l('حفظ السيناريو'))


class FactoryJobForm(FlaskForm):
    user_id = IntegerField(_l('معرف اللاعب'), validators=[DataRequired()])
    job_type = SelectField(_l('النوع'), choices=[
        ('bullets', _l('رصاص')),
        ('explosives', _l('متفجرات'))
    ], validators=[DataRequired()])
    metal_used = IntegerField(_l('معدن مستخدم'), default=0)
    diamonds_used = IntegerField(_l('ماس مستخدم'), default=0)
    output_amount = IntegerField(_l('الكمية الناتجة'), default=0)
    status = SelectField(_l('الحالة'), choices=[
        ('running', _l('جاري العمل')),
        ('claimed', _l('تم الاستلام')),
        ('canceled', _l('ملغي'))
    ], default='running')
    ends_at = DateTimeField(
        _l('وقت الانتهاء (YYYY-MM-DD HH:MM:SS)'),
        format='%Y-%m-%d %H:%M:%S',
        validators=[
            DataRequired()])
    submit = SubmitField(_l('حفظ المهمة'))


class MarketAssetForm(FlaskForm):
    symbol = StringField(_l('الرمز (Symbol)'), validators=[DataRequired()])
    name = StringField(_l('اسم الأصل'), validators=[DataRequired()])
    type = SelectField(_l('النوع'), choices=[
        ('commodity', _l('سلعة (Commodity)')),
        ('stock', _l('سهم (Stock)')),
        ('crypto', _l('عملة رقمية (Crypto)')),
        ('index', _l('مؤشر (Index)'))
    ], validators=[DataRequired()])
    base_price = IntegerField(
        _l('السعر الأساسي'),
        default=100,
        validators=[
            DataRequired()])
    volatility = IntegerField(
        _l('التقلب (0-100%)'),
        default=5,
        validators=[
            DataRequired()])
    description = TextAreaField(_l('الوصف'))
    is_active = BooleanField(_l('نشط'), default=True)
    submit = SubmitField(_l('حفظ الأصل'))
