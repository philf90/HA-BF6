"""Basisklasse fuer Entitaeten am Geraet eines Spielers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, CONF_PERSONA_ID, CONF_PLATFORM, DOMAIN, PLATFORM_NAMES
from .coordinator import Bf6PlayerCoordinator


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
