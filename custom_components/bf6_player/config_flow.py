"""Einrichtung ueber die Oberflaeche.

Ein Haupteintrag je Home Assistant, darunter je Spieler ein Untereintrag.
Spieler findet man ueber den Namen; weil Namen nicht eindeutig sind, waehlt
man das Konto aus der Trefferliste und es werden nur die IDs gespeichert.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import parsers
from .api import GametoolsClient, GametoolsError, GametoolsNotFound, PlayerRef
from .const import (
    CONF_ACCOUNT,
    CONF_NAME,
    CONF_NUCLEUS_ID,
    CONF_PERSONA_ID,
    CONF_PLATFORM,
    DOMAIN,
    MAIN_TITLE,
    PLATFORM_NAMES,
    SEARCH_LIMIT,
    SUBENTRY_PLAYER,
)

NAME_SCHEMA = vol.Schema({vol.Required(CONF_NAME): TextSelector()})


class Bf6PlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Legt den Haupteintrag "gametools API" an.

    Zugangsdaten gibt es nicht: Die gametools API ist ohne Schluessel
    erreichbar. Mehr als ein Haupteintrag ergibt keinen Sinn, weil alle
    Spieler am selben Eintrag haengen.
    """

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_PLAYER: PlayerSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=MAIN_TITLE, data={})
        return self.async_show_form(step_id="user")


def account_label(account: dict[str, Any]) -> str:
    """Zeile im Auswahldialog, z. B. "Name · Steam · 2020-10-01 · 🔒".

    Datum und Plattform unterscheiden gleichnamige Konten; das Schloss steht
    fuer Konten, deren Sichtbarkeit nicht "EVERYONE" ist.
    """
    parts = [account["name"] or str(account["persona_id"])]
    parts.append(PLATFORM_NAMES.get(account["platform"], account["platform"]))
    if account["created"] is not None:
        parts.append(f"{account['created']:%Y-%m-%d}")
    if not account["public"]:
        parts.append("🔒")
    return " · ".join(parts)


class PlayerSubentryFlow(ConfigSubentryFlow):
    """Spieler hinzufuegen: Name suchen, Konto waehlen."""

    def __init__(self) -> None:
        self._name = ""
        # persona_id als Text -> Treffer aus parsers.player_results
        self._accounts: dict[str, dict[str, Any]] = {}

    @property
    def _client(self) -> GametoolsClient:
        return self._get_entry().runtime_data.client

    def _configured(self) -> set[str]:
        return {
            str(sub.data.get(CONF_PERSONA_ID))
            for sub in self._get_entry().subentries.values()
            if sub.subentry_type == SUBENTRY_PLAYER
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            found: list[dict[str, Any]] | None
            try:
                found = parsers.player_results(
                    await self._client.search_players(name, SEARCH_LIMIT)
                )
            except GametoolsNotFound:
                # Bisher antwortete die Suche ohne Treffer mit {"results": []};
                # ein 404 heisst dasselbe.
                found = []
            except GametoolsError:
                found = None
                errors["base"] = "cannot_connect"
            if found is not None:
                configured = self._configured()
                accounts = {
                    str(a["persona_id"]): a
                    for a in found
                    if str(a["persona_id"]) not in configured
                }
                if not found:
                    errors["base"] = "no_players"
                elif not accounts:
                    return self.async_abort(reason="already_configured")
                else:
                    self._name = name
                    self._accounts = accounts
                    return await self.async_step_select()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(NAME_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            account = self._accounts[user_input[CONF_ACCOUNT]]
            player = PlayerRef(
                account["persona_id"], account["nucleus_id"], account["platform"]
            )
            try:
                stats = parsers.player_stats(await self._client.stats(player))
            except GametoolsError:
                errors["base"] = "cannot_connect"
            else:
                if not stats["has_results"]:
                    # HTTP 200 mit hasResults = false: Die API kennt zu dem
                    # Konto keine Battlefield-6-Werte.
                    errors["base"] = "no_stats"
                else:
                    return self.async_create_entry(
                        title=account["name"] or self._name,
                        data={
                            CONF_NAME: account["name"] or self._name,
                            CONF_PERSONA_ID: account["persona_id"],
                            CONF_NUCLEUS_ID: account["nucleus_id"],
                            CONF_PLATFORM: account["platform"],
                        },
                        unique_id=str(account["persona_id"]),
                    )
        options = [
            SelectOptionDict(value=key, label=account_label(account))
            for key, account in self._accounts.items()
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                )
            }
        )
        return self.async_show_form(
            step_id="select",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders={
                "name": self._name,
                "count": str(len(self._accounts)),
            },
        )
