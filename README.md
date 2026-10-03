# Outfit-Dashboard (MK1)

Lokales Web-Dashboard, das aus dem eigenen Kleiderschrank bei jedem Aufruf ein
**farblich passendes Outfit zum heutigen Wetter** zusammenstellt.
Gestaltet im dunklen Lattice-Design der übrigen Dashboards, optimiert für das
iPhone und gedacht für den Dauerbetrieb auf einem **GL.iNet Slate 7** (OpenWrt).
Zusätzlich gibt es eine **Windows-EXE** und eine **macOS-App**, die per GitHub
Actions automatisch gebaut und als Release veröffentlicht werden.

Aktuelle Version: **v1.4.0**

> **Alles in einem Ordner:** `/root/Outfit-Dashboard` (auf dem Router
> `root@GL-BE3600:~# Outfit-Dashboard`). Die Nutzerdaten liegen darin im
> Unterordner `daten/`. Bei einem Update werden nur die Programmdateien
> ersetzt – Aktivitäten, Standort, Kleidungsstücke, Fotos, Labels und
> Konfiguration bleiben erhalten.

---

## Funktionen

### Nutzermodus (`/`)
- **Wetterkarte**: aktuelle Außentemperatur, gefühlte Temperatur, Tageshöchst- und
  Tiefstwert, erwartete Niederschlagsmenge (mm) und -wahrscheinlichkeit
- **Reiter „Outfit“**
  - Zusammenstellung aus **Oberteil, Hose, Unterwäsche** und einer
    **Schuh-Empfehlung**, Bilder untereinander
  - wird bei **jedem Neuladen** neu gewürfelt (zusätzlich Knopf „Neu“)
  - **Aktivitäten-Leiste** an der Seite: Oberteil und Hose werden nur aus Stücken
    mit dem passenden Aktivitäts-Label gewählt („Alle“ = ohne Filter)
  - Auswahl nach **Farbharmonie** und **Wetterpassung** (Temperatur + Niederschlag),
    Bewertung als Prozent-Badges
- **Reiter „Kleiderschrank“**: alle Stücke mit Bild, Temperatur- und
  Niederschlags-Balkendiagramm (inkl. Markierung des heutigen Werts) und den
  Aktivitäts-Labels darunter; Filter nach Typ

### Einstellungen (`/einstellungen`)
- **Standort** per Ortssuche oder manuellen Koordinaten
- **Aktivitäten** anlegen, umbenennen, löschen
- **Kleidungsstücke** anlegen/bearbeiten/löschen:
  Foto (Kamera oder Mediathek), Name, Typ, Farbe, Aktivitäten,
  Temperatur- und Niederschlagsbereich mit Live-Balkendiagramm

- **Datenspeicher & Sicherung**: Speicherort und -belegung anzeigen,
  komplette Sicherung als ZIP herunterladen und wieder einspielen

### Nutzungsbedingungen (`/nutzungsbedingungen`)
Hinweise zu Betrieb, Datenspeicherung, Wetterdaten-Lizenz und Haftung.

---

## Wie die Zusammenstellung funktioniert

1. **Zielwerte des Tages**
   Temperatur = Tiefstwert + 65 % der Spanne bis zum Höchstwert
   (tagsüber zählt mehr), Niederschlag = erwartete Tagessumme in mm.
2. **Wetterpassung je Stück**: liegt der Zielwert im eingestellten Bereich → 100 %.
   Außerhalb fällt der Wert linear ab (Temperatur: 0 % bei 10 °C Abstand,
   Niederschlag: 0 % bei 6 mm Abstand).
3. **Farbharmonie** zwischen Oberteil, Hose und Schuhen:
   - Neutrale Farben (Schwarz, Grau, Weiß, Beige, Braun, Marine, Jeansblau …)
     passen zu fast allem
   - zwei Farbtöne: analog oder komplementär = gut, „unruhige“ Abstände = schlecht
   - gedeckte Farben (Oliv, Bordeaux, Rosa, Hellblau) sind nachsichtiger
   - „Bunt / Muster“ passt zu Neutralem, aber nicht zu weiterem Muster
