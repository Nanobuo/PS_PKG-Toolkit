# Novità

Ogni release pubblica come descrizione la sezione della propria versione.
Prima di creare una release aggiungi qui una sezione `## vX.Y.Z`.

## v1.5.0

- **Versione portatile**: le impostazioni vengono salvate nella cartella
  `PkgFree-data` accanto al programma, così PKG Free funziona anche da una
  chiavetta USB. Le cartelle sulla stessa chiavetta vengono ricordate anche se
  cambia la lettera dell'unità. Le impostazioni della versione precedente
  vengono riprese automaticamente.
- *Impostazioni → Informazioni* mostra dove sono salvate le impostazioni.

## v1.4.0

- **Ripresa automatica**: un'estrazione interrotta riparte da dove si era
  fermata, saltando i file e i PKG già completati.
- **Controllo dello spazio libero** prima di estrarre, con avviso se un disco
  non basta.
- **Libreria**: nuova pagina con i giochi già estratti, la versione installata
  e i DLC.
- **Verifica dei PKG** (opzionale): controlla le impronte SHA-256 per scoprire
  i download danneggiati. Anche da riga di comando: `verify` e `--verify`.
- **PKG nel Cestino** al termine (opzionale), solo se tutto è riuscito;
  da riga di comando `--delete-pkg`.
- **Notifica** di fine estrazione e percentuale nel titolo della finestra.
- **Aggiornamento dall'app**: avviso quando esce una nuova versione, download
  verificato e riavvio automatico.
- **Interfaccia in inglese**: lingua scelta in *Impostazioni → Aspetto* oppure
  automatica.

## v1.3.0

- **Cartella con il nome del gioco**: i giochi vengono estratti in
  `Giochi\<Titolo>\CUSA00003` (es. `Giochi\Driveclub\CUSA00003`), così si
  riconoscono a colpo d'occhio. shadPS4 li trova comunque. Si può disattivare da
  *Impostazioni → Cartella con il nome del gioco* o con `--no-title-folder`.
- Se un gioco è già stato estratto altrove nella cartella giochi (anche nel
  vecchio formato `Giochi\CUSA00003`), aggiornamenti e patch vengono applicati
  lì invece di creare una seconda cartella.
- Gli interruttori nelle Impostazioni mostrano "Attivo"/"Disattivo" invece di
  "On"/"Off".

## v1.2.0

- Prima release pubblica.
- Versioni per **Linux** (AppImage) e **macOS** (Apple Silicon), oltre a Windows.
- **Controllo della versione installata**: avviso e conferma prima di riportare
  un gioco a una versione più vecchia; da riga di comando serve `--force`.
- Corretto l'errore "Immagine PFSC non trovata" con alcuni fPKG reali.
- Interfaccia in stile Windows 11 (Fluent) con tema chiaro e scuro.
