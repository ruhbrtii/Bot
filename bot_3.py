import asyncio, aiohttp, sqlite3
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties

# ===== CONFIG =====
CRYPTO_TOKEN = "633267:AABuXtRuRijonfHf2Ewf7QjuSe53gpUdUmg"
BOT_TOKEN    = "8625668503:AAFWioq56KwTZZd_aVNRhJKSX72qc7glYJU"
CRYPTO_API   = "https://pay.crypt.bot/api"
ASSET        = "USDT"
LOG_CHAT     = -1003913074849

# ===== DB =====
_write_lock = asyncio.Lock()

def db():
    con = sqlite3.connect("accs.db")
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, invoice_id TEXT UNIQUE, amount REAL,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now')))""")
    con.commit()
    return con
 # ===== CRYPTO API =====
async def api(method, **kw):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{CRYPTO_API}/{method}", params=kw,
                         headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}) as r:
            return await r.json()

async def is_paid(invoice_id):
    j = await api("getInvoices", invoice_id=invoice_id)
    if j.get("ok") and j["result"]["items"]:
        row = j["result"]["items"][0]
        return row["status"] == "paid", float(row["amount"])
    return False, 0.0

async def add_balance(uid, amount):
    async with _write_lock:
        con = db()
        try:
            if con.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone() is None:
                con.execute("INSERT INTO users (id, balance) VALUES (?,?)", (uid, amount))
            else:
                con.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
            con.execute("UPDATE transactions SET status='paid' WHERE user_id=? AND status='active'", (uid,))
            con.commit()
            return con.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()["balance"]
        finally:
            con.close()

# ===== BOT =====
router = Router()

router.message(Command("баланс"))
async def balance(msg):
    con = db()
    try:
        row = con.execute("SELECT balance FROM users WHERE id=?", (msg.from_user.id,)).fetchone()
        await msg.answer(f"💰 Баланс: {row['balance'] if row else 0} USDT")
    finally:
        con.close()

router.message(Command("пополнить"))
async def topup(msg):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("10 USDT", callback_data="t_10"),
         InlineKeyboardButton("25 USDT", callback_data="t_25"),
         InlineKeyboardButton("50 USDT", callback_data="t_50")],
        [InlineKeyboardButton("100 USDT", callback_data="t_100"),
         InlineKeyboardButton("250 USDT", callback_data="t_250")]
    ])
    await msg.answer("Выбери сумму пополнения (USDT через Crypto Bot):", reply_markup=kb)

router.callback_query(F.data.startswith("t_"))
async def make_inv(cb: CallbackQuery, bot: Bot):
    amount = int(cb.data.split("_")[1])
    inv = await api("createInvoice", asset=ASSET, amount=str(amount),
                    custom=str(cb.from_user.id), expires_in=3600)
    if not inv.get("ok"):
return await cb.answer("⚠️ Не удалось создать счёт", show_alert=True)
         r = inv["result"]
         con = db()
         try:
             con.execute("INSERT INTO transactions (user_id, invoice_id, amount) VALUES (?,?,?)",
                         (cb.from_user.id, r["invoice_id"], amount))
             con.commit()
         finally:
             con.close()
         kb = InlineKeyboardMarkup(inline_keyboard=[
             [InlineKeyboardButton("💎 Оплатить в Send", url=r["pay_url"])],
             [InlineKeyboardButton("✅ Я оплатил", callback_data=f"c_{r['invoice_id']}")]
         ])
         try:
             await cb.message.edit_text(
                 f"Счёт создан!\n\n💠 Сумма: {amount} USDT\n⏳ Действует 60 мин — оплати в Send",
                 reply_markup=kb)
         except Exception:
             pass
         await bot.send_message(LOG_CHAT, f"🧾 Счёт: {cb.from_user.id} на {amount} USDT")
     
     router.callback_query(F.data.startswith("c_"))
     async def check(cb: CallbackQuery, bot: Bot):
         inv_id = int(cb.data.split("_", 1)[1])
         paid, amt = await is_paid(inv_id)
         if not paid:
             return await cb.answer("Платёж не найден. Оплати в Send и нажми ещё раз", show_alert=True)
         bal = await add_balance(cb.from_user.id, amt)
         try:
             await cb.message.edit_text(f"✅ Оплачено! Начислено {amt} USDT")
         except Exception:
             pass
         await bot.send_message(LOG_CHAT, f"🟢 ПОПОЛНЕНИЕ: {cb.from_user.id} +{amt} USDT (баланс {bal})")
     
     async def poll_mark():
         while True:
             await asyncio.sleep(30)
             try:
                 con = db()
                 try:
                     rows = con.execute(
                         "SELECT user_id, invoice_id FROM transactions WHERE status='active'").fetchall()
                 finally:
                     con.close()
                 for row in rows:
                     paid, amt = await is_paid(row["invoice_id"])
                     if paid:
                         await add_balance(row["user_id"], amt)
             except Exception:
                 pass
     
     async def main():
         bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
         dp = Dispatcher()
         dp.include_router(router)
         asyncio.create_task(poll_mark())
         await dp.start_polling(bot)
     
     if name == "main":
         asyncio.run(main())
     
     И `requirements.txt`:
     aiogram==3.10.0
     aiohttp==3.9.5   