4. **Oberteil + Hose** werden als Paar bewertet
   (40 % Temperatur, 20 % Niederschlag, 40 % Farbe).
   **Schuhe** passen sich farblich an das Paar an und bekommen einen kleinen
   Bonus, wenn sie zur Aktivität passen. **Unterwäsche** richtet sich nach der
   Temperatur.
5. Aus den Kandidaten wird **gewichtet zufällig** gezogen: gute Kombinationen sind
   deutlich wahrscheinlicher, aber es gibt Abwechslung.

Ohne Wetterdaten (kein Standort / offline) zählen nur Farbe und Aktivität.

---

## Ordneraufbau

```
/root/Outfit-Dashboard/
├── app.py                  Flask-Server, Seiten und REST-API
├── outfit.py               Typen, Farbpalette, Bewertungs- und Auswahllogik
├── weather.py              Open-Meteo-Abfrage und Ortssuche (nur Standardbibliothek)
├── storage.py              threadsicherer JSON-Speicher mit atomarem Schreiben
├── version.py              Versionsnummer
├── requirements.txt        einzige Abhängigkeit: Flask
├── config.example.json     Vorlage für daten/config.json
├── templates/              base, index (Nutzer), settings, terms
├── static/                 style.css, common.js, user.js, settings.js, icon.svg
├── .github/workflows/
│   └── build-release.yml   GitHub Actions: EXE, Mac-App, Router-Paket, Release
├── packaging/
│   ├── outfit_dashboard.spec  PyInstaller-Spezifikation (Windows/macOS)
│   └── make_icon.py        zeichnet das Programm-Icon beim Build
├── openwrt/
│   ├── install.sh          Installation und Update (GL.iNet Slate 7)
│   ├── update.sh           Update – ersetzt nur die Programmdateien
│   └── outfit-dashboard.init  procd-Dienst (Autostart)
├── CHANGELOG.md
├── README.md
└── daten/                  ← Nutzerdaten, entsteht beim ersten Start, NICHT im Repo
    ├── config.json         Port, Upload-Grenzen, Wetter-Cache …
    ├── settings.json       Standort und Aktivitäten
    ├── clothes.json        Kleidungsstücke mit allen Labels
    ├── images/             Fotos
    └── backups/            automatische Sicherungen (vor Update / Wiederherstellung)
```

| Teil                    | bei Update             |
|-------------------------|------------------------|
| Programmdateien         | werden ersetzt         |
| `daten/`                | **bleibt unverändert** |

Wichtig: Beim Update **nicht** den ganzen Ordner `/root/Outfit-Dashboard`
löschen, sondern `update.sh` benutzen (oder neue Dateien darüberkopieren) –
dann bleibt `daten/` erhalten.

Ein abweichender Datenordner lässt sich über die Umgebungsvariable
`OUTFIT_HOME` setzen.

**Übernahme älterer Versionen:** Daten aus v1.0.0 (`data/` im Programmordner)
und v1.1.0 (`/srv/outfit-dashboard`, `~/.outfit-dashboard`) werden beim ersten
Start bzw. durch `install.sh` automatisch nach `daten/` übernommen.

**Datenformat:** Die Dateien tragen eine Schema-Nummer; fehlende Felder werden
beim Laden ergänzt, damit ältere Datenstände auch mit neuen Programmversionen
funktionieren.

---

## Installation auf dem PC / Raspberry Pi (Test)

```bash
pip install -r requirements.txt
python3 app.py
```

Daten landen im Unterordner `daten/` neben `app.py`.

Aufruf: `http://<IP-des-Rechners>:8095`

---

## Installation auf dem GL.iNet Slate 7

Voraussetzungen: SSH-Zugang (`ssh root@192.168.8.1`), Internetverbindung des
Routers, ca. **30–40 MB** freier Speicher auf `/overlay` für Python + Flask.
Den freien Speicher zeigt `df -h /overlay`.

### Erstinstallation

