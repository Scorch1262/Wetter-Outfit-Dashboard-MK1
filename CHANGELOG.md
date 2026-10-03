# Changelog

Alle Änderungen am Outfit-Dashboard-MK1. Versionierung nach Semantic Versioning.

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
