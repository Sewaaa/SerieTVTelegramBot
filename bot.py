import os
import re
import asyncpg
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Leggi le variabili d'ambiente
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DATABASE_URL = os.getenv("DATABASE_URL")  # Stringa di connessione al database

# Funzione per connettersi al database
async def connetti_al_database():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("DEBUG: Connessione al database riuscita.")
        return conn
    except Exception as e:
        print(f"DEBUG: Errore durante la connessione al database: {e}")
        raise

# Funzione per inizializzare le tabelle nel database
async def inizializza_tabelle(conn):
    query = """
    CREATE TABLE IF NOT EXISTS serie (
        id SERIAL PRIMARY KEY,
        serie_id TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS episodi (
        id SERIAL PRIMARY KEY,
        episodio_id TEXT UNIQUE NOT NULL,
        serie_id TEXT REFERENCES serie(serie_id) ON DELETE CASCADE,
        stagione INT NOT NULL,
        episodio INT NOT NULL,
        titolo TEXT NOT NULL,
        file_id TEXT NOT NULL
    );
    """
    await conn.execute(query)
    print("DEBUG: Tabelle inizializzate correttamente.")

# Funzione per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Controlla se l'update proviene da un messaggio o da un callback
    if update.message:
        message = update.message
    elif update.callback_query:
        message = update.callback_query.message
    else:
        return

    conn = await connetti_al_database()
    try:
        # Recupera tutte le serie
        serie = await conn.fetch("SELECT serie_id, nome FROM serie")
        if not serie:
            await message.reply_text("Non ci sono serie TV disponibili al momento.")
            return

        # Crea i pulsanti delle serie
        buttons = [
            [InlineKeyboardButton(record["nome"], callback_data=record["serie_id"])]
            for record in serie
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)
    finally:
        await conn.close()

# Funzione per mostrare le stagioni
async def mostra_stagioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serie_id = query.data
    conn = await connetti_al_database()
    try:
        stagioni = await conn.fetch(
            "SELECT DISTINCT stagione FROM episodi WHERE serie_id = $1 ORDER BY stagione", serie_id
        )
        if not stagioni:
            await query.message.edit_text("Non ci sono stagioni disponibili per questa serie.")
            return

        buttons = [
            [InlineKeyboardButton(f"Stagione {record['stagione']}", callback_data=f"{serie_id}|{record['stagione']}")]
            for record in stagioni
        ]
        buttons.append([InlineKeyboardButton("Torna alla lista", callback_data="indietro")])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text("Scegli una stagione:", reply_markup=reply_markup)
    finally:
        await conn.close()

# Funzione per mostrare gli episodi
async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        serie_id, stagione = query.data.split("|")
        stagione = int(stagione)
    except ValueError:
        await query.message.edit_text("Errore: callback data non valido.")
        return

    conn = await connetti_al_database()
    try:
        episodi = await conn.fetch(
            "SELECT episodio_id, titolo FROM episodi WHERE serie_id = $1 AND stagione = $2 ORDER BY episodio",
            serie_id, stagione
        )
        if not episodi:
            await query.message.edit_text("Non ci sono episodi disponibili per questa stagione.")
            return

        buttons = [
            [InlineKeyboardButton(record["titolo"], callback_data=f"play|{record['episodio_id']}")]
            for record in episodi
        ]
        buttons.append([InlineKeyboardButton("Torna indietro", callback_data=serie_id)])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text("Scegli un episodio:", reply_markup=reply_markup)
    finally:
        await conn.close()

# Funzione per inviare un episodio selezionato
async def invia_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        episodio_id = query.data.split("|")[1]

        conn = await connetti_al_database()
        try:
            episodio = await conn.fetchrow(
                "SELECT file_id FROM episodi WHERE episodio_id = $1", episodio_id
            )
            if episodio:
                await query.message.reply_video(video=episodio["file_id"])
            else:
                await query.message.reply_text("Errore: episodio non trovato.")
        finally:
            await conn.close()
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

        # Estrai i dati dalla descrizione
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

        conn = await connetti_al_database()
        try:
            # Inserisci la serie
            await conn.execute(
                """
                INSERT INTO serie (serie_id, nome)
                VALUES ($1, $2)
                ON CONFLICT (serie_id) DO NOTHING;
                """,
                serie_id, serie_nome
            )

            # Inserisci l'episodio
            await conn.execute(
                """
                INSERT INTO episodi (episodio_id, serie_id, stagione, episodio, titolo, file_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (episodio_id) DO NOTHING;
                """,
                episodio_id, serie_id, stagione, episodio, titolo, file_id
            )
            print(f"Aggiunto: {serie_nome} - Stagione {stagione}, Episodio {episodio}: {titolo}")
        finally:
            await conn.close()

# Configurazione del bot
async def main():
    if not TOKEN or not CHANNEL_ID or not DATABASE_URL:
        raise ValueError("TOKEN, CHANNEL_ID o DATABASE_URL non configurati nelle variabili d'ambiente.")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern=r"^(?!indietro$)[^|]+$"))
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=r".*\|\d+"))
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern=r"^play\|"))
    application.add_handler(CallbackQueryHandler(torna_alla_lista, pattern=r"^indietro$"))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))

    # Connetti al database e inizializza le tabelle
    conn = await connetti_al_database()
    await inizializza_tabelle(conn)
    await conn.close()
    print("DEBUG: Inizializzazione completata. Avvio del bot...")

    # Avvia il polling del bot
    await application.run_polling()

# Verifica se un loop è già in esecuzione, altrimenti avvia l'app
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if str(e) == "This event loop is already running":
            print("DEBUG: Loop già in esecuzione, avvio manuale del bot.")
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        else:
            raise