1. Ordner `Outfit-Dashboard` vom PC direkt ins Home-Verzeichnis des Routers kopieren:
   `scp -r Outfit-Dashboard root@192.168.8.1:/root/`
   (bei neueren OpenSSH-Versionen ggf. `scp -O -r …`)
2. Auf dem Router (`root@GL-BE3600:~#`):
   `cd Outfit-Dashboard`
   `sh openwrt/install.sh`
3. Aufruf im Browser: `http://192.168.8.1:8095`

Das Skript

- installiert `python3`, `python3-pip`, CA-Zertifikate (opkg oder apk) und Flask –
  nur falls noch nicht vorhanden,
- legt `/root/Outfit-Dashboard/daten/` an,
- übernimmt Daten früherer Versionen (`/opt/outfit-dashboard`, `/srv/outfit-dashboard`)
  und entfernt den alten Programmordner `/opt/outfit-dashboard`,
- richtet den Dienst mit Autostart ein,
- trägt `/root/Outfit-Dashboard/` und den Dienst in `/etc/sysupgrade.conf` ein,
  damit beides bei einem **Firmware-Update mit „Einstellungen behalten“**
  mitgesichert wird.

### Update auf eine neue Version

1. Neuen Ordner `Outfit-Dashboard` nach `/tmp/` auf den Router kopieren:
   `scp -r Outfit-Dashboard root@192.168.8.1:/tmp/`
2. `cd /tmp/Outfit-Dashboard`
3. `sh openwrt/update.sh`

Dabei passiert:

- Dienst anhalten
- kleine Sicherung von `config.json`, `settings.json`, `clothes.json` nach
  `daten/backups/vor-update-<Datum>.tar.gz` (die letzten 3 bleiben)
- Programmdateien in `/root/Outfit-Dashboard` einzeln ersetzen
- Dienst starten

`daten/` wird dabei **nie** verändert oder gelöscht.
Danach kann `/tmp/Outfit-Dashboard` gelöscht werden (verschwindet ohnehin beim Neustart).

### Nach einem Firmware-Update des Routers

Mit „Einstellungen behalten“ bleibt `/root/Outfit-Dashboard` samt `daten/`
erhalten, die Python-Pakete aber nicht. Dann einfach erneut ausführen:
`cd /root/Outfit-Dashboard && sh openwrt/install.sh`
Zusätzlich empfiehlt sich vorher eine **Sicherung über die Einstellungsseite**.

### Dienst bedienen

```sh
/etc/init.d/outfit-dashboard restart
/etc/init.d/outfit-dashboard stop
logread -e python3 -f        # Log live ansehen
```

### Speicherplatz sparen

Fotos werden im Browser auf max. 900 px (JPEG) verkleinert, ein Stück belegt
typischerweise 60–150 KB. Den Speicherverbrauch zeigt die Einstellungsseite
unter „Datenspeicher & Sicherung“.

---

## Windows-EXE und macOS-App

### Herunterladen

Unter **Releases** im GitHub-Repo liegen pro Version:

| Datei                                  | Für                                   |
|----------------------------------------|---------------------------------------|
| `Outfit-Dashboard-vX.Y.Z-windows.exe`  | Windows 10/11                         |
| `Outfit-Dashboard-vX.Y.Z-macos.zip`    | macOS 11+ (Apple Silicon)             |
| `Outfit-Dashboard-vX.Y.Z-router.zip`   | GL.iNet Slate 7 – enthält den Ordner `Outfit-Dashboard` |

### Bedienung

- **Doppelklick** startet den Server und öffnet die Seite im Standard-Browser.
- Windows zeigt ein Konsolenfenster mit der Adresse fürs Netzwerk
  (z. B. `http://192.168.8.20:8095` für das iPhone). Schließen des Fensters
  beendet das Programm.
- macOS hat kein Fenster – beenden über **Einstellungen → Programm beenden**
  (der Knopf erscheint nur am eigenen Rechner).
- Ein zweiter Doppelklick startet nichts doppelt, sondern öffnet nur den Browser.
- Ist Port 8095 von einem anderen Programm belegt, wird automatisch 8096–8105
  verwendet.
