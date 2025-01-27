import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
database = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Comando /start ricevuto")
    print(f"Contenuto del database: {database}")

    if not database:
        await update.message.reply_text("Non ci sono serie TV disponibili al momento.")
        return

    buttons = [
        [InlineKeyboardButton(serie["nome"], callback_data=serie_id)]
        for serie_id, serie in database.items()
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    print(f"Pulsanti generati: {buttons}")
    await update.message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)

async def leggi_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post and update.channel_post.video:
        file_id = update.channel_post.video.file_id
        caption = update.channel_post.caption

        match = re.search(r"Serie: (.+)\nStagione: (\d+)\nEpisodio: (\d+)", caption, re.IGNORECASE)
        if not match:
            print("Formato della descrizione non valido.")
            return

        serie_nome, stagione, episodio = match.groups()
        stagione = int(stagione)
        episodio = int(episodio)

        titolo = f"S{stagione}EP{episodio}"
        serie_id = serie_nome.lower().replace(" ", "_")

        if serie_id not in database:
            database[serie_id] = {"nome": serie_nome, "stagioni": {}}
        if stagione not in database[serie_id]["stagioni"]:
            database[serie_id]["stagioni"][stagione] = []
        database[serie_id]["stagioni"][stagione].append({"episodio": titolo, "file_id": file_id})

        print(f"Database aggiornato: {database}")
        print(f"Aggiunto: {serie_nome} - Stagione {stagione}, Episodio {episodio}: {titolo}")

def main():
    if not TOKEN or not CHANNEL_ID:
        raise ValueError("TOKEN o CHANNEL_ID non configurati.")

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))
    application.run_polling()

if __name__ == "__main__":
    main()
