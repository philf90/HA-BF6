"""Vergleichsbasis je Spieler, ueber Neustarts gespeichert (seit 0.6.13).

"Match beendet" und "Rang gestiegen" entstehen aus dem Vergleich zweier
Abfragen. Bis 0.6.12 lag der Stand der letzten Abfrage nur im Speicher: Nach
einem Neustart oder Neuladen setzte die erste Abfrage nur den Ausgangsstand,
Matches dazwischen erzeugten kein Ereignis (Review E5). Jetzt steht je
Spieler der letzte uebernommene Stand der Zaehler, der Rang und die Zeit in
.storage/bf6_player.<entry_id>. Seit 0.7.0 auch Dog Tags und Abzeichen
(PROFILE_COUNTERS): Ihre Sensoren sind total_increasing, ein Rueckgang
gegenueber dem gespeicherten Stand soll wie bei den Zaehlern der Statistik
erst nach Bestaetigung gelten. Aeltere Dateien ohne diese Werte bleiben
gueltig (None).

Gespeichert werden nur Zahlen, keine Namen und keine IDs ausser der
subentry_id als Schluessel.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MATCH_COUNTERS, PROFILE_COUNTERS

STORE_VERSION = 1
# Sekunden bis zum Schreiben; mehrere Spieler einer Runde ergeben einen
# Schreibvorgang. Beim Beenden schreibt Home Assistant ausstehende Daten.
SAVE_DELAY = 30


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class Bf6Baseline:
    """Letzter Stand je Spieler.

    {"stats": {zaehler: int}, "rank": int, "dog_tags": int, "badges": int,
    "at": iso}
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self._data: dict[str, dict[str, Any]] = {}
        # Geaendert, aber noch nicht geschrieben
        self._dirty = False

    async def async_load(self) -> None:
        geladen = await self._store.async_load()
        self._data = geladen if isinstance(geladen, dict) else {}

    def get(self, subentry_id: str) -> dict[str, Any] | None:
        """Gespeicherter Stand, nur mit gueltigen Werten; sonst None.

        Eine beschaedigte oder von Hand geaenderte Datei soll nichts
        ausloesen: Unpassende Werte fallen weg, ohne Zaehler gibt es keinen
        Stand.
        """
        eintrag = self._data.get(subentry_id)
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("stats"), dict):
            return None
        stats = {
            key: wert
            for key in MATCH_COUNTERS
            if (wert := _int(eintrag["stats"].get(key))) is not None
        }
        if "matches" not in stats:
            return None
        at = eintrag.get("at")
        zeit = dt_util.parse_datetime(at) if isinstance(at, str) else None
        return {
            "stats": stats,
            "rank": _int(eintrag.get("rank")),
            **{key: _int(eintrag.get(key)) for key in PROFILE_COUNTERS},
            "at": zeit,
        }

    @callback
    def set(
        self,
        subentry_id: str,
        stats: dict[str, Any],
        rank: int | None,
        at: datetime,
        profile_counters: dict[str, Any] | None = None,
    ) -> None:
        counters = profile_counters or {}
        self._data[subentry_id] = {
            "stats": {
                key: wert
                for key in MATCH_COUNTERS
                if (wert := _int(stats.get(key))) is not None
            },
            "rank": _int(rank),
            **{key: _int(counters.get(key)) for key in PROFILE_COUNTERS},
            "at": at.isoformat(),
        }
        self._dirty = True
        self._store.async_delay_save(self._to_save, SAVE_DELAY)

    @callback
    def remove(self, subentry_id: str) -> None:
        if self._data.pop(subentry_id, None) is not None:
            self._dirty = True
            self._store.async_delay_save(self._to_save, SAVE_DELAY)

    @callback
    def _to_save(self) -> dict[str, dict[str, Any]]:
        self._dirty = False
        return self._data

    async def async_flush(self) -> None:
        """Ausstehendes sofort schreiben, beim Entladen des Eintrags.

        Laedt der Eintrag neu (geaenderte Optionen), liest der neue Start die
        Datei; ohne Schreiben laege dort ein Stand bis zu SAVE_DELAY alt, und
        ein gerade gemeldetes Match kaeme ein zweites Mal.
        """
        if self._dirty:
            self._dirty = False
            await self._store.async_save(self._data)

    async def async_remove(self) -> None:
        """Datei loeschen, wenn der Haupteintrag geloescht wird."""
        await self._store.async_remove()
