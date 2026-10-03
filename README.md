# Outfit-Dashboard-MK1

Lokales Web-Dashboard, das aus dem eigenen Kleiderschrank bei jedem Aufruf ein
**farblich passendes Outfit zum heutigen Wetter** zusammenstellt.
Gestaltet im dunklen Lattice-Design der übrigen Dashboards, optimiert für das
iPhone und gedacht für den Dauerbetrieb auf einem **GL.iNet Slate 7** (OpenWrt).

Aktuelle Version: **v1.1.0**

> **Update-sicher:** Programm und Nutzerdaten liegen in getrennten Ordnern.
> Bei einem Update werden nur die Programmdateien ausgetauscht – Aktivitäten,
> Standort, Kleidungsstücke, Fotos, Labels und Konfiguration bleiben erhalten.

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

## Projektstruktur

```
outfit-dashboard-mk1/
├── app.py                  Flask-Server, Seiten und REST-API
├── outfit.py               Typen, Farbpalette, Bewertungs- und Auswahllogik
├── weather.py              Open-Meteo-Abfrage und Ortssuche (nur Standardbibliothek)
├── storage.py              threadsicherer JSON-Speicher mit atomarem Schreiben
├── version.py              Versionsnummer
├── requirements.txt        einzige Abhängigkeit: Flask
├── config.example.json     Vorlage für config.json
├── templates/
│   ├── base.html
│   ├── index.html          Nutzermodus
│   ├── settings.html       Einstellungen
│   └── terms.html          Nutzungsbedingungen
├── static/
│   ├── style.css           Lattice-Design, iPhone-optimiert
│   ├── common.js           Hilfsfunktionen, Balkendiagramme, Wetter-Icons
│   ├── user.js             Nutzermodus
│   ├── settings.js         Einstellungen
│   └── icon.svg
├── openwrt/
│   ├── install.sh          Installation und Update (GL.iNet Slate 7 / OpenWrt)
│   ├── update.sh           Update – tauscht nur die Programmdateien aus
│   └── outfit-dashboard.init  procd-Dienst (Autostart)
├── CHANGELOG.md
└── README.md
```

---

## Datenablage – getrennt vom Programm

| Ordner                     | Inhalt                                   | bei Update |
|----------------------------|------------------------------------------|------------|
| `/opt/outfit-dashboard`    | Programmdateien                          | wird ersetzt |
| `/srv/outfit-dashboard`    | Nutzerdaten (siehe unten)                | **bleibt erhalten** |

```
/srv/outfit-dashboard/
├── config.json             Port, Upload-Grenzen, Wetter-Cache …
├── data/
│   ├── settings.json       Standort und Aktivitäten
│   ├── clothes.json        Kleidungsstücke mit allen Labels
│   └── images/             Fotos
└── backups/                automatische Sicherungen (vor Update / Wiederherstellung)
```

Der Datenordner wird automatisch gewählt:

| Umgebung              | Datenordner               |
|-----------------------|---------------------------|
| OpenWrt / GL.iNet     | `/srv/outfit-dashboard`   |
| PC / Raspberry Pi     | `~/.outfit-dashboard`     |
| frei wählbar          | Umgebungsvariable `OUTFIT_HOME` |

**Übernahme aus v1.0.0:** Lagen `config.json` und `data/` noch im
Programmordner, werden sie beim ersten Start von v1.1.0 (bzw. durch
`install.sh`) automatisch in den Datenordner übernommen.

**Datenformat:** Die Dateien tragen eine Schema-Nummer; fehlende Felder werden
beim Laden ergänzt, damit ältere Datenstände auch mit neuen Programmversionen
funktionieren.

---

## Installation auf dem PC / Raspberry Pi (Test)

```bash
pip install -r requirements.txt
python3 app.py
```

Daten landen dort in `~/.outfit-dashboard`.

Aufruf: `http://<IP-des-Rechners>:8095`

---

## Installation auf dem GL.iNet Slate 7

Voraussetzungen: SSH-Zugang (`ssh root@192.168.8.1`), Internetverbindung des
Routers, ca. **30–40 MB** freier Speicher auf `/overlay` für Python + Flask.
Den freien Speicher zeigt `df -h /overlay`.

### Erstinstallation

