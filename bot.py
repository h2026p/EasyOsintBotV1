import os
import telebot
from telebot import types
import subprocess
import json
import re
import ipaddress
from openai import OpenAI
from dotenv import load_dotenv

# ================= НАСТРОЙКИ =================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

llm_client = OpenAI(
    api_key="AQ.Ab8RN6KFlO11Dldlf7WGNhS3MDeRN0VEph6OLr8w2V6j4NFzyw",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
GEMINI_MODEL = "gemini-2.5-flash"

bot = telebot.TeleBot(BOT_TOKEN)

# ================= ФУНКЦИИ LLM =================

def ask_llm(system_prompt: str, user_text: str) -> str:
    try:
        response = llm_client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[Ошибка LLM: {str(e)[:200]}]"

def extract_entities(text: str) -> dict:
    system = (
        "Ты — парсер данных. Извлеки из текста пользователя IP-адрес и никнейм. "
        "Верни ТОЛЬКО валидный JSON без markdown-обёрток: "
        '{"ip": "строка или null", "username": "строка или null"}. '
        "Если чего-то нет — ставь null. Не придумывай данные."
    )
    raw = ask_llm(system, text)
    clean = re.sub(r'^```json\s*|\s*```$', '', raw.strip())
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"ip": None, "username": None}

# ================= ФУНКЦИИ OSINT =================

def is_valid_ip(ip_str: str) -> bool:
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False

def run_openosint_ip(ip: str) -> str:
    try:
        result = subprocess.run(
            ["openosint", "ip", ip, "--json"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip()[:2500]
        return f"Ошибка openosint: {result.stderr[:500]}"
    except FileNotFoundError:
        return "openosint не установлен."
    except subprocess.TimeoutExpired:
        return "Таймаут при проверке IP."

def run_openosint_username(username: str) -> str:
    try:
        result = subprocess.run(
            ["openosint", "--allow-active", "username", username, "--json"],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            return result.stdout.strip()[:2500]
        return f"Ошибка openosint: {result.stderr[:500]}"
    except FileNotFoundError:
        return "openosint не установлен."
    except subprocess.TimeoutExpired:
        return "Таймаут при поиске никнейма."

# ================= КЛАВИАТУРЫ =================

def main_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📚 База знаний", callback_data="knowledge_base"),
        types.InlineKeyboardButton("🕵️ OSINT", callback_data="osint_section"),
        types.InlineKeyboardButton("💻 Open-Source", callback_data="opensource_section")
    )
    return kb

def back_keyboard(callback_data="main_menu"):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("◀️ Назад", callback_data=callback_data))
    return kb

# ================= ОБРАБОТЧИКИ =================

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    text = (
        "👋 *Добро пожаловать в OSINT-бота!*\n\n"
        "Выберите раздел:"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown",
                     reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if call.data == "main_menu":
        bot.edit_message_text("👋 *Главное меню*\n\nВыберите раздел:",
                              chat_id, msg_id, parse_mode="Markdown",
                              reply_markup=main_menu_keyboard())
        bot.answer_callback_query(call.id)

    elif call.data == "knowledge_base":
        text = (
            "📚 *База знаний*\n\n"
            "*1. Что такое OSINT?*\n"
            "OSINT — разведка по открытым источникам.\n\n"
            "*2. Где используется?*\n"
            "Кибербезопасность, журналистика, бизнес-разведка.\n\n"
            "*3. Принцип работы*\n"
            "Планирование → Сбор → Обработка → Анализ → Отчёт.\n\n"
            "*4. О боте*\n"
            "Учебный прототип на базе openosint и Google Gemini.\n\n"
            "*5. Что такое Open-Source?*\n"
            "ПО с открытым исходным кодом.\n\n"
            "*6. Как пользоваться?*\n"
            "Нажмите «OSINT» и напишите запрос свободным текстом."
        )
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown",
                              reply_markup=back_keyboard())
        bot.answer_callback_query(call.id)

    elif call.data == "opensource_section":
        text = (
            "💻 *Open-Source*\n\n"
            "Open Source — модель разработки с открытым исходным кодом.\n\n"
            "Большинство OSINT-инструментов (sherlock, holehe, openosint) "
            "являются open-source.\n\n"
            "⚠️ Используйте только в законных целях."
        )
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown",
                              reply_markup=back_keyboard())
        bot.answer_callback_query(call.id)

    elif call.data == "osint_section":
        text = (
            "🕵️ *OSINT-режим*\n\n"
            "Напишите запрос в свободной форме.\n\n"
            "*Пример:*\n"
            "«Найди информацию. IP: 8.8.8.8, никнейм: john_doe»\n\n"
            "Я извлеку данные и проверю их через openosint."
        )
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown",
                              reply_markup=back_keyboard())
        bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_osint_request(message):
    user_text = message.text.strip()
    if not user_text or user_text.startswith('/'):
        return

    bot.send_message(message.chat.id, "🧠 Анализирую запрос...")
    entities = extract_entities(user_text)
    ip = entities.get("ip")
    username = entities.get("username")

    findings = []

    if ip:
        if is_valid_ip(ip):
            bot.send_message(message.chat.id, f"🔍 Проверяю IP: `{ip}`...",
                             parse_mode="Markdown")
            findings.append(f"**Результат по IP {ip}:**\n{run_openosint_ip(ip)}")
        else:
            findings.append(f"⚠️ IP `{ip}` невалиден.")

    if username:
        bot.send_message(message.chat.id,
                         f"🔍 Ищу никнейм: `{username}` (может занять время)...",
                         parse_mode="Markdown")
        findings.append(f"**Результат по никнейму {username}:**\n{run_openosint_username(username)}")

    if not findings:
        bot.reply_to(message, "Не нашёл в тексте ни IP, ни никнейма.")
        return

    raw_data = "\n\n".join(findings)
    final_system = (
        "Ты — дружелюбный OSINT-ассистент. Проанализируй сырые данные и ответь "
        "пользователю связным текстом на русском. Не выдумывай факты."
    )
    final_answer = ask_llm(final_system, f"Запрос: {user_text}\n\nДанные:\n{raw_data}")
    bot.reply_to(message, final_answer[:4000])

# ================= ЗАПУСК =================

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling(timeout=60)