import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re  # Per estrarre i dati dalla descrizione

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


async def mostra_stagioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serie_id = query.data  # Ottieni l'ID della serie dal callback data
    serie = database.get(serie_id)

    print(f"DEBUG: mostra_stagioni chiamata. Serie ID: {serie_id}, Serie: {serie}")  # Debug

    if serie:
        # Crea i pulsanti per le stagioni
        buttons = []
        for stagione in sorted(serie["stagioni"].keys()):  # Ordina le stagioni numericamente
            callback_data = f"{serie_id}|{stagione}"  # Crea il callback data
            print(f"DEBUG: Pulsante creato - Stagione {stagione}, callback_data={callback_data}")  # Debug
            buttons.append([InlineKeyboardButton(f"Stagione {stagione}", callback_data=callback_data)])

        # Aggiungi un pulsante per tornare alla lista delle serie
        buttons.append([InlineKeyboardButton("Torna alla lista", callback_data="indietro")])

        reply_markup = InlineKeyboardMarkup(buttons)

        # Modifica il messaggio per mostrare le stagioni
        try:
            await query.message.edit_text(f"Scegli una stagione di {serie['nome']}:", reply_markup=reply_markup)
            print(f"DEBUG: Messaggio aggiornato per mostrare le stagioni di {serie['nome']}.")  # Debug
        except Exception as e:
            print(f"DEBUG: Errore nell'aggiornamento del messaggio delle stagioni: {e}")  # Debug
    else:
        print(f"DEBUG: Nessuna serie trovata con ID {serie_id}.")  # Debug
        await query.message.edit_text("Errore: serie non trovata nel database.")

async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        # Ottieni serie ID e numero stagione dal callback data
        serie_id, stagione = query.data.split("|")
        stagione = int(stagione)  # Converti in intero
        print(f"DEBUG: mostra_episodi chiamata. Serie ID: {serie_id}, Stagione: {stagione}")  # Debug
    except ValueError as e:
        print(f"DEBUG: Errore nel parsing del callback data: {query.data}, errore: {e}")
        await query.message.edit_text("Errore: callback data non valido.")
        return

    # Recupera la serie dal database
    serie = database.get(serie_id)
    print(f"DEBUG: Serie trovata: {serie}")  # Debug

    # Controlla se la serie e la stagione esistono nel database
    if serie and stagione in serie["stagioni"]:
        episodi = serie["stagioni"][stagione]
        print(f"DEBUG: Episodi trovati: {episodi}")  # Debug

        # Crea i pulsanti per gli episodi
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
            print("DEBUG: Messaggio aggiornato con la lista degli episodi.")  # Debug
        except Exception as e:
            print(f"DEBUG: Errore nell'aggiornamento del messaggio degli episodi: {e}")  # Debug
    else:
        print(f"DEBUG: Nessun episodio trovato per serie_id={serie_id}, stagione={stagione}")  # Debug
        await query.message.edit_text(
            f"Nessun episodio trovato per {serie['nome']} - Stagione {stagione}."
            if serie else "Errore: serie non trovata nel database."
        )

# Funzione per inviare un episodio selezionato
async def invia_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        # Ottieni episodio_id dal callback data
        episodio_id = query.data.split("|")[1]
        print(f"DEBUG: invia_episodio chiamata. Episodio ID: {episodio_id}")  # Debug

        # Cerca il file_id corrispondente nel database
        for serie in database.values():
            for stagioni in serie["stagioni"].values():
                for episodio in stagioni:
                    if episodio["episodio_id"] == episodio_id:
                        file_id = episodio["file_id"]
                        await query.message.reply_video(video=file_id)
                        print(f"DEBUG: Video inviato per episodio ID: {episodio_id}")  # Debug
                        return

        # Se non troviamo l'episodio
        print(f"DEBUG: Episodio ID non trovato: {episodio_id}")  # Debug
        await query.message.reply_text("Errore: episodio non trovato.")
    except Exception as e:
        print(f"DEBUG: Errore nell'invio dell'episodio: {e}")  # Debug
        await query.message.reply_text("Errore durante l'invio dell'episodio.")


# Funzione per tornare alla lista delle serie
async def torna_indietro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

# Funzione per aggiungere i video al database
async def leggi_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post and update.channel_post.video:
        file_id = update.channel_post.video.file_id
        caption = update.channel_post.caption

        # Estrai i dati dalla descrizione
        match = re.search(
            r"Serie: (.+)\nStagione: (\d+)\nEpisodio: (\d+)", caption, re.IGNORECASE
        )
        if not match:
            print("DEBUG: Formato della descrizione non valido.")
            return

        serie_nome, stagione, episodio = match.groups()

        # Converti stagione ed episodio in numeri
        stagione = int(stagione)
        episodio = int(episodio)

        # Costruisci il titolo in automatico (es. "S1EP1")
        titolo = f"S{stagione}EP{episodio}"

        # Costruisci un identificatore univoco per l'episodio
        episodio_id = f"{serie_nome.lower().replace(' ', '_')}_{stagione}_{episodio}"

        # Aggiungi la serie al database se non esiste
        serie_id = serie_nome.lower().replace(" ", "_")
        if serie_id not in database:
            database[serie_id] = {
                "nome": serie_nome,
                "stagioni": {}
            }

        # Aggiungi la stagione se non esiste
        if stagione not in database[serie_id]["stagioni"]:
            database[serie_id]["stagioni"][stagione] = []

        # Aggiungi l'episodio alla stagione
        database[serie_id]["stagioni"][stagione].append({
            "episodio": titolo,
            "file_id": file_id,
            "episodio_id": episodio_id
        })

        print(f"Aggiunto: {serie_nome} - Stagione {stagione}, Episodio {episodio}: {titolo}")

#stampa del db nei log
async def debug_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Stampa la struttura del database nei log
    print(f"DEBUG: Struttura del database:\n{database}")
    await update.message.reply_text("La struttura del database è stata stampata nei log.")

# Configurazione del bot
def main():
    # Controllo che TOKEN e CHANNEL_ID siano presenti
    if not TOKEN or not CHANNEL_ID:
        raise ValueError("TOKEN o CHANNEL_ID non configurati nelle variabili d'ambiente.")

    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()

   # Funzione per tornare alla lista delle serie
async def torna_alla_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Richiama la funzione /start per mostrare la lista delle serie
    await start(update, context)

    # Registra i callback handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern=r"^[^|]+$"))  # Per le serie
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=r".*\|\d+"))  # Per le stagioni
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern=r"^play\|"))  # Per gli episodi
    application.add_handler(CallbackQueryHandler(torna_alla_lista, pattern=r"^indietro$"))  # Per tornare alla lista
    application.add_handler(CommandHandler("debug", debug_database))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))


    # Avvia il bot
    application.run_polling()

if __name__ == "__main__":
    main()
