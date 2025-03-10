import os
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Variabili d'ambiente
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Percorso del file per il database
DATABASE_FILE = "/data/database.json"  # Assicurati che il volume persistente su Railway punti a /data

# Database per le serie TV
database = {}

# Funzione per prendere username telegram
def get_user_info(update: Update):
    """Restituisce l'username, l'ID e il nome dell'utente che interagisce con il bot."""
    user = update.effective_user
    username = f"@{user.username}" if user.username else "Sconosciuto"
    return f"{username} | {user.first_name}"

# Funzione per salvare il database su un file JSON
def salva_database():
    try:
        with open(DATABASE_FILE, "w", encoding="utf-8") as file:
            json.dump(database, file, indent=4, ensure_ascii=False)
        print("DEBUG: Database salvato correttamente.")
    except Exception as e:
        print(f"DEBUG: Errore durante il salvataggio del database: {e}")

def carica_database():
    """Carica il database dal file e normalizza i dati:
       - Converte le chiavi stagioni in interi
       - Se mancano i campi 'numero' negli episodi, li aggiunge automaticamente
         parsando la stringa 'episodio' (es. S2EP5 -> numero = 5)."""
    global database
    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            database = json.load(file)
        print("DEBUG: Database caricato correttamente.")
    except FileNotFoundError:
        print("DEBUG: Nessun file di database trovato, avvio con database vuoto.")
        database = {}
        return
    except Exception as e:
        print(f"DEBUG: Errore durante il caricamento del database: {e}")
        database = {}
        return

    # 1) Converte le chiavi delle stagioni in interi
    for serie_id, serie_data in database.items():
        if "stagioni" in serie_data:
            # Converte la chiave in int
            serie_data["stagioni"] = {
                int(stagione_num): episodi
                for stagione_num, episodi in serie_data["stagioni"].items()
            }

    # 2) Aggiunge automaticamente "numero" negli episodi che non lo hanno
    changed = False  # per capire se dobbiamo risalvare il file
    for serie_id, serie_data in database.items():
        stagioni = serie_data.get("stagioni", {})
        for stg_num, episodi_list in stagioni.items():
            for ep_data in episodi_list:
                if "numero" not in ep_data:
                    # Esempio ep_data["episodio"] = "S2EP5"
                    match = re.match(r"S(\d+)EP(\d+)", ep_data["episodio"], re.IGNORECASE)
                    if match:
                        numero_episodio = int(match.group(2))
                        ep_data["numero"] = numero_episodio
                        changed = True
                        print(f"DEBUG: Aggiunto automaticamente 'numero': {numero_episodio} a {ep_data['episodio']}")
                    else:
                        # Se non combacia con SxEPy, lascia invariato (numero=0) o gestisci diversamente
                        ep_data["numero"] = 0
                        changed = True
                        print(f"DEBUG: Non è stato possibile parsare l'episodio: {ep_data['episodio']}. Imposto numero=0")

    if changed:
        salva_database()

# Funzione per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[{get_user_info(update)}] DEBUG: Comando /start ricevuto")
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

