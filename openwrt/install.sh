#!/bin/sh
# Outfit-Dashboard – Installation UND Update auf GL.iNet-Routern (OpenWrt)
# getestet für: Slate 7 (GL-BE3600), Brume 2 (GL-MT2500 / GL-MT2500A)
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
#
# Optionen (Zugriff von der WAN-Seite, z. B. Brume 2 hinter dem Hauptrouter):
#     --wan             Port auf der WAN-Seite freigeben (nur bei privater WAN-Adresse)
#     --wan-erzwingen   freigeben, auch wenn die WAN-Adresse öffentlich ist (Vorsicht!)
#     --kein-wan        Freigabe wieder entfernen
#   ohne Option: bestehende Freigabe bleibt, bei Erstinstallation wird gefragt.
set -e

# OUTFIT_TEST_ROOT nur für Tests außerhalb eines Routers (Pfade umlenken)
ROOT="${OUTFIT_TEST_ROOT:-}"
APP_DIR="$ROOT/root/Outfit-Dashboard"
DATA_DIR="$APP_DIR/daten"
SERVICE="outfit-dashboard"
FW_RULE="Outfit-Dashboard-WAN"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROGRAM_FILES="app.py outfit.py weather.py storage.py version.py requirements.txt
               config.example.json README.md CHANGELOG.md .gitignore templates static openwrt"

say() { echo "==> $*"; }
warn() { echo "!!  $*"; }
same_dir() { [ "$(cd "$1" 2>/dev/null && pwd -P)" = "$(cd "$2" 2>/dev/null && pwd -P)" ]; }
svc() {
	if [ -n "$ROOT" ]; then echo "    (Test) Dienst $1"; else "/etc/init.d/$SERVICE" "$1"; fi
}
fw_reload() {
	if [ -n "$ROOT" ]; then echo "    (Test) Firewall neu laden"; else /etc/init.d/firewall reload >/dev/null 2>&1 || true; fi
}

# --- Optionen -------------------------------------------------------------
WAN_MODE=""
for arg in "$@"; do
	case "$arg" in
		--wan) WAN_MODE="an" ;;
		--wan-erzwingen) WAN_MODE="erzwingen" ;;
		--kein-wan) WAN_MODE="aus" ;;
		-h|--help) sed -n '2,26p' "$0"; exit 0 ;;
		*) echo "Unbekannte Option: $arg  (siehe --help)"; exit 1 ;;
	esac
done

[ -f "$SRC_DIR/app.py" ] || { echo "app.py nicht gefunden – bitte aus dem Projektordner starten."; exit 1; }
NEW_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$SRC_DIR/version.py")
OLD_VERSION=""
for v in "$APP_DIR/version.py" "$ROOT/opt/outfit-dashboard/version.py"; do
	if [ -z "$OLD_VERSION" ] && [ -f "$v" ] && ! same_dir "$(dirname "$v")" "$SRC_DIR"; then
		OLD_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$v")
	fi
done
MODEL=$(ubus call system board 2>/dev/null | jsonfilter -e '@.model' 2>/dev/null || true)
[ -n "$MODEL" ] && say "Gerät: $MODEL"
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
		warn "nur $((FREE_KB / 1024)) MB frei auf /overlay – Python + Flask brauchen ca. 30 MB."
	fi
	say "Pakete installieren (python3, pip, CA-Zertifikate)"
	$PKG_UPDATE
	$PKG_ADD python3 python3-pip ca-bundle ca-certificates
fi
if ! python3 -c "import sys; sys.exit(sys.version_info < (3, 8))" 2>/dev/null; then
	echo "Python $(python3 -V 2>&1) ist zu alt – benötigt wird mindestens Python 3.8."; exit 1
