"""Diagnose: Zustand der Abfragen, ohne Namen und IDs der Spieler.

Geschwaerzt werden nur Titel und Daten des Untereintrags (Name, Persona- und
Nucleus-ID). Die ausgewerteten Daten enthalten keinen Spielernamen; ihre
Felder "name" (Waffen, Fahrzeuge, Klassen, Karten, Modi) bleiben lesbar.
Bis 0.5.0 lief die Schwaerzung ueber alles und machte auch diese Namen
unlesbar.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.core import HomeAssistant

from . import Bf6ConfigEntry
from .const import CONF_NAME, CONF_NUCLEUS_ID, CONF_PERSONA_ID

TO_REDACT = {CONF_NAME, CONF_PERSONA_ID, CONF_NUCLEUS_ID}


def _coordinator(coordinator: Any) -> dict[str, Any]:
    return {
        "last_update_success": coordinator.last_update_success,
        "last_exception": str(coordinator.last_exception)
        if coordinator.last_exception
        else None,
        "update_interval_s": coordinator.update_interval.total_seconds()
        if coordinator.update_interval
        else None,
        "data": coordinator.data,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Bf6ConfigEntry
) -> dict[str, Any]:
    runtime = entry.runtime_data
    players = []
    for subentry_id, coordinator in runtime.coordinators.items():
        subentry = entry.subentries[subentry_id]
        players.append(
            {
                "title": REDACTED,
                "subentry": async_redact_data(dict(subentry.data), TO_REDACT),
                "profile_interval_s": coordinator.profile_interval.total_seconds(),
                **_coordinator(coordinator),
            }
        )
    return {
        "options": dict(entry.options),
        "players": players,
        "world": _coordinator(runtime.world) if runtime.world else None,
    }
