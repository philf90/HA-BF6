"""BF6 Spieler: Statistiken von Battlefield-6-Spielern aus der gametools API.

Ein Haupteintrag haelt die Einstellungen, darunter haengt je Spieler ein
Untereintrag (seit 0.3.0), wie die Charaktere bei WoW Charakter
(philf90/HA-WOW). Geraete und Sensoren je Spieler folgen mit 0.4.0.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GametoolsClient
from .const import CONF_NAME, CONF_PLATFORM, DOMAIN, SUBENTRY_PLAYER, player_title

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class Bf6RuntimeData:
    """Laufzeitdaten des Haupteintrags."""

    client: GametoolsClient


type Bf6ConfigEntry = ConfigEntry[Bf6RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: Bf6ConfigEntry) -> bool:
    """Haupteintrag laden.

    Die gametools API braucht keinen Schluessel; anders als bei WoW
    Charakter gibt es deshalb beim Start nichts zu pruefen.
    """
    entry.runtime_data = Bf6RuntimeData(GametoolsClient(async_get_clientsession(hass)))
    _add_platform_to_titles(hass, entry)
    return True


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


async def async_unload_entry(hass: HomeAssistant, entry: Bf6ConfigEntry) -> bool:
    """Haupteintrag entladen."""
    return True
