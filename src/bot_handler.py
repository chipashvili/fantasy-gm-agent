import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from memory_manager import MemoryManager

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

class BotHandler:
    def __init__(self):
        self.memory = MemoryManager()
        if not TELEGRAM_TOKEN:
            print("Warning: TELEGRAM_TOKEN not found in environment.")
            self.app = None
            return
        
        self.app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("update_cookie", self.update_cookie))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        self.approval_callbacks = {}  # action_id -> callback_func

    async def update_cookie(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
            return
            
        if not context.args:
            await update.message.reply_text("Please provide the cookie: /update_cookie <your_espn_s2>")
            return
            
        new_cookie = context.args[0]
        os.environ["ESPN_S2"] = new_cookie
        await update.message.reply_text("✅ ESPN_S2 Cookie updated successfully in memory! The agent will use this for the next scheduled job.")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
            await update.message.reply_text("Unauthorized user.")
            return
        await update.message.reply_text("🏈 Fantasy GM Agent is online and monitoring your roster!")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
            return
        await update.message.reply_text("All systems nominal. Scanning waiver wire and lineup health...")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if data.startswith("approve_"):
            action_id = data.split("_", 1)[1]
            await query.edit_message_text(text=f"✅ Approved action: {action_id}")
            self.memory.log_decision(action_id, True, query.message.text)
            if action_id in self.approval_callbacks:
                res = self.approval_callbacks[action_id](approved=True)
                if asyncio.iscoroutine(res):
                    await res
                
        elif data.startswith("reject_"):
            action_id = data.split("_", 1)[1]
            await query.edit_message_text(text=f"❌ Rejected action: {action_id}")
            self.memory.log_decision(action_id, False, query.message.text)
            if action_id in self.approval_callbacks:
                res = self.approval_callbacks[action_id](approved=False)
                if asyncio.iscoroutine(res):
                    await res

    async def send_trade_proposal(self, message: str, action_id: str, callback_func):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print(f"[DRY RUN / NO BOT] Trade Proposal: {message}")
            return
            
        self.approval_callbacks[action_id] = callback_func
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{action_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{action_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        temp_bot = Bot(token=TELEGRAM_TOKEN)
        await temp_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, reply_markup=reply_markup)

    async def send_approval_request(self, message: str, action_id: str, callback):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print(f"[DRY RUN / NO BOT] Would ask for approval: {message}")
            return
            
        self.approval_callbacks[action_id] = callback
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{action_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{action_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        temp_bot = Bot(token=TELEGRAM_TOKEN)
        await temp_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, reply_markup=reply_markup)

    async def send_alert(self, message: str):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print(f"[DRY RUN / NO BOT] Alert: {message}")
            return
        # Use a raw Bot instance for outbound alerts to avoid hanging if the app loop hasn't started
        temp_bot = Bot(token=TELEGRAM_TOKEN)
        await temp_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

    def run_polling(self):
        if self.app:
            self.app.run_polling()
