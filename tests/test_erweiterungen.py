"""Erweiterungen aus dem Review (0.7.0): E1, E2, E4.

E1: Top-Gadget und Portal-Warteschlange; beide wurden seit 0.5.0/0.6.0
ausgewertet, aber nirgends ausgegeben (Review B20).
E2: Dog Tags, Abzeichen und Ranked-Rang als eigene Sensoren. Dog Tags und
Abzeichen sind total_increasing; ein Rueckgang gilt wie bei den Zaehlern der
Statistik erst, wenn die naechste Abfrage ihn bestaetigt.
E4: Blueprints fuer "Match beendet" und "Rang gestiegen". Sie verwerfen
Zustandswechsel ohne Zustand davor (Start) und von "unavailable" (Neuladen);
dafuer kommt ein nachgeholtes Ereignis seit 0.7.0 erst nach dem ersten
Zustand der Ereignis-Entitaet.
"""

import copy
import json
from datetime import timedelta
from pathlib import Path

import pytest
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as yaml_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.bf6_player import parsers
from custom_components.bf6_player.baseline import STORE_VERSION
from custom_components.bf6_player.const import DOMAIN
from custom_components.bf6_player.sensor import Bf6Sensor

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
REPO = Path(__file__).parent.parent
BLUEPRINTS = REPO / "blueprints" / "automation" / "bf6_player"
MATCH_BP = "bf6_match_finished_notify.yaml"
RANK_BP = "bf6_rank_up_notify.yaml"
MATCH_EVENT = "event.testspieler_match_finished"
RANK_EVENT = "event.testspieler_rank_up"
NOTIFY = "bf6_test_notify"


def _sensor(hass: HomeAssistant, key: str) -> State | None:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"1000000001-{key}"
    )
    return hass.states.get(entity_id) if entity_id else None


def _profile(dog_tags: int | None = 12, badges: int | None = 7, rank: int = 42):
    data = copy.deepcopy(PROFILE)
    profile = data["playerProfiles"][0]
    profile["totalDogTags"]["intValue"] = dog_tags
    profile["badgeSummary"]["totalBadges"] = badges
    profile["playerCard"]["rank"] = rank
    return data


def _stats(**changes):
    data = copy.deepcopy(STATS)
    for key, value in changes.items():
        data[key] += value
    return data


def _store(entry, **werte) -> dict:
    """Gespeicherte Vergleichsbasis wie nach 0.6.13/0.7.0."""
    subentry_id = next(iter(entry.subentries))
    stats = {
        "matches": 50,
        "wins": 30,
        "losses": 20,
        "kills": 1000,
        "deaths": 400,
        "assists": 300,
        "revives": 120,
        "xp": 500000,
        "seconds_played": 54000,
    }
    stats.update(werte.pop("stats", {}))
    return {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {
            subentry_id: {
                "stats": stats,
                "rank": 42,
                "at": "2026-11-02T20:00:00+00:00",
                **werte,
            }
        },
    }


async def _setup(hass, aioclient_mock, entry=None, profile=None):
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=STATS)
    aioclient_mock.get(PROFILE_URL, json=profile or PROFILE)
    mock_world(aioclient_mock)
    entry = entry or main_entry(player_subentry())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _next(hass, aioclient_mock, freezer, stats=None, profile=None, minutes=15):
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=stats or STATS)
    aioclient_mock.get(PROFILE_URL, json=profile or PROFILE)
    mock_world(aioclient_mock)
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


# --- E1 ----------------------------------------------------------------------


async def test_top_gadget(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock)
    state = _sensor(hass, "top_gadget")
    assert state.state == "Werfer"
    assert state.attributes["top"] == [
        {"name": "Werfer", "type": "Launchers", "kills": 12, "image": None}
    ]


def test_gadgets_without_kills_are_not_listed():
    """Wie Waffen und Fahrzeuge nach Kills; beim Beispielkonto der API am
    03.11.2026 hatten alle vier Gadgets 0 Kills (Leiter, Raketenwerfer ...)."""
    data = copy.deepcopy(STATS)
    data["gadgets"] = [
        {"type": "Deployable Gadgets", "gadgetName": "Leiter", "kills": 0},
        {"type": "Launchers", "gadgetName": "Werfer", "kills": 3},
    ]
    assert [g["name"] for g in parsers.player_stats(data)["gadgets"]] == ["Werfer"]
    data["gadgets"][1]["kills"] = 0
    assert parsers.player_stats(data)["gadgets"] == []


async def test_portal_queue(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock)
    state = hass.states.get("sensor.bf6_world_portal_queue")
    assert state.state == "3"
    assert state.attributes["state_class"] == "measurement"


# --- E2 ----------------------------------------------------------------------


