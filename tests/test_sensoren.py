"""Tests fuer Geraet, Sensoren und Abfrage je Spieler (0.4.0)."""

import json
from datetime import timedelta
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bf6_player.const import DOMAIN, PLATFORM_ICONS, PLATFORM_NAMES
from custom_components.bf6_player.sensor import SENSORS, WORLD_SENSORS, Bf6Sensor

from .conftest import (
    PROFILE,
    PROFILE_REDUZIERT,
    STATS,
    STATS_EMPTY,
    device_of,
    main_entry,
    mock_world,
    player_subentry,
)

BASE = "https://api.gametools.network"
STATS_URL = f"{BASE}/bf6/stats/"
PROFILE_URL = f"{BASE}/bf6/profile/"
INTEGRATION = Path(__file__).parents[1] / "custom_components" / "bf6_player"


async def _setup(hass: HomeAssistant, *players: ConfigSubentryData) -> MockConfigEntry:
    entry = main_entry(*(players or (player_subentry(),)))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, key: str, persona_id: int = 1000000001):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{persona_id}-{key}"
    )
    assert entity_id, key
    return hass.states.get(entity_id)


def _mock(aioclient_mock: AiohttpClientMocker, stats=STATS, profile=PROFILE):
    aioclient_mock.get(STATS_URL, json=stats)
    aioclient_mock.get(PROFILE_URL, json=profile)
    mock_world(aioclient_mock)


