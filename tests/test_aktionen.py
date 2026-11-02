"""Tests fuer die Aktionen bf6_player.refresh und bf6_player.get_player (0.5.0)."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.bf6_player.const import DOMAIN

from .conftest import SEARCH, STATS, device_of, main_entry, player_subentry

BASE = "https://api.gametools.network"
STATS_URL = f"{BASE}/bf6/stats/"
SEARCH_URL = f"{BASE}/bf6/player/"


def _calls(aioclient_mock, url):
    return sum(1 for c in aioclient_mock.mock_calls if str(c[1]).startswith(url))


async def _setup(hass):
    entry = main_entry(
        player_subentry(), player_subentry(1000000002, 2000000002, "steam")
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_refresh_all(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(STATS_URL, json=STATS)
    await _setup(hass)
    assert _calls(aioclient_mock, STATS_URL) == 2
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert _calls(aioclient_mock, STATS_URL) == 4


async def test_refresh_one_device(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(STATS_URL, json=STATS)
    await _setup(hass)
    device = device_of(hass, "1000000002-kills")
    assert (DOMAIN, "1000000002") in device.identifiers
    await hass.services.async_call(
        DOMAIN, "refresh", {"device_id": device.id}, blocking=True
    )
    queries = [
        c[1].query["playerid"]
        for c in aioclient_mock.mock_calls
        if str(c[1]).startswith(STATS_URL)
    ]
    assert queries[2:] == ["1000000002"]


async def test_refresh_unknown_device(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(STATS_URL, json=STATS)
    await _setup(hass)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "refresh", {"device_id": "gibt-es-nicht"}, blocking=True
        )
    assert err.value.translation_key == "unknown_device"


async def test_get_player(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(SEARCH_URL, json=SEARCH)
    entry = main_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    response = await hass.services.async_call(
        DOMAIN,
        "get_player",
        {"name": " Testspieler "},
        blocking=True,
        return_response=True,
    )
    assert response["accounts"][0] == {
        "name": "Testspieler",
        "persona_id": 1000000001,
        "nucleus_id": 2000000001,
        "platform": "ea",
        "platform_name": "EA app",
        "created": "2015-03-01T10:00:00+00:00",
        "public": True,
    }
    assert len(response["accounts"]) == 2


async def test_get_player_invalid_name(hass: HomeAssistant, aioclient_mock):
    entry = main_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "get_player", {"name": "a\nb"}, blocking=True, return_response=True
        )
    assert _calls(aioclient_mock, SEARCH_URL) == 0


async def test_get_player_api_error(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(SEARCH_URL, status=500)
    entry = main_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "get_player",
            {"name": "Testspieler"},
            blocking=True,
            return_response=True,
        )
