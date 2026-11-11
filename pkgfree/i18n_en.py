"""English translations, keyed by the Italian source text (see i18n.tr)."""

EN = {
    # -- command line --------------------------------------------------------------
    "NON CORRISPONDE": "DOES NOT MATCH",
    "assente (non verificabile)": "missing (cannot be verified)",
    "ATTENZIONE: {message}": "WARNING: {message}",
    "ERRORE: verrebbe installata una versione più vecchia di quella presente. Usa --force per "
    "procedere comunque.":
        "ERROR: an older version than the installed one would be extracted. Use --force to "
        "proceed anyway.",
    "ATTENZIONE: spazio insufficiente su {path}: servono {needed}, liberi {free}.":
        "WARNING: not enough space on {path}: {needed} needed, {free} free.",
    "ERRORE: spazio su disco insufficiente. Libera spazio o usa --force.":
        "ERROR: not enough disk space. Free some space or use --force.",
    "Estrae PKG PS4 (fPKG) in cartelle per shadPS4 unendo gioco, patch e DLC, oppure crea "
    "un nuovo PKG con gioco e aggiornamenti già uniti.":
        "Extracts PS4 PKGs (fPKG) into folders for shadPS4, merging game, patches and DLC, or "
        "creates a new PKG with the game and its updates already merged.",
    "mostra le informazioni di uno o più PKG": "show information about one or more PKGs",
    "elenca anche i file contenuti": "also list the files inside",
    "mostra dettagli tecnici (utili per segnalare problemi)":
        "show technical details (useful when reporting problems)",
    "verifica l'integrità (SHA-256) di uno o più PKG":
        "check the integrity (SHA-256) of one or more PKGs",
    "estrae e unisce gioco base, aggiornamenti e DLC":
        "extract and merge base game, updates and DLC",
    "file PKG (in qualsiasi ordine)": "PKG files (in any order)",
    "cartella dei giochi": "games folder",
    "cartella DLC (predefinita: <output>/addcont)": "DLC folder (default: <output>/addcont)",
    "estrai gli aggiornamenti in <TITLE_ID>-UPDATE invece di unirli":
        "extract updates to <TITLE_ID>-UPDATE instead of merging them",
    "estrai in <output>/<TITLE_ID> invece di <output>/<titolo>/<TITLE_ID>":
        "extract to <output>/<TITLE_ID> instead of <output>/<title>/<TITLE_ID>",
    "procedi anche se sul disco c'è una versione più recente o lo spazio libero non basta":
        "proceed even if a newer version is installed or free space is not enough",
    "verifica le impronte SHA-256 di ogni PKG prima di estrarlo":
        "check the SHA-256 digests of each PKG before extracting it",
    "cancella i PKG dopo un'estrazione completata senza errori":
        "delete the PKGs after an extraction completed without errors",
    "non riprendere un'estrazione interrotta: estrai tutto da capo":
        "do not resume an interrupted extraction: extract everything again",
    "verifica {pct:3d}%": "verifying {pct:3d}%",
    "ERRORE: {message}": "ERROR: {message}",
    "Annullato.": "Cancelled.",
    "Tipo:": "Type:",
    "Titolo:": "Title:",
    "Versione:": "Version:",
    "{key}, PFSC a 0x{pfsc:X}, mode esterno=0x{mode:X}":
        "{key}, PFSC at 0x{pfsc:X}, outer mode=0x{mode:X}",
    "Decifrato:": "Decrypted:",
    "ERRORE:": "ERROR:",

    # -- crypto / PKG ----------------------------------------------------------------
    "Testo cifrato RSA fuori intervallo": "RSA ciphertext out of range",
    "RSA padding non valido (PKG retail o chiave errata)":
        "invalid RSA padding (retail PKG or wrong key)",
    "Nome file non valido nel PKG: {name}": "Invalid file name in the PKG: {name}",
    "Immagine PFSC non trovata: PKG non supportato o danneggiato (mode=0x{mode:X}, "
    "flags=0x{flags:016X}, blocco=0x{block:X}, chiave valida: {valid}; provate: {tried})":
        "PFSC image not found: unsupported or damaged PKG (mode=0x{mode:X}, "
        "flags=0x{flags:016X}, block=0x{block:X}, valid key: {valid}; tried: {tried})",
    "Fine del file inattesa: il PKG è incompleto o danneggiato":
        "Unexpected end of file: the PKG is incomplete or damaged",
    "Non è un file PKG PS4 valido": "Not a valid PS4 PKG file",
    "Il PKG è incompleto (dimensione inferiore a quella dichiarata)":
        "The PKG is incomplete (smaller than its declared size)",
    "Il PKG non contiene la chiave dell'immagine PFS": "The PKG has no PFS image key",
    "Intestazione PFSC non valida": "Invalid PFSC header",
    "Dimensione blocco PFS interna inattesa": "Unexpected inner PFS block size",
    "Formato PFS interno non supportato (mode=0x{mode:X})":
        "Unsupported inner PFS format (mode=0x{mode:X})",
    "chiave 'new crypt'": "'new crypt' key",
    "chiave classica": "classic key",
    "Riferimento a blocco PFS fuori dai limiti": "PFS block reference out of range",
    "Cartella 'uroot' non trovata nel PFS": "'uroot' folder not found in the PFS",
    "Il PKG non contiene la tabella delle chiavi": "The PKG has no key table",
    "Impossibile decifrare la chiave PFS: sono supportati solo i PKG 'fake' (fPKG). ({error})":
        "Cannot decrypt the PFS key: only 'fake' PKGs (fPKG) are supported. ({error})",
    "Il PKG non contiene file di gioco": "The PKG contains no game files",
    "in chiaro": "unencrypted",
    "Impossibile decifrare il PKG: sono supportati solo i PKG 'fake' (fPKG). ({error})":
        "Cannot decrypt the PKG: only 'fake' PKGs (fPKG) are supported. ({error})",
    "nessuna": "none",
    "Blocco compresso danneggiato ({error})": "Damaged compressed block ({error})",
    "param.sfo non valido": "invalid param.sfo",

    # -- installer --------------------------------------------------------------------
    "Sconosciuto": "Unknown",
    "Completato.": "Done.",
    "Sul disco è già installata la versione {installed}: dopo l'estrazione il gioco "
    "tornerebbe alla {final}.":
        "Version {installed} is already installed: after the extraction the game would go "
        "back to {final}.",
    "Gioco base": "Base game",
    "Aggiornamento": "Update",
    "{name} è una patch 'delta' (incrementale): non contiene i file completi e il risultato "
    "potrebbe non funzionare.":
        "{name} is a 'delta' (incremental) patch: it does not contain the full files and the "
        "result may not work.",
    "Manca il gioco base e nella destinazione non c'è già una cartella {title_id}: "
    "l'aggiornamento verrà estratto da solo.":
        "The base game is missing and there is no {title_id} folder in the destination yet: "
        "the update will be extracted on its own.",
    "Più di un gioco base per {tid}: {name}": "More than one base game for {tid}: {name}",
    "già estratto nell'esecuzione interrotta: saltato":
        "already extracted in the interrupted run: skipped",
    "Rimosso {name}": "Removed {name}",
    "La versione {installed} è già installata: la patch verrà riapplicata sopra quella "
    "esistente.":
        "Version {installed} is already installed: the patch will be applied again on top "
        "of it.",
    "Tipo di PKG non riconosciuto ({category}): {name}":
        "Unrecognised PKG type ({category}): {name}",
    "{name} è danneggiato: le impronte SHA-256 ({digests}) non corrispondono. Scaricalo di "
    "nuovo.":
        "{name} is damaged: the SHA-256 digests ({digests}) do not match. Download it again.",
    "Impossibile rimuovere {name}: {error}": "Cannot remove {name}: {error}",
    "verifica: il PKG non contiene impronte, non verificabile":
        "verify: the PKG has no digests, it cannot be verified",
    "verifica integrità: OK": "integrity check: OK",
    "(nessun file di gioco: solo licenza/metadati)": "(no game files: license/metadata only)",
    "ripresa: {size:.1f} GB già estratti, saltati":
        "resume: {size:.1f} GB already extracted, skipped",

    # -- updater ----------------------------------------------------------------------
    "Questa release non contiene il file per il tuo sistema.":
        "This release has no file for your system.",
    "GitHub ha risposto con l'errore {code}.": "GitHub answered with error {code}.",
    "Impossibile contattare GitHub: {error}": "Cannot reach GitHub: {error}",
    "Download incompleto.": "Incomplete download.",
    "Il file scaricato è danneggiato (SHA-256 diverso).":
        "The downloaded file is damaged (SHA-256 mismatch).",
    "Download non riuscito: {error}": "Download failed: {error}",
    "Installazione dell'aggiornamento non riuscita: {error}":
        "Installing the update failed: {error}",
    "Nessuna release trovata (il repository potrebbe essere privato).":
        "No release found (the repository may be private).",
    "Lo zip scaricato non contiene l'app.": "The downloaded zip does not contain the app.",
    "Aggiornamento annullato.": "Update cancelled.",

    # -- GUI: Estrai page ---------------------------------------------------------------
    "Rimuovi questo PKG": "Remove this PKG",
    "Rimuovi questo gioco dall'elenco": "Remove this game from the list",
    "Cartella in cui estrarre i giochi": "Folder to extract the games to",
    "Svuota": "Clear",
    "Estrai tutto": "Extract all",
    "Seleziona i file PKG": "Select the PKG files",
    "PKG PS4 (*.pkg);;Tutti i file (*)": "PS4 PKG (*.pkg);;All files (*)",
    "Cartella con file PKG": "Folder with PKG files",
    "Cartella dei giochi": "Games folder",
    "Attenzione": "Warning",
    "I tuoi giochi": "Your games",
    "Nessun PKG aggiunto. Puoi aggiungere insieme gioco base, aggiornamenti e DLC: vengono "
    "raggruppati per gioco e applicati nell'ordine giusto.":
        "No PKG added. You can add base game, updates and DLC together: they are grouped by "
        "game and applied in the right order.",
    "Alcuni PKG non sono stati aggiunti": "Some PKGs were not added",
    "{games} giochi · {pkgs} PKG · {size}": "{games} games · {pkgs} PKG · {size}",
    "Nessun PKG": "No PKG",
    "Scegli la cartella dei giochi…": "Choose the games folder…",
    "Ordine di applicazione": "Order of application",
    "La cartella non contiene file .pkg.": "The folder contains no .pkg files.",
    "Versione finale": "Final version",
    "Destinazione: {dest}": "Destination: {dest}",
    "Aggiungi PKG…": "Add PKG…",
    "Aggiungi cartella…": "Add folder…",
    "Trascina qui i file .pkg (gioco, aggiornamenti, DLC, in qualsiasi ordine) oppure":
        "Drop .pkg files here (game, updates, DLC, in any order) or",

    # -- GUI: Libreria ------------------------------------------------------------------
    "Apri la cartella del gioco": "Open the game folder",
    "Aggiorna": "Refresh",
    "aggiornamento separato": "separate update",
    "Libreria": "Library",
    "Scegli la cartella dei giochi nella pagina Estrai o nelle Impostazioni.":
        "Choose the games folder in the Extract page or in Settings.",
    "Nessun gioco estratto in {folder}": "No extracted games in {folder}",
    "{n} giochi in {folder}": "{n} games in {folder}",
    "1 gioco in {folder}": "1 game in {folder}",

    # -- GUI: Avanzamento ---------------------------------------------------------------
    "Verifica {pct}%": "Verifying {pct}%",
    "Già estratto": "Already extracted",
    "Completato": "Done",
    "Nessuna estrazione in corso": "No extraction in progress",
    "Annulla": "Cancel",
    "Estrazione in corso": "Extraction in progress",
    "Preparazione…": "Preparing…",
    "Verifica integrità: {done} / {total}": "Integrity check: {done} / {total}",
    "{size} scritti": "{size} written",
    "In attesa": "Waiting",
    "Aggiungi i PKG nella pagina Estrai e premi «Estrai tutto».":
        "Add the PKGs in the Extract page and press “Extract all”.",
    "Verifica integrità del PKG…": "Checking the PKG integrity…",
    "Sto scrivendo: {name}": "Writing: {name}",
    "Estrazione completata": "Extraction completed",
    "Tempo impiegato: {sec} s": "Time taken: {sec} s",
    "Pronto per shadPS4": "Ready for shadPS4",
    "Aggiungi la cartella dei giochi in shadPS4 e imposta la cartella DLC nelle sue "
    "impostazioni.":
        "Add the games folder in shadPS4 and set the DLC folder in its settings.",
    "Apri cartella": "Open folder",
    "Estrazione interrotta": "Extraction stopped",
    "Errore": "Error",
    "Operazione annullata. Avviando di nuovo l'estrazione con gli stessi PKG riprenderà da "
    "dove si è fermata.":
        "Cancelled. Starting the extraction again with the same PKGs resumes where it "
        "stopped.",
    "Errore inatteso: {error}": "Unexpected error: {error}",
    "circa {min} min {sec} s rimanenti": "about {min} min {sec} s left",
    "circa {sec} s rimanenti": "about {sec} s left",
    "Interrotto": "Stopped",

    # -- GUI: Impostazioni / Registro ---------------------------------------------------
    "Cartelle": "Folders",
    "Scegli cartella": "Choose folder",
    "Cartella giochi": "Games folder",
    "Cartella DLC": "DLC folder",
    "Estrazione": "Extraction",
    "Unisci gli aggiornamenti al gioco": "Merge updates into the game",
    "Se disattivato, gli aggiornamenti vengono estratti a parte in <TITLE_ID>-UPDATE":
        "When off, updates are extracted separately to <TITLE_ID>-UPDATE",
    "Cartella con il nome del gioco": "Folder named after the game",
    "Es. Giochi\\Driveclub\\CUSA00003: shadPS4 trova il gioco anche nella sottocartella. "
    "I DLC restano in addcont\\<TITLE_ID>.":
        "E.g. Games\\Driveclub\\CUSA00003: shadPS4 finds the game in the subfolder too. "
        "DLC stay in addcont\\<TITLE_ID>.",
    "Verifica i PKG prima di estrarli": "Verify PKGs before extracting them",
    "Controlla le impronte SHA-256 per scoprire download danneggiati. Rilegge tutto il PKG: "
    "circa un minuto in più ogni 50 GB.":
        "Checks the SHA-256 digests to catch damaged downloads. Reads the whole PKG again: "
        "about one extra minute every 50 GB.",
    "Sposta i PKG nel Cestino al termine": "Move the PKGs to the Trash when done",
    "Solo se l'estrazione di tutti i PKG è riuscita.":
        "Only if the extraction of every PKG succeeded.",
    "Notifica a fine estrazione": "Notify when the extraction ends",
    "Mostra una notifica di sistema se nel frattempo stai usando un'altra finestra.":
        "Shows a system notification if you are using another window meanwhile.",
    "Aspetto": "Appearance",
    "Tema": "Theme",
    "Chiaro, scuro o come Windows": "Light, dark or like the system",
    "Lingua": "Language",
    "Si applica al prossimo avvio": "Applies at the next start",
    "Aggiornamenti": "Updates",
    "Controlla gli aggiornamenti all'avvio": "Check for updates at startup",
    "Cerca una nuova versione su GitHub quando apri il programma.":
        "Looks for a new version on GitHub when the program opens.",
    "Controlla ora": "Check now",
    "Versione installata": "Installed version",
    "Informazioni": "About",
    "Attivo": "On",
    "Disattivo": "Off",
    "Impostazioni": "Settings",
    "Codice sorgente": "Source code",
    "Versione {version} · GPL-3.0 · supporta solo PKG fake (fPKG)":
        "Version {version} · GPL-3.0 · supports fake PKGs (fPKG) only",
    "Non impostata": "Not set",
    "<cartella giochi>\\addcont": "<games folder>\\addcont",
    "Predefinita: {folder}": "Default: {folder}",
    "Registro": "Log",
    "Chiaro": "Light",
    "Scuro": "Dark",
    "Usa impostazione di sistema": "Use system setting",
    "Automatica (lingua del sistema)": "Automatic (system language)",

    # -- GUI: update dialog ---------------------------------------------------------------
    "Più tardi": "Later",
    "Download in corso…": "Downloading…",
    "Aggiornamento installato. Riavvio…": "Update installed. Restarting…",
    "Riprova": "Retry",
    "Chiudi": "Close",
    "PS PKG Toolkit {version} disponibile": "PS PKG Toolkit {version} available",
    "Nessuna nota per questa versione.": "No notes for this version.",
    "Aggiorna e riavvia": "Update and restart",
    "Il programma verrà scaricato, sostituito e riavviato.":
        "The program will be downloaded, replaced and restarted.",
    "Apri la pagina della release": "Open the release page",
    "Aggiornamento automatico non disponibile per questa copia (avviata dal codice sorgente "
    "o file mancante nella release).":
        "Automatic update is not available for this copy (started from source, or no file "
        "for it in the release).",
    "Download: {done} / {total}": "Download: {done} / {total}",
    "Impossibile sostituire il programma: {error}. Scarica la nuova versione dalla pagina "
    "delle release.":
        "Cannot replace the program: {error}. Download the new version from the releases "
        "page.",
    "Aggiornamento installato. Riavvia PS PKG Toolkit a mano ({error}).":
        "Update installed. Restart PS PKG Toolkit yourself ({error}).",

    # -- GUI: main window -----------------------------------------------------------------
    "Estrai": "Extract",
    "Avanzamento": "Progress",
    "Cambia tema": "Switch theme",
    "Controllo in corso…": "Checking…",
    "PS PKG Toolkit {current} · disponibile la versione {version}":
        "PS PKG Toolkit {current} · version {version} available",
    "Disponibile PS PKG Toolkit {version}": "PS PKG Toolkit {version} available",
    "Aggiornamento disponibile": "Update available",
    "Dettagli": "Details",
    "PS PKG Toolkit {current} · è l'ultima versione": "PS PKG Toolkit {current} · up to date",
    "PS PKG Toolkit {current} · controllo non riuscito": "PS PKG Toolkit {current} · check failed",
    "Controllo aggiornamenti: {message}": "Update check: {message}",
    "Riavvio necessario": "Restart needed",
    "La nuova lingua verrà usata al prossimo avvio.":
        "The new language will be used at the next start.",
    "Spazio su disco insufficiente": "Not enough disk space",
    "Estrai comunque": "Extract anyway",
    "Nessun aggiornamento": "No update",
    "Stai già usando l'ultima versione ({version}).":
        "You are already using the latest version ({version}).",
    "Controllo non riuscito": "Check failed",
    "Aggiorna al termine dell'operazione.": "Update when the current operation is over.",
    "Versione più vecchia": "Older version",
    "Sovrascrivi": "Overwrite",
    "{path}: servono {needed}, liberi {free}": "{path}: {needed} needed, {free} free",
    "L'estrazione si fermerebbe a metà. Libera spazio oppure scegli un'altra cartella.":
        "The extraction would stop halfway. Free some space or choose another folder.",
    "Estrazione completata.": "Extraction completed.",
    "Annullamento…": "Cancelling…",
    "Vuoi interrompere l'operazione in corso e uscire?": "Stop the current operation and quit?",
    "Interrompi ed esci": "Stop and quit",
    "Continua": "Continue",
    "Impossibile procedere": "Cannot proceed",
    "Vuoi davvero sovrascrivere la versione installata?":
        "Do you really want to overwrite the installed version?",
    "Cartella già esistente": "Folder already exists",
    "Esiste già una cartella per {games}. I file con lo stesso nome verranno sovrascritti. "
    "Continuare?":
        "A folder for {games} already exists. Files with the same name will be overwritten. "
        "Continue?",
    "Controllo dello spazio non riuscito: {error}": "Free space check failed: {error}",
    "Versione portatile": "Portable version",
    "Impostazioni salvate in": "Settings saved in",
    "Impostazioni salvate accanto al programma: {folder}":
        "Settings saved next to the program: {folder}",
    # -- PKG creation ----------------------------------------------------------------
    "CONTENT_ID non valido nel param.sfo: '{cid}'":
        "Invalid CONTENT_ID in param.sfo: '{cid}'",
    'Calcolo delle impronte…':
        'Computing digests…',
    'Crea PKG':
        'Create PKG',
    'Crea comunque':
        'Create anyway',
    'Creato {path} ({cid})':
        'Created {path} ({cid})',
    'Creato {path}: {title} v{version} ({cid})':
        'Created {path}: {title} v{version} ({cid})',
    'Creazione del PKG in corso':
        'Creating the PKG',
    'Creazione del PKG interrotta':
        'PKG creation stopped',
    'Creazione di {path}':
        'Creating {path}',
    'Dimensione inattesa per {path}: {got} invece di {size} byte':
        'Unexpected size for {path}: {got} instead of {size} bytes',
    'ERRORE: spazio insufficiente per il nuovo PKG: servono {needed}, liberi {free}. Usa --force per procedere comunque.':
        'ERROR: not enough space for the new PKG: {needed} needed, {free} free. Use --force to go ahead anyway.',
    'ERRORE: {path} non trovato: non è la cartella di un gioco.':
        'ERROR: {path} not found: this is not a game folder.',
    'Immagine PFS interna di dimensione inattesa':
        'Inner PFS image has an unexpected size',
    'Lettura di {name}...':
        'Reading {name}...',
    "Libera spazio oppure scegli un'altra cartella.":
        'Free up some space or choose another folder.',
    'Manca sce_sys/param.sfo: non è la cartella di un gioco':
        'sce_sys/param.sfo is missing: this is not a game folder',
    'Operazione annullata: il PKG incompleto è stato eliminato.':
        'Cancelled: the incomplete PKG has been deleted.',
    'Operazione in corso':
        'Operation in progress',
    'PKG PS4 (*.pkg)':
        'PS4 PKG (*.pkg)',
    'PKG creato':
        'PKG created',
    'PKG creato.':
        'PKG created.',
    'PKG pronto':
        'PKG ready',
    'Per il nuovo PKG servono fino a {needed}, liberi {free}.':
        'The new PKG needs up to {needed}, {free} free.',
    'Preparazione del file system ({n} file)...':
        'Preparing the file system ({n} files)...',
    'Salva il nuovo PKG':
        'Save the new PKG',
    'Scegli un nome diverso da quello dei PKG di origine.':
        'Choose a name different from the source PKGs.',
    "Scrittura dell'immagine PFS ({size} MB)...":
        'Writing the PFS image ({size} MB)...',
    'Serve esattamente un gioco base per creare il PKG (trovati: {n})':
        'Exactly one base game is needed to create the PKG (found: {n})',
    "Si possono creare solo PKG di giochi (categoria 'gd', trovata '{cat}')":
        "Only game PKGs can be created (category 'gd', found '{cat}')",
    'Struttura del PKG':
        'PKG structure',
    'Unisce gioco base e aggiornamenti in un nuovo PKG, da installare su una PS4 modificata. I DLC restano PKG separati.':
        'Merges the base game and its updates into a new PKG to install on a modded PS4. DLC stay separate PKGs.',
    'cartella del gioco (quella che contiene sce_sys)':
        'game folder (the one containing sce_sys)',
    'crea un PKG di gioco da una cartella estratta':
        'create a game PKG from an extracted folder',
    'crea un nuovo PKG di gioco unendo il gioco base e i suoi aggiornamenti':
        'create a new game PKG merging the base game and its updates',
    'file PKG da creare, oppure una cartella (nome automatico)':
        'PKG file to create, or a folder (automatic name)',
    'gioco base e aggiornamenti (in qualsiasi ordine)':
        'base game and updates (in any order)',
    'procedi anche se lo spazio libero non basta':
        'go ahead even if there is not enough free space',
    'Installalo sulla PS4 modificata come un normale PKG.':
        'Install it on the modded PS4 like any other PKG.',
    '{name} è un aggiornamento di un altro gioco ({other})':
        '{name} is an update for another game ({other})',
    '{name} è una patch delta: non può essere unita':
        '{name} is a delta patch: it cannot be merged',
    '{name}: param.sfo mancante':
        '{name}: param.sfo missing',
    '{name}: solo il gioco base e i suoi aggiornamenti possono essere uniti in un PKG (i DLC restano PKG separati)':
        '{name}: only the base game and its updates can be merged into a PKG (DLC stay separate PKGs)',
    '{size} elaborati':
        '{size} processed',
}
