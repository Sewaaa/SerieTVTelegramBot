import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re

# Leggi le variabili d'ambiente
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Database per le serie TV
database = {}

# Funzione per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Controlla se l'update proviene da un messaggio o da un callback
    if update.message:
        message = update.message
    elif update.callback_query:
        message = update.callback_query.message
    else:
        return  # Nessun messaggio disponibile

    if not database:
        await message.reply_text("Non ci sono serie TV disponibili al momento.")
        return

    # Mostra la lista delle serie TV
    buttons = [
        [InlineKeyboardButton(serie["nome"], callback_data=serie_id)]
        for serie_id, serie in database.items()
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)

# Funzione per mostrare le stagioni
async def mostra_stagioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serie_id = query.data  # Ottieni l'ID della serie dal callback data
    serie = database.get(serie_id)

    print(f"DEBUG: mostra_stagioni chiamata. Serie ID: {serie_id}, Serie: {serie}")

    if serie:
        buttons = []
        for stagione in sorted(serie["stagioni"].keys()):
            callback_data = f"{serie_id}|{stagione}"
            print(f"DEBUG: Pulsante creato - Stagione {stagione}, callback_data={callback_data}")
            buttons.append([InlineKeyboardButton(f"Stagione {stagione}", callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("Torna alla lista", callback_data="indietro")])

        reply_markup = InlineKeyboardMarkup(buttons)

        try:
            await query.message.edit_text(f"Scegli una stagione di {serie['nome']}:", reply_markup=reply_markup)
            print(f"DEBUG: Messaggio aggiornato per mostrare le stagioni di {serie['nome']}.")
        except Exception as e:
            print(f"DEBUG: Errore nell'aggiornamento del messaggio delle stagioni: {e}")
    else:
        print(f"DEBUG: Nessuna serie trovata con ID {serie_id}.")
        await query.message.edit_text("Errore: serie non trovata nel database.")

# Funzione per mostrare gli episodi
async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        serie_id, stagione = query.data.split("|")
        stagione = int(stagione)
        print(f"DEBUG: mostra_episodi chiamata. Serie ID: {serie_id}, Stagione: {stagione}")
    except ValueError as e:
        print(f"DEBUG: Errore nel parsing del callback data: {query.data}, errore: {e}")
        await query.message.edit_text("Errore: callback data non valido.")
        return

    serie = database.get(serie_id)
    print(f"DEBUG: Serie trovata: {serie}")

    if serie and stagione in serie["stagioni"]:
        episodi = serie["stagioni"][stagione]
        print(f"DEBUG: Episodi trovati: {episodi}")

        buttons = [
            [InlineKeyboardButton(ep["episodio"], callback_data=f"play|{ep['episodio_id']}")]
            for ep in episodi
        ]
        buttons.append([InlineKeyboardButton("Torna indietro", callback_data=serie_id)])

        reply_markup = InlineKeyboardMarkup(buttons)

        try:
            await query.message.edit_text(
                f"Episodi di {serie['nome']} - Stagione {stagione}:",
                reply_markup=reply_markup
            )
            print("DEBUG: Messaggio aggiornato con la lista degli episodi.")
        except Exception as e:
            print(f"DEBUG: Errore nell'aggiornamento del messaggio degli episodi: {e}")
    else:
        print(f"DEBUG: Nessun episodio trovato per serie_id={serie_id}, stagione={stagione}")
        await query.message.edit_text(
            f"Nessun episodio trovato per {serie['nome']} - Stagione {stagione}."
            if serie else "Errore: serie non trovata nel database."
        )

# Funzione per inviare un episodio selezionato
async def invia_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        episodio_id = query.data.split("|")[1]
        print(f"DEBUG: invia_episodio chiamata. Episodio ID: {episodio_id}")

        for serie in database.values():
            for stagioni in serie["stagioni"].values():
                for episodio in stagioni:
                    if episodio["episodio_id"] == episodio_id:
                        file_id = episodio["file_id"]
                        await query.message.reply_video(video=file_id)
                        print(f"DEBUG: Video inviato per episodio ID: {episodio_id}")
                        return

        print(f"DEBUG: Episodio ID non trovato: {episodio_id}")
        await query.message.reply_text("Errore: episodio non trovato.")
    except Exception as e:
        print(f"DEBUG: Errore nell'invio dell'episodio: {e}")
        await query.message.reply_text("Errore durante l'invio dell'episodio.")

# Funzione per tornare alla lista delle serie
async def torna_alla_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

# Funzione per aggiungere i video al database
async def leggi_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post and update.channel_post.video:
        file_id = update.channel_post.video.file_id
        caption = update.channel_post.caption

        match = re.search(
            r"Serie: (.+)\nStagione: (\d+)\nEpisodio: (\d+)", caption, re.IGNORECASE
        )
        if not match:
            print("DEBUG: Formato della descrizione non valido.")
            return

        serie_nome, stagione, episodio = match.groups()
        stagione = int(stagione)
        episodio = int(episodio)
        titolo = f"S{stagione}EP{episodio}"
        episodio_id = f"{serie_nome.lower().replace(' ', '_')}_{stagione}_{episodio}"
        serie_id = serie_nome.lower().replace(" ", "_")

        if serie_id not in database:
            database[serie_id] = {
                "nome": serie_nome,
                "stagioni": {}
            }

        if stagione not in database[serie_id]["stagioni"]:
            database[serie_id]["stagioni"][stagione] = []

        database[serie_id]["stagioni"][stagione].append({
            "episodio": titolo,
            "file_id": file_id,
            "episodio_id": episodio_id
        })

        print(f"Aggiunto: {serie_nome} - Stagione {stagione}, Episodio {episodio}: {titolo}")

# Funzione per stampare il database nei log
async def debug_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"DEBUG: Struttura del database:\n{database}")
    await update.message.reply_text("La struttura del database è stata stampata nei log.")

# Configurazione del bot
def main():
    if not TOKEN or not CHANNEL_ID:
        raise ValueError("TOKEN o CHANNEL_ID non configurati nelle variabili d'ambiente.")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern=r"^(?!indietro$)[^|]+$"))  # Per le serie
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=r".*\|\d+"))  # Per le stagioni
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern=r"^play\|"))  # Per gli episodi
    application.add_handler(CallbackQueryHandler(torna_alla_lista, pattern=r"^indietro$"))  # Per tornare alla lista
    application.add_handler(CommandHandler("debug", debug_database))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))


    application.run_polling()

if __name__ == "__main__":
    main()
