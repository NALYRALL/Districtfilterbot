import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters, ConversationHandler, CallbackQueryHandler
import json
import time

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation handler
PHOTO, BUTTONS, TRIGGER = range(3)

# Dictionary to store filters for each chat
chat_filters = {}
user_data_store = {}

# Load existing filters if available
def load_filters():
    try:
        with open('filters.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save filters to file
def save_filters():
    with open('filters.json', 'w') as f:
        json.dump(chat_filters, f)

# Load filters on startup
chat_filters = load_filters()

async def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "This bot allows you to create message filters in any group, including private ones.\n\n"
        "*How to use:*\n"
        "1️⃣ Add this bot to your group (must be admin)\n"
        "2️⃣ Use /filter to create a new filter (admin only)\n"
        "3️⃣ Send an image within 60 seconds (or skip with /skip)\n"
        "4️⃣ Create buttons in format: text|url, text2|url2\n"
        "5️⃣ Set the trigger word for your filter\n\n"
        "*Filter Management:*\n"
        "• /filters - List all filters in current chat\n"
        "• /stop - Cancel current operation\n"
        "• /deletefilter <trigger> - Remove a filter (admin only)\n\n"
        "*Advanced Features:*\n"
        "• Supports unlimited filters per group\n"
        "• Works in private groups\n"
        "• Image and button support\n"
        "• Admin-only filter management",
        parse_mode='Markdown'
    )

async def check_admin(update: Update, context: CallbackContext) -> bool:
    """Check if the user is an admin in the group."""
    if update.effective_chat.type == 'private':
        return True

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    try:
        user = await context.bot.get_chat_member(chat_id, user_id)
        return user.status in ('administrator', 'creator')
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def filter_command(update: Update, context: CallbackContext) -> int:
    """Start the filter creation process."""
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id

    # Check if user is admin
    is_admin = await check_admin(update, context)
    if not is_admin:
        await update.message.reply_text("Only admins can create filters.")
        return ConversationHandler.END

    # Initialize user data
    if chat_id not in user_data_store:
        user_data_store[chat_id] = {}

    user_data_store[chat_id][user_id] = {"photo_file_id": None, "buttons": None}

    await update.message.reply_text(
        "Send me an image for the filter or use /skip if you don't want to include an image.",
        reply_to_message_id=update.message.message_id
    )
    return PHOTO

async def photo(update: Update, context: CallbackContext) -> int:
    """Store the photo and ask for button data."""
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id

    if update.message.photo:
        # Get the largest available photo
        photo_file_id = update.message.photo[-1].file_id
        user_data_store[chat_id][user_id]["photo_file_id"] = photo_file_id

    await update.message.reply_text(
        "Great! Now send me the buttons in the format:\n"
        "text1|url1, text2|url2\n\n"
        "Or use /skip if you don't want buttons."
    )
    return BUTTONS

async def skip_photo(update: Update, context: CallbackContext) -> int:
    """Skip the photo step."""
    await update.message.reply_text(
        "No image selected. Now send me the buttons in the format:\n"
        "text1|url1, text2|url2\n\n"
        "Or use /skip if you don't want buttons."
    )
    return BUTTONS

async def buttons(update: Update, context: CallbackContext) -> int:
    """Store the button data and ask for trigger word."""
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id

    if update.message.text != "/skip":
        user_data_store[chat_id][user_id]["buttons"] = update.message.text

    await update.message.reply_text(
        "Almost there! Now, what word or phrase should trigger this filter?"
    )
    return TRIGGER

async def skip_buttons(update: Update, context: CallbackContext) -> int:
    """Skip the buttons step."""
    await update.message.reply_text(
        "No buttons added. Now, what word or phrase should trigger this filter?"
    )
    return TRIGGER

