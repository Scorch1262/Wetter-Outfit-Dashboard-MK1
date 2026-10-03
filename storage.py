"""Einfacher, threadsicherer JSON-Speicher mit atomarem Schreiben.

Bewusst ohne Datenbank, damit das Programm auch auf Routern mit wenig
Speicher (GL.iNet / OpenWrt) ohne Zusatzpakete läuft.
"""

import copy
import json
import os
import threading


class JsonStore:
    def __init__(self, path, default):
        self.path = path
        self.default = default
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not os.path.exists(path):
            self.save(copy.deepcopy(default))

    def load(self):
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                data = copy.deepcopy(self.default)
            # fehlende Schlüssel aus dem Default ergänzen
            if isinstance(data, dict) and isinstance(self.default, dict):
                for key, value in self.default.items():
                    data.setdefault(key, copy.deepcopy(value))
            return data

    def save(self, data):
        with self._lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            os.replace(tmp, self.path)

    def update(self, func):
        """Lädt, verändert per func(data) und speichert atomar unter Lock."""
        with self._lock:
            data = self.load()
            result = func(data)
            self.save(data)
            return result
