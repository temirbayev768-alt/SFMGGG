import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Конфигурация ───────────────────────────────────────────────────────────────
BOT_TOKEN = "8892971073:AAE0ab7OC5bK1GAzTMGsxWwePQ5BqcozqR4"          # Токен от @BotFather
DIRECTOR_CHAT_ID = "1380327188"      # Chat ID директора (число)

# ─── Состояния разговора ────────────────────────────────────────────────────────
CHOOSE_REPORT = 0

# Утренний отчёт: шаги 1–8
MORNING_IIKO      = 10
MORNING_TEAM      = 11
MORNING_STOPLIST_KITCHEN = 12
MORNING_STOPLIST_BAR     = 13
MORNING_HALL      = 14
MORNING_RESTROOM  = 15
MORNING_TERRACE   = 16
MORNING_DISPLAY   = 17

# Вечерний отчёт: шаги 1–2
EVENING_SALES     = 20
EVENING_SEATING   = 21

# Отчёт закрытия: шаги 1–5
CLOSING_HALL_FB   = 30
CLOSING_KITCHEN_FB = 31
CLOSING_PRAISED   = 32
CLOSING_DISLIKED  = 33
CLOSING_REVENUE   = 34

# ─── Описания шагов ─────────────────────────────────────────────────────────────
MORNING_STEPS = {
    MORNING_IIKO:            ("📸 Шаг 1/8 — Открытие смены IIKO",      "Прикрепите фото открытия смены в системе IIKO"),
    MORNING_TEAM:            ("👥 Шаг 2/8 — Фото команды",             "Прикрепите фото всей команды (до 08:30)"),
    MORNING_STOPLIST_KITCHEN:("🍽️ Шаг 3/8 — Стоп-лист по Кухне",      "Введите стоп-лист по кухне (до 11:00) или напишите «Нет»"),
    MORNING_STOPLIST_BAR:    ("🍹 Шаг 4/8 — Стоп-лист по Бару",        "Введите стоп-лист по бару (до 11:00) или напишите «Нет»"),
    MORNING_HALL:            ("🏠 Шаг 5/8 — Фото зала",                "Прикрепите 2–3 фотографии зала"),
    MORNING_RESTROOM:        ("🚿 Шаг 6/8 — Фото санузла",             "Прикрепите фото санузла (чистота)"),
    MORNING_TERRACE:         ("☀️ Шаг 7/8 — Фото летника",              "Прикрепите фото летней террасы"),
    MORNING_DISPLAY:         ("🥐 Шаг 8/8 — Витрина выпечки",          "Прикрепите фото витрины с выпечкой"),
}

EVENING_STEPS = {
    EVENING_SALES:   ("📊 Шаг 1/2 — Отчёт по продажам",   "Введите промежуточный отчёт по продажам (16:00) — текстом или фото"),
    EVENING_SEATING: ("💺 Шаг 2/2 — Отчёт по посадке",    "Введите отчёт по заполняемости зала — текстом или фото"),
}

CLOSING_STEPS = {
    CLOSING_HALL_FB:    ("🗣️ Шаг 1/5 — Обратная связь от зала",    "Напишите обратную связь от зала"),
    CLOSING_KITCHEN_FB: ("👨‍🍳 Шаг 2/5 — Обратная связь от кухни", "Напишите обратную связь от кухни"),
    CLOSING_PRAISED:    ("⭐ Шаг 3/5 — За что хвалили гости?",      "Напишите, за что гости хвалили заведение"),
    CLOSING_DISLIKED:   ("😕 Шаг 4/5 — Что не понравилось гостям?", "Напишите, что гостям не понравилось"),
    CLOSING_REVENUE:    ("💰 Шаг 5/5 — Общая выручка за смену",     "Введите общую выручку за смену (сумму цифрами)"),
}

# Порядок шагов
MORNING_ORDER  = [MORNING_IIKO, MORNING_TEAM, MORNING_STOPLIST_KITCHEN, MORNING_STOPLIST_BAR,
                  MORNING_HALL, MORNING_RESTROOM, MORNING_TERRACE, MORNING_DISPLAY]
EVENING_ORDER  = [EVENING_SALES, EVENING_SEATING]
CLOSING_ORDER  = [CLOSING_HALL_FB, CLOSING_KITCHEN_FB, CLOSING_PRAISED, CLOSING_DISLIKED, CLOSING_REVENUE]

NEXT_STEP = {}
for i, s in enumerate(MORNING_ORDER[:-1]):  NEXT_STEP[s] = MORNING_ORDER[i+1]
for i, s in enumerate(EVENING_ORDER[:-1]):  NEXT_STEP[s] = EVENING_ORDER[i+1]
for i, s in enumerate(CLOSING_ORDER[:-1]):  NEXT_STEP[s] = CLOSING_ORDER[i+1]

