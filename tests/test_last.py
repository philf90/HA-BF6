"""Last auf der API: Abfragelimit, Retry-After, Aktion refresh (0.6.8).

Bis 0.6.7 galt das Limit von zwei gleichzeitigen Abfragen nur beim Start;
im regulaeren Takt und bei bf6_player.refresh liefen alle Spieler zugleich.
HTTP 429 wartete nicht auf Retry-After, und refresh umging den Debouncer.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.bf6_player.api import GametoolsError, GametoolsRateLimited
from custom_components.bf6_player.api import retry_after as header_seconds
from custom_components.bf6_player.const import (
    DOMAIN,
    PARALLEL_REQUESTS,
    RETRY_AFTER_MAX_SECONDS,
)
from custom_components.bf6_player.coordinator import retry_after

from .conftest import PERSONA_ID, STATS, main_entry, player_subentry

BASE = "https://api.gametools.network"
STATS_URL = f"{BASE}/bf6/stats/"
STATUS_URL = f"{BASE}/bf6/status/"
TAKT = timedelta(minutes=15)


def _calls(aioclient_mock, url: str) -> int:
    return sum(1 for c in aioclient_mock.mock_calls if str(c[1]).startswith(url))


async def _setup(hass: HomeAssistant, players: int = 1):
    entry = main_entry(
        *(
            player_subentry(PERSONA_ID + i, 2000000001 + i, name=f"Spieler{i}")
            for i in range(players)
        )
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, unique_id: str, domain: str = "sensor"):
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    return hass.states.get(entity_id)


async def test_limit_holds_at_start_in_operation_and_refresh(
    hass: HomeAssistant, aioclient_mock, freezer
):
    """6 Spieler: nie mehr als PARALLEL_REQUESTS Abfragen gleichzeitig."""
    laufend = {"jetzt": 0, "max": 0}

    async def langsam(method, url, data):
        laufend["jetzt"] += 1
        laufend["max"] = max(laufend["max"], laufend["jetzt"])
        # Mehrmals an die Ereignisschleife abgeben, damit andere Abfragen
        # starten koennten (echtes sleep steht unter freezegun still).
        for _ in range(50):
            await asyncio.sleep(0)
        laufend["jetzt"] -= 1
        return AiohttpClientMockResponse(method, url, json=STATS)

    aioclient_mock.get(STATS_URL, side_effect=langsam)
    await _setup(hass, players=6)
    assert _calls(aioclient_mock, STATS_URL) == 6
    beobachtet = [laufend["max"]]

    laufend["max"] = 0
    freezer.tick(TAKT + timedelta(seconds=1))
    async_fire_time_changed(hass)
    # Der Takt laeuft als Hintergrund-Task; wegen des Limits warten 4 davon.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _calls(aioclient_mock, STATS_URL) == 12
    beobachtet.append(laufend["max"])

    laufend["max"] = 0
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert _calls(aioclient_mock, STATS_URL) == 18
    beobachtet.append(laufend["max"])

    # Start, Takt, Aktion; bis 0.6.7: [2, 6, 6]
    assert beobachtet == [PARALLEL_REQUESTS] * 3


async def test_refresh_is_debounced(hass: HomeAssistant, aioclient_mock, freezer):
    """Zwei Aufrufe in 10 s: einer sofort, der zweite am Ende der Abklingzeit."""
    aioclient_mock.get(STATS_URL, json=STATS)
    await _setup(hass)
    assert _calls(aioclient_mock, STATS_URL) == 1
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert _calls(aioclient_mock, STATS_URL) == 2
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert _calls(aioclient_mock, STATS_URL) == 2
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Die beiden gesperrten Aufrufe ergeben zusammen eine Abfrage
    assert _calls(aioclient_mock, STATS_URL) == 3


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("120", 120.0),
        (" 0 ", 0.0),
        ("Mon, 02 Nov 2026 12:10:00 GMT", 600.0),
        # Datum in der Vergangenheit: sofort
        ("Mon, 02 Nov 2026 11:00:00 GMT", 0.0),
        ("-5", None),
        ("bald", None),
        ("", None),
        (None, None),
    ],
)
def test_retry_after_header(header, expected) -> None:
    now = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    assert header_seconds(header, now) == expected


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        # Kuerzer als der Takt: nicht oefter als eingestellt abfragen
        (GametoolsRateLimited("/x", 5), TAKT.total_seconds()),
        (GametoolsRateLimited("/x", 3600), 3600),
        (GametoolsRateLimited("/x", 10**9), RETRY_AFTER_MAX_SECONDS),
        (GametoolsRateLimited("/x"), None),
        (GametoolsError("/x"), None),
    ],
)
def test_retry_after_bounds(err, expected) -> None:
    assert retry_after(err, TAKT) == expected


async def test_rate_limit_waits_for_retry_after(
    hass: HomeAssistant, aioclient_mock, freezer
):
    aioclient_mock.get(STATS_URL, status=429, headers={"Retry-After": "3600"})
    await _setup(hass)
    assert _calls(aioclient_mock, STATS_URL) == 1
    assert _state(hass, f"{PERSONA_ID}-kills").state == STATE_UNAVAILABLE
    # Nach dem normalen Takt von 15 min noch keine neue Abfrage ...
    freezer.tick(TAKT + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _calls(aioclient_mock, STATS_URL) == 1
    # ... erst nach einer Stunde
    freezer.tick(timedelta(minutes=45))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _calls(aioclient_mock, STATS_URL) == 2


async def test_rate_limit_without_header_keeps_interval(
    hass: HomeAssistant, aioclient_mock, freezer
):
    aioclient_mock.get(STATS_URL, status=429)
    await _setup(hass)
    freezer.tick(TAKT + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _calls(aioclient_mock, STATS_URL) == 2


async def test_parse_error_makes_player_unavailable(
    hass: HomeAssistant, aioclient_mock
):
    """Scheitert die Auswertung doch, wirkt das wie ein API-Fehler."""
    aioclient_mock.get(STATS_URL, json=STATS)
    with patch(
        "custom_components.bf6_player.coordinator.parsers.player_stats",
        side_effect=ValueError("kaputt"),
    ):
        entry = await _setup(hass)
    assert _state(hass, f"{PERSONA_ID}-kills").state == STATE_UNAVAILABLE
    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    assert "ValueError" in str(coordinator.last_exception)


async def test_season_parse_error_keeps_portal(hass: HomeAssistant, aioclient_mock):
    """Bis 0.6.7 riss ein Fehler in parsers.season die Portal-Daten mit."""
    with patch(
        "custom_components.bf6_player.coordinator.parsers.season",
        side_effect=ValueError("year 56791 is out of range"),
    ):
        entry = await _setup(hass, players=0)
    servers = _state(hass, f"{entry.entry_id}-world-portal_servers")
    assert servers.state == "1000"
    assert _state(hass, f"{entry.entry_id}-world-season_end").state == "unknown"
