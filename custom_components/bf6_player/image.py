"""Rang-Abzeichen je Spieler als Bild-Entitaet."""

from __future__ import annotations

from functools import partial

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import Bf6ConfigEntry
from .coordinator import Bf6PlayerCoordinator
from .entity import Bf6PlayerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Bf6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        add = partial(async_add_entities, config_subentry_id=subentry_id)
        add([Bf6RankImage(hass, coordinator)])


class Bf6RankImage(Bf6PlayerEntity, ImageEntity):
    """Abzeichen des aktuellen Rangs.

    Die Adresse kommt aus dem Profil und ist schon geprueft
    (parsers.image_url: nur https://cdn.gametools.network). Home Assistant
    laedt das Bild selbst und zeigt es ueber die eigene Adresse an.
    """

    def __init__(self, hass: HomeAssistant, coordinator: Bf6PlayerCoordinator) -> None:
        Bf6PlayerEntity.__init__(self, coordinator, "rank_badge")
        ImageEntity.__init__(self, hass)
        self._attr_image_url = self._url()
        self._attr_image_last_updated = (
            dt_util.utcnow() if self._attr_image_url else None
        )

    def _url(self) -> str | None:
        data = self.coordinator.data or {}
        return (data.get("profile") or {}).get("rank_image")

    @callback
    def _handle_coordinator_update(self) -> None:
        url = self._url()
        if url != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()
