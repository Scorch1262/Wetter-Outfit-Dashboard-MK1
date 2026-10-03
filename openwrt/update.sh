#!/bin/sh
# Update des Outfit-Dashboards: ersetzt nur die Programmdateien in
# /root/Outfit-Dashboard. Der Unterordner daten/ (Aktivitäten, Standort,
# Kleidungsstücke, Labels, Fotos, Konfiguration) bleibt unverändert;
# vorher werden die JSON-Daten automatisch gesichert.
exec sh "$(dirname "$0")/install.sh" "$@"
