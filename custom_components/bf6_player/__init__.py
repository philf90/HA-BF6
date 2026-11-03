"""BF6 Spieler: Statistiken von Battlefield-6-Spielern aus der gametools API.

Ein Haupteintrag haelt die Einstellungen, darunter haengt je Spieler ein
Untereintrag (seit 0.3.0) mit eigenem Geraet und eigenen Entitaeten (seit
0.4.0), wie die Charaktere bei WoW Charakter (philf90/HA-WOW). Dazu ein
Geraet "BF6-Spielwelt" (seit 0.5.0).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import GametoolsClient
from .baseline import Bf6Baseline
from .const import (
    CONF_API_NAME,
    CONF_NAME,
    CONF_PLATFORM,
    DOMAIN,
    FIRST_REFRESH_WAIT_SECONDS,
    SIGNAL_NEW_PLAYER,
    SUBENTRY_PLAYER,
    player_title,
)
from .coordinator import Bf6PlayerCoordinator, Bf6WorldCoordinator, issue_id
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.EVENT, Platform.IMAGE, Platform.SENSOR]

# Dashboard-Karten (seit 0.6.0), von der Integration selbst ausgeliefert wie
# bei WoW Charakter; alle Dateien unter frontend/ sind unter CARD_PATH
# erreichbar. Gemeinsame Teile und der Editor werden von den Karten mit
# ihrer Version im Pfad nachgeladen und sind deshalb keine eigenen Module.
CARD_PATH = f"/{DOMAIN}"
CARD_DIR = Path(__file__).parent / "frontend"
CARDS = (
    "bf6-player-card.js",
    "bf6-arsenal-card.js",
    "bf6-classes-card.js",
    "bf6-maps-card.js",
    "bf6-modes-card.js",
    "bf6-squad-card.js",
    "bf6-world-card.js",
    "bf6-history-card.js",
)
CARD_SUPPORT = ("bf6-common.js", "bf6-card-editor.js")


@dataclass
class Bf6RuntimeData:
    """Laufzeitdaten des Haupteintrags."""

    client: GametoolsClient
    # Gespeicherte Vergleichsbasis fuer die Ereignisse (seit 0.6.13)
    baseline: Bf6Baseline
    world: Bf6WorldCoordinator | None = None
    # subentry_id -> Coordinator des Spielers
    coordinators: dict[str, Bf6PlayerCoordinator] = field(default_factory=dict)
    # Optionen, mit denen dieser Start arbeitet; aendern sie sich, wird neu
    # geladen (Takte). Spieler kommen und gehen ohne Neuladen (seit 0.6.13).
    options: tuple[Any, ...] = ()


type Bf6ConfigEntry = ConfigEntry[Bf6RuntimeData]


def _players(entry: ConfigEntry) -> frozenset[str]:
    return frozenset(
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_PLAYER
    )


def _options(entry: ConfigEntry) -> tuple[Any, ...]:
    return tuple(sorted(entry.options.items()))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Aktionen und Karten einmal je Home Assistant anmelden."""
    await _async_register_cards(hass)
    async_setup_services(hass)
    return True


