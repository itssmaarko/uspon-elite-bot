import asyncio
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    PicklePersistence,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

(
    COLLECTING_NAME,
    COLLECTING_EMAIL,
    SHOWING_BENEFITS,
    BROKER_QUESTION,
    BROKER_SELECTION,
    WAITING_GOTOVO,
    WAITING_FINAL,
) = range(7)

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

FOLLOW_UP_TIMES = [30 * 60, 3 * 3600, 6 * 3600, 24 * 3600]

FOLLOW_UP_MESSAGES = {
    "instructions": [
        "Hej {name}! 👋\n\nJesi li uspio poslati email brokeru? Ako trebaš pomoć s bilo čim, tu sam.",
        "Hej {name}, samo da provjerim — ide li sve ok? Jednom kad pošalješ email, stisni Gotovo i ulaz je tvoj.",
        "{name}, primjećujem da još nisi završio. Ako se zaglaviš negdje, javi mi se odmah. 💬",
        "Zadnji podsjetnik, {name} — čim pošalješ email brokeru i stisneš Gotovo, odmah te dodajem. 🚀",
    ],
    "registration": [
        "Hej {name}! 👋\n\nJesi li uspio napraviti registraciju? Javi mi se ako trebaš pomoć s bilo kojim korakom.",
        "Hej {name}, samo da provjerim — ide li registracija ok? Jednom kad odradiš depozit, pošalji screenshot i ulaz je tvoj!",
        "{name}, primjećujem da još nisi poslao potvrdu. Ako se zaglaviš negdje, tu sam! 💬",
        "Zadnji podsjetnik, {name} — tri koraka i community je tvoj. Jednom kad napraviš depozit, samo pošalji screenshot ovdje. 🚀",
    ],
    "waiting_email": [
        "Hej {name}! 👋\n\nJoš samo da nam pošalješ email adresu s kojom si registriran na brokera i odmah te dodajemo.",
        "{name}, samo podsjetnik — pošalji nam email adresu s brokera i ulaz u community je tvoj. 🎯",
        "{name}, još uvijek čekamo tvoj email. Javi se ako ima kakvih problema. 💬",
        "Zadnji podsjetnik, {name} — pošalji email adresu s brokera i odmah te dodajemo u sve grupe. 🚀",
    ],
    "waiting_screenshot": [
        "Hej {name}! 👋\n\nJoš samo screenshot potvrde depozita i odmah ti aktiviramo pristup svim grupama.",
        "{name}, samo podsjetnik — jednom kad nam pošalješ screenshot, ulaz u community je tvoj. 🎯",
        "{name}, još uvijek čekamo potvrdu depozita. Javi se ako ima kakvih problema. 💬",
        "Zadnji podsjetnik, {name} — pošalji screenshot depozita i odmah te dodajemo u sve grupe. 🚀",
    ],
}


