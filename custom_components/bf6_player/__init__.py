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
from .const import DOMAIN

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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Bf6ConfigEntry) -> bool:
    """Haupteintrag entladen."""
    return True