async def _async_register_cards(hass: HomeAssistant) -> None:
    """Karten ausliefern und im Frontend laden, ohne eigene Dashboard-Ressource.

    Die Version im Pfad sorgt dafuer, dass der Browser nach einem Update die
    neue Datei laedt.
    """
    if getattr(hass, "http", None) is None:
        return
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(f"{CARD_PATH}/{card}", str(CARD_DIR / card), True)
            for card in (*CARDS, *CARD_SUPPORT)
        ]
    )
    if "frontend" not in hass.config.components:
        return
    from homeassistant.components.frontend import add_extra_js_url

    integration = await async_get_integration(hass, DOMAIN)
    for card in CARDS:
        add_extra_js_url(hass, f"{CARD_PATH}/{card}?v={integration.version}")


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Gespeicherte Daten einmalig umstellen (seit 0.8.0, Review B13).

    1.1 -> 1.2: Plattform in alte Titel (Spieler aus 0.3.0); bis 0.7.1 lief
    das bei jedem Start. Dazu CONF_API_NAME = CONF_NAME fuer bestehende
    Spieler: Beide Namen stammen aus displayName der Namenssuche, der
    Spieler folgt damit einer spaeteren Umbenennung bei EA (naming.py).
    Eine neuere Version als diese kennt die Integration nicht.
    """
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        _add_platform_to_titles(hass, entry)
        _store_api_names(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=2)
        _LOGGER.debug("Eintrag auf Version 1.2 umgestellt")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: Bf6ConfigEntry) -> bool:
    """Haupteintrag laden und die Abfragen starten.

    Die gametools API braucht keinen Schluessel; anders als bei WoW
    Charakter gibt es deshalb beim Start nichts zu pruefen. Scheitert die
    erste Abfrage eines Spielers, sind nur seine Entitaeten nicht verfuegbar.
    """
    _remove_stale_issues(hass, entry)
    baseline = Bf6Baseline(hass, entry.entry_id)
    await baseline.async_load()
    runtime = Bf6RuntimeData(GametoolsClient(async_get_clientsession(hass)), baseline)
    runtime.options = _options(entry)
    runtime.world = Bf6WorldCoordinator(hass, entry, runtime.client)
    for subentry_id in _players(entry):
        runtime.coordinators[subentry_id] = Bf6PlayerCoordinator(
            hass, entry, runtime.client, entry.subentries[subentry_id], baseline
        )
    await _first_refresh(hass, entry, [runtime.world, *runtime.coordinators.values()])
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def _first_refresh(
    hass: HomeAssistant, entry: ConfigEntry, coordinators: list[Any]
) -> None:
    """Erste Abfragen als Hintergrund-Tasks des Eintrags (beim Entladen
    abgebrochen), darauf hoechstens FIRST_REFRESH_WAIT_SECONDS warten (seit
    0.6.9). Das Limit gleichzeitiger Abfragen haelt der Client.
    """
    first = [
        entry.async_create_background_task(
            hass, coordinator.async_refresh(), f"{coordinator.name} first refresh"
        )
        for coordinator in coordinators
    ]
    _, pending = await asyncio.wait(first, timeout=FIRST_REFRESH_WAIT_SECONDS)
    if pending:
        _LOGGER.info(
            "%s von %s ersten Abfragen nach %s s noch offen; sie laufen im "
            "Hintergrund weiter",
            len(pending),
            len(first),
            FIRST_REFRESH_WAIT_SECONDS,
        )


async def _async_entry_updated(hass: HomeAssistant, entry: Bf6ConfigEntry) -> None:
    """Optionen geaendert: neu laden. Spieler hinzugefuegt oder geloescht:
    nur diesen Spieler anlegen bzw. stoppen (seit 0.6.13).

    Bis 0.6.12 lud jeder neue oder geloeschte Spieler den ganzen Eintrag neu:
    alle Spieler und die Spielwelt wurden erneut abgefragt, und die
    Vergleichsbasis fuer die Ereignisse ging verloren (Review B9). Umbenennen
    aendert nichts.
    """
    runtime = entry.runtime_data
    if _options(entry) != runtime.options:
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return
    players = _players(entry)
    for subentry_id in set(runtime.coordinators) - players:
        # Geraet und Entitaeten entfernt Home Assistant mit dem Untereintrag
        coordinator = runtime.coordinators.pop(subentry_id)
        await coordinator.async_shutdown()
        runtime.baseline.remove(subentry_id)
        ir.async_delete_issue(hass, DOMAIN, issue_id(subentry_id))
    new = {
        subentry_id: Bf6PlayerCoordinator(
            hass, entry, runtime.client, entry.subentries[subentry_id], runtime.baseline
        )
        for subentry_id in players - set(runtime.coordinators)
    }
    if not new:
        return
    # Vor dem Warten eintragen: ein zweiter Aufruf legt sie nicht noch einmal an
    runtime.coordinators.update(new)
    await _first_refresh(hass, entry, list(new.values()))
    for subentry_id, coordinator in new.items():
        async_dispatcher_send(
            hass, SIGNAL_NEW_PLAYER.format(entry.entry_id), subentry_id, coordinator
        )


async def async_unload_entry(hass: HomeAssistant, entry: Bf6ConfigEntry) -> bool:
    """Haupteintrag entladen; gespeicherte Vergleichsbasis sofort schreiben."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.baseline.async_flush()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Eintrag geloescht: seine Reparaturhinweise und die gespeicherte
    Vergleichsbasis mit."""
    for subentry_id in entry.subentries:
        ir.async_delete_issue(hass, DOMAIN, issue_id(subentry_id))
    await Bf6Baseline(hass, entry.entry_id).async_remove()


def _remove_stale_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Hinweise geloeschter Spieler entfernen."""
    known = {issue_id(subentry_id) for subentry_id in entry.subentries}
    registry = ir.async_get(hass)
    for domain, issue in list(registry.issues):
        if domain == DOMAIN and issue.startswith("no_stats_") and issue not in known:
            ir.async_delete_issue(hass, DOMAIN, issue)


def _add_platform_to_titles(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Spieler aus 0.3.0 hiessen nur nach dem Namen; seit 0.3.1 steht die
    Plattform im Titel. Umbenannte Spieler (Titel ungleich Name) bleiben.
    Seit 0.8.0 nur noch in der Migration auf 1.2.
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


def _store_api_names(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """CONF_API_NAME fuer Spieler von vor 0.8.0 (Migration auf 1.2)."""
    for subentry in list(entry.subentries.values()):
        if subentry.subentry_type != SUBENTRY_PLAYER:
            continue
        if CONF_API_NAME in subentry.data or not subentry.data.get(CONF_NAME):
            continue
        hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data={**subentry.data, CONF_API_NAME: subentry.data[CONF_NAME]},
        )
