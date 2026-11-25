import asyncio
import html
import logging
import os
import re
from typing import Any
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import Database
from services.etisalat import EtisalatService
import فودافون
from settings import load_settings

BOT_NAME = "Mikey Bot"
logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@mikeyxii")
CHANNEL_URL = "https://t.me/mikeyxii"
WHATSAPP_GROUP_URL = "https://chat.whatsapp.com/LjEIn0lVbrtCreYHZDwNHd?s=cl&p=a&iam=2"


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📦 الاشتراك في باقات Plus (فودافون)", callback_data="menu:subscribe")],
            [InlineKeyboardButton("🎁 هدايا اتصالات (سوشيال وستريمنج)", callback_data="menu:etisalat_gift")],
            [InlineKeyboardButton("⚡ 1 جيجا فودافون (قريباً)", callback_data="menu:vf_1gb_soon")],
            [InlineKeyboardButton("💬 جروب الواتساب (600+ عضو)", url=WHATSAPP_GROUP_URL)],
            [
                InlineKeyboardButton("👤 حسابي", callback_data="menu:account"),
                InlineKeyboardButton("📋 طلباتي", callback_data="menu:orders"),
            ],
            [
                InlineKeyboardButton("💳 الباقات المتاحة", callback_data="menu:packages"),
                InlineKeyboardButton("🆘 الدعم الفني", callback_data="menu:support"),
            ],
            [InlineKeyboardButton("ℹ️ حول البوت", callback_data="menu:about")],
        ]
    )


def etisalat_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📱 500 ميجا سوشيال", callback_data="etisalat_gift:social")],
            [InlineKeyboardButton("🎬 500 ميجا ستريمنج", callback_data="etisalat_gift:streaming")],
            [InlineKeyboardButton("🚀 تفعيل الهديتين معاً (1 جيجا)", callback_data="etisalat_gift:all")],
            [InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="menu:home")],
        ]
    )


def back_keyboard(target: str = "menu:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء والعودة", callback_data=target)]])


def sub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 قناة البوت", url=CHANNEL_URL)],
            [InlineKeyboardButton("💬 جروب الواتساب (600+ عضو)", url=WHATSAPP_GROUP_URL)],
            [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_subscription")],
        ]
    )


def admin_keyboard(paused: bool) -> InlineKeyboardMarkup:
    pause_label = "▶️ استئناف استقبال الطلبات" if paused else "⏸ إيقاف استقبال الطلبات"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats")],
            [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin:users")],
            [InlineKeyboardButton("📋 أحدث الطلبات", callback_data="admin:orders")],
            [InlineKeyboardButton(pause_label, callback_data="admin:toggle_pause")],
            [InlineKeyboardButton("📣 إرسال إشعار", callback_data="admin:broadcast")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:home")],
        ]
    )


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.application.bot_data["db"]


def _admin_id(context: ContextTypes.DEFAULT_TYPE) -> int:
    return context.application.bot_data["admin_id"]


def _register_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    user = update.effective_user
    if user is None:
        raise RuntimeError("تعذر تحديد المستخدم")
    _db(context).upsert_user(user.id, user.username)
    return _db(context).get_user(user.id) or {}


def _clear_session_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("action", None)
    context.user_data.pop("temp_phone", None)
    context.user_data.pop("etisalat_phone", None)
    context.user_data.pop("etisalat_password", None)
    context.user_data.pop("etisalat_gift_type", None)
    context.user_data.pop("auth_flow_target", None)


async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """التحقق من اشتراك المستخدم في قناة البوت الإجبارية"""
    bot = getattr(context, "bot", None) or getattr(getattr(context, "application", None), "bot", None)
    if not bot or not hasattr(bot, "get_chat_member"):
        return True

    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in ("creator", "administrator", "member")
    except TelegramError as e:
        error_msg = str(e).lower()
        if "admin" in error_msg or "administrator" in error_msg:
            logger.error("⚠️ يجب رفع البوت كمشرف (Admin) في القناة %s حتى يستطيع التحقق من اشتراك الأعضاء!", REQUIRED_CHANNEL)
            return True
        logger.info("المستخدم %s غير مشترك في القناة %s: %s", user_id, REQUIRED_CHANNEL, e)
        return False
    except Exception as e:
        logger.warning("خطأ غير متوقع عند فحص اشتراك القناة للمستخدم %s: %s", user_id, e)
        return False


