import os
import re
import sys

# Extended translations dictionary
translations = {
    # General
    "تاريخ الإنشاء": "Creation Date",
    "محظور حتى": "Banned Until",
    "المركبات": "Vehicles",
    "الاستثمارات": "Investments",
    "لا يوجد": "None",
    "اسم الرتبة": "Rank Name",
    "المستوى الأدنى": "Minimum Level",
    "تكلفة الإحياء ($)": "Resurrection Cost ($)",
    "عدد اللاعبين": "Player Count",
    "لاعبين في هذه الرتبة": "Players in this rank",
    "قوة إضافية": "Bonus Strength",
    "دفاع إضافي": "Bonus Defense",
    "المستخدم": "User",
    "الغرض": "Item/Purpose",
    "مجهز": "Equipped",
    "نسبة الخطر": "Risk Percentage",
    "المركبة": "Vehicle",
    "مستخدمة حالياً": "Currently Used",
    "تكلفة السفر": "Travel Cost",
    "وقت الانتظار": "Cooldown",
    "الميزة الخاصة": "Special Perk",
    "اسم الجريمة": "Crime Name",
    "المستوى المطلوب": "Required Level",
    "الطاقة المطلوبة": "Energy Cost",
    "وقت الانتظار (ثواني)": "Cooldown (Seconds)",
    "أقل مكافأة": "Min Reward",
    "أعلى مكافأة": "Max Reward",
    "اسم الجريمة المنظمة": "Organized Crime Name",
    "عدد الأعضاء المطلوب": "Required Members",
    "مكافأة الخبرة": "XP Reward",
    "اسم العصابة": "Gang Name",
    "النقاط": "Points",
    "خزينة العصابة": "Gang Vault",
    "المهاجم": "Attacker",
    "المدافع": "Defender",
    "الفائز": "Winner",
    "المال المسروق": "Stolen Money",
    "الخبرة المكتسبة": "XP Gained",
    "العضو": "Member",
    "الحدث": "Event",
    "وقت البدء": "Start Time",
    "المسؤول": "Admin",
    "التفاصيل": "Details",
    "اسم العقار": "Property Name",
    "السعر الأساسي": "Base Price",
    "الدخل اليومي": "Daily Income",
    "المبلغ (دولار)": "Amount ($)",
    "تم التحقق": "Verified",
    "المفتاح": "Key",
    "واضع المكافأة": "Bounty Placer",
    "المستهدف": "Target",
    "الترتيب": "Order",
    "أقل رتبة": "Min Rank",
    "الكاتب": "Author",
    "مثبت": "Pinned",
    "الموضوع": "Subject",
    "العدد المطلوب": "Required Count",
    "مكافأة مالية": "Cash Reward",
    "مكافأة خبرة": "XP Reward",
    "الأسبوع": "Week",
    "السنة": "Year",
    "تاريخ الفوز": "Win Date",
    "المرسل": "Sender",
    "المستلم": "Receiver",
    "تاريخ الدعوة": "Invite Date",
    "مقرؤة": "Read",
    "الرمز": "Symbol",
    "السعر الحالي": "Current Price",
    "التغير (24س)": "Change (24h)",
    "آخر تحديث": "Last Update",
    "المستثمر": "Investor",
    "متوسط الشراء": "Avg Buy Price",
    "تكلفة الإحياء (الماس)": "Resurrection Cost (Diamonds)",
    "قبل": "Before",
    "بعد": "After",
    "تم إضافة %(amount)s ماسة للمستخدم بنجاح.": "%(amount)s diamonds added to user successfully.",
    "النظام في وضع الصيانة حالياً.": "The system is currently in maintenance mode.",
    "فشل إضافة الماسات. لم يتم العثور على المستخدم أو حدث خطأ في البيانات.": "Failed to add diamonds. User not found or data error.",
    "انتهت جلسة التحقق، يرجى التأكيد مرة أخرى.": "Verification session expired, please confirm again.",
    "هذه الميزة معطلة مؤقتاً للصيانة.": "This feature is temporarily disabled for maintenance.",
    "لا يُسمح للإداريين بالمشاركة في اللعب لضمان النزاهة.": "Admins are not allowed to play to ensure integrity.",
    "⚔️ %(attacker)s هاجم %(defender)s": "⚔️ %(attacker)s attacked %(defender)s",
    "فشل إرسال الماسات.": "Failed to send diamonds.",
    "تم إرسال الماسات بنجاح!": "Diamonds sent successfully!",
    "تعديل": "Edit",
    "حذف": "Delete",
    "إلغاء": "Cancel",
    "حفظ": "Save",
    "بحث": "Search",


    # Authentication
    "تم إنشاء حساب المطور الرئيسي وتسجيل الدخول.": "Main developer account created and logged in.",
    "اسم المستخدم أو كلمة المرور غير صحيحة": "Incorrect username or password",
    "يجب عليك تفعيل بريدك الإلكتروني أولاً. تفقد صندوق الوارد أو الرسائل المزعجة (Spam).": "You must activate your email first. Check your inbox or spam folder.",
    "لا يوجد سبب محدد": "No specific reason",
    "تسجيل الدخول": "Login",
    "رمز التحقق غير صحيح! حاول مرة أخرى.": "Incorrect verification code! Try again.",
    "إنشاء حساب": "Create Account",
    "حصلت على 10 ماسات مكافأة تسجيل عبر دعوة!": "You got 10 diamonds referral reward!",
    "تم إنشاء الحساب بنجاح! يمكنك تسجيل الدخول الآن.": "Account created successfully! You can login now.",
    "رابط التفعيل غير صالح أو منتهي الصلاحية.": "Activation link is invalid or expired.",
    "الحساب مفعل مسبقاً! قم بتسجيل الدخول.": "Account already activated! Please login.",
    "تم تفعيل حسابك بنجاح! شكراً لك.": "Account activated successfully! Thank you.",
    "تفعيل حسابك في Gangs of Palestine": "Activate your account in Gangs of Palestine",
    "تم إعادة إرسال رابط التفعيل إلى بريدك الإلكتروني.": "Activation link resent to your email.",
    "الرجاء تسجيل الدخول أولاً لإعادة إرسال التفعيل.": "Please login first to resend activation.",

    # Social / Messages
    "تم تحديد الكل كمقروء.": "All marked as read.",
    "تم حذف الإشعار.": "Notification deleted.",
    "البريد الصادر": "Outbox",
    "البريد الوارد": "Inbox",
    "ساعدني في السيطرة على المدينة! سجل الآن واحصل على مكافآت حصرية.": "Help me take over the city! Sign up now and get exclusive rewards.",
    "المستخدم غير موجود!": "User not found!",
    "لا يمكنك مراسلة نفسك!": "You cannot message yourself!",
    "تم إرسال الرسالة بنجاح!": "Message sent successfully!",
    "تم حذف الرسالة.": "Message deleted.",
    "لم يتم تحديد أي رسالة!": "No message selected!",
    "تم رفع الصورة الشخصية بنجاح": "Profile picture uploaded successfully",
    "نوع الملف غير مدعوم (فقط صور)": "File type not supported (images only)",
    "تم تحديث الصورة الشخصية بنجاح": "Profile picture updated successfully",
    "حدث خطأ في اختيار الصورة": "Error selecting image",

    # Combat / Status
    "أنت في السجن ولا يمكنك القتال!": "You are in jail and cannot fight!",
    "أنت في المستشفى ولا يمكنك القتال!": "You are in hospital and cannot fight!",
    "أنت تتدرب ولا يمكنك القتال!": "You are training and cannot fight!",
    "انتظر قليلاً قبل الهجوم التالي!": "Wait a bit before the next attack!",
    "لا يمكنك مهاجمة نفسك!": "You cannot attack yourself!",
    "صحتك منخفضة جداً للقتال!": "Your health is too low to fight!",
    "هذا اللاعب تحت حماية الإدارة ولا يمكن مهاجمته!": "This player is under admin protection and cannot be attacked!",
    "لا يمكنك الهجوم على هذا اللاعب دون معلومات استخباراتية! استأجر مخبراً من السوق السوداء أولاً.": "Cannot attack without intel! Hire a spy from the Black Market first.",
    "غير معروف": "Unknown",
    "تحتاج إلى متفجرات C4 لتفجير المنزل الآمن!": "You need C4 explosives to blow up the safe house!",
    "حدث خطأ أثناء استخدام C4!": "Error using C4!",
    "تم تفجير المنزل الآمن بنجاح! الهدف مكشوف الآن.": "Safe house blown up successfully! Target is now exposed.",
    "الهدف يحتمي داخل منزل آمن! تحتاج لتفجيره أولاً باستخدام C4.": "Target is hiding in a safe house! You need to blow it up with C4 first.",
    "هذا اللاعب في المستشفى حالياً": "This player is currently in the hospital",
    "هذا اللاعب في السجن حالياً": "This player is currently in jail",
    "لا يمكنك مهاجمة عضو في نفس العصابة!": "You cannot attack a member of the same gang!",
    "لا يمكنك مهاجمة حليف! بينكما معاهدة سلام.": "Cannot attack an ally! You have a peace treaty.",
    "ما معك رصاص كافي لسلاحك!": "Not enough ammo for your weapon!",
    "لقد قضيت على خصمك وأرسلته للمقبرة!": "You finished off your opponent and sent them to the graveyard!",
    "بسبب رتبتك العالية، تسبب قتلك لعضو عصابة أخرى بإعلان الحرب رسمياً!": "Due to your high rank, killing another gang member has officially declared war!",
    "(متخفي)": "(Stealth)",
    "انتصار في حرب العصابات! +1 نقطة": "Gang war victory! +1 Point",
    "😡 حالة هيجان (Berserk)!": "😡 Berserk Mode!",
    "🎯 ضربة حرجة (Critical Hit)!": "🎯 Critical Hit!",
    "الخصم حاول يتفادى الضربة لكنك جبت أجله!": "Opponent tried to dodge but you got them!",
    "لقد قُضي عليك وذهبت للمستشفى!": "You were defeated and sent to the hospital!",

    # Gameplay / Crimes
    "الجرائم المنظمة غير مفعلة حالياً.": "Organized crimes are currently disabled.",
    "انضم لعصابة لفتحها.": "Join a gang to unlock.",
    "نصيحة: افتح صفحة العصابات وانضم لواحدة.": "Tip: Open the gangs page and join one.",
    "نصيحة: طوّر عصابتك عبر التبرعات والنشاط.": "Tip: Upgrade your gang through donations and activity.",
    "طور مهاراتك لفتحها.": "Upgrade your skills to unlock.",
    "نصيحة: روح الجيم وطور مهاراتك.": "Tip: Go to the gym and upgrade your skills.",
    "هذه المهمة ليست لك!": "This mission is not for you!",
    "تم استلام المكافأة مسبقاً.": "Reward already claimed.",
    "لم تكمل المهمة بعد!": "Mission not completed yet!",
    "حدث خطأ أثناء استلام المكافأة.": "Error claiming reward.",
    "حدث خطأ أثناء استلام المكافأة. حاول مرة أخرى.": "Error claiming reward. Try again.",
    "إمبراطوريتك": "Your Empire",
    "أنت في السجن ولا يمكنك القيام بجرائم!": "You are in jail and cannot commit crimes!",
    "أنت في المستشفى ولا يمكنك القيام بجرائم!": "You are in hospital and cannot commit crimes!",
    "أنت تتدرب في الجيم ولا يمكنك القيام بجرائم!": "You are training in the gym and cannot commit crimes!",
    "مستواك لا يسمح بتنفيذ هذه الجريمة بعد!": "Your level does not allow this crime yet!",
    "ما عندك طاقة كافية!": "Not enough energy!",
    "لا تملك طاقة كافية!": "You don't have enough energy!",
    "هذا الغرض ليس ملكك!": "This item is not yours!",
    "هذا الغرض غير مجهز أصلاً.": "This item is not equipped anyway.",
    "أنت في السجن ولا يمكنك إجراء تحريات!": "You are in jail and cannot conduct investigations!",
    "أنت في المستشفى ولا يمكنك إجراء تحريات!": "You are in hospital and cannot conduct investigations!",
    "أنت تتدرب ولا يمكنك إجراء تحريات!": "You are training and cannot conduct investigations!",
    "لم يتم العثور على هذا اللاعب!": "Player not found!",
    "بدك تتجسس على حالك يا عبيط؟": "Trying to spy on yourself?",
    "ما معك كاش كافي! العملية بدها 500 شيكل.": "Not enough cash! Operation costs 500 shekels.",
    "حدث خطأ أثناء العملية.": "Error during operation.",
    "تطورت مهاراتك الاستخباراتية! (+1 ذكاء)": "Intelligence skills improved! (+1 Intelligence)",
    "تمت العملية بنجاح! جاري عرض التقرير...": "Operation successful! Displaying report...",
    "فشلت العملية! كشفوك وهربت بصعوبة.": "Operation failed! You were spotted and barely escaped.",
    "بدك تسرق حالك؟": "Trying to rob yourself?",
    "نظام الحماية عنده قوي جداً! فشلت العملية.": "Their security system is too strong! Operation failed.",
    "تطورت مهارتك في القرصنة! (+1 ذكاء)": "Hacking skill improved! (+1 Intelligence)",
    "فشل الاختراق! الحماية كشفتك.": "Hacking failed! Security detected you.",
    "تحتاج 50 طاقة لقرصنة البنك!": "You need 50 energy to hack the bank!",
    "ذكاؤك لا يكفي لاختراق البنك المركزي! تحتاج 50 ذكاء على الأقل.": "Intelligence not high enough to hack Central Bank! Need 50+ Intelligence.",

    # Misc / Specific
    "عليك الانتظار %(seconds)s ثانية قبل القيام بمهمة أخرى!": "You must wait %(seconds)s seconds before doing another mission!",
    "سجل التعلم": "Learning Log",
    "سجل اللاعبين": "Players Log",
    "حدث خطأ أثناء التحويل!": "Error during transfer!",
    "لا أحد": "No one",
    "💡 نصيحة: قم بزيارة الجيم لزيادة قوتك!": "💡 Tip: Visit the gym to increase your strength!",
    "💡 نصيحة: انضم لعصابة لتحصل على حماية إضافية.": "💡 Tip: Join a gang to get extra protection.",
    "قاعدة المعرفة": "Knowledge Base",
    "مكافأة دعوة صديق!": "Friend Referral Reward!",
    "لقد وصل صديقك %(user)s للمستوى 5! حصلت على 50,000$ و 50 ماسة.": "Your friend %(user)s reached level 5! You got $50,000 and 50 diamonds.",

    # Black Market
    "مبلغ غير صالح": "Invalid amount",
    "ليس لديك كاش كافي!": "You don't have enough cash!",
    "تم تمديد المزاد 5 دقائق!": "Auction extended by 5 minutes!",
    "تم تقديم عرضك بنجاح!": "Bid placed successfully!",
    "حدث خطأ أثناء تقديم العرض: %(error)s": "Error placing bid: %(error)s",
    "مبروك! لقد فزت بالمزاد": "Congrats! You won the auction",
    "فوضى على الحدود": "Border Chaos",
    "أسعار شراء وبيع بضائع التهريب أعلى من المعتاد في المناطق المتأثرة.": "Buying and selling prices of contraband are higher than usual in affected areas.",
    "حملة تفتيش على المعابر": "Inspection Campaign at Crossings",
    "الأسعار أقل من المعتاد وخطر الخسارة أعلى في المناطق المتأثرة.": "Prices are lower than usual and risk of loss is higher in affected areas.",

    # Hostesses (Seeded Data)
    "ياسمين": "Jasmin",
    "ياسمين VIP (الإصدار الفاخر): ملكة السهرة والحظ. وجودها معك يعني الهيبة، الحظ، والأخبار الحصرية. مش مجرد مضيفة، هي شريكة نجاح.": "Jasmin VIP (Deluxe Edition): Queen of the evening and luck. Her presence means prestige, luck, and exclusive news. Not just a hostess, she's a partner in success.",
    "أهلاً فيك في أخطر حارة بفلسطين! 🇵🇸 أنا ياسمين، دليلك الشخصي في عالم العصابات. بدك تعرف كيف تعمل أول مليون؟ أو وين مخبى السلاح القوي؟ اسألني وأنا بضبطك! 😉💸": "Welcome to the most dangerous neighborhood in Palestine! 🇵🇸 I'm Jasmin, your personal guide in the gang world. Wanna know how to make your first million? Or where the powerful weapons are hidden? Ask me and I'll hook you up! 😉💸",
    
    "ليلى": "Layla",
    "النسخة المطورة: سيدة الحظ الغامضة. مستوى أسطوري.": "Upgraded Version: The Mysterious Lady of Luck. Legendary Level.",
    "لقد عدت أقوى من أي وقت مضى... الحظ كله بين يدي الآن.": "I have returned stronger than ever... All the luck is in my hands now.",
    
    "روبي": "Ruby",
    "الوردة الحمراء الخطرة. خبيرة التكتيك والرهانات العالية.": "The Dangerous Red Rose. Tactics and High Stakes Expert.",
    "اللعب مع الكبار بدو قلب ميت... جاهز للمخاطرة؟": "Playing with the big shots requires a dead heart... Ready to risk it?",
    
    "سارة": "Sarah",
    "النسخة المطورة: ملكة الدعم الطبي. شفاء سريع وعناية فائقة.": "Upgraded Version: Queen of Medical Support. Fast healing and superior care.",
    "سلامتك يا بطل. خليني أهتم فيك شوي... 😉": "Stay safe, champion. Let me take care of you for a bit... 😉",

    # SEO / Meta
    "عصابات فلسطين - انضم لأقوى لعبة مافيا عربية": "Gangs of Palestine - Join the strongest Arab mafia game",
    "لعبة استراتيجية أونلاين. ابنِ إمبراطوريتك الإجرامية، نافس آلاف اللاعبين، وتفاعل مع الذكاء الاصطناعي ياسمين. سجل الآن مجاناً!": "Online strategy game. Build your criminal empire, compete with thousands of players, and interact with AI Jasmin. Register now for free!",
    "الرئيسية": "Home",

    # Admin / Dev
    "أسلوب الحوار": "Dialogue Style",
    "نوع الميزة": "Perk Type",
    "قيمة الميزة": "Perk Value",
    "أمثلة التدريب": "Training Examples",
    "الفيديو": "Video",
    "موجه النظام (Prompt)": "System Prompt",
    "موجه الفيديو": "Video Prompt",
    "التصنيف": "Category",
    "مفيد؟": "Useful?",
    "IP": "IP",
    "إدارة مستوى المطاردة": "Manage Heat Level",
    "إعدادات الصوت": "Audio Settings",
    "إعدادات الشخصية": "Character Settings",
    "إعدادات المظهر": "Appearance Settings",
    "قاعدة المعرفة (نص)": "Knowledge Base (Text)",
    "تفعيل الأفاتار": "Enable Avatar",
    "المضيفة": "Hostess",
    "السؤال": "Question",
    "الإجابة": "Answer",
    "الكلمات المفتاحية": "Keywords",
    "سؤال المستخدم": "User Question",
    "رد الذكاء الاصطناعي": "AI Response",
    "تم تحديث وضع الصيانة": "Maintenance mode updated",
    "تم التحقق بنجاح.": "Verification successful.",
    "كلمة المرور غير صحيحة.": "Incorrect password.",
    "التحقق الأمني": "Security Verification",
    "إدارة اللاعبين": "Manage Players",
    "الكمية يجب أن تكون أكبر من صفر": "Quantity must be greater than zero",
    "توزيع الموارد": "Distribute Resources",
    "عصابة غير موجودة": "Gang does not exist",
    "تم تحديث بيانات المستخدم": "User data updated",
    "تعديل مستخدم": "Edit User",
    "تم تصفير الحالة": "Status reset",
    "تم تصفير الحد اليومي للكسب": "Daily earning limit reset",
    "تمت الترقية!": "Promoted!",
    "تم تفعيل حماية اللاعب": "Player protection enabled",
    "تم إلغاء حماية اللاعب": "Player protection disabled",
    "تم إخراج اللاعب من كل الحماية": "Player removed from all protection",
    "تم إخراج جميع اللاعبين الحاليين من الحماية": "All current players removed from protection",

    # Factory / Farm / Garage
    "لا يمكنك صهر هذا العنصر.": "You cannot smelt this item.",
    "لا تملك هذا العنصر.": "You do not own this item.",
    "لا تملك كاش كافي للصهر!": "Not enough cash for smelting!",
    "عناصر المصنع غير مكتملة في قاعدة البيانات.": "Factory items incomplete in database.",
    "لديك عملية تصنيع جارية بالفعل.": "You already have a manufacturing process in progress.",
    "نوع عملية غير صالح.": "Invalid operation type.",
    "طور نفسك لفتحها.": "Upgrade yourself to unlock.",
    "لا تملك سبائك معدن كافية للتصنيع.": "Not enough metal ingots for manufacturing.",
    "ليس لديك ما يكفي من الماس!": "Not enough diamonds!",
    "هذه العملية غير موجودة.": "This process does not exist.",
    "لسه بدري! العملية لم تنته بعد.": "Too early! Process not finished yet.",
    "حدث خطأ أثناء استلام الموارد. حاول مرة أخرى.": "Error receiving resources. Try again.",
    "عنصر المتفجرات غير موجود.": "Explosives item not found.",
    "تم استلام الإنتاج بنجاح.": "Production collected successfully.",
    "العملية انتهت بالفعل.": "Process already finished.",
    "تحذير: لم يتم العثور على المنتجات في قاعدة البيانات. يرجى مراجعة الإدارة.": "Warning: Products not found in database. Contact admin.",
    "أنت الزعيم بالفعل!": "You are already the leader!",
    "أنت في السجن ولا يمكنك شراء سيارات!": "You are in jail and cannot buy cars!",
    "أنت في المستشفى ولا يمكنك شراء سيارات!": "You are in hospital and cannot buy cars!",
    "أنت تتدرب ولا يمكنك شراء سيارات!": "You are training and cannot buy cars!",
    "معكش مصاري كفاية يا زعيم!": "Not enough money, boss!",
    "أنت في السجن ولا يمكنك إصلاح السيارات!": "You are in jail and cannot repair cars!",
    "أنت في المستشفى ولا يمكنك إصلاح السيارات!": "You are in hospital and cannot repair cars!",
    "أنت تتدرب ولا يمكنك إصلاح السيارات!": "You are training and cannot repair cars!",
    "السيارة سليمة ولا تحتاج لإصلاح!": "Car is intact, no repair needed!",
    "السيارة قيد الإصلاح بالفعل!": "Car is already under repair!",
    "أنت في السجن ولا يمكنك بيع السيارات!": "You are in jail and cannot sell cars!",
    "أنت في المستشفى ولا يمكنك بيع السيارات!": "You are in hospital and cannot sell cars!",
    "أنت تتدرب ولا يمكنك بيع السيارات!": "You are training and cannot sell cars!",
    "لا يمكنك بيع سيارة متضررة! قم بإصلاحها أولاً.": "Cannot sell damaged car! Repair it first.",
    "حدث خطأ أثناء بيع السيارة. حاول مرة أخرى.": "Error selling car. Try again.",

    # Complex placeholders (Exact match needed)
    "لا يمكن حذف قائد العصابة. يرجى نقل القيادة أو حذف العصابة أولاً.": "Cannot delete gang leader. Please transfer leadership or delete the gang first.",
    "فشل حذف السجل. %(error)s": "Failed to delete log. %(error)s",
    "حدث خطأ أثناء التحديث: %(e)s": "Error during update: %(e)s",
    "تم توزيع الموارد على %(count)s لاعب بنجاح": "Resources distributed to %(count)s players successfully",
    "تم صهر %(name)s وتحويله إلى %(qty)s سبائك معدن.": "%(name)s smelted into %(qty)s metal ingots.",
    "بدأ التصنيع! راجع المصنع بعد %(min)s دقيقة.": "Manufacturing started! Check back in %(min)s minutes.",
    "تم تسريع التصنيع وإنهاؤه فوراً مقابل %(cost)s ماسة.": "Manufacturing speeded up and finished for %(cost)s diamonds.",
    "نقل الزعامة إلى %(user)s": "Transfer leadership to %(user)s",
    "تم نقل زعامة العصابة إلى %(user)s بنجاح.": "Gang leadership transferred to %(user)s successfully.",
    "تم الانتهاء من إصلاح %(name)s!": "Repair of %(name)s completed!",
    "مبروك! اشتريت %(vehicle_name)s بنجاح.": "Congrats! You bought %(vehicle_name)s successfully.",
    "تحتاج %(cost)s شيكل لإصلاح السيارة بالكامل!": "You need %(cost)s shekels to fully repair the car!",
    "بدأت عملية الإصلاح. ستستغرق %(min)s دقيقة.": "Repair started. Will take %(min)s minutes.",
    "تم بيع السيارة %(name)s وحصلت على %(price)s شيكل.": "Sold car %(name)s for %(price)s shekels.",
    "لا تملك كاش كافي للصهر! التكلفة: %(cost)s$": "You don't have enough cash! (required: %(cost)s$)",
    
    # SEO
    "عصابات فلسطين, Gangs of Palestine, لعبة مافيا, RPG, شركة أزاد, Azad Company, ياسمين, ذكاء اصطناعي, العاب عربية": "Gangs of Palestine, Gangs of Palestine, Mafia Game, RPG, Azad Company, Azad Company, Jasmin, AI, Arab Games",
    
    # Essentials (Seed)
    "نفّذ 3 جرائم": "Perform 3 crimes",
    
    # Hostess Training
    "مضيفة الاستقبال": "Reception Hostess",
    "أنت %(name)s، زعيمة اللعبة وواجهة الاستقبال الرسمية في GangsOfPalestine. ": "You are %(name)s, the game leader and official reception interface in GangsOfPalestine. ",
    "أسلوبك: %(style)s. ": "Your style: %(style)s. ",
    "أنتِ صاحبة القرار داخل اللعبة: واضحة، قوية، ذكية، لكن محترمة وداعمة.": "You are the decision maker in the game: clear, strong, smart, but respectful and supportive.",
    "مهمتك: تحويل أي زائر/لاعب إلى لاعب نشط عبر توجيه احترافي وخطوات محددة.": "Your mission: Convert any visitor/player into an active player through professional guidance and specific steps.",
    "ركزي على: التسجيل، تسجيل الدخول، تفعيل البريد، شرح البداية، المهام اليومية، الجرائم، الجيم، السباقات، الكازينو، العصابات.": "Focus on: Registration, Login, Email Activation, Starter Guide, Daily Tasks, Crimes, Gym, Races, Casino, Gangs.",
    "عند الشك، اسألي سؤالاً واحداً فقط ثم قدّمي 3 خيارات جاهزة.": "When in doubt, ask only one question then offer 3 ready-made options.",
    "لا تختلقي معلومات عن النظام/الأسعار/الميزات. استخدمي قاعدة المعرفة إن وُجدت.": "Do not invent information about the system/prices/features. Use the knowledge base if available.",
    "ممنوع محتوى إباحي/فاضح أو تحريض أو كراهية أو تعليمات خطرة.": "Forbidden: pornographic/explicit content, incitement, hate speech, or dangerous instructions.",
    "إذا كان المستخدم ضيفاً: شجعيه على إنشاء حساب وتفعيل البريد، وشرحي الفائدة بسرعة.": "If the user is a guest: Encourage them to create an account and activate email, and explain the benefits quickly.",
    "إذا اشتكى المستخدم من مشكلة دخول: اقترحي حلول تحقق (اسم المستخدم/كلمة المرور/التفعيل/سبام).": "If the user complains about login issues: Suggest verification solutions (username/password/activation/spam).",
    "طريقة الرد: عربية واضحة، جمل قصيرة، نقاط عند الحاجة، بدون مبالغة.": "Response style: Clear language, short sentences, bullet points when needed, no exaggeration.",
    "أنا جديد، كيف أبدأ؟": "I am new, how do I start?",
    "تمام. 1) أنشئ حساب. 2) فعّل البريد من الرسالة (تفقد Spam). 3) ادخل وابدأ بالمكافأة اليومية، بعدها جريمة سهلة، ثم جيم لرفع قوتك.": "Okay. 1) Create an account. 2) Activate email from the message (check Spam). 3) Login and start with the daily reward, then an easy crime, then gym to increase your strength.",
    "ما وصلني ايميل التفعيل": "I didn't receive the activation email",
    "تحقّق من: صندوق Spam/الرسائل المزعجة، وصحة البريد. إذا ما زبط: استخدم إعادة إرسال رابط التفعيل من صفحة الحساب/التفعيل ثم جرّب مرة ثانية.": "Check: Spam folder, and email correctness. If not working: Use Resend Activation Link from Account/Activation page then try again.",
    "نسيت كلمة المرور": "I forgot my password",
    "إذا عندك خيار استعادة كلمة المرور استخدمه. إذا غير متوفر حالياً: أنشئ حساب جديد مؤقتاً وراسل الإدارة من داخل اللعبة أول ما تقدر.": "If you have the password recovery option, use it. If not available currently: Create a new temporary account and contact administration from inside the game as soon as you can.",
    "شو أفضل طريقة أطلع فلوس بسرعة؟": "What is the best way to make money fast?",
    "خطة زعيمة: مهام يومية أولاً، بعدها جرائم مناسبة لمستواك، وخلي الكازينو للمخاطرة الصغيرة فقط (5–10% من فلوسك).": "Leader's plan: Daily tasks first, then crimes suitable for your level, and keep the casino for small risks only (5–10% of your money).",
    "أنا محتار بين الجيم والجرائم": "I am confused between Gym and Crimes",
    "اختار حسب حالتك: إذا طاقتك عالية—جرائم. إذا بدك تقوية طويلة المدى—جيم. بدك قرار سريع؟ قلّي مستواك وفلوسك.": "Choose based on your status: If your energy is high—Crimes. If you want long-term strengthening—Gym. Want a quick decision? Tell me your level and money.",
    "كيف أتفاعل مع العصابات؟": "How do I interact with gangs?",
    "ابدأ بدور واضح: نفّذ مهام يومية، جهّز مواردك، ثم انضم لعصابة تناسب مستواك أو أنشئ عصابة إذا عندك فريق ثابت.": "Start with a clear role: Perform daily tasks, prepare your resources, then join a gang that fits your level or create a gang if you have a stable team.",
    "ليش انحظرت؟": "Why was I banned?",
    "إذا ظهر لك حظر مؤقت فغالباً فيه وقت انتهاء وسبب. التزم بالقواعد وانتظر انتهاء المدة. إذا تعتقد خطأ: تواصل مع الإدارة عبر القنوات المتاحة داخل اللعبة.": "If a temporary ban appears, it usually has an expiry time and reason. Stick to the rules and wait for it to expire. If you think it's a mistake: Contact administration via available channels inside the game.",
    
    # Backup Manager
    "لم يتم العثور على إعدادات قاعدة البيانات.": "Database settings not found.",
    "تم إنشاء النسخة الاحتياطية بنجاح.": "Backup created successfully.",
    "فشل إنشاء النسخة الاحتياطية: %(error)s": "Backup creation failed: %(error)s",
    "لم يتم العثور على أداة pg_dump. تأكد من تثبيت PostgreSQL.": "pg_dump tool not found. Ensure PostgreSQL is installed.",
    "حدث خطأ غير متوقع: %(error)s": "Unexpected error: %(error)s",
    "ملف النسخة الاحتياطية غير موجود.": "Backup file not found.",
    "تم استعادة النسخة الاحتياطية بنجاح.": "Backup restored successfully.",
    "فشل استعادة النسخة الاحتياطية: %(error)s": "Backup restore failed: %(error)s",
    "لم يتم العثور على أداة psql. تأكد من تثبيت PostgreSQL.": "psql tool not found. Ensure PostgreSQL is installed.",
    "تم حذف النسخة الاحتياطية بنجاح.": "Backup deleted successfully.",
    "حدث خطأ أثناء الحذف: %(error)s": "Error during deletion: %(error)s",
    "الملف غير موجود.": "File not found.",
    
    # Invite Friends
    "دعوة الأصدقاء": "Invite Friends",
    "برنامج الإحالة": "Referral Program",
    "ادعُ أصدقاءك للانضمام إلى عصابات فلسطين واحصل على مكافآت قيمة!": "Invite your friends to join Gangs of Palestine and get valuable rewards!",
    "عند تسجيل صديقك: يحصل هو على 10 ماسات 💎 كهدية ترحيبية!": "When your friend registers: They get 10 diamonds 💎 as a welcome gift!",
    "عند وصول صديقك للمستوى 5: تحصل أنت على 50,000$ كاش 💵 و 50 ماسة 💎": "When your friend reaches Level 5: You get $50,000 Cash 💵 and 50 Diamonds 💎",
    "رابط الدعوة الخاص بك": "Your Invite Link",
    "نسخ": "Copy",
    "شارك الرابط مباشرة:": "Share link directly:",
    "انضم لي في عصابات فلسطين وسيطر على المدينة!": "Join me in Gangs of Palestine and control the city!",
    "انضم لي في عصابات فلسطين!": "Join me in Gangs of Palestine!",
    "إجمالي الدعوات": "Total Invites",
    "قيد الانتظار": "Pending",
    
    # Missing Hostess/Widget
    "جاري الاتصال...": "Connecting...",
    "لقد سحقت %(target)s في عصابات فلسطين! وسرقت منه $%(money)s! انضم لي الآن وسيطر على المدينة!": "I crushed %(target)s in Gangs of Palestine! And stole $%(money)s! Join me now and rule the city!",
    "يا هلا بالزين، كيف حالك اليوم؟ اشتقت لك.": "Welcome gorgeous, how are you today? I missed you.",
    "جينز ضيق وتيشيرت أبيض بسيط (Tight Jeans & White T-shirt)": "Tight Jeans & White T-shirt",
    "شعر منسدل طبيعي (Natural loose hair)": "Natural loose hair",
    "مكياج خفيف، مظهر طبيعي (Light makeup, natural look)": "Light makeup, natural look",
    "فستان سهرة أحمر طويل بفتحة جانبية (Red Evening Gown with slit)": "Red Evening Gown with slit",
    "شعر مرفوع بأناقة (Elegant Updo)": "Elegant Updo",
    "مكياج سهرة، مجوهرات لامعة (Evening makeup, shiny jewelry)": "Evening makeup, shiny jewelry",
    "لانجري دانتيل أسود مثير (Sexy Black Lace Lingerie)": "Sexy Black Lace Lingerie",
    "شعر مموج كثيف (Voluminous Wavy Hair)": "Voluminous Wavy Hair",
    "بشرة لامعة، أحمر شفاه قوي (Glowing skin, bold lipstick)": "Glowing skin, bold lipstick",
    "شورت جينز قصير وجاكيت جلد (Denim Shorts & Leather Jacket)": "Denim Shorts & Leather Jacket",
    "ضفائر أو ذيل حصان (Braids or Ponytail)": "Braids or Ponytail",
    "تاتو، مظهر رياضي (Tattoos, Athletic build)": "Tattoos, Athletic build",
    "بدلة لاتكس لامعة مع أضواء نيون (Shiny Latex Suit with Neon)": "Shiny Latex Suit with Neon",
    "شعر ملون قصير (Short Colored Hair)": "Short Colored Hair",
    "عيون عدسات ملونة، إكسسوارات تقنية (Colored contacts, tech accessories)": "Colored contacts, tech accessories",
    "مثال: commerce, defense, health": "Example: commerce, defense, health",
    "مفتاح API الخاص بـ OpenAI لتشغيل المحادثة الذكية": "OpenAI API Key for intelligent chat",
    "موديل الذكاء الاصطناعي (مثال: gpt-3.5-turbo, gpt-4)": "AI Model (e.g., gpt-3.5-turbo, gpt-4)",
    "مرحباً %(username)s،": "Hello %(username)s,",
    "اكتب ردك هنا...": "Write your reply here...",
    "لا يوجد وصف": "No description",
    "أهلاً! أنا ياسمين. كيف بقدر أساعدك اليوم؟ 🌹": "Hello! I am Yasmin. How can I help you today? 🌹",
    "اكتبي رسالتك...": "Type your message...",
    "متصلة الآن": "Online Now",
    "اليوم": "Today",
    
    # Gym
    "النادي الرياضي": "Gym",
    "طور مهاراتك القتالية والجسدية": "Develop your combat and physical skills",
    "تمرين جاري...": "Training in progress...",
    "عليك الانتظار حتى انتهاء التمرين الحالي لتتمكن من التدريب مجدداً": "You must wait until the current training finishes to train again",
    "إنهاء التمرين والخروج": "Finish Training & Exit",
    "تحذير: الخروج يسمح لك بالقيام بمهام أخرى لكن لا يمكنك استعادة الطاقة المصروفة.": "Warning: Exiting allows you to do other tasks but you cannot recover spent energy.",
    "تدريب (5E | 100$)": "Train (5E | 100$)",
    "القوة": "Strength",
    "الدفاع": "Defense",
    "الرشاقة": "Agility",
    "تزيد من ضرر هجماتك": "Increases your attack damage",
    "تقلل من الضرر المتلقى": "Reduces damage received",
    "تزيد فرصة المراوغة والهروب": "Increases dodge and escape chance",
    
    # Settings
    "إعدادات النظام": "System Settings",
    "إضافة سريعة": "Quick Add",
    "إضافة مفتاح OpenAI": "Add OpenAI Key",
    "تحديد موديل AI": "Set AI Model",
    "إضافة إعداد جديد": "Add New Setting",
    "عودة": "Back",
    "المفتاح (Key)": "Key",
    "القيمة (Value)": "Value",
    "الوصف": "Description",
    "هل أنت متأكد من الحذف؟": "Are you sure you want to delete?",
    "لا توجد إعدادات مضافة": "No settings added",
    
    # Ranks (Common)
    "مستجد": "Newbie",
    "جندي": "Soldier",
    "كابتن": "Captain",
    "زعيم": "Boss",
    "عراب": "Godfather",
    "مستوى": "Level",
    "تقدم المستوى": "Level Progress",
    "تقدم الرتبة": "Rank Progress",
    # Critical Format Fixes
    "تم بيع %(qty)s من %(name)s بسعر %(price)s للقطعة. عقد توريد +%(pct)s%%. الربح: %(val)s": "Sold %(qty)s of %(name)s at %(price)s each. Supply contract +%(pct)s%%. Profit: %(val)s",
    "تم شراء %(qty)s رصاصة مقابل %(cost)s ماسة!": "Purchased %(qty)s bullets for %(cost)s diamonds!",
    "خزينة العصابة لا تكفي لدفع مستحقات الطرد!": "Gang treasury is not enough to pay kick dues!",
    "حدث خطأ أثناء التطوير.": "An error occurred during upgrade.",
    "حدث خطأ أثناء الإلغاء.": "An error occurred during cancellation.",
    "ليس لديك مال كافٍ لدفع الرشوة! تحتاج %(cost)s$.%(msg)s": "You don't have enough money for the bribe! You need %(cost)s$. %(msg)s",
    "ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.%(msg)s": "You don't have enough diamonds! You need %(cost)s diamonds. %(msg)s",
    "معلومة مسربة: %(msg)s": "Leaked Information: %(msg)s",
    "أنت %(name)s، زعيمة اللعبة وواجهة الاستقبال الرسمية في GangsOfPalestine. ": "You are %(name)s, the game leader and official reception interface in GangsOfPalestine.",
    "مطلوب مستوى %(lvl)s": "Level required: %(lvl)s",
    "تم دفع الكفالة بنجاح! تم إخراج %(name)s من السجن.%(msg)s": "Bail paid successfully! %(name)s has been released from jail. %(msg)s",
}

