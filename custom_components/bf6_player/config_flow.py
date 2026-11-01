"""Einrichtung ueber die Oberflaeche: ein Haupteintrag je Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN, MAIN_TITLE


class Bf6PlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Legt den Haupteintrag "gametools API" an.

    Zugangsdaten gibt es nicht: Die gametools API ist ohne Schluessel
    erreichbar. Mehr als ein Haupteintrag ergibt keinen Sinn, weil alle
    Spieler am selben Eintrag haengen.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=MAIN_TITLE, data={})
        return self.async_show_form(step_id="user")
