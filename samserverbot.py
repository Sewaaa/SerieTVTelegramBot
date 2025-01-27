from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Database delle serie TV
database = {
    "serie1": {
        "nome": "Serie TV 1",
        "stagioni": {
            "Stagione 1": [
                {"episodio": "Episodio 1", "file_id": "file_id_episodio1"},
                {"episodio": "Episodio 2", "file_id": "file_id_episodio2"}
            ],
            "Stagione 2": [
                {"episodio": "Episodio 1", "file_id": "file_id_episodio3"},
            ]
        }
    },
    "serie2": {
        "nome": "Serie TV 2",
        "stagioni": {
            "Stagione 1": [
                {"episodio": "Episodio 1", "file_id": "file_id_episodio4"},
            ]
        }
    }
}

# Funzione per mostrare la lista delle serie TV
def start(update: Update, context: CallbackContext):
    buttons = [
        [InlineKeyboardButton(serie["nome"], callback_data=serie_id)]
        for serie_id, serie in database.items()
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    update.message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)

# Funzione per mostrare le stagioni di una serie TV
def mostra_stagioni(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    serie_id = query.data
    serie = database.get(serie_id)
    
    if serie:
        buttons = [
            [InlineKeyboardButton(stagione, callback_data=f"{serie_id}|{stagione}")]
            for stagione in serie["stagioni"]
        ]
        buttons.append([InlineKeyboardButton("Torna indietro", callback_data="indietro")])
        reply_markup = InlineKeyboardMarkup(buttons)
        query.edit_message_text(f"Scegli una stagione per *{serie['nome']}*:", reply_markup=reply_markup)

# Funzione per mostrare gli episodi di una stagione
def mostra_episodi(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    data = query.data.split("|")
    serie_id, stagione = data[0], data[1]
    episodi = database[serie_id]["stagioni"].get(stagione, [])
    
    buttons = [
        [InlineKeyboardButton(ep["episodio"], callback_data=f"play|{ep['file_id']}")]
        for ep in episodi
    ]
    buttons.append([InlineKeyboardButton("Torna indietro", callback_data=serie_id)])
    reply_markup = InlineKeyboardMarkup(buttons)
    query.edit_message_text(f"Episodi di *{stagione}*:", reply_markup=reply_markup)

# Funzione per inviare un episodio
def invia_episodio(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    file_id = query.data.split("|")[1]
    query.message.reply_video(video=file_id)

# Funzione per gestire il ritorno indietro
def torna_indietro(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    start(update, context)

# Configurazione del bot
def main():
    updater = Updater("7961156888:AAGjPyKiF9XtIJkw45xYPQ_B7z6ET4z2Xac", use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(mostra_stagioni, pattern="^(?!play|indietro).*"))
    dispatcher.add_handler(CallbackQueryHandler(mostra_episodi, pattern=".*\|.*"))
    dispatcher.add_handler(CallbackQueryHandler(invia_episodio, pattern="^play\|"))
    dispatcher.add_handler(CallbackQueryHandler(torna_indietro, pattern="^indietro$"))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
