# PS PKG Toolkit

Programma per Windows, Linux e macOS che estrae i file **PKG PS4** in una cartella pronta per
l'emulatore [shadPS4](https://github.com/shadps4-emu/shadPS4), unendo
**gioco base + aggiornamenti (patch)** in un'unica cartella aggiornata e
sistemando i **DLC** nella struttura che shadPS4 si aspetta. Può anche creare un
**nuovo PKG** con il gioco e i suoi aggiornamenti già uniti, da installare su
una PS4 modificata.

Fino alla versione 1.5 il programma si chiamava *PKG Free*.

> Sono supportati solo i PKG **"fake" (fPKG)**: backup dei propri giochi e
> homebrew firmati con le chiavi di debug pubbliche. I PKG retail scaricati dal
> PlayStation Store sono cifrati con chiavi della console e **non** possono
> essere estratti. Usa il programma solo con contenuti di cui possiedi i diritti.

![Pagina Estrai, tema chiaro](docs/estrai-chiaro.png)

## Download

Le versioni pubblicate si trovano nella pagina **Releases**. Ogni push compila
anche gli eseguibili con GitHub Actions (scheda **Actions** → ultima esecuzione
di *Build* → artefatti). Creando un tag `v*` (es. `v1.2.0`) viene pubblicata
una release con un file per ogni sistema. In alternativa, senza creare il tag a mano: **Actions → Build →
Run workflow**, scrivendo la versione (es. `v1.2.0`) nel campo del tag; deve
corrispondere a `__version__` in `pkgfree/__init__.py`. La descrizione della release è la
sezione `## vX.Y.Z` di [`CHANGELOG.md`](CHANGELOG.md), che va scritta prima. Per correggere
la descrizione di una release già pubblicata, modifica la sua sezione e avvia
*Run workflow* con il tag e l'opzione **Solo note** (non ricompila nulla).

| Sistema | File |
|---|---|
| Windows 10/11 (x64) | `PS-PKG-Toolkit-windows-x64.exe` (interfaccia grafica, ~60–80 MB perché include Qt) e `pspkg-windows-x64.exe` (riga di comando) |
| Linux (x86_64) | `PS-PKG-Toolkit-linux-x86_64.AppImage` (interfaccia grafica e riga di comando in un unico file) |
| macOS (Apple Silicon) | `PS-PKG-Toolkit-macos-arm64.zip` (contiene `PS-PKG-Toolkit.app`) |

I file `PkgFree-*` presenti nelle release servono solo all'aggiornamento
automatico delle copie installate con il vecchio nome: sono identici a quelli
`PS-PKG-Toolkit-*`.

**Linux:** rendi eseguibile il file e avvialo:

```bash
chmod +x PS-PKG-Toolkit-linux-x86_64.AppImage
./PS-PKG-Toolkit-linux-x86_64.AppImage                 # interfaccia grafica
./PS-PKG-Toolkit-linux-x86_64.AppImage install gioco.pkg patch.pkg -o ~/Giochi/PS4   # riga di comando
```

Se l'AppImage non parte per la mancanza di FUSE, installa `libfuse2` oppure
avvialo con `--appimage-extract-and-run`.

**macOS:** l'app non è firmata, quindi al primo avvio macOS la blocca. Apri
**Impostazioni di Sistema → Privacy e sicurezza** e premi **Apri comunque**,
oppure da Terminale: `xattr -dr com.apple.quarantine /Applications/PS-PKG-Toolkit.app`.
La riga di comando è `PS-PKG-Toolkit.app/Contents/MacOS/PS-PKG-Toolkit install …`.

## Uso (interfaccia grafica)

L'interfaccia segue lo stile **Fluent** di Windows 11 (menu laterale, schede,
sfondo Mica) e supporta il **tema chiaro e scuro**.

1. Avvia `PS-PKG-Toolkit-windows-x64.exe`.
2. Nella pagina **Estrai** trascina i file `.pkg` (o usa **Aggiungi PKG…** /
   **Aggiungi cartella…**): gioco base, aggiornamenti e DLC, in qualsiasi
   ordine. Il tipo viene riconosciuto dal `param.sfo` e i PKG vengono
   **raggruppati per gioco**: ogni scheda mostra icona, versione finale e
   l'**ordine di applicazione** (base → aggiornamenti per `APP_VER` → DLC).
   Eventuali problemi (gioco base mancante, patch delta) compaiono come avvisi
   nella scheda.
