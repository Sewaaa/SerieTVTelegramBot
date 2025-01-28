import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re

# Leggi le variabili d'ambiente
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Database per le serie TV
database = {}

async def scansione_canale(context: ContextTypes.DEFAULT_TYPE):
    async for message in context.bot.get_chat_history(CHANNEL_ID, limit=1000):
        if message.video and message.caption:
            # Usa la funzione leggi_file_id per aggiungere i video al database
            update = Update(update_id=0, channel_post=message)
            await leggi_file_id(update, context)
    print("DEBUG: Scansione del canale completata.")

# Funzione per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        message = update.message
    elif update.callback_query:
        message = update.callback_query.message
    else:
        return

    if not database:
        await message.reply_text("Non ci sono serie TV disponibili al momento.")
        return

    buttons = [
        [InlineKeyboardButton(serie["nome"], callback_data=serie_id)]
        for serie_id, serie in database.items()
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)

# Configurazione del bot
def main():
    if not TOKEN or not CHANNEL_ID:
        raise ValueError("TOKEN o CHANNEL_ID non configurati nelle variabili d'ambiente.")

    # Crea l'applicazione con JobQueue abilitato
    application = Application.builder().token(TOKEN).post_init(lambda app: app.job_queue.start()).build()

    # Registra i comandi e i callback
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern=r"^(?!indietro$)[^|]+$"))
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=r".*\|\d+"))
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern=r"^play\|"))
    application.add_handler(CallbackQueryHandler(torna_alla_lista, pattern=r"^indietro$"))
    application.add_handler(CommandHandler("debug", debug_database))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))

    # Scansione del canale per i vecchi video
    application.job_queue.run_once(scansione_canale, when=0)

    # Avvia il bot
    application.run_polling()

if __name__ == "__main__":
    main()
