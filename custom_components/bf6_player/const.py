"""Konstanten der Integration BF6 Spieler."""

from __future__ import annotations

DOMAIN = "bf6_player"

# Titel des Haupteintrags. Er haelt nur Einstellungen; die gametools API
# braucht keine Zugangsdaten.
MAIN_TITLE = "gametools API"

# Basisadresse der Community-API (OpenAPI unter /openapi.json, Version 1.3.0,
# abgerufen am 01.11.2026).
API_BASE = "https://api.gametools.network"

# Zeitlimit je Abfrage in Sekunden. Gemessen wurden 0,8-1,7 s; eine Antwort
# mit seperation=true ist rund 476 KB gross.
REQUEST_TIMEOUT = 30

# So viele Waffen, Fahrzeuge und Gadgets kommen in die Auswertung (spaeter als
# Attribut; volle Listen sprengen die 16-KB-Grenze des Recorders).
TOP_COUNT = 5
