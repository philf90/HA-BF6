"""Basisklasse fuer Entitaeten am Geraet eines Spielers."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_NAME,
    CONF_PERSONA_ID,
    CONF_PLATFORM,
    DOMAIN,
    PLATFORM_NAMES,
    SIGNAL_NEW_PLAYER,
)
from .coordinator import Bf6PlayerCoordinator, Bf6WorldCoordinator


@callback
def async_add_player_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    entities_for: Callable[[Bf6PlayerCoordinator], Iterable[Entity]],
) -> None:
    """Entitaeten je Spieler anlegen, auch fuer spaeter hinzugefuegte.

    Seit 0.6.13 laedt ein neuer Spieler nicht mehr den ganzen Eintrag neu;
    __init__._async_entry_updated meldet ihn ueber SIGNAL_NEW_PLAYER.
    """

    @callback
    def add(subentry_id: str, coordinator: Bf6PlayerCoordinator) -> None:
        async_add_entities(entities_for(coordinator), config_subentry_id=subentry_id)

    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        add(subentry_id, coordinator)
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_PLAYER.format(entry.entry_id), add)
    )


class Bf6PlayerEntity(CoordinatorEntity[Bf6PlayerCoordinator]):
    """Entitaet eines Spielers; ein Geraet je Spieler."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Bf6PlayerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        data = coordinator.subentry.data
        persona_id = str(data[CONF_PERSONA_ID])
        platform = data[CONF_PLATFORM]
        self._attr_unique_id = f"{persona_id}-{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, persona_id)},
            # Name aus dem Dialog, ohne Steuerzeichen (parsers.clean_name)
            name=data[CONF_NAME],
            manufacturer="Electronic Arts",
            model=f"Battlefield 6 · {PLATFORM_NAMES.get(platform, platform)}",
            entry_type=DeviceEntryType.SERVICE,
        )


class Bf6WorldEntity(CoordinatorEntity[Bf6WorldCoordinator]):
    """Entitaet am Geraet "BF6-Spielwelt"."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Bf6WorldCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}-world-{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}-world")},
            translation_key="world",
            manufacturer="Electronic Arts",
            model="Battlefield 6",
            entry_type=DeviceEntryType.SERVICE,
        )