fi
if ! python3 -c "import flask, certifi" >/dev/null 2>&1; then
	# ältere pip-Versionen (z. B. OpenWrt 21.02 auf dem Brume 2) kennen die
	# fertigen Pakete für ARM64/musl noch nicht – daher zuerst pip aktualisieren
	say "pip aktualisieren"
	python3 -m pip install --no-cache-dir --upgrade pip >/dev/null 2>&1 || warn "pip-Update fehlgeschlagen – versuche es trotzdem"
	say "Flask und certifi installieren"
	python3 -m pip install --no-cache-dir -r "$SRC_DIR/requirements.txt"
fi

# --- 2. Dienst anhalten ---------------------------------------------------
if [ -x "$ROOT/etc/init.d/$SERVICE" ]; then svc stop >/dev/null 2>&1 || true; fi

# --- 3. Datenordner anlegen und Altbestände übernehmen --------------------
mkdir -p "$DATA_DIR"
has_data() { [ -f "$1/clothes.json" ] || [ -f "$1/settings.json" ]; }
MIGRATED_FROM=""
if ! has_data "$DATA_DIR"; then
	for OLD in "$ROOT/srv/outfit-dashboard/data" "$ROOT/opt/outfit-dashboard/data"; do
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
PORT=$(sed -n 's/.*"port"[^0-9]*\([0-9]*\).*/\1/p' "$DATA_DIR/config.json" | head -n1)
PORT="${PORT:-8095}"

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
mkdir -p "$ROOT/etc/init.d"
cp "$APP_DIR/openwrt/outfit-dashboard.init" "$ROOT/etc/init.d/$SERVICE"
chmod +x "$ROOT/etc/init.d/$SERVICE"
svc enable

# --- 6. bei Firmware-Updates ("Einstellungen behalten") mitsichern --------
SYSUP="$ROOT/etc/sysupgrade.conf"
if [ -f "$SYSUP" ]; then
	# Einträge älterer Versionen entfernen
	sed -i '\#^/srv/outfit-dashboard/$#d; \#^/opt/outfit-dashboard/$#d' "$SYSUP"
fi
for p in "/root/Outfit-Dashboard/" "/etc/init.d/$SERVICE"; do
	grep -qxF "$p" "$SYSUP" 2>/dev/null || echo "$p" >> "$SYSUP"
done

# --- 7. alte Programmordner früherer Versionen entfernen ------------------
# (Daten wurden oben bereits übernommen; /srv/outfit-dashboard bleibt als Reserve liegen)
if [ -d "$ROOT/opt/outfit-dashboard" ] && ! same_dir "$ROOT/opt/outfit-dashboard" "$APP_DIR"; then
	say "Alten Programmordner /opt/outfit-dashboard entfernen"
	rm -rf "$ROOT/opt/outfit-dashboard"
fi

# --- 8. Zugriff von der WAN-Seite (z. B. Brume 2 hinter dem Hauptrouter) --
# Der Brume 2 hängt meist mit seinem WAN-Port am Hauptrouter. Geräte im
# Heimnetz (iPhone) liegen dann auf seiner WAN-Seite – dort blockiert die
# Firewall eingehende Verbindungen. Eine Freigabe ist nur sicher, wenn die
# WAN-Adresse privat ist (Heimnetz), nicht wenn sie direkt im Internet liegt.
LAN_IP=$(uci -q get network.lan.ipaddr 2>/dev/null || echo "<router-ip>")
WAN_IP=$(ifstatus wan 2>/dev/null | jsonfilter -e '@["ipv4-address"][0].address' 2>/dev/null || true)
is_private() {
	case "$1" in
		10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[01].*) return 0 ;;
		*) return 1 ;;
	esac
}
fw_rule_ids() { uci -q show firewall 2>/dev/null | sed -n "s/^firewall\.\([^.]*\)\.name='$FW_RULE'$/\1/p"; }
fw_remove() {
	for id in $(fw_rule_ids); do uci -q delete "firewall.$id"; done
	uci commit firewall
}
fw_add() {
	fw_remove
	sec=$(uci add firewall rule)
	uci set "firewall.$sec.name=$FW_RULE"
	uci set "firewall.$sec.src=wan"
	uci set "firewall.$sec.proto=tcp"
	uci set "firewall.$sec.dest_port=$PORT"
	uci set "firewall.$sec.target=ACCEPT"
	uci commit firewall
	fw_reload
}

