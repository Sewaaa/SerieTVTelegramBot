import os
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re

# Leggi le variabili d'ambiente
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

# Pool di connessioni al database
db_pool = None

# Funzione per inizializzare la connessione al database
async def init_db():
    global db_pool
    async with db_pool.acquire() as conn:
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

# Funzione per ottenere le serie dal database
async def get_series():
    async with db_pool.acquire() as conn:
        return await conn.fetch('SELECT * FROM series')

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
    async with db_pool.acquire() as conn:
        serie = await conn.fetchrow('SELECT * FROM series WHERE id = $1', serie_id)
        seasons = await conn.fetch('SELECT * FROM seasons WHERE series_id = $1 ORDER BY number', serie_id)

    if serie and seasons:
        buttons = [
            [InlineKeyboardButton(f"Stagione {season['number']}", callback_data=f"{serie_id}|{season['number']}")]
            for season in seasons
        ]
        buttons.append([InlineKeyboardButton("Torna alla lista", callback_data="indietro")])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(f"Scegli una stagione di {serie['name']}:", reply_markup=reply_markup)
    else:
        await query.message.edit_text("Errore: serie non trovata nel database.")

# Funzione per mostrare gli episodi
async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        serie_id, stagione = query.data.split("|")
        serie_id = int(serie_id)
        stagione = int(stagione)
    except ValueError:
        await query.message.edit_text("Errore: callback data non valido.")
        return

    async with db_pool.acquire() as conn:
        serie = await conn.fetchrow('SELECT * FROM series WHERE id = $1', serie_id)
        season = await conn.fetchrow('SELECT * FROM seasons WHERE series_id = $1 AND number = $2', serie_id, stagione)
        if season:
            episodes = await conn.fetch('SELECT * FROM episodes WHERE season_id = $1 ORDER BY number', season['id'])

    if serie and season and episodes:
        buttons = [
            [InlineKeyboardButton(f"Episodio {ep['number']}", callback_data=f"play|{ep['id']}")]
            for ep in episodes
        ]
        buttons.append([InlineKeyboardButton("Torna indietro", callback_data=str(serie_id))])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(f"Episodi di {serie['name']} - Stagione {stagione}:", reply_markup=reply_markup)
    else:
        await query.message.edit_text("Errore: nessun episodio trovato per questa stagione.")

# Funzione per inviare un episodio selezionato
async def invia_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        episodio_id = int(query.data.split("|")[1])
    except (ValueError, IndexError):
        await query.message.reply_text("Errore: episodio non valido.")
        return

    async with db_pool.acquire() as conn:
        episodio = await conn.fetchrow('SELECT file_id FROM episodes WHERE id = $1', episodio_id)

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
            print("DEBUG: Formato della descrizione non valido.")
            return

        serie_nome, stagione, episodio = match.groups()
        stagione = int(stagione)
        episodio = int(episodio)

        async with db_pool.acquire() as conn:
            # Trova o crea la serie
            serie = await conn.fetchrow('SELECT id FROM series WHERE name = $1', serie_nome)
            if not serie:
                serie = await conn.fetchrow(
                    'INSERT INTO series(name) VALUES($1) RETURNING id', 
                    serie_nome
                )

            # Trova o crea la stagione
            season = await conn.fetchrow(
                'SELECT id FROM seasons WHERE series_id = $1 AND number = $2', 
                serie['id'], stagione
            )
            if not season:
                season = await conn.fetchrow(
                    'INSERT INTO seasons(series_id, number) VALUES($1, $2) RETURNING id',
                    serie['id'], stagione
                )

            # Aggiungi l'episodio
            await conn.execute(
                'INSERT INTO episodes(season_id, number, file_id) VALUES($1, $2, $3)',
                season['id'], episodio, file_id
            )

        print(f"Aggiunto: {serie_nome} - Stagione {stagione}, Episodio {episodio}")

# Funzione per stampare il database nei log
async def debug_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db_pool.acquire() as conn:
        series = await conn.fetch('SELECT * FROM series')
        for serie in series:
            print(f"Serie: {serie['name']}")
            seasons = await conn.fetch('SELECT * FROM seasons WHERE series_id = $1', serie['id'])
            for season in seasons:
                print(f"  Stagione: {season['number']}")
                episodes = await conn.fetch('SELECT * FROM episodes WHERE season_id = $1', season['id'])
                for episode in episodes:
                    print(f"    Episodio: {episode['number']} - File ID: {episode['file_id']}")
    
    await update.message.reply_text("La struttura del database è stata stampata nei log.")

def main():
    if not TOKEN or not CHANNEL_ID or not DATABASE_URL:
        raise ValueError("TOKEN, CHANNEL_ID o DATABASE_URL non configurati nelle variabili d'ambiente.")

    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()

    # Aggiungi gli handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern=r"^(?!indietro$)[^|]+$"))
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=r".*\|\d+"))
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern=r"^play\|"))
    application.add_handler(CallbackQueryHandler(torna_alla_lista, pattern=r"^indietro$"))
    application.add_handler(CommandHandler("debug", debug_database))
    application.add_handler(MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id))

    # Inizializza il database e avvia il polling
    async def start_bot():
        global db_pool
        # Inizializza il pool di connessioni al database
        db_pool = await asyncpg.create_pool(DATABASE_URL)
        await init_db()
        
        print("Database inizializzato con successo!")
        print("Bot in esecuzione...")
        
        # Avvia il bot
        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

    # Avvia il bot
    import asyncio
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