async def test_profile_sensors(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock)
    for key, wert in (("dog_tags", "12"), ("badges", "7")):
        state = _sensor(hass, key)
        assert state.state == wert
        assert state.attributes["state_class"] == "total_increasing"
    ranked = _sensor(hass, "ranked_rank")
    assert ranked.state == "Unranked"
    assert ranked.attributes["season"] == "CompetitiveSeason5"
    assert ranked.attributes["mode"] == "Redsec Quads"
    assert ranked.attributes["ranked"] == [
        {"season": "CompetitiveSeason5", "mode": "Redsec Quads", "rank": "Unranked"}
    ]
    # Die Attribute am Rang bleiben fuer bestehende Vorlagen und Karten
    rank = _sensor(hass, "rank")
    assert rank.attributes["dog_tags"] == 12
    assert rank.attributes["badges"] == 7
    assert rank.attributes["ranked"] == ranked.attributes["ranked"]
    # Listen nicht in die Datenbank
    assert {"ranked", "top"} <= Bf6Sensor._unrecorded_attributes


async def test_private_profile(hass: HomeAssistant, aioclient_mock):
    """Die verkuerzte Antwort hat keine Dog Tags, Abzeichen und Ranked-Raenge."""
    await _setup(hass, aioclient_mock, profile=PROFILE_REDUZIERT)
    for key in ("dog_tags", "badges", "ranked_rank"):
        assert _sensor(hass, key).state == STATE_UNKNOWN
    assert _sensor(hass, "rank").state == "77"


async def test_profile_drop_held_until_confirmed(
    hass: HomeAssistant, aioclient_mock, freezer, caplog
):
    await _setup(hass, aioclient_mock)
    # Profil stuendlich: Abzeichen 7 -> 0 wird einmal gehalten
    await _next(hass, aioclient_mock, freezer, profile=_profile(badges=0), minutes=60)
    assert _sensor(hass, "badges").state == "7"
    assert _sensor(hass, "dog_tags").state == "12"
    assert "badges gesunken" in caplog.text
    # Die naechste Profilabfrage bestaetigt den Rueckgang
    await _next(hass, aioclient_mock, freezer, profile=_profile(badges=0), minutes=60)
    assert _sensor(hass, "badges").state == "0"
    assert "Rueckgang von badges bestaetigt" in caplog.text


async def test_profile_drop_outlier_is_dropped(
    hass: HomeAssistant, aioclient_mock, freezer
):
    """Ein einzelner Ausreisser kommt nie im Sensor an."""
    await _setup(hass, aioclient_mock)
    await _next(hass, aioclient_mock, freezer, profile=_profile(dog_tags=0), minutes=60)
    await _next(
        hass, aioclient_mock, freezer, profile=_profile(dog_tags=13), minutes=60
    )
    assert _sensor(hass, "dog_tags").state == "13"
    # Danach wieder gehalten, nicht als Bestaetigung des alten Rueckgangs
    await _next(hass, aioclient_mock, freezer, profile=_profile(dog_tags=1), minutes=60)
    assert _sensor(hass, "dog_tags").state == "13"


async def test_profile_drop_across_private_profile(
    hass: HomeAssistant, aioclient_mock, freezer
):
    """Ein privates Profil dazwischen loescht den letzten bekannten Wert nicht."""
    await _setup(hass, aioclient_mock)
    await _next(hass, aioclient_mock, freezer, profile=PROFILE_REDUZIERT, minutes=60)
    assert _sensor(hass, "dog_tags").state == STATE_UNKNOWN
    await _next(hass, aioclient_mock, freezer, profile=_profile(dog_tags=5), minutes=60)
    assert _sensor(hass, "dog_tags").state == "12"


async def test_profile_drop_against_stored_state(
    hass: HomeAssistant, aioclient_mock, hass_storage
):
    """Nach dem Start vergleicht das erste Profil mit dem gespeicherten Stand."""
    entry = main_entry(player_subentry())
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _store(entry, dog_tags=20, badges=7)
    await _setup(hass, aioclient_mock, entry)
    assert _sensor(hass, "dog_tags").state == "20"
    assert _sensor(hass, "badges").state == "7"


async def test_store_without_profile_counters(
    hass: HomeAssistant, aioclient_mock, hass_storage
):
    """Gespeicherter Stand von 0.6.13 (ohne Dog Tags, Abzeichen) bleibt gueltig."""
    entry = main_entry(player_subentry())
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _store(entry)
    await _setup(hass, aioclient_mock, entry)
    assert _sensor(hass, "dog_tags").state == "12"
    assert _sensor(hass, "kills").state == "1000"


# --- Nachgeholtes Ereignis nach dem ersten Zustand -------------------------


