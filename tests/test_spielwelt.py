"""Tests fuer das Geraet "BF6-Spielwelt" (0.5.0)."""

from datetime import timedelta

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.bf6_player.const import DOMAIN

from .conftest import EVENTS, STATUS, device_of, main_entry

BASE = "https://api.gametools.network"
EVENTS_URL = f"{BASE}/bf6/gameevents/"
STATUS_URL = f"{BASE}/bf6/status/"


async def _setup(hass):
    entry = main_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass, entry, key):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}-world-{key}"
    )
    return hass.states.get(entity_id)


async def test_world_sensors(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(EVENTS_URL, json=EVENTS)
    aioclient_mock.get(STATUS_URL, json=STATUS)
    entry = await _setup(hass)
    end = _state(hass, entry, "season_end")
    assert end.state == "2027-01-19T11:59:00+00:00"
    assert end.attributes["device_class"] == "timestamp"
    assert end.attributes["season"] == 5
    assert end.attributes["battle_pass"] == 5
    assert end.attributes["season_start"] == "2026-10-13T12:00:00+00:00"
    assert _state(hass, entry, "portal_servers").state == "1000"
    assert _state(hass, entry, "portal_players").state == "500"
    device = device_of(hass, f"{entry.entry_id}-world-portal_servers")
    assert (DOMAIN, f"{entry.entry_id}-world") in device.identifiers
    assert device.manufacturer == "Electronic Arts"


async def test_one_failure_keeps_other(hass, aioclient_mock):
    aioclient_mock.get(EVENTS_URL, status=500)
    aioclient_mock.get(STATUS_URL, json=STATUS)
    entry = await _setup(hass)
    assert _state(hass, entry, "portal_servers").state == "1000"
    assert _state(hass, entry, "season_end").state == "unknown"


async def test_both_fail(hass, aioclient_mock):
    aioclient_mock.get(EVENTS_URL, status=500)
    aioclient_mock.get(STATUS_URL, status=500)
    entry = await _setup(hass)
    assert _state(hass, entry, "portal_players").state == STATE_UNAVAILABLE


async def test_season_only_every_6_hours(hass, aioclient_mock, freezer):
    aioclient_mock.get(EVENTS_URL, json=EVENTS)
    aioclient_mock.get(STATUS_URL, json=STATUS)
    await _setup(hass)

    def calls(url):
        return sum(1 for c in aioclient_mock.mock_calls if str(c[1]).startswith(url))

    for _ in range(4):  # eine Stunde
        freezer.tick(timedelta(minutes=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert (calls(EVENTS_URL), calls(STATUS_URL)) == (1, 5)
    freezer.tick(timedelta(hours=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls(EVENTS_URL) == 2