SUB_REQUIRED_MESSAGE = (
    "⚠️ **عذراً عزيزي!**\n\n"
    "يجب عليك الاشتراك في قناة البوت أولاً لاستخدام الخدمات والعروض!\n"
    f"🔗 القناة: {REQUIRED_CHANNEL}\n\n"
    "💬 ولا تنسوا الانضمام هنا إلى الجروب الخاص بنا على الواتساب (أكثر من 600 عضو):\n"
    f"{WHATSAPP_GROUP_URL}\n\n"
    "اشترك في القناة ثم اضغط على زر **(🔄 تحقق من الاشتراك)** للمتابعة 👇"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _register_user(update, context)
    if user.get("is_blocked"):
        await update.effective_message.reply_text("تم إيقاف وصولك إلى Mikey Bot.")
        return

    subscribed = await check_subscription(update.effective_user.id, context)
    if not subscribed:
        await update.effective_message.reply_text(
            SUB_REQUIRED_MESSAGE,
            reply_markup=sub_keyboard(),
        )
        return

    _clear_session_data(context)
    await update.effective_message.reply_text(
        f"أهلاً بك في {BOT_NAME} 👋\n"
        "💬 ولا تنسوا الانضمام إلى جروب الواتساب الخاص بنا (أكثر من 600 عضو):\n"
        f"{WHATSAPP_GROUP_URL}\n\n"
        "اختر الخدمة التي تريدها من القائمة:",
        reply_markup=main_keyboard(),
    )


async def _show_home(query: Any) -> None:
    await query.edit_message_text(
        f"القائمة الرئيسية لـ {BOT_NAME}:\n"
        "💬 ولا تنسوا الانضمام إلى جروب الواتساب الخاص بنا (أكثر من 600 عضو):\n"
        f"{WHATSAPP_GROUP_URL}\n\n"
        "اختر الخدمة التي تريدها:",
        reply_markup=main_keyboard(),
    )


def _order_status(status: str) -> str:
    return {"pending": "قيد المعالجة", "success": "ناجح", "failed": "فاشل"}.get(
        status, "غير معروف"
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or update.effective_user is None:
        return
    await query.answer()
    data = query.data or ""
    current_user = update.effective_user
    user = _register_user(update, context)
    if user.get("is_blocked") and current_user.id != _admin_id(context):
        await query.edit_message_text("تم إيقاف وصولك إلى Mikey Bot.")
        return

    if data == "check_subscription":
        subscribed = await check_subscription(current_user.id, context)
        if subscribed:
            await query.answer("✅ تم التحقق من اشتراكك بنجاح!", show_alert=True)
            await _show_home(query)
        else:
            await query.answer("❌ لم تقم بالاشتراك في القناة بعد! اشترك ثم حاول مجدداً.", show_alert=True)
        return

    # Enforce Channel Subscription for all buttons
    subscribed = await check_subscription(current_user.id, context)
    if not subscribed:
        await query.answer("⚠️ يجب الاشتراك في قناة البوت أولاً!", show_alert=True)
        await query.edit_message_text(SUB_REQUIRED_MESSAGE, reply_markup=sub_keyboard())
        return

    if data == "menu:home":
        context.user_data.pop("support_waiting", None)
        _clear_session_data(context)
        if current_user.id == _admin_id(context):
            context.user_data.pop("broadcast_state", None)
            context.user_data.pop("broadcast_text", None)
        await _show_home(query)
    elif data == "menu:account":
        await query.edit_message_text(
            f"👤 حسابك في {BOT_NAME}\n"
            f"🆔 Telegram ID: {current_user.id}\n"
            "🔒 الخصوصية والأمان: لا يتم حفظ بيانات الحسابات تلقائياً، وتُطلب البيانات في كل عملية لتسهيل الاستخدام بأكثر من رقم.\n",
            reply_markup=back_keyboard(),
        )
    elif data == "menu:orders":
        orders = _db(context).get_orders(current_user.id)
        if not orders:
            text = f"📋 طلباتك في {BOT_NAME}\nلا توجد طلبات مسجلة."
        else:
            lines = [
                f"#{order['id']} — {html.escape(order['package_name'])} — "
                f"{_order_status(order['status'])} — {order['created_at']}"
                for order in orders
            ]
            text = f"📋 طلباتك في {BOT_NAME}\n" + "\n".join(lines)
        await query.edit_message_text(text, reply_markup=back_keyboard())
    elif data == "menu:etisalat_gift":
        if _db(context).orders_paused():
            await query.edit_message_text(f"⏸ استقبال الطلبات متوقف مؤقتاً في {BOT_NAME}.", reply_markup=back_keyboard())
            return
        await query.edit_message_text(
            "🎁 اختر هدايا اتصالات المتاحة للتفعيل:",
            reply_markup=etisalat_keyboard(),
        )
    elif data == "menu:vf_1gb_soon":
        await query.edit_message_text(
            "⚡ 1 جيجا فودافون مجاناً\n\n"
            "⏳ هذه الخدمة قيد التطوير وستكون متاحة قريباً جداً داخل البوت!",
            reply_markup=back_keyboard(),
        )
    elif data.startswith("etisalat_gift:"):
        gift_type = data.split(":")[1]
        context.user_data["etisalat_gift_type"] = gift_type
        context.user_data["action"] = "awaiting_etisalat_phone"
        await query.edit_message_text(
            "📱 [1/3] يرجى إرسال رقم اتصالات الخاص بك (11 رقم يبدأ بـ 011):",
            reply_markup=back_keyboard("menu:etisalat_gift"),
        )
    elif data in ("menu:packages", "menu:subscribe"):
        if data == "menu:subscribe" and _db(context).orders_paused():
            await query.edit_message_text(f"⏸ استقبال الطلبات متوقف مؤقتاً في {BOT_NAME}.", reply_markup=back_keyboard())
            return

        context.user_data["auth_flow_target"] = data
        context.user_data["action"] = "awaiting_phone"
        await query.edit_message_text("📱 [1/2] لعرض الباقات أو الاشتراك، يرجى إرسال رقم فودافون الخاص بك في رسالة (11 رقم يبدأ بـ 01):", reply_markup=back_keyboard())
    elif data == "menu:support":
        context.user_data["support_waiting"] = True
        await query.edit_message_text(
            f"🆘 الدعم الفني — {BOT_NAME}\nأرسل رسالتك الآن كنص، وسيتم تحويلها إلى الإدارة.",
            reply_markup=back_keyboard(),
        )
    elif data == "menu:about":
        await query.edit_message_text(
            f"ℹ️ {BOT_NAME}\nبوت عربي لإدارة طلبات باقات فودافون وهدايا اتصالات (سوشيال وستريمنج).\n"
            "تطبيق إدارة العروض والحسابات الشخصية بشكل مؤتمت وآمن بدون حفظ بيانات الحسابات.\n\n"
            f"💬 جروب الواتساب: {WHATSAPP_GROUP_URL}",
            reply_markup=back_keyboard(),
        )
    elif data == "menu:admin":
        if current_user.id != _admin_id(context):
            await query.edit_message_text("هذا القسم مخصص للإدارة فقط.")
            return
        context.user_data.pop("broadcast_state", None)
        context.user_data.pop("broadcast_text", None)
        await query.edit_message_text(
            f"🛠 لوحة إدارة {BOT_NAME}",
            reply_markup=admin_keyboard(_db(context).orders_paused()),
        )
    elif data.startswith("vf_pkg:"):
        await _handle_package_selection(update, context, data)
    elif data.startswith("admin:user:"):
        await _handle_user_toggle(update, context, data)
    elif data.startswith("admin:"):
        await _handle_admin_callback(update, context, data)
    else:
        await query.edit_message_text(
            "هذا الخيار غير متاح.", reply_markup=back_keyboard()
        )


async def _process_vodafone_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE, msg_target: Any, phone: str, password: str, target_action: str
) -> None:
    async def _edit(text: str, reply_markup=None):
        if hasattr(msg_target, "edit_text"):
            await msg_target.edit_text(text, reply_markup=reply_markup)
        elif hasattr(msg_target, "edit_message_text"):
            await msg_target.edit_message_text(text, reply_markup=reply_markup)

    await _edit("⏳ جاري تسجيل الدخول لحساب أنا فودافون...")
    auth_result = await asyncio.to_thread(فودافون.plus_login, phone, password)
    if not auth_result.get("success"):
        await _edit(
            f"❌ فشل تسجيل الدخول: {auth_result.get('message')}\nيرجى إعادة المحاولة والتأكد من صحة البيانات.",
            reply_markup=back_keyboard()
        )
        return

    token = auth_result["token"]
    await _edit("⏳ جاري جلب باقات Plus المتاحة...")
    data_response = await asyncio.to_thread(فودافون.get_plus_packages, token, phone)
    if not data_response:
        await _edit("❌ فشل جلب الباقات، يرجى إعادة المحاولة.", reply_markup=back_keyboard())
        return

    packages = await asyncio.to_thread(فودافون.parse_plus_packages, data_response)
    if not packages:
        await _edit("لا توجد باقات Plus متاحة على هذا الرقم حالياً.", reply_markup=back_keyboard())
        return

    if target_action == "menu:packages":
        lines = ["📦 باقات Plus المتاحة لك:"]
        for pkg in packages:
            lines.append(f"- {pkg['name']} بـ {pkg['price']}ج (سعة {pkg['quota']})")
        await _edit("\n".join(lines), reply_markup=back_keyboard())
    elif target_action == "menu:subscribe":
        context.user_data["vf_packages"] = packages
        context.user_data["vf_token"] = token
        context.user_data["vf_phone"] = phone

        rows = []
        for pkg in packages:
            rows.append([InlineKeyboardButton(f"{pkg['name']} - {pkg['price']}ج", callback_data=f"vf_pkg:{pkg['index']}")])
        rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu:home")])
        await _edit("اختر الباقة التي تود الاشتراك بها:", reply_markup=InlineKeyboardMarkup(rows))


async def _handle_package_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    query = update.callback_query
    index = int(data.split(":")[1])
    packages = context.user_data.get("vf_packages", [])
    selected = next((p for p in packages if p["index"] == index), None)
    if not selected:
        await query.edit_message_text("حدث خطأ، يرجى إعادة طلب الباقات.", reply_markup=back_keyboard())
        return

    token = context.user_data.get("vf_token")
    phone = context.user_data.get("vf_phone")
    if not token or not phone:
        await query.edit_message_text("انتهت الجلسة، يرجى إعادة المحاولة.", reply_markup=back_keyboard())
        return

    await query.edit_message_text(f"⏳ جاري تفعيل باقة {selected['name']}...")
    result = await asyncio.to_thread(فودافون.activate_plus_package, token, phone, selected)

    idemp_key = str(uuid.uuid4())
    order_id = _db(context).create_order(
        update.effective_user.id,
        selected['name'],
        selected['price'],
        selected['quota'],
        selected['duration'],
        idemp_key
    )

    if result.get("success"):
        with _db(context)._connection() as conn:
            conn.execute("UPDATE orders SET status = 'success' WHERE id = ?", (order_id,))
        msg = f"✅ تم تفعيل الباقة بنجاح!\nباقة {selected['name']}\nرقم الطلب: #{order_id}"
    else:
        with _db(context)._connection() as conn:
            conn.execute("UPDATE orders SET status = 'failed' WHERE id = ?", (order_id,))
        msg = f"❌ فشل تفعيل الباقة: {result.get('message')}\nرقم الطلب: #{order_id}"

    context.user_data.pop("vf_packages", None)
    context.user_data.pop("vf_token", None)
    context.user_data.pop("vf_phone", None)

    await query.edit_message_text(msg, reply_markup=back_keyboard())


async def _handle_admin_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    query = update.callback_query
    if update.effective_user.id != _admin_id(context):
        await query.edit_message_text("هذا القسم مخصص للإدارة فقط.")
        return
    db = _db(context)
    if data == "admin:stats":
        stats = db.get_stats()
        await query.edit_message_text(
            f"📊 إحصائيات {BOT_NAME}\n"
            f"👥 المستخدمون: {stats['users']}\n"
            f"📋 الطلبات: {stats['orders']}\n"
            f"✅ الناجحة: {stats['success']}\n"
            f"❌ الفاشلة: {stats['failed']}\n"
            f"⌛ قيد المعالجة: {stats['pending']}",
            reply_markup=back_keyboard("menu:admin"),
        )
    elif data == "admin:orders":
        orders = db.get_recent_orders()
        if not orders:
            text = "📋 أحدث الطلبات\nلا توجد طلبات مسجلة."
        else:
            lines = [
                f"#{order['id']} — المستخدم {order['user_id']} — "
                f"{order['package_name']} — {_order_status(order['status'])}"
                for order in orders
            ]
            text = "📋 أحدث الطلبات\n" + "\n".join(lines)
        await query.edit_message_text(text, reply_markup=back_keyboard("menu:admin"))
    elif data == "admin:users":
        users = db.list_users()
        if not users:
            await query.edit_message_text(
                "لا يوجد مستخدمون مسجلون.", reply_markup=back_keyboard("menu:admin")
            )
            return
        rows = []
        for item in users:
            label = f"{'🚫' if item['is_blocked'] else '✅'} {item['user_id']}"
            if item["username"]:
                label += f" (@{item['username']})"
            rows.append(
                [InlineKeyboardButton(label, callback_data=f"admin:user:{item['user_id']}")]
            )
        rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu:admin")])
        await query.edit_message_text(
            f"👥 المستخدمون — اضغط لتغيير حالة الحظر (آخر {len(users)}):",
            reply_markup=InlineKeyboardMarkup(rows),
        )
    elif data == "admin:toggle_pause":
        paused = not db.orders_paused()
        db.set_orders_paused(paused)
        await query.edit_message_text(
            f"تم {'إيقاف' if paused else 'استئناف'} استقبال الطلبات.",
            reply_markup=admin_keyboard(paused),
        )
    elif data == "admin:broadcast":
        context.user_data["broadcast_state"] = "draft"
        await query.edit_message_text(
            "أرسل نص الإشعار الآن. سيظهر لك تأكيد قبل إرساله للعملاء.",
            reply_markup=back_keyboard("menu:admin"),
        )
    elif data == "admin:broadcast_confirm":
        text = context.user_data.pop("broadcast_text", None)
        context.user_data.pop("broadcast_state", None)
        if not text:
            await query.edit_message_text(
                "لا يوجد إشعار جاهز للإرسال.", reply_markup=back_keyboard("menu:admin")
            )
            return
        sent = 0
        failed = 0
        for user_id in db.active_user_ids():
            try:
                await context.bot.send_message(user_id, f"📣 إشعار من {BOT_NAME}\n\n{text}")
                sent += 1
            except TelegramError:
                failed += 1
        await query.edit_message_text(
            f"اكتمل الإرسال.\n✅ تم التسليم: {sent}\n⚠️ تعذر التسليم: {failed}",
            reply_markup=back_keyboard("menu:admin"),
        )
    elif data == "admin:broadcast_cancel":
        context.user_data.pop("broadcast_text", None)
        context.user_data.pop("broadcast_state", None)
        await query.edit_message_text(
            "تم إلغاء الإشعار.", reply_markup=back_keyboard("menu:admin")
        )


async def _handle_user_toggle(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    query = update.callback_query
    if update.effective_user.id != _admin_id(context):
        await query.edit_message_text("هذا القسم مخصص للإدارة فقط.")
        return
    parts = data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await query.edit_message_text("معرّف المستخدم غير صالح.")
        return
    user_id = int(parts[2])
    target = _db(context).get_user(user_id)
    if target is None:
        await query.edit_message_text(
            "المستخدم غير موجود.", reply_markup=back_keyboard("menu:admin")
        )
        return
    blocked = not bool(target["is_blocked"])
    _db(context).set_user_blocked(user_id, blocked)
    await query.edit_message_text(
        f"تم {'حظر' if blocked else 'إلغاء حظر'} المستخدم {user_id}.",
        reply_markup=back_keyboard("menu:admin"),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return
    user = _register_user(update, context)
    if user.get("is_blocked") and update.effective_user.id != _admin_id(context):
        await update.effective_message.reply_text("تم إيقاف وصولك إلى Mikey Bot.")
        return

    subscribed = await check_subscription(update.effective_user.id, context)
    if not subscribed:
        await update.effective_message.reply_text(
            SUB_REQUIRED_MESSAGE,
            reply_markup=sub_keyboard(),
        )
        return

    text = (update.effective_message.text or "").strip()

    action = context.user_data.get("action")

    # Vodafone Auth Flow
    if action == "awaiting_phone":
        clean_phone = text.strip()
        if not (clean_phone.startswith("01") or clean_phone.startswith("201") or clean_phone.startswith("+201")) or not clean_phone.replace("+", "").isdigit() or len(clean_phone) not in (11, 12, 13):
            await update.effective_message.reply_text(
                "❌ رقم فودافون غير صحيح!\nيرجى إرسال رقم هاتف صحيح مكون من 11 رقم يبدأ بـ 01 (مثال: 01012345678):",
                reply_markup=back_keyboard("menu:home")
            )
            return
        context.user_data["temp_phone"] = clean_phone
        context.user_data["action"] = "awaiting_password"
        await update.effective_message.reply_text(
            "🔑 [2/2] الآن أرسل كلمة مرور حساب 'أنا فودافون' الخاص بك:",
            reply_markup=back_keyboard("menu:home")
        )
        return
    elif action == "awaiting_password":
        if len(text) < 3:
            await update.effective_message.reply_text(
                "❌ كلمة المرور قصيرة جداً!\nيرجى إدخال كلمة مرور حساب 'أنا فودافون' الصحيحة:",
                reply_markup=back_keyboard("menu:home")
            )
            return
        phone = context.user_data.pop("temp_phone", "")
        password = text
        target = context.user_data.pop("auth_flow_target", "menu:packages")
        context.user_data.pop("action", None)

        status_msg = await update.effective_message.reply_text("⏳ جاري تسجيل الدخول لحساب أنا فودافون...")
        await _process_vodafone_action(update, context, status_msg, phone, password, target)
        return

    # Etisalat Gift Flow
    elif action == "awaiting_etisalat_phone":
        clean = text.strip()
        if not (clean.startswith("011") or clean.startswith("11") or clean.startswith("2011") or clean.startswith("+2011")) or not clean.replace("+", "").isdigit() or len(clean) not in (10, 11, 12, 13):
            await update.effective_message.reply_text(
                "❌ رقم اتصالات غير صحيح!\nيرجى إرسال رقم صحيح مكون من 11 رقم يبدأ بـ 011 (مثال: 01112345678):",
                reply_markup=back_keyboard("menu:etisalat_gift")
            )
            return
        context.user_data["etisalat_phone"] = clean
        context.user_data["action"] = "awaiting_etisalat_password"
        await update.effective_message.reply_text(
            "🔑 [2/3] الآن أرسل كلمة المرور الخاصة بحسابك في تطبيق My Etisalat:",
            reply_markup=back_keyboard("menu:etisalat_gift")
        )
        return
    elif action == "awaiting_etisalat_password":
        if len(text) < 3:
            await update.effective_message.reply_text(
                "❌ كلمة المرور قصيرة جداً!\nيرجى إعادة إدخال كلمة المرور الخاصة بحساب اتصالات:",
                reply_markup=back_keyboard("menu:etisalat_gift")
            )
            return
        context.user_data["etisalat_password"] = text
        context.user_data["action"] = "awaiting_etisalat_email"
        await update.effective_message.reply_text(
            "📧 [3/3] أخيرًا، أرسل البريد الإلكتروني (الإيميل) المسجل بحساب اتصالات (مثال: example@gmail.com):",
            reply_markup=back_keyboard("menu:etisalat_gift")
        )
        return
    elif action == "awaiting_etisalat_email":
        email = text.strip()
        if not EMAIL_REGEX.match(email):
            await update.effective_message.reply_text(
                "❌ البريد الإلكتروني الذي أدخلته غير صحيح!\nيرجى كتابة بريد إلكتروني صحيح (مثال: example@gmail.com):",
                reply_markup=back_keyboard("menu:etisalat_gift")
            )
            return

        phone = context.user_data.pop("etisalat_phone", "")
        password = context.user_data.pop("etisalat_password", "")
        gift_type = context.user_data.pop("etisalat_gift_type", "all")
        context.user_data.pop("action", None)

        status_msg = await update.effective_message.reply_text("⏳ جاري تفعيل هدية اتصالات، يرجى الانتظار...")

        service = EtisalatService()
        result = await service.activate_gift(phone, password, email, gift_type=gift_type)

        idemp_key = str(uuid.uuid4())
        pkg_name = f"هدية اتصالات ({result.get('quota', '500MB')})"
        order_id = _db(context).create_order(
            update.effective_user.id,
            pkg_name,
            0.0,
            result.get("quota", "500MB"),
            "هدية مجانية",
            idemp_key
        )

        if result.get("success"):
            with _db(context)._connection() as conn:
                conn.execute("UPDATE orders SET status = 'success' WHERE id = ?", (order_id,))
            msg_text = f"نتيجة التفعيل:\n{result.get('message')}\n\nرقم الطلب: #{order_id}"
        else:
            with _db(context)._connection() as conn:
                conn.execute("UPDATE orders SET status = 'failed' WHERE id = ?", (order_id,))
            msg_text = f"نتيجة التفعيل:\n{result.get('message')}\n\nرقم الطلب: #{order_id}"

        await status_msg.edit_text(msg_text, reply_markup=back_keyboard("menu:etisalat_gift"))
        return

    state = context.user_data.get("broadcast_state")
    if state == "draft" and update.effective_user.id == _admin_id(context):
        if not text:
            await update.effective_message.reply_text("أرسل نصاً غير فارغ للإشعار.")
            return
        context.user_data["broadcast_text"] = text
        context.user_data["broadcast_state"] = "confirm"
        await update.effective_message.reply_text(
            f"معاينة إشعار {BOT_NAME}:\n\n{text}\n\nهل تريد الإرسال؟",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✅ تأكيد الإرسال", callback_data="admin:broadcast_confirm")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="admin:broadcast_cancel")],
                ]
            ),
        )
        return
    if context.user_data.pop("support_waiting", False):
        try:
            await context.bot.send_message(
                _admin_id(context),
                f"🆘 رسالة دعم إلى {BOT_NAME}\n"
                f"المستخدم: {update.effective_user.id}\n"
                f"الرد بالأمر: /reply {update.effective_user.id} نص الرد\n\n{text}",
            )
        except TelegramError:
            await update.effective_message.reply_text(
                "تعذر إرسال رسالتك إلى الإدارة حالياً. حاول لاحقاً."
            )
            return
        await update.effective_message.reply_text("تم إرسال رسالتك إلى إدارة Mikey Bot.")
        return
    await update.effective_message.reply_text(
        "استخدم الأزرار للتنقل في Mikey Bot.", reply_markup=main_keyboard()
    )


async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != _admin_id(context):
        await update.effective_message.reply_text("هذا الأمر مخصص للإدارة فقط.")
        return
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.effective_message.reply_text(
            "الاستخدام: /reply TELEGRAM_ID نص الرد"
        )
        return
    user_id = int(context.args[0])
    message = " ".join(context.args[1:])
    try:
        await context.bot.send_message(user_id, f"🆘 رد إدارة {BOT_NAME}:\n\n{message}")
    except TelegramError:
        await update.effective_message.reply_text("تعذر إرسال الرد إلى هذا المستخدم.")
        return
    await update.effective_message.reply_text("تم إرسال الرد.")


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != _admin_id(context):
        await update.effective_message.reply_text("هذا الأمر مخصص للإدارة فقط.")
        return
    _register_user(update, context)
    await update.effective_message.reply_text(
        f"🛠 لوحة إدارة {BOT_NAME}",
        reply_markup=admin_keyboard(_db(context).orders_paused()),
    )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    logger.error("Update handling failed (%s)", type(error).__name__ if error else "unknown")


def build_application(token: str, admin_id: int, database_path: str) -> Application:
    application = Application.builder().token(token).build()
    application.bot_data["db"] = Database(database_path)
    application.bot_data["admin_id"] = admin_id
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("reply", reply_to_user))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    application = build_application(
        settings.bot_token, settings.admin_id, settings.database_path
    )
    logger.info("%s is starting", BOT_NAME)
    application.run_polling()


if __name__ == "__main__":
    main()
