#!/bin/sh
# Outfit-Dashboard – Installation UND Update auf dem GL.iNet Slate 7 (GL-BE3600)
#
# Alles liegt in EINEM Ordner:
#
#   /root/Outfit-Dashboard/
#   ├── app.py, outfit.py, weather.py, …, templates/, static/, openwrt/   Programm
#   └── daten/                                                            Nutzerdaten
#       ├── config.json, settings.json, clothes.json
#       ├── images/          Fotos
#       └── backups/         Sicherungen
#
# Programmdateien werden bei jedem Update ersetzt, "daten/" bleibt immer erhalten.
#
# Aufruf – entweder direkt im Zielordner:
#     cd /root/Outfit-Dashboard && sh openwrt/install.sh
# oder aus einem neuen Projektordner heraus (Update):
#     cd /tmp/Outfit-Dashboard && sh openwrt/install.sh
set -e

APP_DIR="/root/Outfit-Dashboard"
DATA_DIR="$APP_DIR/daten"
SERVICE="outfit-dashboard"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROGRAM_FILES="app.py outfit.py weather.py storage.py version.py requirements.txt
               config.example.json README.md CHANGELOG.md .gitignore templates static openwrt"

say() { echo "==> $*"; }
same_dir() { [ "$(cd "$1" 2>/dev/null && pwd -P)" = "$(cd "$2" 2>/dev/null && pwd -P)" ]; }

[ -f "$SRC_DIR/app.py" ] || { echo "app.py nicht gefunden – bitte aus dem Projektordner starten."; exit 1; }
NEW_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$SRC_DIR/version.py")
OLD_VERSION=""
for v in "$APP_DIR/version.py" /opt/outfit-dashboard/version.py; do
	if [ -z "$OLD_VERSION" ] && [ -f "$v" ] && ! same_dir "$(dirname "$v")" "$SRC_DIR"; then
		OLD_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$v")
	fi
done
if [ -n "$OLD_VERSION" ]; then say "Update v$OLD_VERSION -> v$NEW_VERSION"; else say "Installation v$NEW_VERSION"; fi

# --- 1. Pakete (nur falls noch nicht vorhanden) ----------------------------
if ! command -v python3 >/dev/null 2>&1 || ! command -v pip3 >/dev/null 2>&1; then
	if command -v opkg >/dev/null 2>&1; then
		PKG_UPDATE="opkg update"; PKG_ADD="opkg install"
	elif command -v apk >/dev/null 2>&1; then
		PKG_UPDATE="apk update"; PKG_ADD="apk add"
	else
		echo "Kein Paketmanager (opkg/apk) gefunden."; exit 1
	fi
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
if [ -x "/etc/init.d/$SERVICE" ]; then "/etc/init.d/$SERVICE" stop >/dev/null 2>&1 || true; fi

# --- 3. Datenordner anlegen und Altbestände übernehmen --------------------
mkdir -p "$DATA_DIR"
has_data() { [ -f "$1/clothes.json" ] || [ -f "$1/settings.json" ]; }
if ! has_data "$DATA_DIR"; then
	for OLD in /srv/outfit-dashboard/data /opt/outfit-dashboard/data; do
		if has_data "$OLD"; then
			say "Daten aus $OLD übernehmen"
			cp -a "$OLD/." "$DATA_DIR/"
			OLD_CFG="$(dirname "$OLD")/config.json"
			if [ -f "$OLD_CFG" ] && [ ! -f "$DATA_DIR/config.json" ]; then
				sed 's/"data_dir"[^,}]*/"data_dir": "."/' "$OLD_CFG" > "$DATA_DIR/config.json"
			fi
			MIGRATED_FROM="$OLD"
			break
		fi
	done
fi
[ -f "$DATA_DIR/config.json" ] || cp "$SRC_DIR/config.example.json" "$DATA_DIR/config.json"

if has_data "$DATA_DIR"; then
	mkdir -p "$DATA_DIR/backups"
	STAMP=$(date +%Y%m%d-%H%M%S)
	# nur die kleinen JSON-Dateien – Fotos werden vom Update nie verändert
	( cd "$DATA_DIR" && tar -czf "backups/vor-update-$STAMP.tar.gz" ./*.json ) 2>/dev/null || true
	ls -1t "$DATA_DIR/backups"/vor-update-*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
	say "Sicherung: daten/backups/vor-update-$STAMP.tar.gz"
fi

# --- 4. Programmdateien ersetzen – daten/ wird NICHT angefasst ------------
if same_dir "$SRC_DIR" "$APP_DIR"; then
	say "Programm liegt bereits in $APP_DIR"
else
	say "Programmdateien nach $APP_DIR schreiben"
	mkdir -p "$APP_DIR"
	for f in $PROGRAM_FILES; do
		[ -e "$SRC_DIR/$f" ] || continue
		rm -rf "$APP_DIR/$f.neu"
		cp -a "$SRC_DIR/$f" "$APP_DIR/$f.neu"
		rm -rf "$APP_DIR/$f"
		mv "$APP_DIR/$f.neu" "$APP_DIR/$f"
	done
fi
find "$APP_DIR" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

# --- 5. Dienst einrichten -------------------------------------------------
cp "$APP_DIR/openwrt/outfit-dashboard.init" "/etc/init.d/$SERVICE"
chmod +x "/etc/init.d/$SERVICE"
"/etc/init.d/$SERVICE" enable

# --- 6. bei Firmware-Updates ("Einstellungen behalten") mitsichern --------
if [ -f /etc/sysupgrade.conf ]; then
	# Einträge älterer Versionen entfernen
	sed -i '\#^/srv/outfit-dashboard/$#d; \#^/opt/outfit-dashboard/$#d' /etc/sysupgrade.conf
fi
for p in "$APP_DIR/" "/etc/init.d/$SERVICE"; do
	grep -qxF "$p" /etc/sysupgrade.conf 2>/dev/null || echo "$p" >> /etc/sysupgrade.conf
done

# --- 7. alte Programmordner früherer Versionen entfernen ------------------
# (Daten wurden oben bereits übernommen; /srv/outfit-dashboard bleibt als Reserve liegen)
if [ -d /opt/outfit-dashboard ] && ! same_dir /opt/outfit-dashboard "$APP_DIR"; then
	say "Alten Programmordner /opt/outfit-dashboard entfernen"
	rm -rf /opt/outfit-dashboard
fi

"/etc/init.d/$SERVICE" start

PORT=$(sed -n 's/.*"port"[^0-9]*\([0-9]*\).*/\1/p' "$DATA_DIR/config.json" | head -n1)
IP=$(uci -q get network.lan.ipaddr || echo "<router-ip>")
echo ""
echo "Fertig – Outfit-Dashboard v$NEW_VERSION"
echo "  Webseite:  http://$IP:${PORT:-8095}"
echo "  Ordner:    $APP_DIR"
echo "  Daten:     $DATA_DIR  (bleibt bei Updates erhalten)"
echo "  Log:       logread -e python3 -f"
if [ -n "$MIGRATED_FROM" ] && [ -d /srv/outfit-dashboard ]; then
	echo ""
	echo "Hinweis: Die alten Daten in /srv/outfit-dashboard werden nicht mehr benötigt."
	echo "         Nach Kontrolle der Webseite löschen mit:  rm -rf /srv/outfit-dashboard"
fi