3. In basso scegli la **cartella giochi** (la cartella DLC si imposta in
   **Impostazioni**; se vuota si usa `<cartella giochi>\addcont`).
4. Premi **Estrai tutto**. Prima di iniziare il programma controlla che sui
   dischi di destinazione ci sia **spazio sufficiente** e avvisa se non basta.
   Si apre la pagina **Avanzamento** con percentuale, velocità, tempo
   rimanente e lo stato di ogni PKG (la percentuale compare anche nel titolo
   della finestra). Il pulsante **Annulla** interrompe l'operazione; i
   messaggi dettagliati sono nella pagina **Registro**.
5. A fine estrazione, se stai usando un'altra finestra, arriva una
   **notifica di sistema**.

**Ripresa automatica**: se un'estrazione si interrompe (annullata, PC spento,
disco pieno), avviandola di nuovo con gli stessi PKG riparte da dove si era
fermata: i file già scritti e i PKG già completati vengono saltati.

**Libreria**: elenca i giochi già presenti nella cartella giochi con icona,
versione installata, eventuale cartella di aggiornamento separata e DLC.

**Impostazioni → Estrazione** permette inoltre di:

- **verificare i PKG** prima di estrarli (impronte SHA-256 contenute nel PKG:
  scopre i download danneggiati; rilegge tutto il PKG, circa un minuto in più
  ogni 50 GB);
- **spostare i PKG nel Cestino** al termine, solo se l'estrazione di tutti i
  PKG è riuscita;
- disattivare la notifica di fine estrazione.

**Tema e lingua**: pulsante **Cambia tema** nel menu laterale (in basso),
oppure **Impostazioni → Aspetto**: tema *Chiaro*, *Scuro* o di sistema e
lingua *Italiano*, *English* o automatica (la lingua cambia al riavvio).

**Aggiornamenti**: all'avvio il programma controlla se su GitHub c'è una nuova
release (disattivabile in **Impostazioni → Aggiornamenti**, dove c'è anche
**Controlla ora**). Se c'è, un avviso permette di leggere le novità e di
**aggiornare con un clic**: il file viene scaricato, verificato (SHA-256),
sostituito e il programma si riavvia. Funziona con le versioni scaricate dalle
release (exe di Windows, AppImage, app macOS) e solo se il repository è
pubblico.

| Avanzamento (scuro) | Completato (scuro) | Libreria (scuro) | Impostazioni (chiaro) |
|---|---|---|---|
| ![](docs/avanzamento-scuro.png) | ![](docs/completato-scuro.png) | ![](docs/libreria-scuro.png) | ![](docs/impostazioni-chiaro.png) |

Risultato:

```
<cartella giochi>\<Titolo>\CUSA12345\               gioco + tutti gli aggiornamenti
<cartella DLC>\CUSA12345\<ENTITLEMENT_LABEL>\       un DLC per cartella
```

La cartella `<Titolo>` (es. `Giochi\Driveclub\CUSA00003`) serve solo a
riconoscere il gioco a colpo d'occhio: shadPS4 cerca i giochi anche nelle
sottocartelle. Si può disattivare in **Impostazioni → Cartella con il nome del
gioco** (da riga di comando: `--no-title-folder`). Se un gioco è già stato
estratto altrove nella cartella giochi (es. `Giochi\CUSA00003`), aggiornamenti
e patch vengono applicati lì. I DLC restano in `addcont\CUSA12345`, dove
shadPS4 li cerca.

In shadPS4:

- aggiungi la *cartella giochi* tra le cartelle dei giochi;
- imposta la *cartella DLC* come cartella dei contenuti aggiuntivi
  (`addon install dir`, oppure `shadPS4.exe --set-addon-folder "<cartella DLC>"`).
  In alternativa scegli direttamente come cartella DLC quella predefinita di
  shadPS4 (`user\addcont`).

Opzione **Impostazioni → Unisci gli aggiornamenti al gioco** (attiva di
default): se la disattivi, le patch vengono estratte in `CUSA12345-UPDATE`
accanto alla cartella del gioco, formato che shadPS4 riconosce e sovrappone al gioco base
all'avvio.

### Creare un PKG unico (per PS4 modificata)

