"""BF6 Spieler: Statistiken von Battlefield-6-Spielern aus der gametools API.

Ein Haupteintrag haelt die Einstellungen, darunter haengt je Spieler ein
Untereintrag (seit 0.3.0) mit eigenem Geraet und eigenen Entitaeten (seit
0.4.0), wie die Charaktere bei WoW Charakter (philf90/HA-WOW). Dazu ein
Geraet "BF6-Spielwelt" (seit 0.5.0).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import GametoolsClient
from .const import (
    CONF_NAME,
    CONF_PLATFORM,
    DOMAIN,
    PARALLEL_PLAYERS,
    SUBENTRY_PLAYER,
    player_title,
)
from .coordinator import Bf6PlayerCoordinator, Bf6WorldCoordinator, issue_id
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.EVENT, Platform.IMAGE, Platform.SENSOR]


@dataclass
class Bf6RuntimeData:
    """Laufzeitdaten des Haupteintrags."""

    client: GametoolsClient
    world: Bf6WorldCoordinator | None = None
    # subentry_id -> Coordinator des Spielers
    coordinators: dict[str, Bf6PlayerCoordinator] = field(default_factory=dict)
    # Stand, mit dem dieser Start arbeitet (fuer _async_reload)
    snapshot: tuple[Any, ...] = ()


type Bf6ConfigEntry = ConfigEntry[Bf6RuntimeData]


def _players(entry: ConfigEntry) -> frozenset[str]:
    return frozenset(
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_PLAYER
    )


def _snapshot(entry: ConfigEntry) -> tuple[Any, ...]:
    """Spieler und Optionen: Aendert sich eines davon, wird neu geladen."""
    return (_players(entry), tuple(sorted(entry.options.items())))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Aktionen einmal je Home Assistant anmelden."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: Bf6ConfigEntry) -> bool:
    """Haupteintrag laden und die Abfragen starten.

    Die gametools API braucht keinen Schluessel; anders als bei WoW
    Charakter gibt es deshalb beim Start nichts zu pruefen. Scheitert die
    erste Abfrage eines Spielers, sind nur seine Entitaeten nicht verfuegbar.
    """
    _add_platform_to_titles(hass, entry)
    _remove_stale_issues(hass, entry)
    runtime = Bf6RuntimeData(GametoolsClient(async_get_clientsession(hass)))
    runtime.snapshot = _snapshot(entry)
    runtime.world = Bf6WorldCoordinator(hass, entry, runtime.client)
    for subentry_id in _players(entry):
        runtime.coordinators[subentry_id] = Bf6PlayerCoordinator(
            hass, entry, runtime.client, entry.subentries[subentry_id]
        )
    limit = asyncio.Semaphore(PARALLEL_PLAYERS)

    async def first_refresh(coordinator: Any) -> None:
        async with limit:
            await coordinator.async_refresh()

    await asyncio.gather(
        first_refresh(runtime.world),
        *map(first_refresh, runtime.coordinators.values()),
    )
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Spieler hinzugefuegt oder geloescht, Optionen geaendert: neu laden.
    # Umbenennen nicht.
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: Bf6ConfigEntry) -> None:
    if _snapshot(entry) != entry.runtime_data.snapshot:
        hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: Bf6ConfigEntry) -> bool:
    """Haupteintrag entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Eintrag geloescht: seine Reparaturhinweise mit."""
    for subentry_id in entry.subentries:
        ir.async_delete_issue(hass, DOMAIN, issue_id(subentry_id))


def _remove_stale_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Hinweise geloeschter Spieler entfernen."""
    known = {issue_id(subentry_id) for subentry_id in entry.subentries}
    registry = ir.async_get(hass)
    for domain, issue in list(registry.issues):
        if domain == DOMAIN and issue.startswith("no_stats_") and issue not in known:
            ir.async_delete_issue(hass, DOMAIN, issue)


def _add_platform_to_titles(hass: HomeAssistant, entry: Bf6ConfigEntry) -> None:
    """Spieler aus 0.3.0 hiessen nur nach dem Namen; seit 0.3.1 steht die
    Plattform im Titel. Umbenannte Spieler (Titel ungleich Name) bleiben.
    """
    for subentry in list(entry.subentries.values()):
        if subentry.subentry_type != SUBENTRY_PLAYER:
            continue
        name = subentry.data.get(CONF_NAME)
        platform = subentry.data.get(CONF_PLATFORM)
        if not name or not platform or subentry.title != name:
            continue
        hass.config_entries.async_update_subentry(
            entry, subentry, title=player_title(name, platform)
        )