# Funzione per mostrare le stagioni
async def mostra_stagioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serie_id = query.data
    serie = database.get(serie_id)

    print(f"DEBUG: mostra_stagioni chiamata. Serie ID: {serie_id}, Serie: {serie}")

    if serie:
        buttons = []
        stagioni = sorted(serie["stagioni"].keys())
        for stagione in stagioni:
            callback_data = f"{serie_id}|{stagione}"
            print(f"[{get_user_info(update)}] DEBUG: Pulsante creato - Stagione {stagione}, callback_data={callback_data}")
            buttons.append([InlineKeyboardButton(f"Stagione {stagione}", callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("Torna alla lista", callback_data="indietro")])
        reply_markup = InlineKeyboardMarkup(buttons)

        try:
            await query.message.edit_text(f"Scegli una stagione di {serie['nome']}:", reply_markup=reply_markup)
            print(f"[{get_user_info(update)}] DEBUG: Messaggio aggiornato per mostrare le stagioni di {serie['nome']}.")
        except Exception as e:
            print(f"[{get_user_info(update)}] DEBUG: Errore nell'aggiornamento del messaggio delle stagioni: {e}")
    else:
        print(f"[{get_user_info(update)}] DEBUG: Nessuna serie trovata con ID {serie_id}.")
        await query.message.edit_text("Errore: serie non trovata nel database.")

# Funzione per mostrare gli episodi in ordine crescente
async def mostra_episodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        serie_id, stagione = query.data.split("|")
        stagione = int(stagione)
        print(f"[{get_user_info(update)}] DEBUG: mostra_episodi chiamata. Serie ID: {serie_id}, Stagione: {stagione}")
    except ValueError as e:
        print(f"[{get_user_info(update)}] DEBUG: Errore nel parsing del callback data: {query.data}, errore: {e}")
        await query.message.edit_text("Errore: callback data non valido.")
        return

    serie = database.get(serie_id)
    print(f"DEBUG: Serie trovata: {serie}")

    if serie and stagione in serie["stagioni"]:
        # Ordina gli episodi in base al campo "numero" (se non c'è, viene 0, ma grazie al pass in carica_database non dovrebbe mancare)
        episodi = sorted(serie["stagioni"][stagione], key=lambda ep: ep.get("numero", 0))
        print(f"[{get_user_info(update)}] DEBUG: Episodi ordinati: {episodi}")

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
            print(f"[{get_user_info(update)}] DEBUG: Messaggio aggiornato con la lista degli episodi.")
        except Exception as e:
            print(f"[{get_user_info(update)}] DEBUG: Errore nell'aggiornamento del messaggio degli episodi: {e}")
    else:
        print(f"[{get_user_info(update)}] DEBUG: Nessun episodio trovato per serie_id={serie_id}, stagione={stagione}")
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
        print(f"[{get_user_info(update)}] DEBUG: invia_episodio chiamata. Episodio ID: {episodio_id}")

        for serie_id, serie in database.items():
            for stagione, episodi in serie["stagioni"].items():
                for episodio in episodi:
                    if episodio["episodio_id"] == episodio_id:
                        file_id = episodio["file_id"]
                        try:
                            await query.message.reply_video(video=file_id)
                            print(f"[{get_user_info(update)}] DEBUG: Video inviato per episodio ID: {episodio_id}")
                            return
                        except Exception as e:
                            print(f"[{get_user_info(update)}] DEBUG: Il file non esiste più per episodio ID: {episodio_id}. Errore: {e}")
                            episodi.remove(episodio)
                            salva_database()
                            await query.message.reply_text("⚠️ Questo episodio non è più disponibile e sarà rimosso dalla lista.")
                            return

        print(f"[{get_user_info(update)}] DEBUG: Episodio ID non trovato: {episodio_id}")
        await query.message.reply_text("Errore: episodio non trovato.")
    except Exception as e:
        print(f"[{get_user_info(update)}] DEBUG: Errore nell'invio dell'episodio: {e}")
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
            print(f"[{get_user_info(update)}] DEBUG: Formato della descrizione non valido. Caption: {caption}")
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

        # Salva anche il numero dell'episodio per ordinamenti futuri
        database[serie_id]["stagioni"][stagione].append({
            "episodio": titolo,
            "file_id": file_id,
            "episodio_id": episodio_id,
            "numero": episodio
        })

        print(f"DEBUG: Aggiunto: {serie_nome} - Stagione {stagione}, Episodio {episodio}: {titolo}")
        salva_database()

# Funzione per rimuovere manualmente un episodio dal database
async def rimuovi_episodio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[{get_user_info(update)}] DEBUG: Comando /rimuovi ricevuto")
    if not context.args:
        await update.message.reply_text("Utilizzo: /rimuovi <episodio_id>")
        print(f"[{get_user_info(update)}] DEBUG: Nessun episodio_id fornito con /rimuovi")
        return

    episodio_id_da_rimuovere = context.args[0]
    trovato = False

    for serie_id, serie in database.items():
        for stagione, episodi in serie["stagioni"].items():
            for episodio in episodi:
                if episodio["episodio_id"] == episodio_id_da_rimuovere:
                    episodi.remove(episodio)
                    salva_database()
                    await update.message.reply_text(f"Episodio {episodio_id_da_rimuovere} rimosso dal database.")
                    print(f"[{get_user_info(update)}] DEBUG: Episodio {episodio_id_da_rimuovere} rimosso dalla serie {serie_id}, stagione {stagione}")
                    trovato = True
                    break
            if trovato:
                break
        if trovato:
            break

    if not trovato:
        await update.message.reply_text("Errore: episodio non trovato.")
        print(f"[{get_user_info(update)}] DEBUG: Episodio {episodio_id_da_rimuovere} non trovato nel database.")

# Funzione per stampare il database nei log
async def debug_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[{get_user_info(update)}] DEBUG: Struttura del database:\n{database}")
    await update.message.reply_text("La struttura del database è stata stampata nei log.")

# Configurazione del bot
def main():
    # Carichiamo il database con la funzione che normalizza le stagioni e aggiunge "numero" mancante
    carica_database()

    if not TOKEN or not CHANNEL_ID:
        raise ValueError("TOKEN o CHANNEL_ID non configurati nelle variabili d'ambiente.")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(mostra_stagioni, pattern=r"^(?!indietro$)[^|]+$"))
    application.add_handler(CallbackQueryHandler(mostra_episodi, pattern=r".*\|\d+"))
    application.add_handler(CallbackQueryHandler(invia_episodio, pattern=r"^play\|"))
    application.add_handler(CallbackQueryHandler(torna_alla_lista, pattern=r"^indietro$"))
    application.add_handler(CommandHandler("debug", debug_database))
    application.add_handler(CommandHandler("rimuovi", rimuovi_episodio))
    application.add_handler(
        MessageHandler(filters.VIDEO & filters.Chat(chat_id=int(CHANNEL_ID)), leggi_file_id)
    )

    application.run_polling()

if __name__ == "__main__":
    main()