def cancel_followups(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    jobs = context.job_queue.get_jobs_by_name(f"fu_{chat_id}")
    for job in jobs:
        job.schedule_removal()


def schedule_followups(context: ContextTypes.DEFAULT_TYPE, chat_id: int, first_name: str, fu_type: str):
    cancel_followups(context, chat_id)
    for i, delay in enumerate(FOLLOW_UP_TIMES):
        context.job_queue.run_once(
            send_followup,
            when=delay,
            chat_id=chat_id,
            name=f"fu_{chat_id}",
            data={"first_name": first_name, "fu_type": fu_type, "attempt": i},
        )


async def send_followup(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    first_name = data["first_name"]
    fu_type = data["fu_type"]
    attempt = data["attempt"]

    messages = FOLLOW_UP_MESSAGES.get(fu_type, FOLLOW_UP_MESSAGES["instructions"])
    text = messages[min(attempt, len(messages) - 1)].format(name=first_name)

    try:
        await context.bot.send_message(chat_id=job.chat_id, text=text)
    except Exception as e:
        logger.error(f"Follow-up slanje nije uspjelo za {job.chat_id}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_followups(context, update.effective_chat.id)
    await update.message.reply_text(
        "Dobrodošao.\n\n"
        "Drago mi je što si ovdje znači da tražiš nešto više od prosjeka.\n\n"
        "Da dobiješ pristup našem community, želim da se malo bolje upoznamo.\n\n"
        "Zanima me kako se zoveš i odakle nam dolaziš."
    )
    return COLLECTING_NAME


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.text.strip()
    first_name = full_name.split()[0]
    context.user_data["full_name"] = full_name
    context.user_data["first_name"] = first_name

    await update.message.reply_text(
        f"Super drago mi je, {first_name}.\n\n"
        "Sad mi treba još samo jedna stvar prije nego krenemo dalje.\n\n"
        "Upiši molim te svoju e-mail adresu."
    )
    return COLLECTING_EMAIL


async def collect_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    context.user_data["email"] = email
    first_name = context.user_data.get("first_name", "")

    await update.message.reply_text(
        f"Hvala, {first_name}.\n\n"
        "Evo što sve dobiješ unutar našeg communitya."
    )

    await asyncio.sleep(1.5)

    await update.message.reply_text(
        "Što dobiješ:\n\n"
        "✅ 8 do 12 visokokvalitetnih trade ideja svaki dan\n"
        "✅ 85% uspješnost na zlatu, tjedan za tjednom\n"
        "✅ Kompletan step-by-step edukacija — od nule do prvog trade-a\n"
        "✅ Tjedni mindset i edukacijski pozivi\n"
        "✅ 6 do 8 live trading sesija tjedno\n"
        "✅ Provjereni broker koji štiti tvoj kapital"
    )

    await asyncio.sleep(1.5)

    keyboard = [
        [
            InlineKeyboardButton("Idući korak →", callback_data="next_step"),
            InlineKeyboardButton("Zašto je besplatno?", callback_data="why_free"),
        ]
    ]

    await update.message.reply_text(
        "I najvažniji dio:\n\n"
        "🚀 Nema nikakvih troškova da kreneš\n"
        "🚀 Nema nikakvih mjesečnih pretplata\n"
        "🚀 Nema nikakvih ugovora, ikad\n\n"
        "Ti si u punoj kontroli nad svojim kapitalom. Uvijek.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return SHOWING_BENEFITS


async def why_free(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    first_name = context.user_data.get("first_name", "")

    await query.message.reply_text(
        f"Odlično pitanje, {first_name}.\n\n"
        "Razumijem zašto pitaš svaki put kad je nešto besplatno, normalno je upitati gdje je kvaka.\n\n"
        "Zapravo i nije toliko komplicirano."
    )

    await asyncio.sleep(2)

    await query.message.reply_text(
        "Radimo s brokerima godinama.\n\n"
        "Izgradili smo provjeren odnos sa njima i oni znaju tko smo i što radimo.\n\n"
        "Odgovor je jednostavan: oni pokrivaju trošak tvog članstva. "
        "Ti trejdaš preko njih, oni nas sponzoriraju na osnovu toga."
    )

    await asyncio.sleep(2)

    await query.message.reply_text(
        "Znači ti dobiješ sve trade ideje svaki dan, live sesije, "
        "tjedne treninge, edukaciju, pozive, kompletan support..."
    )

    await asyncio.sleep(1.5)

    keyboard = [[InlineKeyboardButton("Spreman sam →", callback_data="ready")]]

    await query.message.reply_text(
        "...i to bez ijednog eura što moraš platit.\n\n"
        "Win-win situacija. Ali fokus nije na modelu fokus je da ti profitiraš.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return SHOWING_BENEFITS


async def ask_broker_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("Da, imam ✅", callback_data="has_broker"),
            InlineKeyboardButton("Ne, nov sam u ovome", callback_data="no_broker"),
        ]
    ]

    await query.message.reply_text(
        "Odlično.\n\n"
        "Brzo pitanje prije nego krenemo imaš li već otvoren račun "
        "na Vantageu, VT Marketsu ili TradeQuo?\n\n"
        "Ako nemaš, provest ćemo te korak po korak kroz cijeli proces.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return BROKER_QUESTION


async def has_broker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    first_name = context.user_data.get("first_name", "")

    keyboard = [
        [
            InlineKeyboardButton("TradeQ", callback_data="broker_tradequo"),
            InlineKeyboardButton("Vantage", callback_data="broker_vantage"),
            InlineKeyboardButton("VT Market", callback_data="broker_vtmarket"),
        ]
    ]

    await query.message.reply_text(
        f"Dobro, {first_name}.\n\n"
        "Da bi mogao primati trade ideje i ulaziti na live sesije, "
        "moraš biti registriran ispod nas.\n\n"
        "Na kojemu od ova tri brokera si registriran?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return BROKER_SELECTION


async def broker_tradequo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["broker"] = "TradeQ"
    first_name = context.user_data.get("first_name", "")

    schedule_followups(context, update.effective_chat.id, first_name, "instructions")

    keyboard = [[InlineKeyboardButton("Gotovo ✅", callback_data="gotovo_existing")]]

    await query.message.reply_text(
        "Evo kako da se prebaciš ispod nas.\n\n"
        "📧 Pošalji ovaj email na: support@tradequo.com\n\n"
        "<code>Hey can you put me under the structure of luksuz25@gmail.com "
        "we started working together and I want to work with him.</code>\n\n"
        "Jednom kada pošalješ email, stisni Gotovo.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return WAITING_GOTOVO


async def broker_vantage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["broker"] = "Vantage"
    first_name = context.user_data.get("first_name", "")

    schedule_followups(context, update.effective_chat.id, first_name, "instructions")

    keyboard = [[InlineKeyboardButton("Gotovo ✅", callback_data="gotovo_existing")]]

    await query.message.reply_text(
        "Evo kako da se prebaciš ispod nas.\n\n"
        "📧 Pošalji ovaj email na: support@vantagemarkets.com\n\n"
        "<code>Please transfer me under Alar Toom management and under IB: 24008323</code>\n\n"
        "Jednom kada pošalješ email, stisni Gotovo.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return WAITING_GOTOVO


async def broker_vtmarket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["broker"] = "VT Market"
    first_name = context.user_data.get("first_name", "")

    schedule_followups(context, update.effective_chat.id, first_name, "instructions")

    keyboard = [[InlineKeyboardButton("Gotovo ✅", callback_data="gotovo_existing")]]

    await query.message.reply_text(
        "Evo kako da se prebaciš ispod nas.\n\n"
        "📧 Pošalji ovaj email na: info@vtmarkets.com\n\n"
        "<code>Please move my account under IB rebate acc 22208322. "
        "We started working together and I wish to be on this management.</code>\n\n"
        "Jednom kada pošalješ email, stisni Gotovo.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return WAITING_GOTOVO


async def gotovo_existing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    first_name = context.user_data.get("first_name", "")

    schedule_followups(context, update.effective_chat.id, first_name, "waiting_email")

    await query.message.reply_text(
        "Odlično, drago nam je što si prošao kroz cijeli proces! 🎉\n\n"
        "Molim te pošalji nam još jednom email adresu s kojom si registriran na brokera — "
        "javimo ti se u roku nekoliko minuta sa svim daljnjim koracima."
    )

    return WAITING_FINAL


async def no_broker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["broker"] = "Novi korisnik - registracija"
    first_name = context.user_data.get("first_name", "")

    schedule_followups(context, update.effective_chat.id, first_name, "registration")

    keyboard = [[InlineKeyboardButton("Gotovo ✅", callback_data="gotovo_new")]]

    registration_text = (
        "Nema problema upravo si na pravom mjestu.\n\n"
        "Pročitaj sve upute ispod i slijedi korake.\n\n"
        "DOBRODOŠLI U USPON ELITE! 📈\n\n"
        "Do pristupa vas dijele samo 3 jednostavna koraka.\n\n"
        "📊 Scalp grupa — 5-15 trade ideja dnevno\n"
        "📈 Intraday grupa — 5-10 trade ideja, Risk:Reward 1:1\n"
        "🚀 Swing grupa — 1-4 trade ideje, Risk:Reward 1:3\n\n"
        "1️⃣ Registracija trading računa\n"
        "Registriraj se putem našeg brokerskog partnera:\n"
        "🔗 https://vtm.pro/la1-com/en/sEwAM2iW\n"
        "Referral Code: sEwAM2iW\n\n"
        "2️⃣ Uspon Elite Onboarding\n"
        "Otvori onboarding sustav gdje ćeš naći sve detalje:\n"
        "🔗 https://elite-onboarding-guide.lovable.app\n\n"
        "✅ Kako registrirati račun\n"
        "✅ Kako otvoriti Live račun\n"
        "✅ Kako ostvariti 100% bonus na prvi depozit\n"
        "✅ Sve potrebne upute za jednostavan početak\n\n"
        "3️⃣ Aktivacija pristupa\n"
        "Kada završiš registraciju i napraviš prvi depozit, "
        "pošalji screenshot potvrde ovdje.\n"
        "Nakon toga šaljem ti pristup svim trading grupama. 🎉\n\n"
        "Jednom kada završiš sve korake, stisni Gotovo. 👇"
    )

    await query.message.reply_text(
        registration_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return WAITING_GOTOVO


async def gotovo_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    first_name = context.user_data.get("first_name", "")

    schedule_followups(context, update.effective_chat.id, first_name, "waiting_screenshot")

    await query.message.reply_text(
        "Odlično! 🎉\n\n"
        "Pošalji nam screenshot potvrde depozita ovdje — "
        "aktiviramo ti pristup u roku nekoliko minuta."
    )

    return WAITING_FINAL


async def collect_final_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    first_name = context.user_data.get("first_name", "")
    full_name = context.user_data.get("full_name", "N/A")
    email = context.user_data.get("email", "N/A")
    broker = context.user_data.get("broker", "N/A")

    cancel_followups(context, update.effective_chat.id)

    if ADMIN_CHAT_ID:
        try:
            if update.message.photo:
                summary = (
                    f"🔔 Novi član!\n\n"
                    f"👤 Ime: {full_name}\n"
                    f"📧 Email: {email}\n"
                    f"🏦 Broker: {broker}\n"
                    f"📎 Screenshot depozita poslan ispod."
                )
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=summary)
                await context.bot.forward_message(
                    chat_id=ADMIN_CHAT_ID,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id,
                )
            else:
                final_info = update.message.text
                summary = (
                    f"🔔 Novi član!\n\n"
                    f"👤 Ime: {full_name}\n"
                    f"📧 Email registracije: {email}\n"
                    f"🏦 Broker: {broker}\n"
                    f"📝 Broker email poslan: {final_info}"
                )
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=summary)
        except Exception as e:
            logger.error(f"Admin notifikacija nije uspjela: {e}")

    await update.message.reply_text(
        f"Primljeno, {first_name}! ✅\n\n"
        "Javljamo ti se uskoro. 🚀"
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_followups(context, update.effective_chat.id)
    await update.message.reply_text(
        "Razgovor je prekinut. Stisni /start kada budeš spreman."
    )
    return ConversationHandler.END


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable nije postavljen!")

    persistence = PicklePersistence(filepath="bot_data.pkl")

    application = (
        Application.builder()
        .token(token)
        .persistence(persistence)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            COLLECTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name)
            ],
            COLLECTING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email)
            ],
            SHOWING_BENEFITS: [
                CallbackQueryHandler(why_free, pattern="^why_free$"),
                CallbackQueryHandler(ask_broker_question, pattern="^(next_step|ready)$"),
            ],
            BROKER_QUESTION: [
                CallbackQueryHandler(has_broker, pattern="^has_broker$"),
                CallbackQueryHandler(no_broker, pattern="^no_broker$"),
            ],
            BROKER_SELECTION: [
                CallbackQueryHandler(broker_tradequo, pattern="^broker_tradequo$"),
                CallbackQueryHandler(broker_vantage, pattern="^broker_vantage$"),
                CallbackQueryHandler(broker_vtmarket, pattern="^broker_vtmarket$"),
            ],
            WAITING_GOTOVO: [
                CallbackQueryHandler(gotovo_existing, pattern="^gotovo_existing$"),
                CallbackQueryHandler(gotovo_new, pattern="^gotovo_new$"),
            ],
            WAITING_FINAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_final_info),
                MessageHandler(filters.PHOTO, collect_final_info),
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
        allow_reentry=True,
        persistent=True,
        name="registration_conv",
    )

    application.add_handler(conv_handler)

    logger.info("Uspon Elite bot je pokrenut...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