1. Projektordner vom PC auf den Router kopieren:
   `scp -r outfit-dashboard-mk1 root@192.168.8.1:/tmp/`
   (bei neueren OpenSSH-Versionen ggf. `scp -O -r …`)
2. Auf dem Router:
   `cd /tmp/outfit-dashboard-mk1`
   `sh openwrt/install.sh`
3. Aufruf im Browser: `http://192.168.8.1:8095`

Das Skript

- installiert `python3`, `python3-pip`, CA-Zertifikate (opkg oder apk) und Flask –
  nur falls noch nicht vorhanden,
- legt das Programm in `/opt/outfit-dashboard` und die Daten in
  `/srv/outfit-dashboard` an,
- richtet den Dienst mit Autostart ein,
- trägt Programm, Daten und Dienst in `/etc/sysupgrade.conf` ein, damit sie bei
  einem **Firmware-Update mit „Einstellungen behalten“** mitgesichert werden.

### Update auf eine neue Version

1. Neuen Projektordner nach `/tmp/` auf den Router kopieren (wie oben)
2. `cd /tmp/outfit-dashboard-mk1`
3. `sh openwrt/update.sh`

Dabei passiert:

- Dienst anhalten
- kleine Sicherung von `config.json`, `settings.json`, `clothes.json` nach
  `/srv/outfit-dashboard/backups/vor-update-<Datum>.tar.gz` (die letzten 3 bleiben)
- `/opt/outfit-dashboard` wird komplett ersetzt
- Dienst starten

`/srv/outfit-dashboard` wird dabei **nie** verändert oder gelöscht.

### Nach einem Firmware-Update des Routers

Mit „Einstellungen behalten“ bleiben Programm und Daten erhalten, die
Python-Pakete aber nicht. Dann einfach erneut `sh openwrt/install.sh` aus dem
Projektordner ausführen – Daten bleiben unberührt.
Zusätzlich empfiehlt sich vorher eine **Sicherung über die Einstellungsseite**.

### Dienst bedienen

```sh
/etc/init.d/outfit-dashboard restart
/etc/init.d/outfit-dashboard stop
logread -e python3 -f        # Log live ansehen
```

### Speicherplatz sparen

Fotos werden im Browser auf max. 900 px (JPEG) verkleinert, ein Stück belegt
typischerweise 60–150 KB. Soll der Datenordner auf einen USB-Stick, in
`/etc/init.d/outfit-dashboard` die Zeile `HOME_DIR=` anpassen, z. B.
`HOME_DIR="/mnt/sda1/outfit-dashboard"`, vorhandene Daten dorthin kopieren und
den Dienst neu starten.

---

## Konfiguration (`config.json`)

| Schlüssel               | Standard   | Bedeutung                                              |
|-------------------------|------------|--------------------------------------------------------|
| `host`                  | `0.0.0.0`  | Netzwerkschnittstelle (alle)                           |
| `port`                  | `8095`     | Web-Port (nicht 80/443, die nutzt die GL.iNet-Oberfläche) |
| `data_dir`              | `data`     | Datenordner (relativ zum Programm oder absolut)        |
| `max_upload_mb`         | `12`       | maximale Größe eines Fotos                             |
| `max_backup_mb`         | `300`      | maximale Größe einer einzuspielenden Sicherung         |
| `weather_cache_minutes` | `15`       | wie lange Wetterdaten zwischengespeichert werden       |
| `weather_verify_ssl`    | `true`     | TLS-Zertifikate prüfen (nur bei Zertifikatsproblemen auf `false`) |

Die Datei liegt im Datenordner (`/srv/outfit-dashboard/config.json`).
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

---

## Hinweise

- Kein Passwortschutz – jede Person im LAN kann Einstellungen ändern.
  Nicht per Portweiterleitung ins Internet freigeben.
- Wetterdaten: [Open-Meteo.com](https://open-meteo.com/), Lizenz CC BY 4.0.
- Datensicherung: in den Einstellungen „Sicherung herunterladen“ oder den
  Ordner `/srv/outfit-dashboard` kopieren.

## Versionierung

Semantic Versioning (`MAJOR.MINOR.PATCH`), gepflegt in `version.py` und im
`CHANGELOG.md`; die Version wird im Fuß der Webseite angezeigt.
