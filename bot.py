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
    if not database:
        await update.message.reply_text("Non ci sono serie TV disponibili al momento.")
        return

    # Mostra la lista delle serie TV
    buttons = [
        [InlineKeyboardButton(serie["nome"], callback_data=serie_id)]
        for serie_id, serie in database.items()
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)

# Funzione per gestire il click sulla serie e mostrare le stagioni
async def mostra_stagioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serie_id = query.data  # Ottieni l'ID della serie dal callback data
    serie = database.get(serie_id)

    if serie:
        # Mostra le stagioni disponibili per la serie selezionata
        buttons = [
            [InlineKeyboardButton(f"Stagione {stagione}", callback_data=f"{serie_id}|{stagione}")]
            for stagione in sorted(serie["stagioni"].keys())  # Ordina le stagioni numericamente
        ]
        buttons.append([InlineKeyboardButton("Torna alla lista", callback_data="indietro")])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(f"Scegli una stagione di {serie['nome']}:", reply_markup=reply_markup)

# Funzione per mostrare gli episodi di una stagione
async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Ottieni serie ID e numero stagione dal callback data
    serie_id, stagione = query.data.split("|")
    stagione = int(stagione)  # Converti in intero
    serie = database.get(serie_id)

    if serie and stagione in serie["stagioni"]:
        # Mostra gli episodi della stagione selezionata
        episodi = serie["stagioni"][stagione]
        buttons = [
            [InlineKeyboardButton(ep["episodio"], callback_data=f"play|{ep['file_id']}")]
            for ep in episodi
        ]
        buttons.append([InlineKeyboardButton("Torna indietro", callback_data=serie_id)])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(f"Episodi di {serie['nome']} - Stagione {stagione}:", reply_markup=reply_markup)

# Funzione per inviare un episodio selezionato
async def invia_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Ottieni il file_id dell'episodio selezionato
    file_id = query.data.split("|")[1]
    await query.message.reply_video(video=file_id)

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
            print("Formato della descrizione non valido.")
            return

        serie_nome, stagione, episodio = match.groups()

        # Converti stagione ed episodio in numeri
        stagione = int(stagione)
        episodio = int(episodio)

        # Costruisci il titolo in automatico (es. "S1EP1")
        titolo = f"S{stagione}EP{episodio}"

        # Aggiungi la serie al database se non esiste
        serie_id = serie_nome.lower().replace(" ", "_")  # Usa un ID unico per ogni serie
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
            "file_id": file_id
        })

        print(f"Aggiunto: {serie_nome} - Stagione {stagione}, Episodio {episodio}: {titolo}")

# Configurazione del bot
def main():
    # Controllo che TOKEN e CHANNEL_ID siano presenti
    if not TOKEN or not CHANNEL_ID:
        raise ValueError("TOKEN o CHANNEL_ID non configurati nelle variabili d'ambiente.")

    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern="^(?!play|indietro).*"))
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=".*\|\d+"))
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern="^play\|"))
    application.add_handler(CallbackQueryHandler(torna_indietro, pattern="^indietro$"))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))

    # Avvia il bot
    application.run_polling()

if __name__ == "__main__":
    main()
