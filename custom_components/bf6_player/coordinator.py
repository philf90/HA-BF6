"""Regelmaessige Abfrage je Spieler.

Je Spieler ein Coordinator: Statistik alle 15 Minuten, Profil (Rang,
Abzeichen) stuendlich. Faellt ein Spieler aus, sind nur seine Entitaeten
nicht verfuegbar, wie bei WoW Charakter.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import parsers
from .api import GametoolsClient, GametoolsError, PlayerRef
from .const import (
    CONF_NUCLEUS_ID,
    CONF_PERSONA_ID,
    CONF_PLATFORM,
    DOMAIN,
    PROFILE_INTERVAL_MINUTES,
    STATS_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


def player_ref(subentry: ConfigSubentry) -> PlayerRef:
    data = subentry.data
    return PlayerRef(
        int(data[CONF_PERSONA_ID]), int(data[CONF_NUCLEUS_ID]), data[CONF_PLATFORM]
    )


class Bf6PlayerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Statistik und Profil eines Spielers.

    data = {"stats": parsers.player_stats(...), "profile": parsers.player_profile(...)
    oder None}
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GametoolsClient,
        subentry: ConfigSubentry,
    ) -> None:
        # Im Log steht die Persona-ID, nicht der Name (README, "Sicherheit").
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {subentry.data[CONF_PERSONA_ID]}",
            update_interval=timedelta(minutes=STATS_INTERVAL_MINUTES),
        )
        self.client = client
        self.subentry = subentry
        self.player = player_ref(subentry)
        self._profile: dict[str, Any] | None = None
        self._profile_at: datetime | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            stats = parsers.player_stats(await self.client.stats(self.player))
        except GametoolsError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        if not stats["has_results"]:
            # HTTP 200 mit hasResults = false: Die API kennt das Konto nicht
            # (mehr) oder liefert gerade nichts.
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_stats")
        await self._update_profile()
        return {"stats": stats, "profile": self._profile}

    async def _update_profile(self) -> None:
        """Profil nur stuendlich; scheitert es, bleibt der letzte Stand."""
        now = dt_util.utcnow()
        if self._profile_at is not None and now - self._profile_at < timedelta(
            minutes=PROFILE_INTERVAL_MINUTES
        ):
            return
        try:
            self._profile = parsers.player_profile(
                await self.client.profile(self.player)
            )
        except GametoolsError as err:
            _LOGGER.warning(
                "Profil von Spieler %s nicht geladen: %s",
                self.subentry.data[CONF_PERSONA_ID],
                err,
            )
            return
        self._profile_at = now
