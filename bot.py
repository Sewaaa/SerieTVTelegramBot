from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Funzione per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono il tuo bot. Puoi accedere alle serie TV cliccando sui pulsanti!")

# Funzione per rispondere a un messaggio
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hai scritto: {update.message.text}")

# Configurazione del bot
def main():
    import os
    TOKEN = os.getenv("TOKEN")  # Prende il token dalla variabile d'ambiente

    # Creazione dell'applicazione
    application = Application.builder().token(TOKEN).build()

    # Comandi e funzioni del bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))  # Alias di /start
    application.add_handler(CallbackQueryHandler(echo))

    # Avvia il bot
    application.run_polling()

if __name__ == "__main__":
    main()
