#!/bin/sh
# Outfit-Dashboard – Fehlersuche auf dem Router (GL.iNet Slate 7 / Brume 2)
# Aufruf:  cd /root/Outfit-Dashboard && sh openwrt/diagnose.sh
# Prüft der Reihe nach: Python/Flask, Dienst, Port, lokale Antwort, Firewall,
# Adressen und Log – und sagt am Ende, woran es vermutlich liegt.

APP_DIR="/root/Outfit-Dashboard"
DATA_DIR="$APP_DIR/daten"
SERVICE="outfit-dashboard"
FW_RULE="Outfit-Dashboard-WAN"
PROBLEMS=0

ok()   { echo "  [ OK ] $*"; }
fehl() { echo "  [FEHL] $*"; PROBLEMS=$((PROBLEMS + 1)); }
info() { echo "  [ .. ] $*"; }
kopf() { echo ""; echo "== $* =="; }

http_get() {
	if command -v wget >/dev/null 2>&1; then wget -q -T 4 -O - "$1" 2>/dev/null
	elif command -v curl >/dev/null 2>&1; then curl -s -m 4 "$1" 2>/dev/null
	else python3 -c "import sys,urllib.request;print(urllib.request.urlopen(sys.argv[1],timeout=4).read().decode())" "$1" 2>/dev/null
	fi
}

kopf "Gerät"
MODEL=$(ubus call system board 2>/dev/null | jsonfilter -e '@.model' 2>/dev/null)
REL=$(ubus call system board 2>/dev/null | jsonfilter -e '@.release.description' 2>/dev/null)
info "${MODEL:-unbekannt} – ${REL:-unbekannte Firmware}"
info "Programmordner: $APP_DIR  (Version: $(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$APP_DIR/version.py" 2>/dev/null))"
[ -f "$APP_DIR/app.py" ] && ok "app.py vorhanden" || fehl "app.py fehlt in $APP_DIR"

kopf "Python und Flask"
if command -v python3 >/dev/null 2>&1; then
	ok "$(python3 -V 2>&1)"
	if python3 -c "import flask, certifi" 2>/tmp/outfit-imp.txt; then
		ok "Flask und certifi lassen sich importieren"
	else
		fehl "Flask/certifi fehlen:  $(tail -n 1 /tmp/outfit-imp.txt)"
		info "Abhilfe:  python3 -m pip install --no-cache-dir --upgrade pip && python3 -m pip install -r $APP_DIR/requirements.txt"
	fi
	rm -f /tmp/outfit-imp.txt
else
	fehl "python3 nicht installiert (opkg update && opkg install python3 python3-pip)"
fi

kopf "Dienst"
if [ -x "/etc/init.d/$SERVICE" ]; then
	ok "Startskript /etc/init.d/$SERVICE vorhanden"
	/etc/init.d/$SERVICE enabled && ok "Autostart aktiv" || fehl "Autostart nicht aktiv (/etc/init.d/$SERVICE enable)"
	if /etc/init.d/$SERVICE status 2>/dev/null | grep -qi running; then
		ok "Dienst läuft"
	else
		fehl "Dienst läuft NICHT (/etc/init.d/$SERVICE start, danach Log prüfen)"
	fi
else
	fehl "Startskript fehlt – bitte  sh openwrt/install.sh  ausführen"
fi
PID=$(ps w 2>/dev/null | grep "[a]pp.py" | awk '{print $1}' | head -n1)
[ -n "$PID" ] && ok "Prozess app.py gefunden (PID $PID)" || fehl "kein Prozess app.py"

kopf "Port"
PORT=$(sed -n 's/.*"port"[^0-9]*\([0-9]*\).*/\1/p' "$DATA_DIR/config.json" 2>/dev/null | head -n1)
PORT="${PORT:-8095}"
info "konfigurierter Port: $PORT"
LISTEN=$(netstat -ltn 2>/dev/null | awk -v p=":$PORT" '$4 ~ p"$" {print $4}' | head -n1)
if [ -n "$LISTEN" ]; then
	ok "Port $PORT wird abgehört ($LISTEN)"
else
	fehl "nichts hört auf Port $PORT"
	REAL=$(netstat -lntp 2>/dev/null | grep python | awk '{print $4}' | head -n1)
	[ -n "$REAL" ] && info "python3 hört stattdessen auf $REAL – Port $PORT war vermutlich belegt, Programm ist ausgewichen"
fi

kopf "Lokale Antwort"
ANTWORT=$(http_get "http://127.0.0.1:$PORT/api/meta")
case "$ANTWORT" in
	*Outfit-Dashboard*) ok "Dashboard antwortet auf 127.0.0.1:$PORT" ;;
	*) fehl "keine Antwort von http://127.0.0.1:$PORT/api/meta" ;;
esac

kopf "Adressen und Firewall"
LAN_IP=$(uci -q get network.lan.ipaddr 2>/dev/null)
WAN_IP=$(ifstatus wan 2>/dev/null | jsonfilter -e '@["ipv4-address"][0].address' 2>/dev/null)
info "LAN-Adresse: ${LAN_IP:-?}   →  http://${LAN_IP:-<lan-ip>}:$PORT   (Geräte am LAN-Port des Routers)"
info "WAN-Adresse: ${WAN_IP:-keine}   →  http://${WAN_IP:-<wan-ip>}:$PORT   (Geräte im Netz VOR dem Router, z. B. iPhone im Heim-WLAN)"
if uci -q show firewall 2>/dev/null | grep -q "name='$FW_RULE'"; then
	ok "Firewall-Regel $FW_RULE vorhanden (Port auf WAN-Seite freigegeben)"
	if iptables -S 2>/dev/null | grep -q "dport $PORT"; then
		ok "Regel ist in der aktiven Firewall angekommen"
	else
		fehl "Regel steht in der Konfiguration, ist aber nicht aktiv – /etc/init.d/firewall restart"
	fi
else
	info "keine WAN-Freigabe eingerichtet – nötig, wenn das Handy im Netz VOR dem Router hängt:  sh openwrt/install.sh --wan"
fi

kopf "Letzte Log-Zeilen"
logread 2>/dev/null | grep -i -E "python|outfit|procd.*$SERVICE" | tail -n 15

kopf "Ergebnis"
if [ "$PROBLEMS" -eq 0 ]; then
	echo "  Auf dem Router ist alles in Ordnung. Kommt das Handy/der PC trotzdem nicht durch,"
	echo "  hängt das Gerät im Netz VOR dem Router → Freigabe:  sh openwrt/install.sh --wan"
	echo "  und die WAN-Adresse (siehe oben) im Browser verwenden."
else
	echo "  $PROBLEMS Problem(e) gefunden – siehe [FEHL]-Zeilen oben."
fi
