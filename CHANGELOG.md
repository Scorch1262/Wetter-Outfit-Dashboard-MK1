# Changelog

Alle Änderungen am Outfit-Dashboard-MK1. Versionierung nach Semantic Versioning.

## [1.6.0] – 2026-10-04

### Geändert
- Nutzeransicht: Die Auswahl **„Alle“** in der Aktivitäten-Leiste entfällt –
  es ist immer genau eine Aktivität aktiv (Standard: erste Aktivität,
  die letzte Wahl wird gemerkt). Im Kleiderschrank bleibt der Filter „Alle“.
- **Unterwäsche** hat keine Temperatur- und Niederschlagswerte mehr,
  **Socken** keine Niederschlagswerte; die Felder werden im Formular
  ausgeblendet und vorhandene Werte beim Laden entfernt
- Unterwäsche wird ohne Wetterbezug ausgewählt

### Neu
- Wird ein **Pullover** vorgeschlagen, zählt die **Temperatur des T-Shirts** nicht
- Wird die **Jacke wegen Niederschlags** (nicht wegen Kälte) vorgeschlagen,
  zählt der **Niederschlag von T-Shirt und Pullover** nicht
- Ignorierte Werte werden im Outfit ausgegraut und mit Begründung
  („zählt heute nicht – Pullover darüber“) angezeigt
- **Versionsnummer in den Einstellungen** (neben der Überschrift und im Bereich
  „Datenspeicher & Sicherung“)
- `/api/meta` liefert je Typ, ob es Temperatur-/Niederschlagswerte gibt;
  `/api/outfit` liefert je Teil die ignorierten Werte (`ignored`)

## [1.5.0] – 2026-10-03

### Neu
- **Oberteil ist eine Kategorie** mit den Untertypen T-Shirt, Pullover und Jacke
- Outfit-Zusammenstellung in Schichten: T-Shirt, darüber Pullover, außen Jacke
- Einstellungen → **Regeln für Oberteile**:
  - Grenztemperatur, ab der kein Pullover mehr vorgeschlagen wird (Standard 16 °C)
  - Grenztemperatur, ab der keine Jacke mehr vorgeschlagen wird (Standard 12 °C),
    außer die Niederschlagsvorhersage erreicht die per Balken gewählte Stufe
    (Standard „Mäßig“)
- Hinweiszeile im Outfit-Reiter: Tageswerte mit Stufe und warum Pullover/Jacke
  vorgeschlagen werden oder nicht
- Kleiderschrank-Filter für T-Shirt, Pullover und Jacke
- API `POST /api/settings/rules`

### Geändert
- Temperatur- und Niederschlags-Balken zeigen nur noch **6 Stufen**
  (Frost … Heiß bzw. Trocken … Unwetter), heutige Stufe markiert
- Eingabe im Formular über 6-stufige Schieberegler „von/bis“
- Wetterpassung rechnet in Stufen (gleich 100 %, ±1 Stufe 55 %, ±2 Stufen 20 %)
- Farbharmonie berücksichtigt alle sichtbaren Schichten

### Datenübernahme
- Typ „Jacke“ (bis v1.4.0) → Oberteil · Jacke; übrige Oberteile → Oberteil · T-Shirt
- °C-/mm-Bereiche werden in Stufen umgerechnet; die Stufengrenzen werden
  zusätzlich als `temp_min/max` bzw. `rain_min/max` gespeichert
- `settings.json` Schema 2 mit Abschnitt `rules`

## [1.4.0] – 2026-10-03

### Geändert
- Windows-EXE und macOS-App speichern alle Daten jetzt im Ordner `daten/`
  **direkt neben** der EXE bzw. der `.app` – wie die Python- und Router-Version
- macOS: Programmordner ist der Ordner, in dem die `.app` liegt (nicht das
  Innere des Bundles)
- Hinweistext in „Datenspeicher & Sicherung“ nennt den neuen Ablageort

### Neu
- Daten aus den v1.3.0-Orten (`%LOCALAPPDATA%\Outfit-Dashboard\daten`,
  `~/Library/Application Support/Outfit-Dashboard/daten`) werden beim ersten
  Start automatisch nach `daten/` neben dem Programm übernommen
- Ist der Ordner neben dem Programm nicht beschreibbar oder startet macOS die
  App isoliert (App Translocation), wird ersatzweise ein Benutzerordner
  verwendet und in den Einstellungen ein Hinweis mit Abhilfe angezeigt

## [1.3.0] – 2026-10-03

### Neu
- Windows-EXE und macOS-App per PyInstaller (`packaging/outfit_dashboard.spec`)
- GitHub-Actions-Workflow `.github/workflows/build-release.yml`:
  baut Windows-EXE, macOS-App und Router-Paket, startet jedes Programm
  probeweise und erstellt automatisch ein Release, sobald die Version in
  `version.py` neu ist (Release-Text aus `CHANGELOG.md`)
