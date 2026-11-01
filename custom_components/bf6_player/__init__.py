"""BF6 Spieler: Statistiken von Battlefield-6-Spielern aus der gametools API.

Ein Haupteintrag haelt die Einstellungen. Darunter haengt spaeter je Spieler
ein Untereintrag mit eigenem Geraet und eigenen Sensoren, wie bei der
Integration WoW Charakter (philf90/HA-WOW). Version 0.1.0 ist das
Grundgeruest: Der Haupteintrag laesst sich anlegen, Entitaeten gibt es noch
nicht.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Haupteintrag laden; Plattformen kommen mit den Spielern dazu."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Haupteintrag entladen."""
    return True
