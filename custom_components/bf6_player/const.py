"""Konstanten der Integration BF6 Spieler."""

from __future__ import annotations

DOMAIN = "bf6_player"

# Titel des Haupteintrags. Er haelt nur Einstellungen; die gametools API
# braucht keine Zugangsdaten.
MAIN_TITLE = "gametools API"

# Basisadresse der Community-API (OpenAPI unter /openapi.json, Version 1.3.0,
# abgerufen am 01.11.2026). Wird ab 0.2.0 vom API-Client genutzt.
API_BASE = "https://api.gametools.network"