async def test_catch_up_event_after_first_state(
    hass: HomeAssistant, aioclient_mock, hass_storage
):
    """Bis 0.6.13 war das nachgeholte Ereignis der erste Zustand der Entitaet
    (ohne Zustand davor), wie ein nur wiederhergestelltes altes Ereignis."""
    wechsel: list[tuple[str | None, str]] = []

    def merken(event) -> None:
        if event.data["entity_id"] == MATCH_EVENT:
            alt = event.data["old_state"]
            wechsel.append((alt.state if alt else None, event.data["new_state"].state))

    hass.bus.async_listen(EVENT_STATE_CHANGED, merken)
    entry = main_entry(player_subentry())
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _store(
        entry, stats={"matches": 49, "wins": 29, "kills": 980, "deaths": 390}
    )
    await _setup(hass, aioclient_mock, entry)
    assert len(wechsel) == 2
    assert wechsel[0] == (None, STATE_UNKNOWN)
    assert wechsel[1][0] == STATE_UNKNOWN
    assert hass.states.get(MATCH_EVENT).attributes["matches"] == 1


# --- E4: Blueprints ----------------------------------------------------------


@pytest.mark.parametrize("name", [MATCH_BP, RANK_BP])
def test_blueprint_valid(name: str):
    path = BLUEPRINTS / name
    blueprint = Blueprint(
        yaml_util.load_yaml(str(path)),
        path=str(path),
        expected_domain="automation",
        schema=BLUEPRINT_SCHEMA,
    )
    meta = blueprint.metadata
    assert meta["source_url"].endswith(
        f"/blob/main/blueprints/automation/bf6_player/{name}"
    )
    # Nicht neuer als die Mindestversion der Integration (hacs.json)
    mindest = json.loads((REPO / "hacs.json").read_text())["homeassistant"]
    assert tuple(map(int, meta["homeassistant"]["min_version"].split("."))) <= tuple(
        map(int, mindest.split("."))
    )
    # Aktion wie im Blueprint "Zone Notification" von Home Assistant
    aktion = blueprint.data["actions"][0]
    assert (aktion["domain"], aktion["type"]) == ("mobile_app", "notify")
    assert set(aktion) == {"alias", "domain", "type", "device_id", "title", "message"}


def _testkopie(name: str) -> str:
    """Blueprint mit Ereignis statt App-Benachrichtigung.

    Trigger, Variablen, Bedingungen und die Texte bleiben unveraendert; nur
    die Aktion von mobile_app wird ein Ereignis mit Titel und Text. Die
    Integration mobile_app laesst sich in den Tests nicht laden (sie braucht
    turbojpeg und PyNaCl).
    """
    text = (BLUEPRINTS / name).read_text(encoding="utf-8")
    aktion = yaml_util.load_yaml(str(BLUEPRINTS / name))["actions"][0]
    kopf = text[: text.index("\nactions:")]
    return (
        f"{kopf}\nactions:\n"
        f"  - event: {NOTIFY}\n"
        "    event_data:\n"
        "      device: !input notify_device\n"
        f"      title: {json.dumps(aktion['title'], ensure_ascii=False)}\n"
        f"      message: {json.dumps(aktion['message'], ensure_ascii=False)}\n"
    )


async def _automation(hass: HomeAssistant, tmp_path: Path, name: str, **inputs):
    ziel = tmp_path / "blueprints" / "automation" / "bf6_player"
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / name).write_text(_testkopie(name), encoding="utf-8")
    hass.config.config_dir = str(tmp_path)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": f"bf6_player/{name}",
                    "input": {"notify_device": "geraet", **inputs},
                }
            }
        },
    )
    await hass.async_block_till_done()
    nachrichten: list[dict] = []
    hass.bus.async_listen(NOTIFY, lambda event: nachrichten.append(dict(event.data)))
    return nachrichten


def _alt(entity_id: str, event_type: str, attributes: dict):
    """Wiederhergestelltes letztes Ereignis wie nach einem Neustart."""
    return (
        State(
            entity_id,
            "2026-11-02T19:00:00.000+00:00",
            {"event_type": event_type, "event_types": [event_type], **attributes},
        ),
        {"last_event_type": event_type, "last_event_attributes": attributes},
    )