LAST_STEPS = {MORNING_DISPLAY, EVENING_SEATING, CLOSING_REVENUE}

# ─── Вспомогательные функции ────────────────────────────────────────────────────

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 Утренний отчёт",   callback_data="morning")],
        [InlineKeyboardButton("🌆 Вечерний отчёт",   callback_data="evening")],
        [InlineKeyboardButton("🌙 Отчёт закрытия",   callback_data="closing")],
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отменить отчёт", callback_data="cancel")]
    ])

def all_steps_info(state):
    if state in MORNING_STEPS: return MORNING_STEPS
    if state in EVENING_STEPS: return EVENING_STEPS
    return CLOSING_STEPS

def report_type_name(state):
    if state in MORNING_STEPS:  return "🌅 Утренний отчёт"
    if state in EVENING_STEPS:  return "🌆 Вечерний отчёт"
    return "🌙 Отчёт закрытия"

async def ask_step(update: Update, context: ContextTypes.DEFAULT_TYPE, state: int):
    steps = all_steps_info(state)
    title, prompt = steps[state]
    text = f"*{title}*\n\n{prompt}"
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=cancel_keyboard())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=cancel_keyboard())
    return state

async def save_and_advance(update: Update, context: ContextTypes.DEFAULT_TYPE, current_state: int):
    """Сохраняет ответ пользователя и переходит к следующему шагу или финишу."""
    data = context.user_data.setdefault("report_data", {})

    msg = update.message
    if msg.photo:
        # Сохраняем file_id последнего (наилучшего качества) фото
        data[current_state] = ("photo", msg.photo[-1].file_id, msg.caption or "")
    elif msg.document:
        data[current_state] = ("document", msg.document.file_id, msg.caption or "")
    elif msg.text:
        data[current_state] = ("text", msg.text)
    else:
        await msg.reply_text("⚠️ Пожалуйста, отправьте фото или текст.", reply_markup=cancel_keyboard())
        return current_state

    if current_state in LAST_STEPS:
        return await finish_report(update, context)
    else:
        next_state = NEXT_STEP[current_state]
        return await ask_step(update, context, next_state)

