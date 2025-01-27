from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, ContextTypes

# ID del canale privato
CHANNEL_ID = "CHANNEL_ID"  

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

        # Aggiungi al database (organizzazione base per ora)
        if "Serie TV 1" not in database:
            database["serie1"] = {
                "nome": "Serie TV 1",
                "stagioni": {
                    "Stagione 1": []
                }
            }
        database["serie1"]["stagioni"]["Stagione 1"].append({"episodio": titolo, "file_id": file_id})
        print(f"Aggiunto: {titolo}, File ID: {file_id}")

# Funzione per mostrare le stagioni di una serie
async def mostra_stagioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serie_id = query.data
    serie = database.get(serie_id)

    if serie:
        buttons = [
            [InlineKeyboardButton(stagione, callback_data=f"{serie_id}|{stagione}")]
            for stagione in serie["stagioni"]
        ]
        buttons.append([InlineKeyboardButton("Torna alla lista", callback_data="indietro")])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(f"Scegli una stagione per {serie['nome']}:", reply_markup=reply_markup)

# Funzione per mostrare gli episodi di una stagione
async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    serie_id, stagione = data[0], data[1]
    episodi = database[serie_id]["stagioni"].get(stagione, [])

    buttons = [
        [InlineKeyboardButton(ep["episodio"], callback_data=f"play|{ep['file_id']}")]
        for ep in episodi
    ]
    buttons.append([InlineKeyboardButton("Torna indietro", callback_data=serie_id)])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(f"Episodi di {stagione}:", reply_markup=reply_markup)

# Funzione per inviare un episodio
async def invia_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    file_id = query.data.split("|")[1]
    await query.message.reply_video(video=file_id)

# Funzione per tornare indietro
async def torna_indietro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

# Configurazione del bot
def main():
    import os
    TOKEN = os.getenv("TOKEN")  # Prendi il token dalla variabile d'ambiente

    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(Filters.video & Filters.chat(CHANNEL_ID), leggi_file_id))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern="^(?!play|indietro).*"))
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=".*\|.*"))
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern="^play\|"))
    application.add_handler(CallbackQueryHandler(torna_indietro, pattern="^indietro$"))

    # Avvia il bot
    application.run_polling()

if __name__ == "__main__":
    main()
