"""Bounded Arabic app commands; no translation of clinical records or stimuli."""

import re


def normalize(text):
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
    return re.sub(r"\s+", " ", text).strip().rstrip(".!?؟")


ALIASES = {
    "افتح الاعدادات": "open settings",
    "الاعدادات": "open settings",
    "افتح الصفحة الرئيسية": "open home",
    "افتح الرئيسية": "open home",
    "افتح خطتي": "open plan",
    "اعرض خطتي": "open plan",
    "افتح الرسائل": "open messages",
    "افتح الدعم": "open support",
    "افتح الفحص": "open my check",
    "افتح الملخص الاسبوعي": "open weekly summary",
    "كبر الخط": "larger text",
    "اجعل الخط اكبر": "larger text",
    "افتح الاعدادات وكبر الخط": "settings larger",
    "اقرا خطتي": "read my plan",
    "اقرا الخطة": "read my plan",
    "ماذا افعل الان": "what should i do",
    "ما الخطوة التالية": "next step",
    "كرر هذه الخطوة": "repeat this step",
    "انتهيت": "i finished",
    "افعل هذا لاحقا": "do this later",
    "لاحقا": "do this later",
    "هل وافقت عائلتي": "did my family accept",
    "حالة طلب المساعدة": "help request status",
    "ساعدني": "help me",
    "توقف": "stop",
    "الغاء": "cancel",
    "الغ ذلك": "cancel that",
}


def command(text):
    if not re.search(r"[\u0600-\u06ff]", text):
        return text
    value = normalize(text)
    if any(s in value for s in ["الم في الصدر", "لا استطيع التنفس", "ارتباك مفاجئ"]):
        return "chest pain"
    # Negated or ambiguous Arabic never becomes an execution proposal.
    if re.search(r"(?<!\w)(?:لا|ليس|لن|بدون|مش|مو|ماتفتح|لاتفتح)(?!\w)", value):
        return "do not perform an action"
    return ALIASES.get(value, "do not perform an action")


def localize(result, locale):
    if locale != "ar":
        return result
    result = dict(result)
    intent = result["intent"]
    pages = {
        "home": "الصفحة الرئيسية",
        "check": "الفحص",
        "companion": "المرافق",
        "plan": "خطتي",
        "support": "الدعم",
        "settings": "الإعدادات",
        "messages": "الرسائل",
        "weekly": "الملخص الأسبوعي",
    }
    if intent == "clinical_review":
        result["explanation"] = (
            "لا تنتظر هذا التطبيق. استخدم وسيلة طلب المساعدة العاجلة المعتمدة محليًا أو اتصل بشخص يمكنه مساعدتك الآن. لم يتم الاتصال بأي خدمة طوارئ."
        )
    elif intent == "navigate":
        result["explanation"] = (
            "سأفتح " + pages.get(result.get("screen"), "الصفحة المطلوبة") + "."
        )
    elif intent == "set_text_size":
        result["explanation"] = "هل تريد تكبير النص؟ يرجى التأكيد."
    elif intent == "prepare_help":
        result["explanation"] = (
            "اختر جهة اتصال لديها صلاحية حالية، ثم أكّد طلبك. لم يتم إرسال الطلب."
        )
    elif intent == "stop":
        result["explanation"] = "تم التوقف. لم يتم تأكيد أي إجراء جديد."
    elif intent == "task_response":
        result["explanation"] = (
            "هل تريد تسجيل النشاط "
            + result["task"]["title"]
            + (" كمؤجل؟" if result["response"] == "deferred" else " كمكتمل؟")
            + " يرجى التأكيد."
        )
    elif intent in {"coach_task", "read_plan", "help_status"}:
        # Approved instructions and names are retained in their original language.
        result["original_language_content"] = True
    else:
        result["explanation"] = (
            "يمكنني فتح صفحة، أو عرض خطتك المعتمدة، أو إرشادك إلى نشاط، أو تكبير النص، أو تجهيز طلب مساعدة. يرجى اختيار إجراء واحد بوضوح."
        )
    result["locale"] = "ar"
    result["language_review"] = (
        "engineering_reviewed_draft; qualified clinical/linguistic sign-off pending"
    )
    return result
