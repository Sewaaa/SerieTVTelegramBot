import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Leggi le variabili d'ambiente (Railway le gestisce automaticamente)
TOKEN = os.getenv("TOKEN")  # Token del bot
CHANNEL_ID = os.getenv("CHANNEL_ID")  # ID del canale privato (deve essere in formato stringa)

# Database per le serie TV (in memoria per ora)
database = {}

# Funzione per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not database:
        await update.message.reply_text("Non ci sono serie TV disponibili al momento.")
        return

    buttons = [
        [InlineKeyboardButton(serie["nome"], callback_data=serie_id)]
        for serie_id, serie in database.items()
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)

# Funzione per aggiungere i video al database
async def leggi_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post and update.channel_post.video:
        file_id = update.channel_post.video.file_id
        titolo = update.channel_post.caption or "Senza titolo"

        # Aggiungi al database
        if "Serie TV 1" not in database:
            database["serie1"] = {
                "nome": "Serie TV 1",
                "stagioni": {
                    "Stagione 1": []
                }
            }
        database["serie1"]["stagioni"]["Stagione 1"].append({"episodio": titolo, "file_id": file_id})
        print(f"Aggiunto: {titolo}, File ID: {file_id}")

# Configurazione del bot
def main():
    # Controllo che TOKEN e CHANNEL_ID siano presenti
    if not TOKEN or not CHANNEL_ID:
        raise ValueError("TOKEN o CHANNEL_ID non configurati nelle variabili d'ambiente.")

    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))

    # Avvia il bot
    application.run_polling()

if __name__ == "__main__":
    main()