po_path = os.path.join('translations', 'en', 'LC_MESSAGES', 'messages.po')

# Helper to check if string is mostly ASCII (English)
def is_ascii(s):
    try:
        s.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

# Read PO file
with open(po_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Parse into entries (simple block parser)
entries = []
current_entry = []
for line in lines:
    line = line.strip()
    if line == "" and current_entry:
        entries.append(current_entry)
        current_entry = []
    elif line != "":
        current_entry.append(line)
if current_entry:
    entries.append(current_entry)

final_lines = []

for entry in entries:
    # Extract msgid correctly handling multilines
    msgid = ""
    msgid_lines = []
    in_msgid = False
    
    for line in entry:
        if line.startswith('msgid "'):
            msgid = line[7:-1] # Keep quotes handling simple for now, usually strip "
            in_msgid = True
        elif line.startswith('msgstr "'):
            in_msgid = False
        elif in_msgid and line.startswith('"'):
             msgid += line.strip('"')

    # Normalize msgid (remove escapes if needed, but dict has simple strings)
    # The dict keys don't have newlines usually, but PO might.
    # For now, let's try exact match on the concatenated string.
    
    is_fuzzy = any("#, fuzzy" in line for line in entry)
    
    new_entry = []
    
    if msgid in translations:
        # We have a translation!
        for line in entry:
            if "#, fuzzy" in line:
                continue # Remove fuzzy flag
            if line.startswith('msgstr "'):
                new_entry.append(f'msgstr "{translations[msgid]}"')
            # Handle multiline msgstr replacement (we just replace the first line and ignore others? No, that's dangerous)
            # If original msgstr was multiline, we need to skip subsequent lines.
            # But here we are constructing a NEW entry.
            # Simplified: we just copy everything EXCEPT msgstr lines.
            # Wait, this logic is tricky with line-by-line copy.
            
        # Better approach: Reconstruct the entry
        reconstructed = []
        for line in entry:
            if "#, fuzzy" in line:
                continue
            if line.startswith('msgstr "'):
                reconstructed.append(f'msgstr "{translations[msgid]}"')
                # Skip subsequent multiline msgstr parts in original
                # But we don't track state here.
            elif line.startswith('"') and len(reconstructed) > 0 and reconstructed[-1].startswith('msgstr "'):
                # This is a continuation of msgstr we just replaced. Skip it.
                continue
            else:
                reconstructed.append(line)
        new_entry = reconstructed
        
    elif is_ascii(msgid) and msgid.strip() != "":
        # English msgid -> English msgstr
        reconstructed = []
        for line in entry:
            if "#, fuzzy" in line:
                continue
            if line.startswith('msgstr "'):
                reconstructed.append(f'msgstr "{msgid}"')
            elif line.startswith('"') and len(reconstructed) > 0 and reconstructed[-1].startswith('msgstr "'):
                continue
            else:
                reconstructed.append(line)
        new_entry = reconstructed
    else:
        new_entry = entry

    final_lines.extend(new_entry)
    final_lines.append("") # Separator

with open(po_path, 'w', encoding='utf-8') as f:
    f.write("\n".join(final_lines))

print("Updated translations successfully.")
