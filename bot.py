import os
from collections import defaultdict
from google import genai
from google.genai import types
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, MessageHandler, filters

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SYSTEM = os.getenv(
    "SYSTEM_PROMPT",
    "You are a friendly member of a Telegram group. "
    "Reply in the same language as the user, short and casual.",
)
history = defaultdict(list)  # chat_id -> list of (role, text)


async def reply(update, context):
    msg = update.message
    if not msg or not msg.text:
        return

    me = context.bot.username
    if msg.chat.type in ("group", "supergroup"):
        mentioned = f"@{me}" in msg.text
        replied = (
            msg.reply_to_message
            and msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.id == context.bot.id
        )
        if not (mentioned or replied):
            return

    text = msg.text.replace(f"@{me}", "").strip()
    h = history[msg.chat_id]
    h.append(("user", f"{msg.from_user.first_name}: {text}"))
    del h[:-20]  # only the last 20 messages

    await context.bot.send_chat_action(msg.chat_id, ChatAction.TYPING)
    try:
        contents = [
            types.Content(role=role, parts=[types.Part(text=t)]) for role, t in h
        ]
        r = await client.aio.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=SYSTEM),
        )
        answer = r.text or "..."
    except Exception as e:
        h.pop()  # drop the failed user message
        await msg.reply_text(f"خطا: {type(e).__name__}: {e}"[:500])
        return

    h.append(("model", answer))
    await msg.reply_text(answer)


app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
app.run_polling()
