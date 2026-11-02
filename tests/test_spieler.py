"""Tests fuer den Dialog "Spieler hinzufuegen" (Untereintrag)."""

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bf6_player.config_flow import account_label
from custom_components.bf6_player.const import SUBENTRY_PLAYER

from .conftest import SEARCH, STATS, STATS_EMPTY, main_entry, player_subentry

BASE = "https://api.gametools.network"
SEARCH_URL = f"{BASE}/bf6/player/"
STATS_URL = f"{BASE}/bf6/stats/"


def _calls(aioclient_mock: AiohttpClientMocker, url: str) -> list:
    """Aufgerufene Adressen zu url (ohne die Abfragen der Spielwelt)."""
    return [c[1] for c in aioclient_mock.mock_calls if str(c[1]).startswith(url)]


async def _loaded(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _start(hass: HomeAssistant, entry: MockConfigEntry):
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_PLAYER),
        context={"source": config_entries.SOURCE_USER},
    )


async def _search(hass: HomeAssistant, entry: MockConfigEntry, name="Testspieler"):
    result = await _start(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": f"  {name} "}
    )


async def test_add_player(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    aioclient_mock.get(SEARCH_URL, json=SEARCH)
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = await _loaded(hass, main_entry())

    result = await _search(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"
    assert result["description_placeholders"] == {"name": "Testspieler", "count": "2"}
    # Name ohne Leerzeichen am Rand, Trefferzahl wie in der Antwort
    assert _calls(aioclient_mock, SEARCH_URL)[0].query["name"] == "Testspieler"
    assert _calls(aioclient_mock, SEARCH_URL)[0].query["limit"] == "25"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"account": "1000000001"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_PLAYER
    assert subentry.title == "Testspieler · EA app"
    assert subentry.unique_id == "1000000001"
    assert dict(subentry.data) == {
        "name": "Testspieler",
        "persona_id": 1000000001,
        "nucleus_id": 2000000001,
        "platform": "ea",
    }
    # Gepruefte Statistik per ID, nicht per Name
    stats_query = _calls(aioclient_mock, STATS_URL)[0].query
    assert stats_query["playerid"] == "1000000001"
    assert stats_query["nucleus_id"] == "2000000001"
    assert "name" not in stats_query


async def test_no_players(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    aioclient_mock.get(SEARCH_URL, json={"results": []})
    entry = await _loaded(hass, main_entry())
    result = await _search(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_players"}


async def test_search_not_found(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(SEARCH_URL, status=404, json={"errors": ["not found"]})
    entry = await _loaded(hass, main_entry())
    result = await _search(hass, entry)
    assert result["errors"] == {"base": "no_players"}


@pytest.mark.parametrize(
    "kwargs", [{"status": 500}, {"exc": aiohttp.ClientConnectionError()}]
)
async def test_search_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, kwargs
):
    aioclient_mock.get(SEARCH_URL, **kwargs)
    entry = await _loaded(hass, main_entry())
    result = await _search(hass, entry)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_configured_account_not_offered(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(SEARCH_URL, json=SEARCH)
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = await _loaded(hass, main_entry(player_subentry()))
    result = await _search(hass, entry)
    assert result["step_id"] == "select"
    assert result["description_placeholders"]["count"] == "1"
    options = result["data_schema"].schema["account"].config["options"]
    assert [o["value"] for o in options] == ["1000000002"]


async def test_all_accounts_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(SEARCH_URL, json=SEARCH)
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = await _loaded(
        hass,
        main_entry(
            player_subentry(),
            player_subentry(1000000002, 2000000002, "steam"),
        ),
    )
    result = await _search(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_account_without_stats(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(SEARCH_URL, json=SEARCH)
    aioclient_mock.get(STATS_URL, json=STATS_EMPTY)
    entry = await _loaded(hass, main_entry())
    result = await _search(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"account": "1000000002"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"
    assert result["errors"] == {"base": "no_stats"}
    assert not entry.subentries


async def test_stats_fail(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    aioclient_mock.get(SEARCH_URL, json=SEARCH)
    aioclient_mock.get(STATS_URL, exc=TimeoutError())
    entry = await _loaded(hass, main_entry())
    result = await _search(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"account": "1000000001"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_entry_not_loaded(hass: HomeAssistant) -> None:
    entry = main_entry()
    entry.add_to_hass(hass)
    result = await _start(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


def test_account_label() -> None:
    from datetime import UTC, datetime

    account = {
        "persona_id": 1,
        "nucleus_id": 2,
        "platform": "steam",
        "name": "Testspieler",
        "created": datetime(2020, 10, 1, tzinfo=UTC),
        "public": False,
    }
    assert account_label(account) == "Testspieler · Steam · 2020-10-01 · 🔒"
    account.update(name=None, platform="neu", created=None, public=True)
    assert account_label(account) == "1 · neu"


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "a" * 65,
        "Name\nZweite Zeile",
        "Null\x00Byte",
        "Tab\tTab",
        chr(0x202E) + "egnaR",
    ],
)
async def test_invalid_name(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, name: str
):
    entry = await _loaded(hass, main_entry())
    result = await _start(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": name}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_name"}
    assert result["description_placeholders"] == {"max": "64"}
    # Ungueltige Namen gehen gar nicht erst an die API
    assert _calls(aioclient_mock, SEARCH_URL) == []


@pytest.mark.parametrize(
    "name",
    [
        "a&limit=100#x",
        '"><script>alert(1)</script>',
        "'; DROP TABLE x;--",
        "../../bf6/status/",
        "%2F%00",
        "Ä€😀 ナ",
        "a" * 64,
    ],
)
async def test_special_characters_stay_in_parameter(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, name: str
):
    """Sonderzeichen kommen unveraendert und kodiert als Parameter name an."""
    aioclient_mock.get(SEARCH_URL, json={"results": []})
    entry = await _loaded(hass, main_entry())
    result = await _search(hass, entry, name)
    assert result["errors"] == {"base": "no_players"}
    url = _calls(aioclient_mock, SEARCH_URL)[0]
    assert url.path == "/bf6/player/"
    assert dict(url.query) == {"name": name, "limit": "25"}


async def test_name_in_description_has_no_markdown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(SEARCH_URL, json=SEARCH)
    entry = await _loaded(hass, main_entry())
    result = await _search(hass, entry, "[Klick](https://example.com)*x*")
    assert result["description_placeholders"]["name"] == (
        r"\[Klick\]\(https://example\.com\)\*x\*"
    )


async def test_api_name_cleaned(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Steuer- und Richtungszeichen aus der API landen nicht im Titel."""
    answer = {
        "results": [
            {
                **SEARCH["results"][0],
                "displayName": "Böser\n" + chr(0x202E) + "Name\x00 <b>",
            }
        ]
    }
    aioclient_mock.get(SEARCH_URL, json=answer)
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = await _loaded(hass, main_entry())
    result = await _search(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"account": "1000000001"}
    )
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "BöserName <b> · EA app"
    assert subentry.data["name"] == "BöserName <b>"