async def finish_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Собирает итоговое сообщение и отправляет директору."""
    data = context.user_data.get("report_data", {})
    report_type = context.user_data.get("report_type", "отчёт")
    user = update.message.from_user
    admin_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Администратор"

    if report_type == "morning":
        steps, order = MORNING_STEPS, MORNING_ORDER
    elif report_type == "evening":
        steps, order = EVENING_STEPS, EVENING_ORDER
    else:
        steps, order = CLOSING_STEPS, CLOSING_ORDER

    # Проверка заполненности
    missing = [steps[s][0] for s in order if s not in data]
    if missing:
        await update.message.reply_text(
            "⚠️ Не все шаги заполнены:\n" + "\n".join(f"• {m}" for m in missing)
        )
        return ConversationHandler.END

    report_name = {"morning": "🌅 Утренний отчёт", "evening": "🌆 Вечерний отчёт", "closing": "🌙 Отчёт закрытия"}[report_type]
    header = (
        f"╔══════════════════════════╗\n"
        f"        МОЁ ТОРГОВОЕ ПРЕДПРИЯТИЕ\n"
        f"╚══════════════════════════╝\n\n"
        f"📋 *{report_name}*\n"
        f"👤 Администратор: {admin_name}\n"
        f"{'─'*30}\n\n"
    )

    # Отправляем текстовую сводку
    summary_lines = [header]
    photo_items = []
    for s in order:
        title, _ = steps[s]
        val = data[s]
        if val[0] == "text":
            summary_lines.append(f"*{title}*\n{val[1]}\n")
        elif val[0] in ("photo", "document"):
            caption = val[2] if val[2] else "—"
            summary_lines.append(f"*{title}*\n📎 Медиафайл прикреплён. {caption}\n")
            photo_items.append((title, val))

    summary_text = "\n".join(summary_lines)

    try:
        await context.bot.send_message(
            chat_id=DIRECTOR_CHAT_ID,
            text=summary_text,
            parse_mode="Markdown"
        )
        # Отправляем фото директору
        for title, val in photo_items:
            kind, file_id, cap = val
            caption_text = f"📎 {title}" + (f"\n{cap}" if cap else "")
            if kind == "photo":
                await context.bot.send_photo(chat_id=DIRECTOR_CHAT_ID, photo=file_id, caption=caption_text)
            else:
                await context.bot.send_document(chat_id=DIRECTOR_CHAT_ID, document=file_id, caption=caption_text)

        await update.message.reply_text(
            "✅ *Отчёт успешно отправлен директору!*\n\nСпасибо за работу 👏",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки директору: {e}")
        await update.message.reply_text(
            "❌ Не удалось отправить отчёт директору. Проверьте настройки бота.",
            reply_markup=main_menu_keyboard()
        )

    context.user_data.clear()
    return CHOOSE_REPORT

# ─── Обработчики ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    text = (
        "☕ *Моё торговое предприятие*\n\n"
        "Добро пожаловать!\nВыберите тип отчёта:"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    else:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return CHOOSE_REPORT

async def choose_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        context.user_data.clear()
        await query.message.reply_text(
            "❌ Отчёт отменён.\n\nВыберите тип отчёта:",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSE_REPORT

    context.user_data["report_type"] = query.data
    context.user_data["report_data"] = {}

    if query.data == "morning":
        await query.message.reply_text(
            "🌅 *Утренний отчёт*\nОтличное начало дня! Заполним отчёт по шагам.\n",
            parse_mode="Markdown"
        )
        return await ask_step(update, context, MORNING_IIKO)
    elif query.data == "evening":
        await query.message.reply_text(
            "🌆 *Вечерний отчёт*\nЗаполним промежуточный отчёт.\n",
            parse_mode="Markdown"
        )
        return await ask_step(update, context, EVENING_SALES)
    elif query.data == "closing":
        await query.message.reply_text(
            "🌙 *Отчёт закрытия*\nПодведём итоги смены.\n",
            parse_mode="Markdown"
        )
        return await ask_step(update, context, CLOSING_HALL_FB)

# ─── Универсальный обработчик ввода ─────────────────────────────────────────────

def make_handler(state):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await save_and_advance(update, context, state)
    return handler

# ─── Запуск ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    media_filter = filters.TEXT | filters.PHOTO | filters.Document.ALL

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_REPORT: [
                CallbackQueryHandler(choose_report)
            ],
            # Утренний отчёт
            MORNING_IIKO:             [MessageHandler(media_filter, make_handler(MORNING_IIKO)),
                                       CallbackQueryHandler(choose_report)],
            MORNING_TEAM:             [MessageHandler(media_filter, make_handler(MORNING_TEAM)),
                                       CallbackQueryHandler(choose_report)],
            MORNING_STOPLIST_KITCHEN: [MessageHandler(media_filter, make_handler(MORNING_STOPLIST_KITCHEN)),
                                       CallbackQueryHandler(choose_report)],
            MORNING_STOPLIST_BAR:     [MessageHandler(media_filter, make_handler(MORNING_STOPLIST_BAR)),
                                       CallbackQueryHandler(choose_report)],
            MORNING_HALL:             [MessageHandler(media_filter, make_handler(MORNING_HALL)),
                                       CallbackQueryHandler(choose_report)],
            MORNING_RESTROOM:         [MessageHandler(media_filter, make_handler(MORNING_RESTROOM)),
                                       CallbackQueryHandler(choose_report)],
            MORNING_TERRACE:          [MessageHandler(media_filter, make_handler(MORNING_TERRACE)),
                                       CallbackQueryHandler(choose_report)],
            MORNING_DISPLAY:          [MessageHandler(media_filter, make_handler(MORNING_DISPLAY)),
                                       CallbackQueryHandler(choose_report)],
            # Вечерний отчёт
            EVENING_SALES:    [MessageHandler(media_filter, make_handler(EVENING_SALES)),
                               CallbackQueryHandler(choose_report)],
            EVENING_SEATING:  [MessageHandler(media_filter, make_handler(EVENING_SEATING)),
                               CallbackQueryHandler(choose_report)],
            # Закрытие
            CLOSING_HALL_FB:    [MessageHandler(media_filter, make_handler(CLOSING_HALL_FB)),
                                 CallbackQueryHandler(choose_report)],
            CLOSING_KITCHEN_FB: [MessageHandler(media_filter, make_handler(CLOSING_KITCHEN_FB)),
                                 CallbackQueryHandler(choose_report)],
            CLOSING_PRAISED:    [MessageHandler(media_filter, make_handler(CLOSING_PRAISED)),
                                 CallbackQueryHandler(choose_report)],
            CLOSING_DISLIKED:   [MessageHandler(media_filter, make_handler(CLOSING_DISLIKED)),
                                 CallbackQueryHandler(choose_report)],
            CLOSING_REVENUE:    [MessageHandler(media_filter, make_handler(CLOSING_REVENUE)),
                                 CallbackQueryHandler(choose_report)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(choose_report, pattern="^cancel$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)

    print("🤖 Бот «Моё торговое предприятие» запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
