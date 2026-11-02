"""Tests fuer Laden und Entladen des Haupteintrags."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bf6_player.const import player_title

from .conftest import PROFILE, STATS, main_entry, player_subentry


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    entry = main_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_platform_added_to_old_titles(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Spieler aus 0.3.0 bekommen die Plattform in den Titel, umbenannte nicht."""
    aioclient_mock.get("https://api.gametools.network/bf6/stats/", json=STATS)
    aioclient_mock.get("https://api.gametools.network/bf6/profile/", json=PROFILE)
    old = player_subentry(1000000001, 2000000001, "steam", "Alt")
    renamed = player_subentry(1000000002, 2000000002, "psn", "Zweiter")
    renamed["title"] = "Mein Name"
    current = player_subentry(1000000003, 2000000003, "xbox", "Neu")
    current["title"] = "Neu · Xbox"
    entry = main_entry(old, renamed, current)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    titles = {sub.unique_id: sub.title for sub in entry.subentries.values()}
    assert titles == {
        "1000000001": "Alt · Steam",
        "1000000002": "Mein Name",
        "1000000003": "Neu · Xbox",
    }


def test_player_title() -> None:
    assert player_title("(★) Name", "steam") == "(★) Name · Steam"
    assert player_title("Name", "neu") == "Name · neu"
