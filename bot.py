from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Funzione per il comando /start
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Ciao! Sono il tuo bot. Puoi accedere alle serie TV cliccando sui pulsanti!")

# Funzione per rispondere a un messaggio
def echo(update: Update, context: CallbackContext):
    update.message.reply_text(f"Hai scritto: {update.message.text}")

# Configurazione del bot
def main():
    import os
    TOKEN = os.getenv("7961156888:AAGjPyKiF9XtIJkw45xYPQ_B7z6ET4z2Xac")  # Prende il token dalla variabile d'ambiente
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Comandi e funzioni del bot
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))
    dispatcher.add_handler(CallbackQueryHandler(echo))

    # Avvia il bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
