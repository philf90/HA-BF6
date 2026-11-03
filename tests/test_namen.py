"""Name eines Spielers (0.8.0): Abgleich mit der API (B12), Dialog "Neu
konfigurieren" (E6) und versionierte Migration (B13).

/bf6/stats/ liefert userName bei einer Abfrage ueber die IDs leer; der Name
kommt deshalb aus /bf6/player/?playerid=...&nucleus_id=... (displayName).
"""

import logging
from datetime import timedelta

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.bf6_player.const import DOMAIN, MAIN_TITLE, SUBENTRY_PLAYER
from custom_components.bf6_player.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import (
    PLAYER_BY_ID,
    PROFILE,
    STATS,
    device_of,
    mock_world,
    player_subentry,
)

BASE = "https://api.gametools.network"
STATS_URL = f"{BASE}/bf6/stats/"
PROFILE_URL = f"{BASE}/bf6/profile/"


def _antwort(name: str | None, persona_id: int = 1000000001) -> dict:
    """Antwort von /bf6/player/ ueber die IDs, Aufbau wie live am 03.11.2026."""
    return {
        "results": [
            {
                "personaId": str(persona_id),
                "nucleusId": "2000000001",
                "platform": "ea",
                "displayName": name,
                "username": name,
                "visibility": "EVERYONE",
                "status": "ACTIVE",
                "createdAt": "2015-03-01T10:00:00Z",
            },
            # Weiteres Konto derselben Nucleus-ID mit anderem Namen
            {
                "personaId": "1009999999",
                "nucleusId": "2000000001",
                "platform": "steam",
                "displayName": "Anderes Konto",
                "visibility": "EVERYONE",
            },
        ]
    }


def _mocks(aioclient_mock, players=None, status=200) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=STATS)
    aioclient_mock.get(PROFILE_URL, json=PROFILE)
    if status != 200:
        aioclient_mock.get(PLAYER_BY_ID, status=status)
    mock_world(aioclient_mock, players=players)


def _entry(*subentries, minor_version: int = 2, version: int = 1) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=MAIN_TITLE,
        unique_id=DOMAIN,
        data={},
        version=version,
        minor_version=minor_version,
        subentries_data=list(subentries),
    )


def _player(name="Testspieler", api_name="Testspieler", title=None, **kwargs):
    sub = player_subentry(name=name, **kwargs)
    if api_name is not None:
        sub["data"] = {**sub["data"], "api_name": api_name}
    sub["title"] = title or f"{name} · EA app"
    return sub


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _sub(entry):
    return next(iter(entry.subentries.values()))


def _device(hass: HomeAssistant):
    return device_of(hass, "1000000001-kills")


def _by_id_calls(aioclient_mock) -> int:
    return sum(1 for c in aioclient_mock.mock_calls if PLAYER_BY_ID.search(str(c[1])))


async def _tick(hass, freezer, **kwargs) -> None:
    freezer.tick(timedelta(**kwargs))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


# --- B13: Migration ----------------------------------------------------------


async def test_migration_to_1_2(hass: HomeAssistant, aioclient_mock):
    """1.1: Titel aus 0.3.0 bekommen die Plattform, CONF_API_NAME kommt dazu."""
    _mocks(aioclient_mock)
    alt = player_subentry(name="Alt")  # Titel "Alt" wie in 0.3.0
    umbenannt = player_subentry(1000000002, 2000000002, "psn", "Zweiter")
    umbenannt["title"] = "Mein Name"
    entry = _entry(alt, umbenannt, minor_version=1)
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert (entry.version, entry.minor_version) == (1, 2)
    subs = {sub.unique_id: sub for sub in entry.subentries.values()}
    assert subs["1000000001"].title == "Alt · EA app"
    assert subs["1000000002"].title == "Mein Name"
    assert subs["1000000001"].data["api_name"] == "Alt"
    assert subs["1000000002"].data["api_name"] == "Zweiter"


async def test_no_title_change_after_migration(hass: HomeAssistant, aioclient_mock):
    """Bis 0.7.1 lief die Titelumstellung bei jedem Start: Ein Titel, den man
    spaeter wieder auf den reinen Namen setzte, bekam erneut die Plattform."""
    _mocks(aioclient_mock)
    entry = _entry(_player(title="Testspieler"))
    await _setup(hass, entry)
    assert _sub(entry).title == "Testspieler"


