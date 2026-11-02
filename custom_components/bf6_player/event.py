"""Ereignisse je Spieler: "Match beendet" und "Rang gestiegen".

Beide entstehen aus dem Vergleich zweier Abfragen (coordinator.events). Die
erste Abfrage nach dem Start setzt nur den Ausgangsstand; Matches waehrend
eines Neustarts loesen kein Ereignis aus.
"""

from __future__ import annotations

from functools import partial

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Bf6ConfigEntry
from .const import EVENT_MATCH_FINISHED, EVENT_RANK_UP
from .coordinator import Bf6PlayerCoordinator
from .entity import Bf6PlayerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Bf6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        add = partial(async_add_entities, config_subentry_id=subentry_id)
        add(
            [
                Bf6Event(coordinator, EVENT_MATCH_FINISHED),
                Bf6Event(coordinator, EVENT_RANK_UP),
            ]
        )


class Bf6Event(Bf6PlayerEntity, EventEntity):
    """Ein Ereignistyp eines Spielers."""

    def __init__(self, coordinator: Bf6PlayerCoordinator, event_type: str) -> None:
        super().__init__(coordinator, event_type)
        self._event_type = event_type
        self._attr_event_types = [event_type]
        # Ereignisse der Abfrage, die beim Anlegen schon vorlag, gelten als
        # gesehen.
        self._serial = coordinator.events_serial

    @property
    def available(self) -> bool:
        # Ein Ereignis bleibt sichtbar, auch wenn eine Abfrage scheitert.
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.events_serial == self._serial:
            return
        self._serial = self.coordinator.events_serial
        for event_type, data in self.coordinator.events:
            if event_type == self._event_type:
                self._trigger_event(event_type, data)
                self.async_write_ha_state()