- Beim ersten Start fragt die Firewall, ob Zugriffe aus dem Netzwerk erlaubt
  werden – für das iPhone „Zulassen“ wählen.

### Datenordner – immer direkt neben dem Programm

Bei allen Varianten entsteht der Ordner `daten/` **im selben Verzeichnis**,
in dem das Programm liegt:

```
Windows                      macOS                        Python / Router
Outfit-Dashboard\            Outfit-Dashboard/            Outfit-Dashboard/
├── Outfit-Dashboard.exe     ├── Outfit-Dashboard.app     ├── app.py …
└── daten\                   └── daten/                   └── daten/
```

Empfehlung: EXE bzw. App in einen **eigenen Ordner** legen (z. B.
`Dokumente\Outfit-Dashboard` oder `~/Outfit-Dashboard`), nicht direkt auf den
Desktop oder in „Downloads“.

Beim Update einfach die EXE bzw. App durch die neue ersetzen – `daten/`
bleibt liegen. Zum Umziehen den ganzen Ordner (Programm + `daten/`) kopieren.

**Sonderfälle** – dann wird ersatzweise ein Benutzerordner verwendet und in den
Einstellungen unter „Datenspeicher & Sicherung“ ein Hinweis angezeigt:

- Windows: Ordner nicht beschreibbar (z. B. `C:\Programme`) →
  `%LOCALAPPDATA%\Outfit-Dashboard\daten`
- macOS: App wird von macOS isoliert gestartet („App Translocation“, passiert bei
  frisch heruntergeladenen Apps) → `~/Library/Application Support/Outfit-Dashboard/daten`.
  Abhilfe: `xattr -cr <Pfad>/Outfit-Dashboard.app` und neu starten.

Daten, die v1.3.0 noch in `%LOCALAPPDATA%` bzw. `Application Support` abgelegt
hat, werden beim ersten Start automatisch nach `daten/` neben dem Programm übernommen.

### Nicht signiert

- **Windows SmartScreen:** „Weitere Informationen“ → „Trotzdem ausführen“
- **macOS Gatekeeper:** im Terminal einmalig
  `xattr -cr ~/Outfit-Dashboard/Outfit-Dashboard.app` ausführen (Pfad anpassen).
  Das entfernt die Download-Markierung, dann startet die App normal **und**
  kann ihre Daten neben sich ablegen. Alternativ Rechtsklick → „Öffnen“.

---

## GitHub Actions: Build und automatisches Release

Workflow: `.github/workflows/build-release.yml`

Bei **jedem Push** (und jedem Pull-Request):

1. Version aus `version.py` lesen
2. **Windows** (`windows-latest`) und **macOS** (`macos-latest`) parallel bauen
   mit PyInstaller (`packaging/outfit_dashboard.spec`)
3. Jedes gebaute Programm wird **probeweise gestartet** und muss auf
   `/api/meta` mit der richtigen Version antworten
4. Router-Paket bauen (Syntaxprüfung von Python- und Shell-Dateien)
5. Alle Dateien als **Build-Artefakte** hochladen (30 Tage)

Auf `main`/`master` zusätzlich:

6. Existiert noch **kein Release `v<Version>`**, wird es automatisch erstellt –
   mit Tag, Titel „Outfit-Dashboard v<Version>“, dem passenden Abschnitt aus
   `CHANGELOG.md` als Beschreibung und allen drei Dateien.
7. Existiert es schon, wird nur gebaut (Hinweis im Log: Version hochzählen).

**Neues Release veröffentlichen:**
`version.py` hochzählen → Abschnitt `## [X.Y.Z]` in `CHANGELOG.md` ergänzen → pushen.

Voraussetzung im Repo: *Settings → Actions → General → Workflow permissions*
auf **„Read and write permissions“** (für das Anlegen des Releases).
Der Workflow setzt zusätzlich `permissions: contents: write`.

### Lokal bauen

```bash
pip install -r requirements.txt pyinstaller pillow
python packaging/make_icon.py
pyinstaller --noconfirm --clean packaging/outfit_dashboard.spec
```