async def test_unknown_newer_version(hass: HomeAssistant, aioclient_mock):
    _mocks(aioclient_mock)
    entry = _entry(_player(), version=2, minor_version=1)
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_flow_creates_current_version():
    from custom_components.bf6_player.config_flow import Bf6PlayerConfigFlow

    assert (Bf6PlayerConfigFlow.VERSION, Bf6PlayerConfigFlow.MINOR_VERSION) == (1, 2)


# --- B12: Abgleich mit der API ----------------------------------------------


async def test_name_follows_ea(hass: HomeAssistant, aioclient_mock, caplog):
    caplog.set_level(logging.INFO)
    _mocks(aioclient_mock, players=_antwort("Neuer Name"))
    entry = _entry(_player())
    await _setup(hass, entry)
    sub = _sub(entry)
    assert sub.data["name"] == "Neuer Name"
    assert sub.data["api_name"] == "Neuer Name"
    assert sub.title == "Neuer Name · EA app"
    assert _device(hass).name == "Neuer Name"
    # Abgefragt ueber beide IDs
    call = next(c for c in aioclient_mock.mock_calls if PLAYER_BY_ID.search(str(c[1])))
    assert call[1].query["playerid"] == "1000000001"
    assert call[1].query["nucleus_id"] == "2000000001"
    # Im Log die Persona-ID, kein Name
    assert "Spieler 1000000001: Name bei EA geaendert" in caplog.text
    assert "Neuer Name" not in caplog.text
    assert "Testspieler" not in caplog.text


async def test_rename_later_keeps_name_by_user(
    hass: HomeAssistant, aioclient_mock, freezer
):
    _mocks(aioclient_mock, players=_antwort("Testspieler"))
    entry = _entry(_player())
    await _setup(hass, entry)
    registry = dr.async_get(hass)
    registry.async_update_device(_device(hass).id, name_by_user="Mein Gerät")
    _mocks(aioclient_mock, players=_antwort("Neuer Name"))
    await _tick(hass, freezer, hours=24)
    device = _device(hass)
    assert device.name == "Neuer Name"
    assert device.name_by_user == "Mein Gerät"
    assert _sub(entry).title == "Neuer Name · EA app"
    # Entity-IDs bestehender Entitaeten bleiben
    kills = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "1000000001-kills")
    assert kills == "sensor.testspieler_kills"
    assert hass.states.get(kills).state == "1000"


async def test_custom_name_stays(hass: HomeAssistant, aioclient_mock):
    """Eigener Name (Dialog "Neu konfigurieren"): nur CONF_API_NAME folgt."""
    _mocks(aioclient_mock, players=_antwort("Neuer Name"))
    entry = _entry(_player(name="Eigener", api_name="Testspieler"))
    await _setup(hass, entry)
    sub = _sub(entry)
    assert sub.data["name"] == "Eigener"
    assert sub.data["api_name"] == "Neuer Name"
    assert sub.title == "Eigener · EA app"
    assert _device(hass).name == "Eigener"


async def test_custom_title_stays(hass: HomeAssistant, aioclient_mock):
    _mocks(aioclient_mock, players=_antwort("Neuer Name"))
    entry = _entry(_player(title="Mein Titel"))
    await _setup(hass, entry)
    sub = _sub(entry)
    assert sub.title == "Mein Titel"
    assert sub.data["name"] == "Neuer Name"
    assert _device(hass).name == "Neuer Name"


async def test_name_cleaned(hass: HomeAssistant, aioclient_mock):
    """Steuer- und Richtungszeichen aus der Antwort fallen weg (clean_name)."""
    _mocks(aioclient_mock, players=_antwort("Neu\u202eer\nName"))
    entry = _entry(_player())
    await _setup(hass, entry)
    assert _sub(entry).data["name"] == "NeuerName"


@pytest.mark.parametrize(
    "players",
    [{"results": []}, _antwort(None), _antwort("X", 1000000077)],
    ids=["keine_treffer", "ohne_namen", "anderes_konto"],
)
async def test_no_change_without_name(hass: HomeAssistant, aioclient_mock, players):
    """Konto fehlt in der Antwort oder hat keinen Namen: nichts aendert sich."""
    _mocks(aioclient_mock, players=players)
    entry = _entry(_player())
    await _setup(hass, entry)
    sub = _sub(entry)
    assert sub.data["name"] == "Testspieler"
    assert sub.data["api_name"] == "Testspieler"


