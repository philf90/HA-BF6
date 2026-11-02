"""Aktionen: bf6_player.refresh und bf6_player.get_player."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import parsers
from .api import GametoolsClient, GametoolsError
from .const import CONF_NAME, DOMAIN, NAME_MAX, PLATFORM_NAMES, SEARCH_LIMIT

SERVICE_REFRESH = "refresh"
SERVICE_GET_PLAYER = "get_player"
ATTR_DEVICE_ID = "device_id"

REFRESH_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}
)
GET_PLAYER_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, _async_refresh, schema=REFRESH_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PLAYER,
        _async_get_player,
        schema=GET_PLAYER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def _coordinators(hass: HomeAssistant) -> dict[str, Any]:
    """Geraete-Kennung (DOMAIN, ...) -> Coordinator aller geladenen Eintraege."""
    result: dict[str, Any] = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        runtime = entry.runtime_data
        for coordinator in runtime.coordinators.values():
            result[str(coordinator.player.persona_id)] = coordinator
        if runtime.world is not None:
            result[f"{entry.entry_id}-world"] = runtime.world
    return result


def _client(hass: HomeAssistant) -> GametoolsClient:
    """Client des geladenen Eintrags (gemeinsames Limit), sonst ein eigener."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data.client
    return GametoolsClient(async_get_clientsession(hass))


async def _async_refresh(call: ServiceCall) -> None:
    """Spieler und Spielwelt sofort abfragen; ohne Geraet alle.

    Die API cacht Antworten 600 s; eine Abfrage kurz nach der letzten
    liefert deshalb oft dieselben Werte.
    """
    hass = call.hass
    coordinators = _coordinators(hass)
    device_ids = call.data.get(ATTR_DEVICE_ID)
    if device_ids:
        registry = dr.async_get(hass)
        chosen = []
        for device_id in device_ids:
            device = registry.async_get(device_id)
            keys = [
                key
                for domain, key in (device.identifiers if device else ())
                if domain == DOMAIN and key in coordinators
            ]
            if not keys:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_device",
                    translation_placeholders={"device_id": device_id},
                )
            chosen.extend(coordinators[key] for key in keys)
    else:
        chosen = list(coordinators.values())
    # async_request_refresh statt async_refresh (seit 0.6.8): Der Debouncer
    # des Coordinators fasst Aufrufe innerhalb von 10 s zusammen; das Limit
    # gleichzeitiger Abfragen haelt der Client.
    await asyncio.gather(
        *(coordinator.async_request_refresh() for coordinator in chosen)
    )


async def _async_get_player(call: ServiceCall) -> ServiceResponse:
    """Konten zu einem Namen nachschlagen, ohne etwas anzulegen."""
    from .config_flow import valid_name

    name = call.data[CONF_NAME].strip()
    if not valid_name(name):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_name",
            translation_placeholders={"max": str(NAME_MAX)},
        )
    client = _client(call.hass)
    try:
        found = parsers.player_results(await client.search_players(name, SEARCH_LIMIT))
    except GametoolsError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    return {
        "accounts": [
            {
                "name": account["name"],
                "persona_id": account["persona_id"],
                "nucleus_id": account["nucleus_id"],
                "platform": account["platform"],
                "platform_name": PLATFORM_NAMES.get(
                    account["platform"], account["platform"]
                ),
                "created": account["created"].isoformat()
                if account["created"]
                else None,
                "public": account["public"],
            }
            for account in found
        ]
    }
