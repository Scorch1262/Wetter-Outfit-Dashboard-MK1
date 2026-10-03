#!/bin/sh
# Installiert Outfit-Dashboard-MK1 auf einem GL.iNet-Router (OpenWrt).
# Aufruf im entpackten Projektordner:  sh openwrt/install.sh
set -e

APP_DIR="/opt/outfit-dashboard"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Pakete installieren (python3, pip, CA-Zertifikate)"
opkg update
opkg install python3 python3-pip ca-bundle ca-certificates

echo "==> Flask installieren"
pip3 install --no-cache-dir -r "$SRC_DIR/requirements.txt"

echo "==> Programmdateien nach $APP_DIR kopieren"
mkdir -p "$APP_DIR"
cp -r "$SRC_DIR/app.py" "$SRC_DIR/outfit.py" "$SRC_DIR/weather.py" "$SRC_DIR/storage.py" \
      "$SRC_DIR/version.py" "$SRC_DIR/requirements.txt" "$SRC_DIR/templates" "$SRC_DIR/static" "$APP_DIR/"
if [ ! -f "$APP_DIR/config.json" ]; then
	cp "$SRC_DIR/config.example.json" "$APP_DIR/config.json"
fi

echo "==> Dienst einrichten"
cp "$SRC_DIR/openwrt/outfit-dashboard.init" /etc/init.d/outfit-dashboard
chmod +x /etc/init.d/outfit-dashboard
/etc/init.d/outfit-dashboard enable
/etc/init.d/outfit-dashboard restart

PORT=$(grep -o '"port"[^0-9]*[0-9]*' "$APP_DIR/config.json" | grep -o '[0-9]*$')
IP=$(uci -q get network.lan.ipaddr || echo "<router-ip>")
echo ""
echo "Fertig. Dashboard: http://$IP:${PORT:-8095}"
echo "Log ansehen:       logread -e python3 -f"
