"""Spieler ohne Neuladen, Vergleichsbasis ueber Neustarts (0.6.13).

B9: Bis 0.6.12 lud jeder neue oder geloeschte Spieler den ganzen Eintrag neu;
alle Spieler und die Spielwelt wurden erneut abgefragt und die
Vergleichsbasis fuer die Ereignisse ging verloren.

E5: Bis 0.6.12 setzte die erste Abfrage nach einem Neustart nur den
Ausgangsstand; Matches und Rangaufstiege waehrend des Neustarts erzeugten
kein Ereignis. Jetzt liegt der letzte Stand in .storage/bf6_player.<entry_id>.
"""

import copy
from datetime import timedelta

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.bf6_player.baseline import SAVE_DELAY, STORE_VERSION
from custom_components.bf6_player.const import DOMAIN

from .conftest import PROFILE, STATS, main_entry, mock_world, player_subentry

BASE = "https://api.gametools.network"
STATS_URL = f"{BASE}/bf6/stats/"
PROFILE_URL = f"{BASE}/bf6/profile/"
STATUS_URL = f"{BASE}/bf6/status/"
ZWEITER = 1000000002


def _calls(aioclient_mock, url: str, playerid: int | None = None) -> int:
    return sum(
        1
        for c in aioclient_mock.mock_calls
        if str(c[1]).startswith(url)
        and (playerid is None or c[1].query.get("playerid") == str(playerid))
    )


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)


def _store_key(entry) -> str:
    return f"{DOMAIN}.{entry.entry_id}"


def _stand(entry, subentry_id: str, matches: int, rank: int | None, **zaehler):
    """Gespeicherter Stand wie aus baseline.py, Zaehler aus STATS."""
    stats = {
        "matches": matches,
        "wins": 30,
        "losses": 20,
        "kills": 1000,
        "deaths": 400,
        "assists": 300,
        "revives": 120,
        "xp": 500000,
        "seconds_played": 54000,
        **zaehler,
    }
    return {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": _store_key(entry),
        "data": {
            subentry_id: {
                "stats": stats,
                "rank": rank,
                "at": "2026-11-02T20:00:00+00:00",
            }
        },
    }


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _tick(hass: HomeAssistant, freezer, **kwargs) -> None:
    freezer.tick(timedelta(**kwargs))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


# --- B9: Spieler ohne Neuladen ----------------------------------------------


async def test_add_player_without_reload(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    await _setup(hass, entry)
    runtime = entry.runtime_data
    erster = next(iter(runtime.coordinators.values()))
    vorher = (_calls(aioclient_mock, STATS_URL), _calls(aioclient_mock, STATUS_URL))

    hass.config_entries.async_add_subentry(
        entry, ConfigSubentry(**player_subentry(ZWEITER, 2000000002, "steam"))
    )
    await hass.async_block_till_done()

    # Kein Neuladen: gleiche Laufzeitdaten, gleicher Coordinator des ersten
    assert entry.runtime_data is runtime
    assert erster in runtime.coordinators.values()
    # Abgefragt nur der neue Spieler, nicht der erste und nicht die Spielwelt
    assert _calls(aioclient_mock, STATS_URL) == vorher[0] + 1
    assert _calls(aioclient_mock, STATS_URL, ZWEITER) == 1
    assert _calls(aioclient_mock, STATUS_URL) == vorher[1]
    # Alle Entitaeten des neuen Spielers, mit Werten
    kills = _entity_id(hass, "sensor", f"{ZWEITER}-kills")
    assert hass.states.get(kills).state == "1000"
    assert _entity_id(hass, "event", f"{ZWEITER}-match_finished")
    assert _entity_id(hass, "event", f"{ZWEITER}-rank_up")
    assert _entity_id(hass, "image", f"{ZWEITER}-rank_badge")


async def test_remove_player_without_reload(
    hass: HomeAssistant, aioclient_mock, freezer, hass_storage
):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry(), player_subentry(ZWEITER, 2000000002, "steam"))
    await _setup(hass, entry)
    runtime = entry.runtime_data
    zweiter_id = next(
        sid
        for sid, sub in entry.subentries.items()
        if sub.data["persona_id"] == ZWEITER
    )
    await _tick(hass, freezer, seconds=SAVE_DELAY + 1)
    assert zweiter_id in hass_storage[_store_key(entry)]["data"]

    assert hass.config_entries.async_remove_subentry(entry, zweiter_id)
    await hass.async_block_till_done()

    assert entry.runtime_data is runtime
    assert zweiter_id not in runtime.coordinators
    assert _entity_id(hass, "sensor", f"{ZWEITER}-kills") is None
    # Der verbliebene Spieler laeuft weiter, der entfernte wird nicht mehr
    # abgefragt, sein gespeicherter Stand ist weg
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=STATS)
    aioclient_mock.get(PROFILE_URL, json=PROFILE)
    mock_world(aioclient_mock)
    await _tick(hass, freezer, minutes=15)
    # Die Abfrage plant das Speichern neu; danach die Verzoegerung abwarten
    await _tick(hass, freezer, seconds=SAVE_DELAY + 1)
    assert _calls(aioclient_mock, STATS_URL, 1000000001) == 1
    assert _calls(aioclient_mock, STATS_URL, ZWEITER) == 0
    assert zweiter_id not in hass_storage[_store_key(entry)]["data"]


