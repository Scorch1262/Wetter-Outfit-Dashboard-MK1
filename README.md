# Outfit-Dashboard-MK1

Lokales Web-Dashboard, das aus dem eigenen Kleiderschrank bei jedem Aufruf ein
**farblich passendes Outfit zum heutigen Wetter** zusammenstellt.
Gestaltet im dunklen Lattice-Design der übrigen Dashboards, optimiert für das
iPhone und gedacht für den Dauerbetrieb auf einem **GL.iNet-Router (OpenWrt)**.

Aktuelle Version: **v1.0.0**

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
│   ├── install.sh          Installationsskript für GL.iNet / OpenWrt
│   └── outfit-dashboard.init  procd-Dienst (Autostart)
├── CHANGELOG.md
└── README.md
```

Laufzeitdaten (nicht im Repo, siehe `.gitignore`):

```
config.json                 wird beim ersten Start automatisch angelegt
data/settings.json          Standort und Aktivitäten
data/clothes.json           Kleidungsstücke
data/images/                Fotos
```

---

## Installation auf dem PC / Raspberry Pi (Test)

```bash
pip install -r requirements.txt
python3 app.py
```

Aufruf: `http://<IP-des-Rechners>:8095`

---

## Installation auf einem GL.iNet-Router (OpenWrt)

Voraussetzungen: SSH-Zugang (`ssh root@192.168.8.1`), Internetverbindung des
Routers, ca. **25–30 MB** freier Speicher für Python + Flask.

### Automatisch

1. Projektordner auf den Router kopieren, z. B. vom PC aus:
   `scp -r outfit-dashboard-mk1 root@192.168.8.1:/tmp/`
2. Auf dem Router:
   `cd /tmp/outfit-dashboard-mk1`
   `sh openwrt/install.sh`
3. Aufruf im Browser: `http://192.168.8.1:8095`

Das Skript installiert `python3`, `python3-pip`, die CA-Zertifikate und Flask,
kopiert das Programm nach `/opt/outfit-dashboard` und richtet den Dienst mit
Autostart ein.

### Manuell

```sh
opkg update
opkg install python3 python3-pip ca-bundle ca-certificates
pip3 install --no-cache-dir flask
mkdir -p /opt/outfit-dashboard
cp -r app.py outfit.py weather.py storage.py version.py requirements.txt templates static /opt/outfit-dashboard/
cp config.example.json /opt/outfit-dashboard/config.json
cp openwrt/outfit-dashboard.init /etc/init.d/outfit-dashboard
chmod +x /etc/init.d/outfit-dashboard
/etc/init.d/outfit-dashboard enable
/etc/init.d/outfit-dashboard start
```

### Dienst bedienen

```sh
/etc/init.d/outfit-dashboard restart
/etc/init.d/outfit-dashboard stop
logread -e python3 -f        # Log live ansehen
```

### Speicherplatz sparen

Fotos werden im Browser auf max. 900 px (JPEG) verkleinert, ein Stück belegt
typischerweise 60–150 KB. Bei wenig internem Speicher den Datenordner auf einen
USB-Stick legen, z. B. in `/opt/outfit-dashboard/config.json`:

```json
"data_dir": "/mnt/sda1/outfit-data"
```

---

## Konfiguration (`config.json`)

| Schlüssel               | Standard   | Bedeutung                                              |
|-------------------------|------------|--------------------------------------------------------|
| `host`                  | `0.0.0.0`  | Netzwerkschnittstelle (alle)                           |
| `port`                  | `8095`     | Web-Port (nicht 80/443, die nutzt die GL.iNet-Oberfläche) |
| `data_dir`              | `data`     | Datenordner (relativ zum Programm oder absolut)        |
| `max_upload_mb`         | `12`       | maximale Upload-Größe                                  |
| `weather_cache_minutes` | `15`       | wie lange Wetterdaten zwischengespeichert werden       |
| `weather_verify_ssl`    | `true`     | TLS-Zertifikate prüfen (nur bei Zertifikatsproblemen auf `false`) |

Ein anderer Pfad zur Konfigurationsdatei kann über die Umgebungsvariable
`OUTFIT_CONFIG` gesetzt werden.

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

---

## Hinweise

- Kein Passwortschutz – jede Person im LAN kann Einstellungen ändern.
  Nicht per Portweiterleitung ins Internet freigeben.
- Wetterdaten: [Open-Meteo.com](https://open-meteo.com/), Lizenz CC BY 4.0.
- Datensicherung: Ordner `data/` kopieren.

## Versionierung

Semantic Versioning (`MAJOR.MINOR.PATCH`), gepflegt in `version.py` und im
`CHANGELOG.md`; die Version wird im Fuß der Webseite angezeigt.
