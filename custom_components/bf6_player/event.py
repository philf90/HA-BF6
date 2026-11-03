"""Ereignisse je Spieler: "Match beendet" und "Rang gestiegen".

Beide entstehen aus dem Vergleich zweier Abfragen (coordinator.events). Seit
0.6.13 vergleicht die erste Abfrage nach dem Start mit dem gespeicherten
Stand (baseline.py): Matches waehrend eines Neustarts loesen danach ein
Ereignis aus, mit "since" als Zeit des verglichenen Stands.

Seit 0.7.0 kommt ein solches nachgeholtes Ereignis erst nach dem ersten
Schreiben des Zustands (wiederhergestelltes letztes Ereignis). Vorher war es
selbst der erste Zustand, und eine Automation konnte es nicht von einem nur
wiederhergestellten alten Ereignis unterscheiden (beide ohne Zustand davor).
Die Blueprints verwerfen genau diesen Fall.
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import Bf6ConfigEntry
from .const import EVENT_MATCH_FINISHED, EVENT_RANK_UP
from .coordinator import Bf6PlayerCoordinator
from .entity import Bf6PlayerEntity, async_add_player_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Bf6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_player_entities(
        hass,
        entry,
        async_add_entities,
        lambda coordinator: [
            Bf6Event(coordinator, EVENT_MATCH_FINISHED),
            Bf6Event(coordinator, EVENT_RANK_UP),
        ],
    )


class Bf6Event(Bf6PlayerEntity, EventEntity):
    """Ein Ereignistyp eines Spielers."""

    def __init__(self, coordinator: Bf6PlayerCoordinator, event_type: str) -> None:
        super().__init__(coordinator, event_type)
        self._event_type = event_type
        self._attr_event_types = [event_type]
        # Nummer der zuletzt ausgeloesten Abfrage. Seit 0.6.13 bei 0: Die
        # erste Abfrage nach dem Start kann gegen den gespeicherten Stand
        # Ereignisse liefern, oft bevor die Entitaet angelegt ist; bis 0.6.12
        # galten deren Ereignisse als gesehen (es gab dort noch keine).
        self._serial = 0

    @property
    def available(self) -> bool:
        # Ein Ereignis bleibt sichtbar, auch wenn eine Abfrage scheitert.
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Ereignisse einer Abfrage, die vor dem Anlegen fertig war. Home
        # Assistant schreibt den ersten Zustand erst nach dieser Methode
        # (Entity.add_to_platform_finish); deshalb erst danach ausloesen.
        self.async_on_remove(async_call_later(self.hass, 0, self._fire_after_add))

    @callback
    def _fire_after_add(self, _now: datetime) -> None:
        self._fire_new()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._fire_new()

    @callback
    def _fire_new(self) -> None:
        """Ereignisse einer neuen Abfrage je Nummer hoechstens einmal ausloesen."""
        if self.coordinator.events_serial == self._serial:
            return
        self._serial = self.coordinator.events_serial
        for event_type, data in self.coordinator.events:
            if event_type == self._event_type:
                self._trigger_event(event_type, data)
                self.async_write_ha_state()
