"""Tests fuer api.py: Parameter, Fehlerbilder und Umgang mit Antworten."""

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bf6_player.api import (
    GametoolsClient,
    GametoolsError,
    GametoolsNotFound,
    GametoolsRateLimited,
    PlayerRef,
)

from .conftest import EVENTS, NUCLEUS_ID, PERSONA_ID, PROFILE, SEARCH, STATS, STATUS

BASE = "https://api.gametools.network"
PLAYER = PlayerRef(PERSONA_ID, NUCLEUS_ID, "ea")
IDS = {"playerid": str(PERSONA_ID), "nucleus_id": str(NUCLEUS_ID), "platform": "ea"}


def _client(hass: HomeAssistant) -> GametoolsClient:
    return GametoolsClient(async_get_clientsession(hass))


async def test_stats_by_id(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    params = {**IDS, "format_values": "false", "seperation": "false"}
    aioclient_mock.get(f"{BASE}/bf6/stats/", params=params, json=STATS)
    assert await _client(hass).stats(PLAYER) == STATS
    assert aioclient_mock.call_count == 1


async def test_stats_with_separation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    params = {**IDS, "format_values": "false", "seperation": "true"}
    aioclient_mock.get(f"{BASE}/bf6/stats/", params=params, json=STATS)
    assert await _client(hass).stats(PLAYER, separation=True) == STATS


async def test_other_endpoints(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(
        f"{BASE}/bf6/player/",
        params={"name": "Testspieler", "limit": "10"},
        json=SEARCH,
    )
    aioclient_mock.get(f"{BASE}/bf6/profile/", params=IDS, json=PROFILE)
    aioclient_mock.get(f"{BASE}/bf6/gameevents/", json=EVENTS)
    aioclient_mock.get(f"{BASE}/bf6/status/", json=STATUS)
    client = _client(hass)
    assert await client.search_players("Testspieler") == SEARCH
    assert await client.profile(PLAYER) == PROFILE
    assert await client.game_events() == EVENTS
    assert await client.portal_status() == STATUS


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (404, GametoolsNotFound),
        (429, GametoolsRateLimited),
        (500, GametoolsError),
        (503, GametoolsError),
    ],
)
async def test_http_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status, error
):
    aioclient_mock.get(
        f"{BASE}/bf6/status/", status=status, json={"errors": ["Player not found"]}
    )
    with pytest.raises(error):
        await _client(hass).portal_status()


def test_not_found_is_api_error() -> None:
    assert issubclass(GametoolsNotFound, GametoolsError)
    assert issubclass(GametoolsRateLimited, GametoolsError)


@pytest.mark.parametrize(
    ("kwargs", "text"),
    [
        ({"text": "Internal Server Error"}, "kein JSON"),
        ({"json": [1, 2]}, "kein JSON-Objekt"),
        ({"exc": TimeoutError()}, "keine Antwort nach 30 s"),
        ({"exc": aiohttp.ClientConnectionError("weg")}, "ClientConnectionError"),
    ],
)
async def test_broken_answers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, kwargs, text
):
    aioclient_mock.get(f"{BASE}/bf6/gameevents/", **kwargs)
    with pytest.raises(GametoolsError, match=text):
        await _client(hass).game_events()


def test_player_ref_params() -> None:
    assert PLAYER.params() == IDS
