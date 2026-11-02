"""Start ohne Warten auf eine haengende API und Schutz der Zaehler (0.6.9).

B2: Bis 0.6.8 wartete das Setup auf alle ersten Abfragen, bei haengender API
bis zu (Spieler + 1) / 2 x 30 s, und hielt damit den Start von Home Assistant
auf. Jetzt hoechstens FIRST_REFRESH_WAIT_SECONDS.

B4: Die Zaehler-Sensoren sind total_increasing. Ein einmaliger Rueckgang (z. B.
0 Kills) zaehlte Home Assistant als neuen Zyklus; kam danach der richtige Wert,
sprang die Summe der Langzeitstatistik um den ganzen Zaehlerstand.
"""

import asyncio
import copy
import logging
from datetime import timedelta
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.bf6_player.const import DOMAIN

from .conftest import (
    PERSONA_ID,
    PROFILE,
    STATS,
    main_entry,
    mock_world,
    player_subentry,
)

BASE = "https://api.gametools.network"
STATS_URL = f"{BASE}/bf6/stats/"
PROFILE_URL = f"{BASE}/bf6/profile/"


def _state(hass: HomeAssistant, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{PERSONA_ID}-{key}"
    )
    return hass.states.get(entity_id).state


async def _haengende_api(hass, aioclient_mock):
    """Stats-Abfrage, die erst antwortet, wenn das Ereignis gesetzt ist."""
    frei = asyncio.Event()
    frei.abgebrochen = False

    async def warten(method, url, data):
        try:
            await frei.wait()
        except asyncio.CancelledError:
            frei.abgebrochen = True
            raise
        return AiohttpClientMockResponse(method, url, json=STATS)

    aioclient_mock.get(STATS_URL, side_effect=warten)
    entry = main_entry(player_subentry())
    entry.add_to_hass(hass)
    with patch("custom_components.bf6_player.FIRST_REFRESH_WAIT_SECONDS", 0.05):
        # Bis 0.6.8 kehrte das Setup hier nie zurueck.
        assert await asyncio.wait_for(
            hass.config_entries.async_setup(entry.entry_id), timeout=5
        )
    return entry, frei


async def test_setup_does_not_wait_for_hanging_api(
    hass: HomeAssistant, aioclient_mock, caplog
):
    caplog.set_level(logging.INFO, logger="custom_components.bf6_player")
    entry, frei = await _haengende_api(hass, aioclient_mock)
    assert entry.state is ConfigEntryState.LOADED
    assert "1 von 2 ersten Abfragen nach 0.05 s noch offen" in caplog.text
    # Entitaeten sind angelegt, die Werte kommen nach
    assert _state(hass, "kills") == STATE_UNKNOWN
    frei.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, "kills") == "1000"


async def test_unload_cancels_pending_first_refresh(
    hass: HomeAssistant, aioclient_mock
):
    entry, frei = await _haengende_api(hass, aioclient_mock)
    assert await asyncio.wait_for(
        hass.config_entries.async_unload(entry.entry_id), timeout=5
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Die offene Abfrage gehoert zum Eintrag und endet mit ihm
    assert frei.abgebrochen


def _stats(**werte):
    data = copy.deepcopy(STATS)
    data.update(werte)
    return data


async def _setup(hass, aioclient_mock, stats):
    aioclient_mock.get(STATS_URL, json=stats)
    entry = main_entry(player_subentry())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _next(hass, aioclient_mock, freezer, stats):
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=stats)
    aioclient_mock.get(PROFILE_URL, json=PROFILE)
    mock_world(aioclient_mock)
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_single_drop_is_ignored(hass: HomeAssistant, aioclient_mock, freezer):
    """1000 -> 0 -> 1000 Kills: der Sensor bleibt bei 1000."""
    await _setup(hass, aioclient_mock, STATS)
    assert _state(hass, "kills") == "1000"
    await _next(hass, aioclient_mock, freezer, _stats(kills=0, deaths=0))
    # Bis 0.6.8: "0", danach wieder "1000" und die Summe +1000
    assert _state(hass, "kills") == "1000"
    assert _state(hass, "deaths") == "400"
    await _next(hass, aioclient_mock, freezer, STATS)
    assert _state(hass, "kills") == "1000"


async def test_confirmed_drop_is_taken(
    hass: HomeAssistant, aioclient_mock, freezer, caplog
):
    """Echter Ruecksetzer: zwei Abfragen in Folge unter dem alten Stand."""
    await _setup(hass, aioclient_mock, STATS)
    await _next(hass, aioclient_mock, freezer, _stats(kills=500))
    assert _state(hass, "kills") == "1000"
    assert "kills gesunken; Abfrage verworfen" in caplog.text
    await _next(hass, aioclient_mock, freezer, _stats(kills=510))
    assert _state(hass, "kills") == "510"
    assert "Rueckgang von kills bestaetigt" in caplog.text
    # Danach wieder normal: ein Anstieg gilt sofort
    await _next(hass, aioclient_mock, freezer, _stats(kills=520))
    assert _state(hass, "kills") == "520"


async def test_drop_does_not_fire_match_event(
    hass: HomeAssistant, aioclient_mock, freezer
):
    """Die verworfene Abfrage erzeugt kein Ereignis, auch wenn Matches steigen."""
    await _setup(hass, aioclient_mock, STATS)
    event_id = er.async_get(hass).async_get_entity_id(
        "event", DOMAIN, f"{PERSONA_ID}-match_finished"
    )
    await _next(
        hass, aioclient_mock, freezer, _stats(kills=0, matchesPlayed=51, wins=31)
    )
    assert hass.states.get(event_id).state == STATE_UNKNOWN