Ergebnis in `dist/` (Windows: `Outfit-Dashboard.exe`, macOS: `Outfit-Dashboard.app`).

---

## Konfiguration (`config.json`)

| Schlüssel               | Standard   | Bedeutung                                              |
|-------------------------|------------|--------------------------------------------------------|
| `host`                  | `0.0.0.0`  | Netzwerkschnittstelle (alle)                           |
| `port`                  | `8095`     | Web-Port (nicht 80/443, die nutzt die GL.iNet-Oberfläche) |
| `data_dir`              | `.`        | Ablage von settings/clothes/images, relativ zu `daten/` |
| `max_upload_mb`         | `12`       | maximale Größe eines Fotos                             |
| `max_backup_mb`         | `300`      | maximale Größe einer einzuspielenden Sicherung         |
| `weather_cache_minutes` | `15`       | wie lange Wetterdaten zwischengespeichert werden       |
| `weather_verify_ssl`    | `true`     | TLS-Zertifikate prüfen (nur bei Zertifikatsproblemen auf `false`) |
| `open_browser`          | EXE/App: `true`, sonst `false` | Browser beim Start automatisch öffnen |

Umgebungsvariablen: `OUTFIT_HOME` (Datenordner), `OUTFIT_CONFIG`
(Konfigurationsdatei), `OUTFIT_PORT` (Port), `OUTFIT_OPEN_BROWSER` (`1`/`0`).

Die Datei liegt unter `/root/Outfit-Dashboard/daten/config.json`.
Ein abweichender Pfad kann über die Umgebungsvariable `OUTFIT_CONFIG` gesetzt werden.

---

## iPhone

- Layout für 375–430 px Breite ausgelegt, Safe-Area (Notch / Home-Indicator)
  berücksichtigt, Eingabefelder mit 16 px (kein Auto-Zoom), Touch-Ziele ≥ 44 px
- **Zum Home-Bildschirm hinzufügen** (Safari → Teilen) öffnet das Dashboard wie eine App
- Fotos können direkt mit der Kamera aufgenommen werden

---

## REST-API

| Methode | Pfad                          | Zweck                                   |
|---------|-------------------------------|-----------------------------------------|
| GET     | `/api/meta`                   | Version, Typen, Farben, Skalen, Aktivitäten, Standort |
| GET     | `/api/weather`                | Wetter des Tages                        |
| GET     | `/api/outfit?activity=<id>`   | neue Zusammenstellung                   |
| GET     | `/api/clothes`                | alle Kleidungsstücke                    |
| POST    | `/api/clothes`                | anlegen (multipart, Feld `image`)       |
| POST    | `/api/clothes/<id>`           | bearbeiten (Bild optional)              |
| DELETE  | `/api/clothes/<id>`           | löschen                                 |
| GET     | `/api/settings`               | Einstellungen                           |
| POST    | `/api/settings/location`      | Standort `{name, lat, lon}`             |
| POST    | `/api/settings/activities`    | Aktivitätenliste `{activities:[…]}`     |
| GET     | `/api/geocode?q=<ort>`        | Ortssuche                               |
| GET     | `/api/storage`                | Speicherort und -belegung               |
| GET     | `/api/backup`                 | Sicherung als ZIP herunterladen         |
| POST    | `/api/backup`                 | Sicherung einspielen (Feld `backup`)    |
| POST    | `/api/shutdown`               | Desktop-Version beenden (nur vom eigenen Rechner) |

---

## Hinweise

- Kein Passwortschutz – jede Person im LAN kann Einstellungen ändern.
  Nicht per Portweiterleitung ins Internet freigeben.
- Wetterdaten: [Open-Meteo.com](https://open-meteo.com/), Lizenz CC BY 4.0.
- Datensicherung: in den Einstellungen „Sicherung herunterladen“ oder den
  Ordner `/root/Outfit-Dashboard/daten` kopieren.

## Versionierung

Semantic Versioning (`MAJOR.MINOR.PATCH`), gepflegt in `version.py` und im
`CHANGELOG.md`; die Version wird im Fuß der Webseite angezeigt.
