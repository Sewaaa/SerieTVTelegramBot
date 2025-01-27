from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Log del callback data ricevuto
    print(f"Callback data ricevuto: {query.data}")

    try:
        # Estrarre serie_id e stagione dal callback data
        serie_id, stagione = query.data.split("|")
        stagione = int(stagione)  # Converti in intero
        serie = database.get(serie_id)

        if not serie:
            print(f"Errore: Serie {serie_id} non trovata nel database.")
            await query.edit_message_text("Errore: Serie non trovata.")
            return

        if stagione not in serie["stagioni"]:
            print(f"Errore: Stagione {stagione} non trovata nella serie {serie_id}.")
            await query.edit_message_text("Errore: Stagione non trovata.")
            return

        # Recupera gli episodi della stagione
        episodi = serie["stagioni"][stagione]
        if not episodi:
            print(f"Nessun episodio trovato per Serie {serie_id}, Stagione {stagione}.")
            await query.edit_message_text("Nessun episodio trovato.")
            return

        # Genera i pulsanti per gli episodi
        buttons = [
            [InlineKeyboardButton(ep["episodio"], callback_data=f"play|{ep['file_id']}")]
            for ep in episodi
        ]
        buttons.append([InlineKeyboardButton("Torna indietro", callback_data=serie_id)])
        reply_markup = InlineKeyboardMarkup(buttons)

        # Mostra gli episodi
        await query.edit_message_text(
            f"Episodi di {serie['nome']} - Stagione {stagione}:",
            reply_markup=reply_markup
        )
    except Exception as e:
        # Log dell'errore
        print(f"Errore in mostra_episodi: {e}")
        await query.edit_message_text("Si è verificato un errore durante il caricamento degli episodi.")