async def test_match_blueprint_after_restart(
    hass: HomeAssistant, aioclient_mock, hass_storage, tmp_path
):
    """Neustart mit einem Match dazwischen: genau eine Nachricht, nicht fuer
    das wiederhergestellte alte Ereignis."""
    mock_restore_cache_with_extra_data(
        hass, [_alt(MATCH_EVENT, "match_finished", {"matches": 1, "kills": 5})]
    )
    nachrichten = await _automation(hass, tmp_path, MATCH_BP, match_event=[MATCH_EVENT])
    entry = main_entry(player_subentry())
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _store(
        entry, stats={"matches": 49, "wins": 29, "kills": 980, "deaths": 390}
    )
    await _setup(hass, aioclient_mock, entry)
    assert nachrichten == [
        {
            "device": "geraet",
            "title": "BF6: Testspieler",
            "message": "Sieg: 20 Kills, 10 Tode, K/D 2.0",
        }
    ]


async def test_match_blueprint_no_message_for_restored_state(
    hass: HomeAssistant, aioclient_mock, hass_storage, freezer, tmp_path
):
    """Neustart und Neuladen ohne neues Match: keine Nachricht."""
    mock_restore_cache_with_extra_data(
        hass, [_alt(MATCH_EVENT, "match_finished", {"matches": 1, "kills": 5})]
    )
    nachrichten = await _automation(hass, tmp_path, MATCH_BP, match_event=[MATCH_EVENT])
    entry = main_entry(player_subentry())
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _store(entry)
    await _setup(hass, aioclient_mock, entry)
    assert hass.states.get(MATCH_EVENT).attributes["kills"] == 5
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await _next(hass, aioclient_mock, freezer)
    assert nachrichten == []


async def test_match_blueprint_in_operation(
    hass: HomeAssistant, aioclient_mock, freezer, tmp_path
):
    nachrichten = await _automation(hass, tmp_path, MATCH_BP, match_event=[MATCH_EVENT])
    await _setup(hass, aioclient_mock)
    assert nachrichten == []
    # Niederlage
    await _next(
        hass,
        aioclient_mock,
        freezer,
        _stats(matchesPlayed=1, loses=1, kills=7, deaths=14),
    )
    # Zwei Matches zwischen zwei Abfragen, ohne Tode: K/D leer
    await _next(
        hass,
        aioclient_mock,
        freezer,
        _stats(matchesPlayed=3, loses=1, wins=1, kills=10, deaths=14),
    )
    assert [n["message"] for n in nachrichten] == [
        "Niederlage: 7 Kills, 14 Tode, K/D 0.5",
        "2 Matches: 3 Kills, 0 Tode, K/D –",
    ]


async def test_match_blueprint_only_wins(
    hass: HomeAssistant, aioclient_mock, freezer, tmp_path
):
    nachrichten = await _automation(
        hass, tmp_path, MATCH_BP, match_event=[MATCH_EVENT], only_wins=True
    )
    await _setup(hass, aioclient_mock)
    await _next(hass, aioclient_mock, freezer, _stats(matchesPlayed=1, loses=1))
    await _next(
        hass, aioclient_mock, freezer, _stats(matchesPlayed=2, loses=1, wins=1, kills=4)
    )
    assert [n["message"] for n in nachrichten] == ["Sieg: 4 Kills, 0 Tode, K/D –"]


async def test_match_blueprint_ignores_other_event_type(
    hass: HomeAssistant, aioclient_mock, freezer, tmp_path
):
    """Falsch ausgewaehlte Entitaet "Rang gestiegen": keine Nachricht."""
    nachrichten = await _automation(hass, tmp_path, MATCH_BP, match_event=[RANK_EVENT])
    await _setup(hass, aioclient_mock)
    await _next(hass, aioclient_mock, freezer, profile=_profile(rank=43), minutes=60)
    assert hass.states.get(RANK_EVENT).attributes["rank"] == 43
    assert nachrichten == []


async def test_rank_blueprint(hass: HomeAssistant, aioclient_mock, freezer, tmp_path):
    nachrichten = await _automation(hass, tmp_path, RANK_BP, rank_event=[RANK_EVENT])
    await _setup(hass, aioclient_mock)
    await _next(hass, aioclient_mock, freezer, profile=_profile(rank=43), minutes=60)
    assert nachrichten == [
        {
            "device": "geraet",
            "title": "BF6: Testspieler",
            "message": "Rang 43 (Testrang) erreicht, vorher Rang 42",
        }
    ]


async def test_rank_blueprint_after_restart(
    hass: HomeAssistant, aioclient_mock, hass_storage, tmp_path
):
    mock_restore_cache_with_extra_data(
        hass,
        [_alt(RANK_EVENT, "rank_up", {"previous_rank": 40, "rank": 41})],
    )
    nachrichten = await _automation(hass, tmp_path, RANK_BP, rank_event=[RANK_EVENT])
    entry = main_entry(player_subentry())
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _store(entry, rank=41)
    await _setup(hass, aioclient_mock, entry)
    assert [n["message"] for n in nachrichten] == [
        "Rang 42 (Testrang) erreicht, vorher Rang 41"
    ]
