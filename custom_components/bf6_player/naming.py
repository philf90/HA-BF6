"""Name eines Spielers: Abgleich mit der API und eigener Name (seit 0.8.0).

Der Name stammt aus dem Dialog "Spieler hinzufuegen" (displayName der
Namenssuche) und bildet Geraetenamen und Titel des Untereintrags. Bis 0.7.1
blieb er nach einer Umbenennung bei EA fuer immer alt (Review B12).

Gespeichert sind CONF_NAME (angezeigter Name) und CONF_API_NAME (zuletzt von
der API gelesen). Sind beide gleich, folgt der Spieler der API: Aendert sich
der Name bei EA, aendern sich CONF_NAME, der Titel (wenn er noch der
automatische war) und der Geraetename. Einen eigenen Namen setzt der Dialog
"Neu konfigurieren" (Review E6); dann aendert sich nur CONF_API_NAME.

Nie geaendert werden Entity-IDs und ein in Home Assistant vergebener
Geraetename (name_by_user).
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_API_NAME,
    CONF_NAME,
    CONF_PERSONA_ID,
    CONF_PLATFORM,
    DOMAIN,
    player_title,
)


@callback
def rename_device(
    hass: HomeAssistant, entry: ConfigEntry, persona_id: Any, name: str
) -> None:
    """Geraetenamen setzen; name_by_user (Umbenennung in HA) bleibt.

    Gesucht ueber die Geraete des Eintrags: device_registry.async_get_device
    ist seit Home Assistant 2026.10 abgekuendigt, der Ersatz
    async_get_device_by_identifier fehlt in der Mindestversion 2026.2.3.
    """
    registry = dr.async_get(hass)
    identifier = (DOMAIN, str(persona_id))
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if identifier in device.identifiers and device.name != name:
            registry.async_update_device(device.id, name=name)


@callback
def async_apply_api_name(
    hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry, api_name: str
) -> bool:
    """Von der API gelesenen Namen uebernehmen; True, wenn umbenannt."""
    data = subentry.data
    if api_name == data.get(CONF_API_NAME):
        return False
    follows = data.get(CONF_NAME) == data.get(CONF_API_NAME)
    new_data = {**data, CONF_API_NAME: api_name}
    title = subentry.title
    if follows:
        new_data[CONF_NAME] = api_name
        platform = data[CONF_PLATFORM]
        # Ein von Hand geaenderter Titel bleibt
        if title == player_title(data[CONF_NAME], platform):
            title = player_title(api_name, platform)
    hass.config_entries.async_update_subentry(
        entry, subentry, data=new_data, title=title
    )
    if follows:
        rename_device(hass, entry, data[CONF_PERSONA_ID], api_name)
    return follows
