"""Tests fuer die Ereignisse "Match beendet" und "Rang gestiegen" (0.5.0)."""

import copy
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bf6_player import parsers
from custom_components.bf6_player.const import DOMAIN
from custom_components.bf6_player.coordinator import match_event, rank_event

from .conftest import (
    PROFILE,
    PROFILE_REDUZIERT,
    STATS,
    main_entry,
    mock_world,
    player_subentry,
)

BASE = "https://api.gametools.network"
STATS_URL = f"{BASE}/bf6/stats/"
PROFILE_URL = f"{BASE}/bf6/profile/"


def _after_match(**changes):
    """STATS nach einem Match; changes = Zuwachs je Feld der API."""
    data = copy.deepcopy(STATS)
    for key, value in changes.items():
        data[key] += value
    return data


def _event_id(hass: HomeAssistant, key: str) -> str:
    return er.async_get(hass).async_get_entity_id("event", DOMAIN, f"1000000001-{key}")


async def _setup(hass, aioclient_mock, *stats, profiles=(PROFILE,)):
    """Antworten der Reihe nach: erste beim Start, weitere je 15 Minuten."""
    entry = main_entry(player_subentry())
    entry.add_to_hass(hass)
    for answer in stats:
        aioclient_mock.get(STATS_URL, json=answer)
    for answer in profiles:
        aioclient_mock.get(PROFILE_URL, json=answer)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _next(hass, aioclient_mock, freezer, stats, profile=None, minutes=15):
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=stats)
    aioclient_mock.get(PROFILE_URL, json=profile or PROFILE)
    mock_world(aioclient_mock)
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_match_finished(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
):
    entry = await _setup(hass, aioclient_mock, STATS)
    entity_id = _event_id(hass, "match_finished")
    # Der Start setzt nur den Ausgangsstand, im Coordinator und in der Entitaet
    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    assert coordinator.events == []
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    after = _after_match(
        matchesPlayed=1,
        wins=1,
        kills=20,
        deaths=10,
        assists=5,
        revives=2,
        secondsPlayed=900,
    )
    after["XP"] = [{"total": 501000}]
    await _next(hass, aioclient_mock, freezer, after)
    state = hass.states.get(entity_id)
    assert state.state != STATE_UNKNOWN
    attrs = state.attributes
    assert attrs["event_type"] == "match_finished"
    assert attrs["matches"] == 1
    assert attrs["wins"] == 1
    assert attrs["losses"] == 0
    assert attrs["kills"] == 20
    assert attrs["deaths"] == 10
    assert attrs["kd"] == 2.0
    assert attrs["xp"] == 1000
    assert attrs["seconds_played"] == 900
    assert attrs["result"] == "win"


async def test_match_finished_without_xp(hass, aioclient_mock, freezer, caplog):
    """B10 im Ablauf: Antworten ohne XP, Ereignis kommt, Warnung nur einmal."""
    ohne = copy.deepcopy(STATS)
    del ohne["XP"]
    await _setup(hass, aioclient_mock, ohne)
    entity_id = _event_id(hass, "match_finished")
    eins = _after_match(matchesPlayed=1, wins=1, kills=20, deaths=10)
    del eins["XP"]
    await _next(hass, aioclient_mock, freezer, eins)
    attrs = hass.states.get(entity_id).attributes
    assert attrs["matches"] == 1
    assert attrs["kills"] == 20
    assert attrs["xp"] is None
    zwei = copy.deepcopy(eins)
    zwei["matchesPlayed"] += 1
    await _next(hass, aioclient_mock, freezer, zwei)
    assert hass.states.get(entity_id).attributes["matches"] == 1
    assert caplog.text.count("xp fehlen in der Antwort") == 1


async def test_no_event_without_new_match(hass, aioclient_mock, freezer):
    await _setup(hass, aioclient_mock, STATS)
    entity_id = _event_id(hass, "match_finished")
    await _next(hass, aioclient_mock, freezer, STATS)
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_failed_refresh_does_not_repeat_event(hass, aioclient_mock, freezer):
    await _setup(hass, aioclient_mock, STATS)
    entity_id = _event_id(hass, "match_finished")
    await _next(hass, aioclient_mock, freezer, _after_match(matchesPlayed=1, loses=1))
    first = hass.states.get(entity_id).state
    assert hass.states.get(entity_id).attributes["result"] == "loss"
    # Naechste Abfrage scheitert: kein zweites Ereignis
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, status=500)
    mock_world(aioclient_mock)
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == first