async def test_options_still_reload(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    await _setup(hass, entry)
    runtime = entry.runtime_data
    hass.config_entries.async_update_entry(
        entry, options={"stats_interval": 30, "profile_interval": 60}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is not runtime
    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    assert coordinator.update_interval == timedelta(minutes=30)


# --- E5: Vergleichsbasis ueber Neustarts ------------------------------------


async def test_events_after_restart(hass: HomeAssistant, aioclient_mock, hass_storage):
    """Gespeichert: 49 Matches, Rang 41. Nach dem Start: 50 Matches, Rang 42."""
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    subentry_id = next(iter(entry.subentries))
    hass_storage[_store_key(entry)] = _stand(
        entry, subentry_id, 49, 41, wins=29, kills=980, deaths=390
    )
    await _setup(hass, entry)

    match = hass.states.get(_entity_id(hass, "event", "1000000001-match_finished"))
    assert match.state != STATE_UNKNOWN
    assert match.attributes["matches"] == 1
    assert match.attributes["kills"] == 20
    assert match.attributes["result"] == "win"
    assert match.attributes["since"] == "2026-11-02T20:00:00+00:00"
    rang = hass.states.get(_entity_id(hass, "event", "1000000001-rank_up"))
    assert rang.attributes["previous_rank"] == 41
    assert rang.attributes["rank"] == 42


async def test_no_event_without_change_after_restart(
    hass: HomeAssistant, aioclient_mock, hass_storage
):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    subentry_id = next(iter(entry.subentries))
    hass_storage[_store_key(entry)] = _stand(entry, subentry_id, 50, 42)
    await _setup(hass, entry)
    for key in ("match_finished", "rank_up"):
        state = hass.states.get(_entity_id(hass, "event", f"1000000001-{key}"))
        assert state.state == STATE_UNKNOWN


async def test_baseline_saved(
    hass: HomeAssistant, aioclient_mock, freezer, hass_storage
):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    subentry_id = next(iter(entry.subentries))
    await _setup(hass, entry)
    assert _store_key(entry) not in hass_storage  # erst nach SAVE_DELAY
    await _tick(hass, freezer, seconds=SAVE_DELAY + 1)
    gespeichert = hass_storage[_store_key(entry)]["data"][subentry_id]
    assert gespeichert["stats"]["matches"] == 50
    assert gespeichert["stats"]["kills"] == 1000
    assert gespeichert["rank"] == 42
    assert gespeichert["at"]
    # Nur Zahlen und Zeit, keine Namen oder IDs des Spielers
    assert set(gespeichert) == {"stats", "rank", "at"}


async def test_rank_kept_when_profile_fails(
    hass: HomeAssistant, aioclient_mock, freezer, hass_storage
):
    """Scheitert das Profil nach dem Start, bleibt der gespeicherte Rang."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=STATS)
    aioclient_mock.get(PROFILE_URL, status=500)
    mock_world(aioclient_mock)
    entry = main_entry(player_subentry())
    subentry_id = next(iter(entry.subentries))
    hass_storage[_store_key(entry)] = _stand(entry, subentry_id, 50, 41)
    await _setup(hass, entry)
    await _tick(hass, freezer, seconds=SAVE_DELAY + 1)
    assert hass_storage[_store_key(entry)]["data"][subentry_id]["rank"] == 41


async def test_damaged_store_is_ignored(
    hass: HomeAssistant, aioclient_mock, hass_storage
):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    subentry_id = next(iter(entry.subentries))
    hass_storage[_store_key(entry)] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": _store_key(entry),
        "data": {
            subentry_id: {"stats": {"matches": "viele", "kills": True}, "at": 5},
            "fremd": "kaputt",
        },
    }
    await _setup(hass, entry)
    kills = _entity_id(hass, "sensor", "1000000001-kills")
    assert hass.states.get(kills).state == "1000"
    state = hass.states.get(_entity_id(hass, "event", "1000000001-match_finished"))
    assert state.state == STATE_UNKNOWN


async def test_drop_against_stored_state(
    hass: HomeAssistant, aioclient_mock, freezer, hass_storage
):
    """Erste Abfrage nach dem Start unter dem gespeicherten Stand: einmal
    nicht verfuegbar statt eines Ausreissers in der Langzeitstatistik; die
    naechste Abfrage bestaetigt den Rueckgang."""
    wenig = copy.deepcopy(STATS)
    wenig["kills"] = 10
    aioclient_mock.get(STATS_URL, json=wenig)
    entry = main_entry(player_subentry())
    subentry_id = next(iter(entry.subentries))
    hass_storage[_store_key(entry)] = _stand(entry, subentry_id, 50, 42)
    await _setup(hass, entry)
    kills = _entity_id(hass, "sensor", "1000000001-kills")
    assert hass.states.get(kills).state == STATE_UNAVAILABLE
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=wenig)
    aioclient_mock.get(PROFILE_URL, json=PROFILE)
    mock_world(aioclient_mock)
    await _tick(hass, freezer, minutes=15)
    assert hass.states.get(kills).state == "10"


async def test_store_removed_with_entry(
    hass: HomeAssistant, aioclient_mock, freezer, hass_storage
):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    await _setup(hass, entry)
    await _tick(hass, freezer, seconds=SAVE_DELAY + 1)
    assert _store_key(entry) in hass_storage
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert _store_key(entry) not in hass_storage


async def test_no_duplicate_event_after_options_reload(
    hass: HomeAssistant, aioclient_mock, freezer, hass_storage
):
    """Match gemeldet, gleich danach Optionen geaendert (Neuladen vor dem
    verzoegerten Speichern): kein zweites "Match beendet"."""
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    await _setup(hass, entry)
    nachher = copy.deepcopy(STATS)
    nachher["matchesPlayed"] += 1
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=nachher)
    aioclient_mock.get(PROFILE_URL, json=PROFILE)
    mock_world(aioclient_mock)
    await _tick(hass, freezer, minutes=15)
    event_id = _entity_id(hass, "event", "1000000001-match_finished")
    gemeldet = hass.states.get(event_id).state
    assert gemeldet != STATE_UNKNOWN

    freezer.tick(timedelta(seconds=1))
    hass.config_entries.async_update_entry(
        entry, options={"stats_interval": 30, "profile_interval": 60}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.coordinators
    # Gleicher Zeitstempel: kein neues Ereignis nach dem Neuladen
    assert hass.states.get(event_id).state == gemeldet


async def test_store_not_recreated_after_removal(
    hass: HomeAssistant, aioclient_mock, freezer, hass_storage
):
    """Eintrag geloescht, waehrend ein verzoegertes Speichern ansteht: die
    Datei kommt danach nicht wieder."""
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = main_entry(player_subentry())
    await _setup(hass, entry)
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass, freezer, seconds=SAVE_DELAY * 3)
    assert _store_key(entry) not in hass_storage