- Icon wird beim Build per `packaging/make_icon.py` erzeugt (keine Binärdateien im Repo)
- Desktop-Start: Browser öffnet sich automatisch, Netzwerkadresse fürs iPhone
  wird angezeigt
- Läuft das Dashboard schon, öffnet ein zweiter Start nur den Browser;
  belegter Port → automatisch nächster freier Port (bis +10)
- Einstellungen: „Programm beenden“ für die Desktop-Version (nur vom eigenen Rechner)
- Protokolldatei `daten/outfit.log`

### Geändert
- Vorlagen/statische Dateien werden aus dem Programm-Bundle geladen
- Datenordner der Desktop-Versionen: Windows `daten\` neben der EXE
  (Rückfall `%LOCALAPPDATA%`), macOS `~/Library/Application Support/Outfit-Dashboard/daten`
- Wetterabruf nutzt das CA-Bündel von `certifi` (neue Abhängigkeit),
  behebt Zertifikatsfehler der Mac-App
- `install.sh` installiert auf dem Router zusätzlich `certifi`
- Neue Konfigurationsoption `open_browser`, Umgebungsvariablen `OUTFIT_PORT`
  und `OUTFIT_OPEN_BROWSER`

## [1.2.0] – 2026-10-03

### Geändert
- Alles in einem Ordner: Programm und Daten liegen gemeinsam in
  `/root/Outfit-Dashboard` (GL.iNet Slate 7, `root@GL-BE3600:~#`)
- Nutzerdaten im Unterordner `daten/` (`config.json`, `settings.json`,
  `clothes.json`, `images/`, `backups/`) – flacher Aufbau ohne `data/`-Unterordner
- Standard für `data_dir` ist jetzt `.` (relativ zu `daten/`)
- `install.sh`/`update.sh` ersetzen die Programmdateien einzeln und lassen
  `daten/` unangetastet; Installation auch direkt aus dem Zielordner möglich
- Init-Skript startet aus `/root/Outfit-Dashboard` mit `OUTFIT_HOME=…/daten`
- `/etc/sysupgrade.conf`: alte Einträge (`/opt`, `/srv`) werden durch
  `/root/Outfit-Dashboard/` ersetzt

### Neu
- Automatische Übernahme von Daten aus v1.0.0 (`data/` im Programmordner) und
  v1.1.0 (`/srv/outfit-dashboard`, `~/.outfit-dashboard`) nach `daten/`
- `install.sh` entfernt den alten Programmordner `/opt/outfit-dashboard` und
  weist auf nicht mehr benötigte Altdaten hin

## [1.1.0] – 2026-10-03

### Neu
- Nutzerdaten liegen getrennt vom Programm (OpenWrt: `/srv/outfit-dashboard`,
  sonst `~/.outfit-dashboard`, einstellbar über `OUTFIT_HOME`) – Aktivitäten,
  Standort, Kleidungsstücke, Fotos, Labels und Konfiguration überstehen Updates
- Automatische Übernahme von `config.json` und `data/` aus v1.0.0
- Einstellungen: Bereich „Datenspeicher & Sicherung“ mit Speicherinfo,
  ZIP-Sicherung zum Herunterladen und Wiederherstellung
- Automatische Sicherung vor jeder Wiederherstellung (letzte 3 bleiben)
- `openwrt/update.sh`: tauscht nur die Programmdateien aus, sichert vorher die
  JSON-Daten
- Installationsskript für GL.iNet Slate 7: erkennt opkg/apk, installiert Pakete
  nur bei Bedarf, prüft freien Speicher, trägt Pfade in `/etc/sysupgrade.conf` ein

### Geändert
- Schema-Nummer in `settings.json`/`clothes.json`; fehlende Felder werden beim
  Laden ergänzt
- Programmordner wird bei Installation/Update atomar ersetzt
- Wiederherstellung schreibt Uploads auf den Datenträger statt in den RAM
- Neue Konfigurationsoption `max_backup_mb`

## [1.0.0] – 2026-10-03

### Neu
- Flask-Webserver mit Nutzermodus, Einstellungen und Nutzungsbedingungen
- Tageswetter über Open-Meteo (aktuelle Temperatur, Höchst-/Tiefstwert,
  Niederschlagsmenge und -wahrscheinlichkeit), Standort per Ortssuche oder Koordinaten
- Aktivitäten frei definierbar
- Kleidungsstücke mit Foto, Typ, Farbe, Aktivitäten, Temperatur- und Niederschlagsbereich
- Balkendiagramme für Temperatur und Niederschlag (Einstellungen und Kleiderschrank)
- Automatische Outfit-Zusammenstellung (Oberteil, Hose, Unterwäsche, Schuh-Empfehlung)
  nach Wetterpassung, Farbharmonie und gewählter Aktivität, bei jedem Neuladen neu
- iPhone-optimiertes Lattice-Design
- OpenWrt-Installationsskript und procd-Dienst für GL.iNet-Router