Nella pagina **Estrai**, ogni gioco aggiunto insieme ai suoi aggiornamenti ha il
pulsante **Crea PKG**: scegli dove salvare il file (il nome proposto è
`Titolo [CUSA12345] v01.28.pkg`) e il programma crea un **nuovo PKG di gioco**
che contiene già l'ultima versione, da installare sulla console al posto di
gioco base + patch. Non serve estrarre nulla: i file vengono letti direttamente
dai PKG di origine, quindi lo spazio necessario è solo quello del nuovo PKG
(circa la somma dei PKG di origine). La velocità è di circa 100 MB/s: per un
gioco da 50 GB servono alcuni minuti.

![PKG creato, tema scuro](docs/crea-pkg-scuro.png)

Il nuovo PKG è un fPKG con la stessa struttura di quelli creati da
[LibOrbisPkg](https://github.com/maxton/LibOrbisPkg): firmato con le chiavi
pubbliche "fake", licenza di debug e passcode di zeri. Si installa come un
normale fPKG, quindi serve una console modificata in grado di installarli.

- I **DLC** non possono far parte del PKG del gioco: restano PKG separati, da
  installare come prima.
- Le **patch delta** non possono essere unite (come per l'estrazione).
- I test automatici controllano ogni PKG creato con gli stessi criteri del
  validatore di LibOrbisPkg (impronte, firme dei blocchi PFS, licenza). Durante
  lo sviluppo non è stato possibile provarlo su una console reale.

### Versione portatile

PS PKG Toolkit non va installato: copia `PS-PKG-Toolkit-windows-x64.exe` (o l'AppImage) dove
vuoi, anche su una chiavetta USB. Al primo avvio crea accanto al programma la
cartella `PS-PKG-Toolkit-data` e vi salva le impostazioni (se c'erano impostazioni di
una copia precedente, anche di *PKG Free*, vengono riprese). Le cartelle che stanno sulla stessa
chiavetta o disco esterno del programma vengono ricordate in modo relativo,
quindi funzionano anche se su un altro PC la chiavetta prende un'altra lettera.
L'aggiornamento dall'app sostituisce solo il programma e lascia intatta la
cartella dei dati.

Se il programma è in una cartella non scrivibile (es. `C:\Program Files`), le
impostazioni finiscono in `%APPDATA%\PS-PKG-Toolkit\config.json` (su Linux in
`~/.config/PS-PKG-Toolkit/config.json`). Su macOS la modalità portatile si attiva
creando a mano la cartella `PS-PKG-Toolkit-data` accanto a `PS-PKG-Toolkit.app`.
*Impostazioni → Informazioni* mostra dove sono salvate.

## Uso (riga di comando)

Su Windows il file della release si chiama `pspkg-windows-x64.exe` (puoi
rinominarlo in `pspkg.exe`); su Linux e macOS si usano l'AppImage o
`PS-PKG-Toolkit.app/Contents/MacOS/PS-PKG-Toolkit` con gli stessi argomenti.

```bat
pspkg info gioco.pkg patch.pkg --files
pspkg install gioco.pkg patch_1.01.pkg patch_1.05.pkg dlc1.pkg -o D:\PS4\Giochi
pspkg install patch.pkg -o D:\PS4\Giochi --separate-update
pspkg install dlc.pkg -o D:\PS4\Giochi --addons C:\shadPS4\user\addcont
pspkg install gioco.pkg -o D:\PS4\Giochi --verify --delete-pkg
pspkg verify gioco.pkg patch.pkg
pspkg merge gioco.pkg patch_1.01.pkg patch_1.05.pkg -o D:\PS4\PKG\
pspkg pack D:\PS4\Giochi\Driveclub\CUSA00003 -o Driveclub.pkg
```

`merge` crea un nuovo PKG di gioco da gioco base e aggiornamenti (se `-o` è una
cartella il nome è automatico; `--force` procede anche con poco spazio libero).
`pack` crea un PKG di gioco da una cartella già estratta (quella che contiene
`sce_sys`).

Opzioni di `install`: `--verify` (verifica SHA-256 prima di estrarre),
`--delete-pkg` (cancella i PKG se tutto è riuscito), `--no-resume` (ignora
un'estrazione interrotta e riparte da zero), `--force` (procede anche con poco
spazio libero o se verrebbe installata una versione più vecchia),
`--separate-update`, `--no-title-folder`. La lingua segue quella del sistema;
per sceglierla: `PSPKG_LANG=en` oppure `PSPKG_LANG=it`.

## Note e limiti

- Le patch **delta** (incrementali) contengono solo le differenze e non
  possono essere unite: viene mostrato un avviso. Le patch fPKG comuni sono
  complete/cumulative e funzionano.
- I DLC che sono solo "chiavi di sblocco" (senza dati) producono una cartella
  con il solo `sce_sys\param.sfo`: è corretto, shadPS4 li riconosce così.
- I file esistenti nella destinazione vengono sovrascritti.
- **Controllo della versione installata**: se nella cartella giochi c'è già il
  gioco (anche in `CUSA12345-UPDATE`), il programma ne legge la versione
  (`APP_VER`). Se l'estrazione lo riporterebbe a una versione più vecchia
  (es. reinstallare il gioco base o una patch precedente sopra la 1.05) chiede
  conferma; se la patch è la stessa già installata lo segnala nella scheda.
  Da riga di comando un declassamento viene rifiutato senza `--force`.
- Velocità indicativa: decine di MB/s (decifratura AES-XTS + decompressione).
- Per la ripresa il programma lascia, durante l'estrazione, un piccolo file
  nascosto `.pkgfree-….resume` nella cartella del gioco; viene cancellato
  quando l'estrazione finisce.

## Compilare da sorgente

Serve Python 3.10 o successivo (la GUI usa PySide6 e PySide6-Fluent-Widgets).

```bat
build.bat
```

oppure manualmente:

```bat
pip install -r requirements.txt pyinstaller
set QT_QPA_PLATFORM=offscreen
python -m unittest discover -s tests
set QT_QPA_PLATFORM=
pyinstaller --onefile --windowed --name PS-PKG-Toolkit --exclude-module tkinter pkgfree_gui.py
pyinstaller --onefile --console --name pspkg --exclude-module PySide6 --exclude-module qfluentwidgets pkgfree_cli.py
```

AppImage per Linux (serve `curl`; scarica `appimagetool`):

```bash
pip install -r requirements.txt pyinstaller pillow
packaging/linux/build_appimage.sh      # crea dist/PS-PKG-Toolkit-x86_64.AppImage
```

Senza compilare: `python -m pkgfree` (GUI) oppure `python -m pkgfree install ...`
(`pkgfree` è il nome interno del pacchetto Python, rimasto quello di prima).

## Struttura del codice

| File | Contenuto |
|---|---|
| `pkgfree/pkg.py` | lettura PKG, decifratura PFS (AES-XTS), decompressione PFSC, estrazione |
| `pkgfree/crypto.py` | RSA / AES-CBC / HMAC / XTS |
| `pkgfree/keys.py` | chiavi RSA pubbliche per fPKG |
| `pkgfree/installer.py` | unione gioco + patch + DLC, ripresa, spazio libero, libreria |
| `pkgfree/builder.py` | creazione di un fPKG di gioco (PFS interno, PFSC, PFS esterno firmato e cifrato, voci e intestazione) |
| `pkgfree/merge.py` | nuovo PKG da gioco base + aggiornamenti, letti direttamente dai PKG |
| `pkgfree/sfo.py` | lettura e scrittura del `param.sfo` |
| `pkgfree/build_keys.py` | chiavi pubbliche e di debug usate per creare i PKG (da LibOrbisPkg) |
| `pkgfree/updater.py` | aggiornamento dall'app (release GitHub) |
| `pkgfree/portable.py` | versione portatile (cartella `PS-PKG-Toolkit-data`, percorsi relativi) |
| `pkgfree/i18n.py`, `pkgfree/i18n_en.py` | traduzione inglese |
| `pkgfree/gui/` | interfaccia Fluent: `extract_page.py` (schede per gioco), `library_page.py`, `progress_page.py` (avanzamento + thread di estrazione), `settings_page.py` (impostazioni, registro), `update_ui.py`, `window.py`, `config.py` |
| `pkgfree/cli.py` | riga di comando |
| `tests/` | test con PKG sintetici generati al volo (estrazione, ripresa, verifica, creazione di PKG con i controlli del validatore di LibOrbisPkg, aggiornamento, traduzioni) più uno smoke test della GUI |
| `packaging/linux/` | script e file per l'AppImage (`build_appimage.sh`, `AppRun`, `.desktop`) |
| `assets/ps-pkg-toolkit.png` | icona dell'app |

## Licenza

GPL-3.0-or-later (richiesta da PySide6-Fluent-Widgets, GPLv3). Il formato e le
chiavi derivano dall'estrattore PKG (GPL-2.0-or-later) storicamente incluso in
shadPS4 e da LibOrbisPkg (LGPL-3.0, di maxton), da cui deriva anche la
struttura dei PKG creati.
