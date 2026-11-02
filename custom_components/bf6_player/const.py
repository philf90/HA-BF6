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

# Untereintrag je Spieler und seine Daten
SUBENTRY_PLAYER = "player"
CONF_NAME = "name"
CONF_ACCOUNT = "account"
CONF_PERSONA_ID = "persona_id"
CONF_NUCLEUS_ID = "nucleus_id"
CONF_PLATFORM = "platform"

# Anzeigenamen der Plattformen aus der Spielersuche (Feld "platform"; laut
# OpenAPI gelten ea, xbox, psn, steam und epic fuer die Stats als dieselbe
# Plattform, weil BF6 ein Konto ueber alle Plattformen fuehrt).
PLATFORM_NAMES = {
    "ea": "EA app",
    "steam": "Steam",
    "epic": "Epic Games",
    "psn": "PlayStation",
    "xbox": "Xbox",
    "pc": "PC",
    "ps4": "PlayStation 4",
    "ps5": "PlayStation 5",
    "xboxone": "Xbox One",
    "xboxseries": "Xbox Series",
}

# Treffer der Spielersuche, die im Auswahldialog stehen (OpenAPI: 1 bis 100)
SEARCH_LIMIT = 25
