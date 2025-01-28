import os
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re

# Leggi le variabili d'ambiente
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Aggiungi l'URL del webhook

# Funzione per inizializzare la connessione al database
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS series (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS seasons (
            id SERIAL PRIMARY KEY,
            series_id INTEGER NOT NULL,
            number INTEGER NOT NULL,
            FOREIGN KEY (series_id) REFERENCES series (id)
        )
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS episodes (
            id SERIAL PRIMARY KEY,
            season_id INTEGER NOT NULL,
            number INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            FOREIGN KEY (season_id) REFERENCES seasons (id)
        )
    ''')
    await conn.close()

# Funzione per ottenere le serie dal database
async def get_series():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch('SELECT * FROM series')
    await conn.close()
    return rows

# Funzione per aggiungere una serie al database
async def add_series(name):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('INSERT INTO series(name) VALUES($1)', name)
    await conn.close()

# Funzione per ottenere le stagioni di una serie dal database
async def get_seasons(series_id):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch('SELECT * FROM seasons WHERE series_id = $1', series_id)
    await conn.close()
    return rows

# Funzione per aggiungere una stagione a una serie nel database
async def add_season(series_id, number):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('INSERT INTO seasons(series_id, number) VALUES($1, $2)', series_id, number)
    await conn.close()

# Funzione per ottenere gli episodi di una stagione dal database
async def get_episodes(season_id):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch('SELECT * FROM episodes WHERE season_id = $1', season_id)
    await conn.close()
    return rows

# Funzione per aggiungere un episodio a una stagione nel database
async def add_episode(season_id, number, file_id):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('INSERT INTO episodes(season_id, number, file_id) VALUES($1, $2, $3)', season_id, number, file_id)
    await conn.close()

# Funzione per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        message = update.message
    elif update.callback_query:
        message = update.callback_query.message
    else:
        return

    series = await get_series()
    if not series:
        await message.reply_text("Non ci sono serie TV disponibili al momento.")
        return

    buttons = [[InlineKeyboardButton(serie["name"], callback_data=str(serie["id"]))] for serie in series]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text("Scegli una serie TV:", reply_markup=reply_markup)

# Funzione per mostrare le stagioni
async def mostra_stagioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serie_id = int(query.data)
    seasons = await get_seasons(serie_id)

    if seasons:
        buttons = []
        for season in seasons:
            callback_data = f"{serie_id}|{season['number']}"
            buttons.append([InlineKeyboardButton(f"Stagione {season['number']}", callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("Torna alla lista", callback_data="indietro")])
        reply_markup = InlineKeyboardMarkup(buttons)

        await query.message.edit_text(f"Scegli una stagione di {seasons[0]['name']}:", reply_markup=reply_markup)
    else:
        await query.message.edit_text("Errore: serie non trovata nel database.")

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

    episodes = await get_episodes(stagione)

    if episodes:
        buttons = [[InlineKeyboardButton(ep["number"], callback_data=f"play|{ep['id']}")] for ep in episodes]
        buttons.append([InlineKeyboardButton("Torna indietro", callback_data=serie_id)])
        reply_markup = InlineKeyboardMarkup(buttons)

        await query.message.edit_text(f"Episodi di {episodes[0]['name']} - Stagione {stagione}:", reply_markup=reply_markup)
    else:
        await query.message.edit_text("Errore: nessun episodio trovato per questa stagione.")

# Funzione per inviare un episodio selezionato
async def invia_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    episodio_id = query.data.split("|")[1]
    conn = await asyncpg.connect(DATABASE_URL)
    episodio = await conn.fetchrow('SELECT file_id FROM episodes WHERE id = $1', episodio_id)
    await conn.close()

    if episodio:
        await query.message.reply_video(video=episodio["file_id"])
    else:
        await query.message.reply_text("Errore: episodio non trovato.")

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

        match = re.search(r"Serie: (.+)\nStagione: (\d+)\nEpisodio: (\d+)", caption, re.IGNORECASE)
        if not match:
            return

        serie_nome, stagione, episodio = match.groups()
        stagione = int(stagione)
        episodio = int(episodio)

        conn = await asyncpg.connect(DATABASE_URL)
        serie = await conn.fetchrow('SELECT id FROM series WHERE name = $1', serie_nome)
        if not serie:
            await conn.execute('INSERT INTO series(name) VALUES($1)', serie_nome)
            serie = await conn.fetchrow('SELECT id FROM series WHERE name = $1', serie_nome)

        season = await conn.fetchrow('SELECT id FROM seasons WHERE series_id = $1 AND number = $2', serie["id"], stagione)
        if not season:
            await conn.execute('INSERT INTO seasons(series_id, number) VALUES($1, $2)', serie["id"], stagione)
            season = await conn.fetchrow('SELECT id FROM seasons WHERE series_id = $1 AND number = $2', serie["id"], stagione)

        await conn.execute('INSERT INTO episodes(season_id, number, file_id) VALUES($1, $2, $3)', season["id"], episodio, file_id)
        await conn.close()

# Funzione per stampare il database nei log
async def debug_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await asyncpg.connect(DATABASE_URL)
    series = await conn.fetch('SELECT * FROM series')
    for serie in series:
        print(f"Serie: {serie['name']}")
        seasons = await conn.fetch('SELECT * FROM seasons WHERE series_id = $1', serie["id"])
        for season in seasons:
            print(f"  Stagione: {season['number']}")
            episodes = await conn.fetch('SELECT * FROM episodes WHERE season_id = $1', season["id"])
            for episode in episodes:
                print(f"    Episodio: {episode['number']} - File ID: {episode['file_id']}")
    await conn.close()
    await update.message.reply_text("La struttura del database è stata stampata nei log.")

# Configurazione del bot
def main():
    if not TOKEN or not CHANNEL_ID or not DATABASE_URL or not WEBHOOK_URL:
        raise ValueError("TOKEN, CHANNEL_ID, DATABASE_URL o WEBHOOK_URL non configurati nelle variabili d'ambiente.")
    
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern=r"^(?!indietro$)[^|]+$"))
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=r".*\|\d+"))
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern=r"^play\|"))
    application.add_handler(CallbackQueryHandler(torna_alla_lista, pattern=r"^indietro$"))
    application.add_handler(CommandHandler("debug", debug_database))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))

    # Imposta il webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", "8443")),
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
