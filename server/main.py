"""Сервер ключей + Telegram-бот (оплата звёздами) для Fake GPS.

Запуск: python -m uvicorn main:app --host 0.0.0.0 --port 8000
Переменные окружения: BOT_TOKEN (обязательно), ADMIN_IDS, APP_DOWNLOAD_URL, DB_PATH
"""
import os
import secrets
import sqlite3
import time
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field
from telegram import (BotCommand, BotCommandScopeChat, BotCommandScopeDefault,
                      InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
                      Update)
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, PreCheckoutQueryHandler,
                          filters)

# Тарифы в Telegram Stars: срок в днях -> цена в звёздах.
PRESETS = {1: 15, 7: 75, 30: 250}
PER_DAY = 12
MIN_PRICE = 15
MAX_DAYS = 365
UNUSED_KEY_TTL = 90 * 86400
TRANSFER_COOLDOWN = 3 * 86400

# Секреты загружаются из server/.env. Сам .env не публикуется.
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=False)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).with_name("keys.db")))
APP_DOWNLOAD_URL = os.environ.get("APP_DOWNLOAD_URL", "").strip()
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "8264558707")
try:
    ADMIN_IDS = {int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip()}
except ValueError as exc:
    raise RuntimeError("ADMIN_IDS должен содержать Telegram ID через запятую.") from exc

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def q(sql, args=(), one=False, commit=False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql, args)
        if commit:
            con.commit()
        return cur.fetchone() if one else cur.fetchall()
    finally:
        con.close()


def init_db():
    q("""CREATE TABLE IF NOT EXISTS keys(
        key TEXT PRIMARY KEY,
        days INTEGER NOT NULL,
        created_at INTEGER NOT NULL,
        activated_at INTEGER,
        expires_at INTEGER,
        device_id TEXT,
        tg_user_id INTEGER,
        charge_id TEXT UNIQUE,
        last_transfer_at INTEGER)""", commit=True)


def gen_key():
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(3)]
    return "FGPS-" + "-".join(groups)


def issue_key(days, tg_user_id, charge_id=None):
    if charge_id:
        row = q("SELECT key FROM keys WHERE charge_id=?", (charge_id,), one=True)
        if row:
            return row["key"]
    while True:
        key = gen_key()
        try:
            q("INSERT INTO keys(key, days, created_at, tg_user_id, charge_id) VALUES(?,?,?,?,?)",
              (key, days, int(time.time()), tg_user_id, charge_id), commit=True)
            return key
        except sqlite3.IntegrityError:
            if charge_id and q("SELECT 1 FROM keys WHERE charge_id=?", (charge_id,), one=True):
                return q("SELECT key FROM keys WHERE charge_id=?", (charge_id,), one=True)["key"]


def price_for(days):
    if days in PRESETS:
        return PRESETS[days]
    discount = 0.7 if days >= 30 else 0.9 if days >= 7 else 1.0
    return max(MIN_PRICE, round(days * PER_DAY * discount))


def days_word(n):
    if n % 100 in range(11, 15):
        w = "дней"
    elif n % 10 == 1:
        w = "день"
    elif n % 10 in (2, 3, 4):
        w = "дня"
    else:
        w = "дней"
    return f"{n} {w}"


def fmt_left(sec):
    d, r = divmod(int(sec), 86400)
    h, m = r // 3600, (r % 3600) // 60
    return f"{d} д {h} ч" if d else f"{h} ч {m} мин"


