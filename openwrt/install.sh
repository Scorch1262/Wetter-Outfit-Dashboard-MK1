#!/bin/sh
# Outfit-Dashboard-MK1 – Installation UND Update auf GL.iNet Slate 7 (OpenWrt)
#
# Aufruf im entpackten Projektordner:   sh openwrt/install.sh
#
# Aufteilung:
#   /opt/outfit-dashboard        Programmdateien   -> werden bei jedem Update ersetzt
#   /srv/outfit-dashboard        Nutzerdaten       -> bleiben IMMER erhalten
#        ├── config.json
#        ├── data/settings.json   (Standort, Aktivitäten)
#        ├── data/clothes.json    (Kleidungsstücke + Labels)
#        ├── data/images/         (Fotos)
#        └── backups/             (automatische Sicherungen)
set -e

APP_DIR="/opt/outfit-dashboard"
HOME_DIR="/srv/outfit-dashboard"
SERVICE="outfit-dashboard"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROGRAM_FILES="app.py outfit.py weather.py storage.py version.py requirements.txt templates static"

say() { echo "==> $*"; }

[ -f "$SRC_DIR/app.py" ] || { echo "app.py nicht gefunden – bitte aus dem Projektordner starten."; exit 1; }
NEW_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$SRC_DIR/version.py")
OLD_VERSION=""
[ -f "$APP_DIR/version.py" ] && OLD_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$APP_DIR/version.py")
if [ -n "$OLD_VERSION" ]; then
	say "Update v$OLD_VERSION -> v$NEW_VERSION"
else
	say "Neuinstallation v$NEW_VERSION"
fi

# --- 1. Pakete (nur falls noch nicht vorhanden) ---------------------------
if command -v opkg >/dev/null 2>&1; then
	PKG_UPDATE="opkg update"; PKG_ADD="opkg install"
elif command -v apk >/dev/null 2>&1; then
	PKG_UPDATE="apk update"; PKG_ADD="apk add"
else
	echo "Kein Paketmanager (opkg/apk) gefunden."; exit 1
fi

if ! command -v python3 >/dev/null 2>&1 || ! command -v pip3 >/dev/null 2>&1; then
	FREE_KB=$(df -k /overlay 2>/dev/null | awk 'NR==2 {print $4}')
	if [ -n "$FREE_KB" ] && [ "$FREE_KB" -lt 40000 ]; then
		echo "WARNUNG: nur $((FREE_KB / 1024)) MB frei auf /overlay – Python + Flask brauchen ca. 30 MB."
	fi
	say "Pakete installieren (python3, pip, CA-Zertifikate)"
	$PKG_UPDATE
	$PKG_ADD python3 python3-pip ca-bundle ca-certificates
fi

if ! python3 -c "import flask" >/dev/null 2>&1; then
	say "Flask installieren"
	pip3 install --no-cache-dir -r "$SRC_DIR/requirements.txt"
fi

# --- 2. Dienst anhalten ---------------------------------------------------
[ -x "/etc/init.d/$SERVICE" ] && "/etc/init.d/$SERVICE" stop >/dev/null 2>&1 || true

# --- 3. Nutzerdaten sichern / aus v1.0.0 übernehmen -----------------------
mkdir -p "$HOME_DIR"
if [ -f "$APP_DIR/data/clothes.json" ] || [ -f "$APP_DIR/data/settings.json" ]; then
	if [ ! -f "$HOME_DIR/data/clothes.json" ] && [ ! -f "$HOME_DIR/data/settings.json" ]; then
		say "Alte Daten aus $APP_DIR/data nach $HOME_DIR/data übernehmen"
		mkdir -p "$HOME_DIR/data"
		cp -a "$APP_DIR/data/." "$HOME_DIR/data/"
	fi
fi
if [ -f "$APP_DIR/config.json" ] && [ ! -f "$HOME_DIR/config.json" ]; then
	say "Alte config.json übernehmen"
	cp -a "$APP_DIR/config.json" "$HOME_DIR/config.json"
fi
if [ ! -f "$HOME_DIR/config.json" ]; then
	cp "$SRC_DIR/config.example.json" "$HOME_DIR/config.json"
fi
if [ -f "$HOME_DIR/data/clothes.json" ]; then
	mkdir -p "$HOME_DIR/backups"
	STAMP=$(date +%Y%m%d-%H%M%S)
	# nur die kleinen JSON-Dateien – Fotos werden vom Update nie verändert
	( cd "$HOME_DIR" && tar -czf "backups/vor-update-$STAMP.tar.gz" config.json data/*.json ) 2>/dev/null || true
	# nur die letzten 3 Update-Sicherungen behalten
	ls -1t "$HOME_DIR/backups"/vor-update-*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
	say "Datensicherung: $HOME_DIR/backups/vor-update-$STAMP.tar.gz"
fi

# --- 4. Dienst einrichten -------------------------------------------------
cp "$SRC_DIR/openwrt/outfit-dashboard.init" "/etc/init.d/$SERVICE"
chmod +x "/etc/init.d/$SERVICE"
"/etc/init.d/$SERVICE" enable

# --- 5. Programmdateien austauschen (Daten werden nicht angefasst) --------
say "Programmdateien nach $APP_DIR schreiben"
rm -rf "$APP_DIR.new"
mkdir -p "$APP_DIR.new"
for f in $PROGRAM_FILES; do
	cp -a "$SRC_DIR/$f" "$APP_DIR.new/"
done
cp -a "$SRC_DIR/openwrt" "$APP_DIR.new/"
cp -a "$SRC_DIR/config.example.json" "$SRC_DIR/README.md" "$SRC_DIR/CHANGELOG.md" "$APP_DIR.new/" 2>/dev/null || true
rm -rf "$APP_DIR.old"
[ -d "$APP_DIR" ] && mv "$APP_DIR" "$APP_DIR.old"
mv "$APP_DIR.new" "$APP_DIR"
rm -rf "$APP_DIR.old"

# --- 6. bei Firmware-Updates ("Einstellungen behalten") mitsichern --------
for p in "$HOME_DIR/" "$APP_DIR/" "/etc/init.d/$SERVICE"; do
	grep -qxF "$p" /etc/sysupgrade.conf 2>/dev/null || echo "$p" >> /etc/sysupgrade.conf
done

"/etc/init.d/$SERVICE" start

PORT=$(sed -n 's/.*"port"[^0-9]*\([0-9]*\).*/\1/p' "$HOME_DIR/config.json" | head -n1)
IP=$(uci -q get network.lan.ipaddr || echo "<router-ip>")
echo ""
echo "Fertig – Outfit-Dashboard v$NEW_VERSION"
echo "  Webseite:   http://$IP:${PORT:-8095}"
echo "  Programm:   $APP_DIR"
echo "  Daten:      $HOME_DIR  (bleibt bei Updates erhalten)"
echo "  Log:        logread -e python3 -f"