async def trigger(update: Update, context: CallbackContext) -> int:
    """Save the complete filter with the trigger word."""
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    trigger_word = update.message.text.lower()

    # Initialize chat filters if not exists
    if chat_id not in chat_filters:
        chat_filters[chat_id] = {}

    # Create filter structure
    filter_data = {
        "photo_file_id": user_data_store[chat_id][user_id].get("photo_file_id"),
        "buttons": user_data_store[chat_id][user_id].get("buttons"),
        "created_by": user_id,
        "created_at": time.time()
    }

    # Save filter
    chat_filters[chat_id][trigger_word] = filter_data
    save_filters()

    # Clean up user data
    if user_id in user_data_store.get(chat_id, {}):
        del user_data_store[chat_id][user_id]

    await update.message.reply_text(f"Filter for '{trigger_word}' has been created!")
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the current operation."""
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id

    # Clean up user data
    if chat_id in user_data_store and user_id in user_data_store.get(chat_id, {}):
        del user_data_store[chat_id][user_id]

    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def list_filters(update: Update, context: CallbackContext) -> None:
    """List all filters in the current chat."""
    chat_id = str(update.effective_chat.id)

    if chat_id not in chat_filters or not chat_filters[chat_id]:
        await update.message.reply_text("No filters have been set for this chat.")
        return

    message = "Filters in this chat:\n"
    for trigger in chat_filters[chat_id]:
        message += f"• {trigger}\n"

    await update.message.reply_text(message)

async def delete_filter(update: Update, context: CallbackContext) -> None:
    """Delete a filter by trigger word."""
    chat_id = str(update.effective_chat.id)

    # Check if user is admin
    is_admin = await check_admin(update, context)
    if not is_admin:
        await update.message.reply_text("Only admins can delete filters.")
        return

    # Check if there are arguments
    if not context.args:
        await update.message.reply_text("Please specify the trigger word to delete.")
        return

    trigger_word = " ".join(context.args).lower()

    if chat_id in chat_filters and trigger_word in chat_filters[chat_id]:
        del chat_filters[chat_id][trigger_word]
        save_filters()
        await update.message.reply_text(f"Filter '{trigger_word}' has been deleted.")
    else:
        await update.message.reply_text(f"No filter found for '{trigger_word}'.")

async def process_message(update: Update, context: CallbackContext) -> None:
    """Check if a message matches any filter trigger."""
    if not update.message or not update.message.text:
        return

    chat_id = str(update.effective_chat.id)
    text = update.message.text.lower()

    if chat_id not in chat_filters:
        return

    for trigger, filter_data in chat_filters[chat_id].items():
        if trigger in text:
            # Process and send the filter response
            buttons = filter_data.get("buttons")
            keyboard = None

            if buttons:
                keyboard_buttons = []
                rows = buttons.split(", ")

                for row in rows:
                    buttons_in_row = []
                    for button_data in row.split(","):
                        if "|" in button_data:
                            text, url = button_data.strip().split("|", 1)
                            buttons_in_row.append(InlineKeyboardButton(text.strip(), url=url.strip()))
                    if buttons_in_row:
                        keyboard_buttons.append(buttons_in_row)

                if keyboard_buttons:
                    keyboard = InlineKeyboardMarkup(keyboard_buttons)

            if filter_data.get("photo_file_id"):
                await update.message.reply_photo(
                    photo=filter_data["photo_file_id"],
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text(
                    f"Filter triggered by '{trigger}'",
                    reply_markup=keyboard
                )
            break

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(os.environ.get("8131249428:AAHF6M4Yah9pLEaOOhujHanHWTIxk-_0cnQ", "8131249428:AAHF6M4Yah9pLEaOOhujHanHWTIxk-_0cnQ")).build()

    # Add conversation handler for filter creation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("filter", filter_command)],
        states={
            PHOTO: [
                MessageHandler(filters.PHOTO, photo),
                CommandHandler("skip", skip_photo),
            ],
            BUTTONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, buttons),
                CommandHandler("skip", skip_buttons),
            ],
            TRIGGER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, trigger),
            ],
        },
        fallbacks=[CommandHandler("stop", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("filters", list_filters))
    application.add_handler(CommandHandler("deletefilter", delete_filter))
    application.add_handler(CommandHandler("stop", cancel))

    # Add message handler to check for filter triggers
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, process_message
    ))

    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
