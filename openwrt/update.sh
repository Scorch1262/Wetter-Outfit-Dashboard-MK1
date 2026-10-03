#!/bin/sh
# Update des Outfit-Dashboards: tauscht nur die Programmdateien aus.
# Aktivitäten, Standort, Kleidungsstücke, Fotos und Konfiguration in
# /srv/outfit-dashboard bleiben unverändert (vorher wird automatisch gesichert).
exec sh "$(dirname "$0")/install.sh" "$@"
