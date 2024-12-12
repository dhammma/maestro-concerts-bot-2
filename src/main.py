import json
import sqlite3
import asyncio
import logging
import sys
from os import getenv
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message
from aiogram.utils.payload import decode_payload, encode_payload
from aiogram.utils.text_decorations import markdown_decoration
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import uvicorn

load_dotenv()
T_TOKEN = getenv("BOT_TOKEN")
X_TOKEN = getenv("MONOBANK_TOKEN")
VALIDATION_KEY = getenv("VALIDATION_KEY")
dp = Dispatcher()
app = FastAPI()

# Підключення до бази даних SQLite
def db_connect():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn

# Реєстрація нового користувача
async def register_user(message: types.Message):
    conn = db_connect()
    cursor = conn.cursor()
    user_id = message.from_user.id
    username = message.from_user.username

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    if cursor.fetchone():
        await message.reply("Ви вже зареєстровані!")
    else:
        cursor.execute("INSERT INTO users (id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        await message.reply("Ви успішно зареєстровані!")

    conn.close()

# Ініціювання платежу через Monobank
async def topup_balance(message: types.Message):
    url = "https://api.monobank.ua/api/merchant/invoice/create"
    payload = {
        "amount": 10000,
        "merchantPaymInfo": {
            "reference": "prepaid-10",
            "destination": "Поповнення рахунку на 100 гривень",
            "comment": "Поповнення рахунку на 100 гривень",
            "customerEmails": [],
            "basketOrder": [
                {
                    "name": "Поповнення рахунку на 100 гривень",
                    "qty": 1,
                    "sum": 10000,
                    "total": 10000,
                    "code": "d21da1c47f3c45fca10a10c32518bdeb",
                    "icon": "https://www.ua-coins.info/images/coins/1943_obverse.jpg"
                }
            ]
        },
        "redirectUrl": "https://t.me/Maestro_Concerts_Bot",
        "webHookUrl": f"https://bot-2.misolla.io/callback_url/{message.from_user.username}",
        "code": "0a8637b3bccb42aa93fdeb791b8b58e9"
    }
    headers = {
        'X-Token': X_TOKEN
    }
    response = requests.request("POST", url, headers=headers, data=json.dumps(payload, indent=2))
    await message.answer(f"Для поповнення рахунку скористайтесь посиланням:\n{response.json()['pageUrl']}")

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    if " " in message.text:
        try:
            parameter = message.text.split(" ", 1)[1]  # Отримуємо параметр
            payload = decode_payload(parameter)
            await message.answer(f"Your payload is {payload}")
        except Exception as e:
            await message.answer(f"🚔 За вами виїхала кіберполіція")
    else:
        await message.answer(f"Вітаю, {markdown_decoration.bold(message.from_user.full_name)}!")



dp.message.register(register_user, Command(commands=["register"]))
dp.message.register(topup_balance, Command(commands=["topup"]))

# HTTP ендпоінт для виконання дії в боті
@app.post("/callback_url/{user_name}")
async def perform_action(user_name, payload: dict):
    print(user_name)
    print(json.dumps(payload, indent=2))
    if payload["status"] == "success":
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (100000, user_name))
        conn.commit()
        conn.close()

    return {"success": True}

bot = Bot(token=T_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))

async def start_polling():
    """Запускає polling для aiogram бота"""
    await dp.start_polling(bot)

@app.on_event("startup")
async def on_startup():
    """Цей метод викликається при запуску FastAPI"""
    asyncio.create_task(start_polling())  # Створюємо задачу для polling

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    # Запуск серверу та aiogram бота одночасно
    uvicorn.run(app, host="localhost", port=8000)