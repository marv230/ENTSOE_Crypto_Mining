from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pathlib import Path
import re
import main

# Function that handles /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! I am your bot. How can I help you today?')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Stopping bot...')
    exit(0)

def get_key() -> str:
    path = Path(main.path_Telegram_token)
    # If key file doesn't exist, instantly abort
    if not path.exists():
        print('./' + path.name + ' not found, aborting....')
        exit(1)

    line = open(path).read()
    match = re.match(r'[0-9]{10}:[a-zA-Z0-9]{13}_[a-zA-Z0-9]{4}_[a-zA-Z0-9]{16}', line)

    if match is None:
        print('No API valid key format found in file, aborting....')
        # TODO: This return will cause any call of use_api() to not be handled correctly by the caller
        exit(1)
    return match.group(0)


def start_bot():
    token = get_key()

    # Use your bot token here
    application = ApplicationBuilder().token(token).build()

    # Register the /start command
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))

    # Run the bot until you send a signal to stop
    application.run_polling()