async def test_sensor_values(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    _mock(aioclient_mock)
    await _setup(hass)
    expected = {
        "kills": "1000",
        "deaths": "400",
        "assists": "300",
        "revives": "120",
        "matches": "50",
        "wins": "30",
        "losses": "20",
        "xp": "500000",
        "time_played": "15.0",  # 54000 s als Stunden
        "kd": "2.5",
        "kpm": "1.11",
        "win_rate": "60.0",
        "accuracy": "25.0",
        "headshot_rate": "15.0",
        "human_kill_rate": "80.0",
        "rank": "42",
        "favorite_class": "Support",
        "top_weapon": "Karabiner B",
        "top_vehicle": "Panzer",
        "platform": "ea",
    }
    for key, value in expected.items():
        assert _state(hass, key).state == value, key
    assert _state(hass, "time_played").attributes["unit_of_measurement"] == "h"
    assert _state(hass, "win_rate").attributes["unit_of_measurement"] == "%"
    assert _state(hass, "kills").attributes["state_class"] == "total_increasing"
    assert _state(hass, "kd").attributes["state_class"] == "measurement"
    rank = _state(hass, "rank").attributes
    assert rank["rank_name"] == "Testrang"
    assert rank["dog_tags"] == 12
    assert rank["badges"] == 7
    assert rank["rank_image"] == "https://cdn.gametools.network/ranks/bf6/r_lg.png"
    top = _state(hass, "top_weapon").attributes["top"]
    assert [w["name"] for w in top] == [
        "Karabiner B",
        "Gewehr A",
        "MP 5",
        "MP 4",
        "MP 3",
    ]
    # Abgefragt per ID und mit Zahlen statt "50%"
    query = next(
        c[1] for c in aioclient_mock.mock_calls if str(c[1]).startswith(STATS_URL)
    ).query
    assert query["playerid"] == "1000000001"
    assert query["format_values"] == "false"


async def test_device(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    _mock(aioclient_mock)
    entry = await _setup(hass)
    device = device_of(hass, "1000000001-kills")
    assert (DOMAIN, "1000000001") in device.identifiers
    assert device.name == "Testspieler"
    assert device.manufacturer == "Electronic Arts"
    assert device.model == "Battlefield 6 · EA app"
    subentry_id = next(iter(entry.subentries))
    entities = er.async_entries_for_device(er.async_get(hass), device.id)
    # Sensoren, Plattform, Rang-Abzeichen, zwei Ereignisse
    assert len(entities) == len(SENSORS) + 1 + 1 + 2
    assert {e.config_subentry_id for e in entities} == {subentry_id}


async def test_api_error_makes_player_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(STATS_URL, status=500)
    mock_world(aioclient_mock)
    await _setup(hass)
    assert _state(hass, "kills").state == STATE_UNAVAILABLE
    # Die Plattform ist gespeichert und bleibt sichtbar
    assert _state(hass, "platform").state == "ea"


async def test_no_results_makes_player_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    _mock(aioclient_mock, stats=STATS_EMPTY)
    await _setup(hass)
    assert _state(hass, "kd").state == STATE_UNAVAILABLE


async def test_one_player_fails_other_stays(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(
        STATS_URL,
        params={
            "playerid": "1000000002",
            "nucleus_id": "2000000002",
            "platform": "steam",
            "format_values": "false",
            "seperation": "false",
        },
        status=500,
    )
    _mock(aioclient_mock)
    await _setup(
        hass, player_subentry(), player_subentry(1000000002, 2000000002, "steam")
    )
    assert _state(hass, "kills").state == "1000"
    assert _state(hass, "kills", 1000000002).state == STATE_UNAVAILABLE


async def test_profile_failure_keeps_stats(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(STATS_URL, json=STATS)
    aioclient_mock.get(PROFILE_URL, status=500)
    mock_world(aioclient_mock)
    await _setup(hass)
    assert _state(hass, "kills").state == "1000"
    assert _state(hass, "rank").state == STATE_UNKNOWN


async def test_private_profile_rank(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Privates Konto (0.6.5): Statistik voll, Profil verkuerzt; Rang,
    Rangname und Rang-Abzeichen kommen trotzdem, Dog Tags und Abzeichen
    bleiben leer."""
    _mock(aioclient_mock, profile=PROFILE_REDUZIERT)
    await _setup(hass)
    assert _state(hass, "kills").state == "1000"
    rank = _state(hass, "rank")
    assert rank.state == "77"
    assert rank.attributes["rank_name"] == "Testoberst"
    assert rank.attributes["dog_tags"] is None
    assert rank.attributes["badges"] is None
    assert rank.attributes["ranked"] == []
    entity_id = er.async_get(hass).async_get_entity_id(
        "image", DOMAIN, "1000000001-rank_badge"
    )
    image = hass.data["entity_components"]["image"].get_entity(entity_id)
    assert image.badge_url == "https://cdn.gametools.network/ranks/bf6/p_lg.png"


async def test_profile_only_hourly(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
):
    _mock(aioclient_mock)
    await _setup(hass)

    def calls(url: str) -> int:
        return sum(
            1 for call in aioclient_mock.mock_calls if str(call[1]).startswith(url)
        )

    assert (calls(STATS_URL), calls(PROFILE_URL)) == (1, 1)
    for _ in range(3):  # 15, 30, 45 Minuten
        freezer.tick(timedelta(minutes=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert (calls(STATS_URL), calls(PROFILE_URL)) == (4, 1)
    freezer.tick(timedelta(minutes=15))  # 60 Minuten
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (calls(STATS_URL), calls(PROFILE_URL)) == (5, 2)


async def test_new_player_reloads_rename_does_not(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    _mock(aioclient_mock)
    entry = await _setup(hass)
    loaded = entry.runtime_data
    subentry = next(iter(entry.subentries.values()))
    hass.config_entries.async_update_subentry(entry, subentry, title="Neuer Titel")
    await hass.async_block_till_done()
    assert entry.runtime_data is loaded

    from homeassistant.config_entries import ConfigSubentry

    hass.config_entries.async_add_subentry(
        entry, ConfigSubentry(**player_subentry(1000000002, 2000000002, "steam"))
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is not loaded
    assert _state(hass, "kills", 1000000002).state == "1000"


async def test_unload(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    _mock(aioclient_mock)
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, "kills").state == STATE_UNAVAILABLE


def test_lists_not_recorded() -> None:
    assert {
        "top",
        "ranked",
        "rank_image",
        "classes",
        "maps",
        "modes",
    } <= Bf6Sensor._unrecorded_attributes


async def test_lists_for_cards(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Listen fuer die Karten (seit 0.6.0) an "Matches" und "Lieblingsklasse"."""
    _mock(aioclient_mock)
    await _setup(hass)
    matches = _state(hass, "matches").attributes
    assert [m["name"] for m in matches["maps"]][:2] == ["Karte Eins", "Karte Zwei"]
    assert [m["name"] for m in matches["modes"]] == ["Conquest", "Rush"]
    classes = _state(hass, "favorite_class").attributes["classes"]
    assert [c["name"] for c in classes] == ["Support", "Assault"]
    for lang in ("en", "de"):
        text = json.loads((INTEGRATION / f"translations/{lang}.json").read_text())
        sensors = text["entity"]["sensor"]
        assert set(sensors["matches"]["state_attributes"]) == {"maps", "modes"}
        assert set(sensors["favorite_class"]["state_attributes"]) == {"classes"}


async def test_lists_empty_without_data(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Ohne Karten, Modi und Klassen leere Listen statt fehlender Attribute."""
    stats = {
        k: v for k, v in STATS.items() if k not in ("maps", "gameModes", "classes")
    }
    _mock(aioclient_mock, stats=stats)
    await _setup(hass)
    matches = _state(hass, "matches").attributes
    assert matches["maps"] == []
    assert matches["modes"] == []
    assert _state(hass, "favorite_class").attributes["classes"] == []


def test_icons_and_translations_match() -> None:
    """Jede Entitaet hat Name und Symbol; Plattformen in allen Listen gleich."""
    icons = json.loads((INTEGRATION / "icons.json").read_text())["entity"]["sensor"]
    keys = {d.key for d in SENSORS + WORLD_SENSORS} | {"platform"}
    assert set(icons) == keys
    for lang in ("en", "de"):
        text = json.loads((INTEGRATION / f"translations/{lang}.json").read_text())
        sensors = text["entity"]["sensor"]
        assert set(sensors) == keys, lang
        assert set(sensors["platform"]["state"]) == set(PLATFORM_NAMES), lang
    assert set(PLATFORM_ICONS) == set(PLATFORM_NAMES)
    state_icons = icons["platform"]["state"]
    for platform, icon in PLATFORM_ICONS.items():
        assert state_icons.get(platform, icons["platform"]["default"]) == icon
