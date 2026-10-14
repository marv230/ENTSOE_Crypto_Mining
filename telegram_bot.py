from pathlib import Path
import re
from telegram import Update
from telegram.constants import MessageLimit
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import main

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Stopping bot...')
    exit(0)

def split_message(text: str, max_length: int = MessageLimit.MAX_TEXT_LENGTH) -> list[str]:
    if not text:
        return []

    messages = []
    current_chunk = ""
    for line in text.splitlines(keepends=True):
        if len(current_chunk) + len(line) <= max_length:
            current_chunk += line
        else:
            if current_chunk:
                messages.append(current_chunk)
            current_chunk = line

    if current_chunk:
        messages.append(current_chunk)

    return messages

async def prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Split output of function into messages able to be sent
    price_data = main.update_data()
    for msg in split_message(price_data):
        await update.message.reply_text(msg)

async def help_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Available commands:\n/start - Start the bot\n/stop - Stop the bot\n/prices - Get current prices\n/help - Display this message')



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
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("prices", prices))
    application.add_handler(CommandHandler("help", help_msg))

    # Run the bot until you send a signal to stop
    application.run_polling()