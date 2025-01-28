import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
import re

# Leggi le variabili d'ambiente
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Database per le serie TV
database = {}

# Funzione per la scansione dei vecchi video dal canale
async def scansione_canale(context: ContextTypes.DEFAULT_TYPE):
    """Scansiona i vecchi messaggi del canale per aggiungere i video esistenti al database."""
    print("DEBUG: Avvio scansione del canale...")

    offset = None  # Partenza senza offset per scansionare dal primo messaggio
    limit = 50  # Numero massimo di messaggi per richiesta

    try:
        while True:
            updates = await context.bot.get_updates(offset=offset, limit=limit, timeout=5)

            if not updates:  # Se non ci sono messaggi, interrompi
                break

            for update in updates:
                if update.channel_post and update.channel_post.video:
                    # Aggiungi il video al database
                    await leggi_file_id(update, context)

                # Aggiorna l'offset per il messaggio successivo
                offset = update.update_id + 1

            # Aggiungi un ritardo più lungo tra le richieste per ridurre il carico
            await asyncio.sleep(1)  # Ritardo di 1 secondo

        print("DEBUG: Scansione del canale completata.")
    except Exception as e:
        print(f"DEBUG: Errore durante la scansione del canale: {e}")

# Funzione per aggiungere video al database
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

# Funzione per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        message = update.message
    elif update.callback_query:
        message = update.callback_query.message
    else:
        return

    if not database:
        await message.reply_text("Non ci sono serie TV disponibili al momento.")
        return

    buttons = [
        [InlineKeyboardButton(serie["nome"], callback_data=serie_id)]
        for serie_id, serie in database.items()
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)

# Funzione per mostrare gli episodi
async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serie_id, stagione = query.data.split("|")
    stagione = int(stagione)

    serie = database.get(serie_id)
    if serie and stagione in serie["stagioni"]:
        episodi = serie["stagioni"][stagione]

        buttons = [
            [InlineKeyboardButton(ep["episodio"], callback_data=f"play|{ep['episodio_id']}")]
            for ep in episodi
        ]
        buttons.append([InlineKeyboardButton("Torna indietro", callback_data=serie_id)])

        reply_markup = InlineKeyboardMarkup(buttons)

        await query.message.edit_text(
            f"Episodi di {serie['nome']} - Stagione {stagione}:",
            reply_markup=reply_markup
        )
    else:
        await query.message.edit_text("Nessun episodio trovato.")

# Funzione per inviare un episodio
async def invia_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    episodio_id = query.data.split("|")[1]
    for serie in database.values():
        for stagioni in serie["stagioni"].values():
            for episodio in stagioni:
                if episodio["episodio_id"] == episodio_id:
                    await query.message.reply_video(video=episodio["file_id"])
                    return

    await query.message.reply_text("Errore: episodio non trovato.")

# Configurazione del bot
def main():
    if not TOKEN or not CHANNEL_ID:
        raise ValueError("TOKEN o CHANNEL_ID non configurati nelle variabili d'ambiente.")

    # Configura il pool di connessioni
    request = HTTPXRequest(connection_pool_size=8)

    # Crea l'applicazione con il pool configurato
    application = Application.builder().token(TOKEN).request(request).concurrent_updates(4).build()

    # Registra i comandi e i callback
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=r".*\|\d+"))
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern=r"^play\|"))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))

    # Avvia la scansione del canale per i vecchi video
    application.job_queue.run_once(scansione_canale, when=0)

    # Avvia il bot
    application.run_polling()

if __name__ == "__main__":
    main()