class Req(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    device_id: str = Field(min_length=1, max_length=128)


def bad(msg):
    return {"valid": False, "message": msg}


def good(expires, now):
    return {"valid": True, "expires_at": expires, "now": now}


def lookup(key):
    return q("SELECT * FROM keys WHERE key=?", (key.strip().upper(),), one=True)


WELCOME = ("Привет! Здесь можно купить доступ к приложению Fake GPS.\n"
           "Оплата звёздами Telegram, ключ приходит сразу в этот чат.")


def btn(text, data):
    return InlineKeyboardButton(text, callback_data=data)


def main_menu():
    rows = [
        [btn(f"1 день · {PRESETS[1]} ⭐", "buy:1"), btn(f"7 дней · {PRESETS[7]} ⭐", "buy:7")],
        [btn(f"30 дней · {PRESETS[30]} ⭐", "buy:30"), btn("Своё число дней", "custom")],
        [btn("Мои ключи", "keys")],
    ]
    if APP_DOWNLOAD_URL:
        rows[-1].append(InlineKeyboardButton("Скачать приложение", url=APP_DOWNLOAD_URL))
    return InlineKeyboardMarkup(rows)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("await_days", None)
    await update.message.reply_text(WELCOME, reply_markup=main_menu())


async def setup_commands(bot):
    try:
        await bot.bot.set_my_commands([BotCommand("start", "Открыть меню")],
                                      scope=BotCommandScopeDefault())
    except Exception as exc:
        print("set_my_commands default:", exc)
    for admin in ADMIN_IDS:
        try:
            await bot.bot.set_my_commands(
                [BotCommand("start", "Открыть меню"),
                 BotCommand("getkey", "Создать ключ: /getkey дни [сколько штук]")],
                scope=BotCommandScopeChat(chat_id=admin))
        except Exception as exc:
            print(f"set_my_commands for {admin}:", exc)


async def cmd_getkey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    try:
        days = int(ctx.args[0])
        count = int(ctx.args[1]) if len(ctx.args) > 1 else 1
        assert 1 <= days <= 3650 and 1 <= count <= 10
    except Exception:
        await update.message.reply_text(
            "Пример: /getkey 7 — ключ на 7 дней\n/getkey 30 5 — пять ключей по 30 дней")
        return
    keys = [issue_key(days, uid) for _ in range(count)]
    body = "\n".join(f"<code>{key}</code>" for key in keys)
    await update.message.reply_text(f"Ключи на {days_word(days)}:\n{body}", parse_mode="HTML")


async def send_invoice(ctx, chat_id, days):
    await ctx.bot.send_invoice(
        chat_id=chat_id,
        title=f"Доступ на {days_word(days)}",
        description="Ключ для приложения Fake GPS. Срок начинается с активации в приложении.",
        payload=f"days:{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(days_word(days), price_for(days))],
    )


async def show_keys(ctx, chat_id, uid):
    rows = q("SELECT * FROM keys WHERE tg_user_id=? ORDER BY created_at DESC LIMIT 10", (uid,))
    if not rows:
        await ctx.bot.send_message(chat_id, "У тебя пока нет ключей. Выбери тариф в меню (/start).")
        return
    now = int(time.time())
    lines, keyboard = [], []
    for row in rows:
        if row["activated_at"] is None:
            status = f"не активирован ({days_word(row['days'])})"
        elif row["expires_at"] <= now:
            status = "срок вышел"
        else:
            status = f"активен, осталось {fmt_left(row['expires_at'] - now)}"
            keyboard.append([btn(f"Перенести на другой телефон: {row['key'][-4:]}",
                                 f"transfer:{row['key']}")])
        lines.append(f"<code>{row['key']}</code> — {status}")
    await ctx.bot.send_message(
        chat_id, "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)


async def do_transfer(ctx, chat_id, uid, key):
    row = q("SELECT * FROM keys WHERE key=? AND tg_user_id=?", (key, uid), one=True)
    now = int(time.time())
    if not row:
        msg = "Ключ не найден."
    elif not row["device_id"]:
        msg = "Ключ сейчас не привязан к телефону — просто введи его на новом."
    elif row["last_transfer_at"] and now - row["last_transfer_at"] < TRANSFER_COOLDOWN:
        left = TRANSFER_COOLDOWN - (now - row["last_transfer_at"])
        msg = f"Переносить можно не чаще раза в 3 дня. Попробуй через {fmt_left(left)}."
    else:
        q("UPDATE keys SET device_id=NULL, last_transfer_at=? WHERE key=?", (now, key), commit=True)
        msg = "Готово! Теперь введи этот ключ в приложении на новом телефоне."
    await ctx.bot.send_message(chat_id, msg)


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    uid = query.from_user.id
    if data.startswith("buy:"):
        days = int(data[4:])
        if days in PRESETS:
            await send_invoice(ctx, chat_id, days)
    elif data == "custom":
        ctx.user_data["await_days"] = True
        await ctx.bot.send_message(
            chat_id, f"Напиши число дней от 1 до {MAX_DAYS}. Чем больше срок, тем дешевле каждый день.")
    elif data == "keys":
        await show_keys(ctx, chat_id, uid)
    elif data.startswith("transfer:"):
        await do_transfer(ctx, chat_id, uid, data[9:])


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("await_days"):
        await update.message.reply_text("Нажми /start, чтобы открыть меню.")
        return
    try:
        days = int(update.message.text.strip())
        assert 1 <= days <= MAX_DAYS
    except Exception:
        await update.message.reply_text(f"Нужно целое число от 1 до {MAX_DAYS}.")
        return
    ctx.user_data.pop("await_days", None)
    await update.message.reply_text(f"{days_word(days)} — {price_for(days)} ⭐")
    await send_invoice(ctx, update.effective_chat.id, days)


async def precheckout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    ok = query.invoice_payload.startswith("days:") and query.currency == "XTR"
    await query.answer(ok=ok, error_message=None if ok else "Неверный заказ")


async def on_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    days = int(payment.invoice_payload.split(":")[1])
    key = issue_key(days, update.effective_user.id, payment.telegram_payment_charge_id)
    await update.message.reply_text(
        f"Готово! Твой ключ:\n\n<code>{key}</code>\n\n"
        f"Доступ на {days_word(days)}. Введи ключ в приложении — срок начнётся с момента активации. "
        "Нажми на ключ, чтобы скопировать.",
        parse_mode="HTML")


@asynccontextmanager
async def lifespan(app):
    if not BOT_TOKEN or BOT_TOKEN in {"PUT_NEW_BOT_TOKEN_HERE", "YOUR_BOT_TOKEN"}:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Создай server/.env на основе .env.example "
            "и вставь НОВЫЙ токен бота от @BotFather. Старый токен из переписки нужно отозвать.")
    if not ADMIN_IDS:
        raise RuntimeError("ADMIN_IDS пуст: укажи свой Telegram ID в server/.env")
    init_db()
    bot = Application.builder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", cmd_start))
    bot.add_handler(CommandHandler("getkey", cmd_getkey))
    bot.add_handler(CallbackQueryHandler(on_button))
    bot.add_handler(PreCheckoutQueryHandler(precheckout))
    bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_paid))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    await bot.initialize()
    await setup_commands(bot)
    await bot.start()
    await bot.updater.start_polling()
    yield
    await bot.updater.stop()
    await bot.stop()
    await bot.shutdown()