HAS_RULE=""
[ -n "$(fw_rule_ids)" ] && HAS_RULE=1
if [ -z "$WAN_MODE" ]; then
	if [ -n "$HAS_RULE" ]; then
		WAN_MODE="an"                       # bestehende Freigabe beibehalten (Port ggf. aktualisieren)
	elif [ -t 0 ] && [ -n "$WAN_IP" ] && is_private "$WAN_IP"; then
		echo ""
		echo "Dieser Router hängt mit seinem WAN-Port im Netz $WAN_IP (z. B. hinter dem Hauptrouter)."
		echo "Sollen Geräte aus diesem Netz (z. B. das iPhone im Heim-WLAN) das Dashboard erreichen?"
		printf "Port %s auf der WAN-Seite freigeben? [j/N] " "$PORT"
		read -r ans || ans=""
		case "$ans" in j|J|ja|Ja|y|Y) WAN_MODE="an" ;; *) WAN_MODE="aus" ;; esac
	fi
fi

WAN_OPEN=""
case "$WAN_MODE" in
	an|erzwingen)
		if [ -z "$WAN_IP" ]; then
			warn "WAN hat keine IPv4-Adresse – Freigabe trotzdem eingerichtet."
			fw_add; WAN_OPEN=1
		elif is_private "$WAN_IP" || [ "$WAN_MODE" = "erzwingen" ]; then
			is_private "$WAN_IP" || warn "WAN-Adresse $WAN_IP ist ÖFFENTLICH – das Dashboard ist jetzt aus dem Internet erreichbar!"
			say "Port $PORT auf der WAN-Seite freigeben (Firewall-Regel $FW_RULE)"
			fw_add; WAN_OPEN=1
		else
			warn "WAN-Adresse $WAN_IP ist öffentlich – keine Freigabe eingerichtet,"
			warn "sonst wäre das Dashboard (ohne Passwort) aus dem Internet erreichbar."
			warn "Nur wenn du sicher bist: sh openwrt/install.sh --wan-erzwingen"
			[ -n "$HAS_RULE" ] && fw_remove && fw_reload
		fi
		;;
	aus)
		if [ -n "$HAS_RULE" ]; then
			say "Freigabe auf der WAN-Seite entfernen"
			fw_remove; fw_reload
		fi
		;;
esac

svc start

echo ""
echo "Fertig – Outfit-Dashboard v$NEW_VERSION${MODEL:+ auf $MODEL}"
echo "  Webseite (LAN):  http://$LAN_IP:$PORT"
if [ -n "$WAN_OPEN" ] && [ -n "$WAN_IP" ]; then
	echo "  Webseite (WAN):  http://$WAN_IP:$PORT   ← aus dem Heimnetz vor dem Router"
elif [ -n "$WAN_IP" ] && is_private "$WAN_IP"; then
	echo "  Aus dem Netz $WAN_IP (WAN-Seite) nicht erreichbar – freigeben mit: sh openwrt/install.sh --wan"
fi
echo "  Ordner:          /root/Outfit-Dashboard"
echo "  Daten:           /root/Outfit-Dashboard/daten  (bleibt bei Updates erhalten)"
echo "  Log:             logread -e python3 -f"
if [ -n "$MIGRATED_FROM" ] && [ -d "$ROOT/srv/outfit-dashboard" ]; then
	echo ""
	echo "Hinweis: Die alten Daten in /srv/outfit-dashboard werden nicht mehr benötigt."
	echo "         Nach Kontrolle der Webseite löschen mit:  rm -rf /srv/outfit-dashboard"
fi