async def test_name_check_once_a_day_and_retry_after_error(
    hass: HomeAssistant, aioclient_mock, freezer
):
    _mocks(aioclient_mock, status=500)
    entry = _entry(_player())
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert _by_id_calls(aioclient_mock) == 1
    # Fehler: Werte da, Name unveraendert, naechste Abfrage versucht es erneut
    assert hass.states.get("sensor.testspieler_kills").state == "1000"
    assert _sub(entry).data["name"] == "Testspieler"
    _mocks(aioclient_mock, players=_antwort("Testspieler"))
    await _tick(hass, freezer, minutes=15)
    assert _by_id_calls(aioclient_mock) == 1
    # Gelungen: erst nach 24 Stunden wieder
    for _ in range(4):
        await _tick(hass, freezer, minutes=15)
    assert _by_id_calls(aioclient_mock) == 1
    await _tick(hass, freezer, hours=24)
    assert _by_id_calls(aioclient_mock) == 2


async def test_diagnostics_redact_api_name(hass: HomeAssistant, aioclient_mock):
    _mocks(aioclient_mock)
    entry = _entry(_player(name="Geheim", api_name="GeheimEA"))
    await _setup(hass, entry)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["players"][0]["subentry"]["api_name"] == "**REDACTED**"
    assert "GeheimEA" not in str(diag)


# --- E6: Neu konfigurieren ---------------------------------------------------


async def _reconfigure(hass, entry):
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_PLAYER),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": _sub(entry).subentry_id},
    )


async def test_reconfigure_own_name(hass: HomeAssistant, aioclient_mock):
    _mocks(aioclient_mock, players=_antwort("Testspieler"))
    entry = _entry(_player())
    await _setup(hass, entry)
    _mocks(aioclient_mock, players=_antwort("[EA](https://x) Name"))
    result = await _reconfigure(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    # Name bei EA ohne Markdown-Wirkung im Text
    assert result["description_placeholders"]["api_name"] == (
        "\\[EA\\]\\(https://x\\) Name"
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "  Mein Name  "}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    sub = _sub(entry)
    assert sub.data["name"] == "Mein Name"
    # Der beim Oeffnen gelesene Name bei EA steht mit; eigener Name bleibt
    assert sub.data["api_name"] == "[EA](https://x) Name"
    assert sub.title == "Mein Name · EA app"
    assert _device(hass).name == "Mein Name"
    kills = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "1000000001-kills")
    assert kills == "sensor.testspieler_kills"
    # IDs und Plattform unveraendert
    assert sub.data["persona_id"] == 1000000001
    assert sub.data["platform"] == "ea"


async def test_reconfigure_back_to_ea_name_follows_again(
    hass: HomeAssistant, aioclient_mock, freezer
):
    _mocks(aioclient_mock, players=_antwort("EA Name"))
    entry = _entry(_player(name="Eigener", api_name="EA Name"))
    await _setup(hass, entry)
    result = await _reconfigure(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "EA Name"}
    )
    assert result["reason"] == "reconfigure_successful"
    # Folgt wieder: naechste Umbenennung bei EA kommt an
    _mocks(aioclient_mock, players=_antwort("Ganz Neu"))
    await _tick(hass, freezer, hours=24)
    assert _sub(entry).data["name"] == "Ganz Neu"


async def test_reconfigure_invalid_name_and_api_down(
    hass: HomeAssistant, aioclient_mock
):
    _mocks(aioclient_mock)
    entry = _entry(_player())
    await _setup(hass, entry)
    _mocks(aioclient_mock, status=500)
    result = await _reconfigure(hass, entry)
    assert result["description_placeholders"]["api_name"] == "–"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Zeile\nUmbruch"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_name"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Gut"}
    )
    assert result["reason"] == "reconfigure_successful"
    sub = _sub(entry)
    assert sub.data["name"] == "Gut"
    # Ohne Antwort der API bleibt der gespeicherte Name bei EA
    assert sub.data["api_name"] == "Testspieler"
    # Ein Abruf beim Oeffnen, nicht bei jedem Absenden
    assert _by_id_calls(aioclient_mock) == 1


async def test_reconfigure_entry_not_loaded(hass: HomeAssistant, aioclient_mock):
    _mocks(aioclient_mock)
    entry = _entry(_player())
    await _setup(hass, entry)
    await hass.config_entries.async_unload(entry.entry_id)
    result = await _reconfigure(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