async def test_rank_up(hass, aioclient_mock, freezer):
    await _setup(hass, aioclient_mock, STATS)
    entity_id = _event_id(hass, "rank_up")
    higher = copy.deepcopy(PROFILE)
    higher["playerProfiles"][0]["playerCard"]["rank"] = 43
    higher["playerProfiles"][0]["rankName"] = "Neuer Rang"
    # Profil erst nach 60 Minuten wieder abgefragt
    await _next(hass, aioclient_mock, freezer, STATS, higher, minutes=60)
    attrs = hass.states.get(entity_id).attributes
    assert attrs["event_type"] == "rank_up"
    assert attrs["previous_rank"] == 42
    assert attrs["rank"] == 43
    assert attrs["rank_name"] == "Neuer Rang"


def test_match_event_rules() -> None:
    base = {
        k: 10
        for k in (
            "matches",
            "wins",
            "losses",
            "kills",
            "deaths",
            "assists",
            "revives",
            "xp",
            "seconds_played",
        )
    }
    two = {**base, "matches": 12, "wins": 11, "losses": 11}
    event = match_event(base, two)
    assert event["matches"] == 2
    assert event["result"] is None  # zwei Matches: kein einzelnes Ergebnis
    assert match_event(base, {**base, "kills": 15}) is None  # kein neues Match
    assert match_event(base, {**base, "matches": 11, "kills": 5}) is None  # sinkt
    assert match_event(base, {**base, "matches": None}) is None
    draw = match_event(base, {**base, "matches": 11})
    assert draw["result"] is None  # Match ohne Sieg und Niederlage


def test_match_event_without_side_counter() -> None:
    """B10: Fehlt ein Zaehler ausser matches, gibt es das Ereignis trotzdem;
    der fehlende Wert ist None (bis 0.6.10 fiel das Ereignis ganz aus)."""
    base = dict.fromkeys(
        (
            "matches",
            "wins",
            "losses",
            "kills",
            "deaths",
            "assists",
            "revives",
            "xp",
            "seconds_played",
        ),
        10,
    )
    ohne_xp = {**base, "xp": None}
    event = match_event(ohne_xp, {**ohne_xp, "matches": 11, "wins": 11, "kills": 14})
    assert event["xp"] is None
    assert event["matches"] == 1
    assert event["kills"] == 4
    assert event["result"] == "win"
    # Fehlen Kills oder Tode, gibt es kein K/D
    event = match_event(base, {**base, "matches": 11, "deaths": None})
    assert event["deaths"] is None
    assert event["kd"] is None
    # Nur in der neuen Abfrage vorhanden: kein Zuwachs bestimmbar
    event = match_event(ohne_xp, {**base, "matches": 11, "xp": 99})
    assert event["xp"] is None
    # Ein vorhandener Zaehler, der sinkt, verhindert das Ereignis weiterhin
    assert match_event(ohne_xp, {**ohne_xp, "matches": 11, "kills": 5}) is None


def test_rank_event_rules() -> None:
    assert rank_event({"rank": 5}, {"rank": 6, "rank_name": "x"})["rank"] == 6
    assert rank_event({"rank": 6}, {"rank": 6}) is None
    assert rank_event({"rank": 6}, {"rank": 5}) is None
    assert rank_event(None, {"rank": 6}) is None


def test_rank_event_private_profile() -> None:
    """Auch aus der verkuerzten Antwort eines privaten Kontos (0.6.5)."""
    vorher = parsers.player_profile(PROFILE_REDUZIERT)
    hoeher = copy.deepcopy(PROFILE_REDUZIERT)
    hoeher["other"][0]["playerProfiles"][0]["rank"] = 78
    event = rank_event(vorher, parsers.player_profile(hoeher))
    assert event == {"previous_rank": 77, "rank": 78, "rank_name": "Testoberst"}