app = FastAPI(title="Fake GPS License Server", version="1.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True, "service": "fakegps-license-server"}


@app.post("/api/activate")
def api_activate(request: Req):
    now = int(time.time())
    row = lookup(request.key)
    if not row:
        return bad("Ключ не найден. Проверь, что ввёл его без ошибок.")
    if row["device_id"] and row["device_id"] != request.device_id:
        return bad("Этот ключ уже привязан к другому телефону.")
    if row["activated_at"] is None:
        if now - row["created_at"] > UNUSED_KEY_TTL:
            return bad("Срок активации этого ключа истёк.")
        expires = now + row["days"] * 86400
        q("UPDATE keys SET activated_at=?, expires_at=?, device_id=? WHERE key=?",
          (now, expires, request.device_id, row["key"]), commit=True)
        return good(expires, now)
    if row["expires_at"] <= now:
        return bad("Срок этого ключа закончился.")
    if not row["device_id"]:
        q("UPDATE keys SET device_id=? WHERE key=?", (request.device_id, row["key"]), commit=True)
    return good(row["expires_at"], now)


@app.post("/api/status")
def api_status(request: Req):
    now = int(time.time())
    row = lookup(request.key)
    if not row:
        return bad("Ключ не найден.")
    if row["device_id"] != request.device_id:
        return bad("Этот ключ привязан к другому телефону.")
    if row["expires_at"] is None or row["expires_at"] <= now:
        return bad("Срок ключа закончился.")
    return good(row["expires_at"], now)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
                reload=False)
