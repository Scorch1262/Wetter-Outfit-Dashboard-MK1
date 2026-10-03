# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Spezifikation für das Outfit-Dashboard
#
#   Windows:  dist/Outfit-Dashboard.exe        (eine Datei, mit Konsolenfenster)
#   macOS:    dist/Outfit-Dashboard.app        (App-Bundle, ohne Terminal)
#   Linux:    dist/Outfit-Dashboard            (eine Datei, nur zum Testen)
#
# Aufruf aus dem Repo-Hauptordner:
#   python packaging/make_icon.py
#   pyinstaller --noconfirm --clean packaging/outfit_dashboard.spec

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
NAME = "Outfit-Dashboard"

with open(os.path.join(ROOT, "version.py"), encoding="utf-8") as fh:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read()).group(1)

ICON = os.path.join(ROOT, "packaging", "icon.png")
ICON = ICON if os.path.exists(ICON) else None

datas = [
    (os.path.join(ROOT, "templates"), "templates"),
    (os.path.join(ROOT, "static"), "static"),
    (os.path.join(ROOT, "config.example.json"), "."),
]

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=["certifi"],
    excludes=["tkinter", "unittest", "pydoc_data", "test"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=NAME,
        console=False,
        icon=ICON,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)
    app = BUNDLE(
        coll,
        name=NAME + ".app",
        icon=ICON,
        bundle_identifier="de.outfitdashboard.mk1",
        version=VERSION,
        info_plist={
            "CFBundleName": NAME,
            "CFBundleDisplayName": "Outfit-Dashboard",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            # Server im lokalen Netz (iPhone-Zugriff)
            "NSLocalNetworkUsageDescription":
                "Das Outfit-Dashboard stellt seine Webseite im lokalen Netzwerk bereit.",
        },
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name=NAME,
        console=True,          # Konsolenfenster zeigt Adresse und Protokoll
        icon=ICON,
        upx=False,
    )
