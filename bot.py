import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    PreCheckoutQuery,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)
from telegram.request import HTTPXRequest

import db

load_dotenv()

# Konfiguratsiya
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OWNER_ID = int(os.getenv("OWNER_ID", "8551800192"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
WEBAPP_URL = (
    os.getenv("WEBAPP_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or "http://10.144.34.77:8000"
).rstrip("/")
PORT = int(os.getenv("PORT", "8000"))

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN o'zgaruvchisi kiritilmadi! Render yoki .env da sozlang.")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_VIDEOS_DIR = UPLOADS_DIR / "videos"
UPLOADS_POSTERS_DIR = UPLOADS_DIR / "posters"

UPLOADS_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_POSTERS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("premium-kinolar")

# Gemini mijozi
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Telegram Bot sozlamasi
httpx_request = HTTPXRequest(
    connect_timeout=60.0,
    read_timeout=120.0,
    write_timeout=120.0,
    pool_timeout=60.0,
)
tg_app = Application.builder().token(TELEGRAM_TOKEN).request(httpx_request).build()


def create_web_button(text: str, path: str) -> InlineKeyboardButton:
    full_url = f"{WEBAPP_URL}{path}"
    if full_url.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=full_url))
    return InlineKeyboardButton(text=text, url=full_url)


# --- TELEGRAM BOT HANDLERS ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_id = user.id

    db_user = db.register_or_get_user(
        user_id=user_id,
        first_name=user.first_name,
        last_name=user.last_name or "",
        username=user.username or "",
    )

    # 1. Deep linking orqali kino yoki to'lov so'ralganmi?
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg in ("buy", "obuna"):
            await buy_stars_handler(update, context)
            return
        if arg.startswith("movie_"):
            movie_code = arg.replace("movie_", "").strip()
            await deliver_movie(update, context, movie_code, db_user)
            return

    # 2. Agar foydalanuvchi ADMIN bo'lsa
    if user_id == OWNER_ID:
        keyboard = [
            [create_web_button("👑 Admin Web Panelni ochish", "/admin")],
            [create_web_button("🍿 Foydalanuvchi Web Katalogi", f"/user?user_id={user_id}")],
        ]
        text = (
            f"Assalomu alaykum, Admin ({user.first_name})! 👑\n\n"
            "**Premium Kinolar** boshqaruv tizimingiz tayyor.\n"
            "Telefoningizdan qulay foydalanish uchun quyidagi tugma orqali **Admin Web Panel**ni ochishingiz mumkin:\n\n"
            "• Yangi kinolarni **video fayl qilib yuklash** (URL kerakmas)\n"
            "• Obuna sotib olganlarni Aktiv/Deaktiv qilish\n"
            "• Mavjud kinolarni o'chirish\n\n"
            "💡 *Qo'shimcha qulaylik:* Shuningdek, xohlasangiz botga to'g'ridan-to'g'ri video fayl tashlab ham kino qo'shishingiz mumkin!"
        )
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # 3. Agar ODDIY FOYDALANUVCHI bo'lsa
    is_active = db_user.get("status") == "active" or db_user.get("is_premium")
    status_text = "Faol obunachi ✅" if is_active else "Obuna bo'linmagan ❌"

    keyboard = []
    if not is_active:
        keyboard.append([InlineKeyboardButton("⭐️ Obuna bo'lish (50 ⭐️ Stars)", callback_data="buy_stars")])
    keyboard.append([create_web_button("🎬 Kinolar Katalogi (Web)", f"/user?user_id={user_id}")])

    text = (
        f"Salom, {user.first_name}! 🎬 **Premium Kinolar** botiga xush kelibsiz!\n\n"
        f"👤 Sizning holatingiz: **{status_text}**\n"
        f"🆔 Sizning Telegram ID: `{user_id}`\n\n"
        "Premyera filmlarni ko'rish, yangi kinolar kodlarini olish va obunani faollashtirish uchun quyidagi tugmani bosing:"
    )
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def deliver_movie(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str, user: dict) -> None:
    chat_id = update.effective_chat.id
    user_id = user["id"]
    movie = db.get_movie_by_code(code)

    if not movie:
        await update.message.reply_text(
            f"❌ Kechirasiz, `#{code}` kodli film topilmadi.\nBarcha filmlarni veb-katalogda ko'rishingiz mumkin.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [create_web_button("🍿 Kinolarni ko'rish", f"/user?user_id={user_id}")]
            ])
        )
        return

    # Foydalanuvchi holatini tekshirish
    is_active = user.get("status") == "active" or user.get("is_premium")
    if not is_active:
        text = (
            f"🔒 **Ushbu filmni ko‘rish uchun obuna bo‘lishingiz kerak!**\n\n"
            f"🎬 **Kino:** {movie['title']}\n"
            f"🔑 **Kodi:** #{movie['code']}\n\n"
            "Obuna narxi: 50 ⭐️ (Telegram Stars).\n"
            "To'g'ridan-to'g'ri Telegramda to'lab, darhol tomosha qilish uchun pastdagi tugmani bosing:"
        )
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐️ 50 Stars bilan to'lash (Obuna)", callback_data="buy_stars")],
                [create_web_button("🍿 Veb Katalog", f"/user?user_id={user_id}")]
            ])
        )
        return

    caption = (
        f"🎬 **{movie['title']}**\n\n"
        f"📌 **Tavsif:** {movie['description']}\n"
        f"🔑 **Film kodi:** #{movie['code']}\n\n"
        f"🍿 Yoqimli tomosha tilaymiz!"
    )
    
    keyboard = [
        [create_web_button("🍿 Boshqa kinolarni ko'rish", f"/user?user_id={user_id}")]
    ]

    # 1. Telegram file_id mavjud bo'lsa (bir zumda yuboradi)
    if movie.get("telegram_file_id"):
        try:
            await context.bot.send_video(
                chat_id=chat_id,
                video=movie["telegram_file_id"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return
        except Exception:
            log.exception("telegram_file_id orqali yuborishda xato")

    # 2. Serverda saqlangan haqiqiy video faylni Telegram orqali yuborish
    video_path = movie.get("video_file")
    if video_path and Path(video_path).exists():
        file_p = Path(video_path)
        temp_msg = await update.message.reply_text("⏳ Film fayli Telegramga yuklanmoqda va sizga yuborilmoqda, kuting...")
        try:
            with open(file_p, "rb") as vf:
                sent = await context.bot.send_video(
                    chat_id=chat_id,
                    video=vf,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
                if sent.video:
                    movie["telegram_file_id"] = sent.video.file_id
                    db.update_movie(movie)
            await temp_msg.delete()
            return
        except Exception:
            log.exception("Lokal video yuborishda xatolik")
            await temp_msg.edit_text("⚠️ Video yuborishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
            return

    # 3. Agar rasm va URL bo'lsa (eski kinolar uchun)
    poster = movie.get("poster_url")
    if poster and not poster.startswith("/uploads"):
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=poster,
                caption=caption + (f"\n\n▶️ **Video:** {movie.get('video_url', '')}" if movie.get("video_url") else ""),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return
        except Exception:
            pass

    await context.bot.send_message(
        chat_id=chat_id,
        text=caption + (f"\n\n▶️ **Video:** {movie.get('video_url', '')}" if movie.get("video_url") else ""),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    user = update.effective_user
    chat_id = update.effective_chat.id

    db_user = db.register_or_get_user(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name or "",
        username=user.username or "",
    )

    clean_code = text.replace("#", "").replace("/kino", "").strip()
    if clean_code.isdigit() or db.get_movie_by_code(clean_code):
        await deliver_movie(update, context, clean_code, db_user)
        return

    # Gemini AI yordamchi
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    try:
        prompt = (
            "Sen 'Premium Kinolar' Telegram boti yordamchisisan. "
            "Foydalanuvchiga kino topishda yordam berasan va xushmuomala bo'lasan. "
            "Agar foydalanuvchi kino so'rasa, unga kino kodini yozishni yoki veb-sahifaga kirishni tavsiya qil. "
            f"Foydalanuvchi xabari: {text}"
        )
        res = await ai_client.aio.models.generate_content(
            model=MODEL, contents=prompt
        )
        reply = res.text or "Sizga qanday yordam bera olaman?"
    except Exception:
        reply = (
            "Kino kodini yuboring (masalan: 101) yoki veb katalogimizdan foydalaning!"
        )

    keyboard = [
        [create_web_button("🎬 Kinolar Katalogi (Web)", f"/user?user_id={user.id}")]
    ]
    await update.message.reply_text(
        reply, reply_markup=InlineKeyboardMarkup(keyboard)
    )


# Admin Telegram orqali to'g'ridan-to'g'ri video tashlasa
async def admin_video_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != OWNER_ID:
        return

    video = update.message.video or update.message.document
    if not video:
        return

    caption = (update.message.caption or "").strip()
    if caption:
        parts = caption.split(maxsplit=2)
        code = parts[0].replace("#", "")
        title = parts[1] if len(parts) > 1 else f"Kino #{code}"
        desc = parts[2] if len(parts) > 2 else "Yangi premyera film"
        try:
            new_m = db.add_movie(
                title=title,
                code=code,
                description=desc,
                poster_url="",
                video_url="",
                video_file="",
                telegram_file_id=video.file_id,
            )
            await update.message.reply_text(
                f"🎉 **Kino Telegram orqali muvaffaqiyatli saqlandi!**\n\n"
                f"🎬 Nomi: {title}\n"
                f"🔑 Kodi: `#{code}`\n"
                f"📌 Tavsif: {desc}\n\n"
                "Film darhol veb katalogga va botga qo'shildi!"
            )
            return
        except Exception as e:
            await update.message.reply_text(f"⚠️ Xatolik: {e}")
            return

    await update.message.reply_text(
        "📹 **Video qabul qilindi!**\n"
        "Ushbu kinoni avtomatik saqlash uchun videoni izoh (caption) bilan yuboring:\n\n"
        "Format: `<kod> <kino nomi> <tavsif>`\n"
        "Masalan: `105 Forsaj 10 Ajoyib poyga filmi`"
    )


# --- TELEGRAM STARS TO'LOV HANDLERLARI ---
async def buy_stars_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id

    prices = [LabeledPrice(label="1 Oylik Premium Obuna (50 ⭐️)", amount=50)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="🎬 Premium Kinolar Obunasi",
        description="1 oylik to'liq Premium obuna. Barcha premyera filmlar kodlarini ochish va yuklab olish.",
        payload=f"stars_sub_{user.id}",
        currency="XTR",
        prices=prices,
        provider_token="",
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    # To'lovga rozilik bildirish
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    user = update.effective_user
    stars_amount = payment.total_amount

    # Bazada foydalanuvchi obunasini yoqish
    db.activate_user_payment(user.id, f"{stars_amount} Stars (XTR)")

    await update.message.reply_text(
        f"🎉 **To‘lovingiz muvaffaqiyatli qabul qilindi!** ({stars_amount} ⭐️)\n\n"
        "✅ Sizning **Premium** obunangiz faollashtirildi!\n"
        "Endi barcha filmlar kodlari ochildi. Veb-katalog orqali istalgan filmni tanlab, botda tomosha qilishingiz mumkin.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [create_web_button("🍿 Kinolarni ko'rish", f"/user?user_id={user.id}")]
        ]),
    )


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data and query.data.startswith("buy_stars"):
        user = update.effective_user
        prices = [LabeledPrice(label="1 Oylik Premium Obuna (50 ⭐️)", amount=50)]
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="🎬 Premium Kinolar Obunasi",
            description="1 oylik to'liq Premium obuna. Barcha premyera filmlar kodlarini ochish va yuklab olish.",
            payload=f"stars_sub_{user.id}",
            currency="XTR",
            prices=prices,
            provider_token="",
        )


# Telegram Bot Handlerlarini ro'yxatdan o'tkazish
tg_app.add_handler(CommandHandler("start", start_handler))
tg_app.add_handler(CommandHandler("buy", buy_stars_handler))
tg_app.add_handler(CommandHandler("obuna", buy_stars_handler))
tg_app.add_handler(CallbackQueryHandler(callback_query_handler))
tg_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
tg_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
tg_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, admin_video_upload_handler))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


# --- FASTAPI WEB SERVER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Telegram Bot ishga tushmoqda...")
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    log.info("Telegram Bot muvaffaqiyatli ishga tushdi va xabarlarni qabul qilmoqda!")
    yield
    log.info("Telegram Bot to'xtatilmoqda...")
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()


app = FastAPI(title="Premium Kinolar Platform", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik fayllar va Yuklangan fayllar
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "Premium Kinolar"}


# Sahifalar
@app.get("/")
@app.get("/user")
async def user_page():
    return FileResponse(STATIC_DIR / "user.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


# API: Kinolar ro'yxati
@app.get("/api/movies")
async def get_movies():
    return db.load_movies()


# API: Yangi kino qo'shish (FAYL SIFATIDA)
@app.post("/api/movies")
async def create_movie(
    title: str = Form(...),
    code: str = Form(...),
    description: str = Form(...),
    video_file: Optional[UploadFile] = File(None),
    poster_file: Optional[UploadFile] = File(None),
    poster_url: Optional[str] = Form(""),
    video_url: Optional[str] = Form(""),
):
    clean_code = str(code).strip()
    saved_video_path = ""
    saved_poster_url = poster_url or ""

    # Video faylni saqlash
    if video_file and video_file.filename:
        ext = Path(video_file.filename).suffix or ".mp4"
        safe_name = f"{clean_code}_{int(asyncio.get_event_loop().time())}{ext}"
        dest = UPLOADS_VIDEOS_DIR / safe_name
        with open(dest, "wb") as f:
            while chunk := await video_file.read(1024 * 1024 * 4):  # 4MB bo'laklar
                f.write(chunk)
        saved_video_path = str(dest)

    # Poster rasm faylini saqlash
    if poster_file and poster_file.filename:
        ext = Path(poster_file.filename).suffix or ".jpg"
        safe_name = f"{clean_code}_{int(asyncio.get_event_loop().time())}{ext}"
        dest = UPLOADS_POSTERS_DIR / safe_name
        with open(dest, "wb") as f:
            while chunk := await poster_file.read(1024 * 1024 * 2):
                f.write(chunk)
        saved_poster_url = f"/uploads/posters/{safe_name}"

    if not saved_video_path and not video_url:
        raise HTTPException(status_code=400, detail="Iltimos, kino video faylini yuklang!")

    try:
        new_movie = db.add_movie(
            title=title,
            code=clean_code,
            description=description,
            poster_url=saved_poster_url,
            video_url=video_url or "",
            video_file=saved_video_path,
        )
        return {"ok": True, "movie": new_movie}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/movies/{movie_id}")
async def remove_movie(movie_id: str):
    success = db.delete_movie(movie_id)
    if not success:
        raise HTTPException(status_code=404, detail="Kino topilmadi")
    return {"ok": True}


# API: Foydalanuvchilar (Obunachilar)
@app.get("/api/users")
async def get_users():
    return db.load_users()


@app.post("/api/users/{user_id}/toggle")
async def toggle_user(user_id: int):
    try:
        updated = db.toggle_user_status(user_id)
        try:
            status_text = "faollashtirildi! 🎉 Endi barcha filmlarni ko'rishingiz mumkin." if updated.get("status") == "active" else "to'xtatildi. ⚠️"
            await tg_app.bot.send_message(
                chat_id=user_id,
                text=f"Hurmatli foydalanuvchi! Sizning obunangiz admin tomonidan {status_text}",
            )
        except Exception:
            pass
        return {"ok": True, "user": updated}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/me")
async def get_my_info(user_id: int = Query(...)):
    user = db.get_user(user_id)
    if not user:
        user = db.register_or_get_user(user_id)
    return user


# API: Telegram Stars To'lov havolasi yaratish
@app.post("/api/create-stars-invoice")
async def create_stars_invoice(req: Request):
    try:
        body = await req.json()
        user_id = body.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id kiritilishi shart!")

        invoice_link = await tg_app.bot.create_invoice_link(
            title="🎬 Premium Kinolar Obunasi",
            description="1 oylik to'liq Premium obuna. Barcha filmlarni yuklab olish va tomosha qilish.",
            payload=f"stars_sub_{user_id}",
            currency="XTR",
            prices=[LabeledPrice(label="1 Oylik Obuna (50 ⭐️)", amount=50)],
            provider_token="",
        )
        return {"ok": True, "invoice_link": invoice_link}
    except Exception as e:
        log.exception("Stars invoice yaratishda xato")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    listen_port = int(os.getenv("PORT", PORT))
    log.info(f"Premium Kinolar serveri {listen_port}-portda ishga tushmoqda...")
    uvicorn.run("bot:app", host="0.0.0.0", port=listen_port, reload=False)


if __name__ == "__main__":
    main()
