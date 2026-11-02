"""Tests fuer das Rang-Abzeichen als Bild-Entitaet (0.5.0)."""

import copy
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.bf6_player.const import DOMAIN

from .conftest import PROFILE, STATS, main_entry, mock_world, player_subentry

BASE = "https://api.gametools.network"


async def test_rank_badge(hass: HomeAssistant, aioclient_mock, freezer):
    aioclient_mock.get(f"{BASE}/bf6/stats/", json=STATS)
    entry = main_entry(player_subentry())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "image", DOMAIN, "1000000001-rank_badge"
    )
    state = hass.states.get(entity_id)
    assert state.attributes["entity_picture"].startswith(
        f"/api/image_proxy/{entity_id}"
    )
    image = hass.data["entity_components"]["image"].get_entity(entity_id)
    assert image.image_url == "https://cdn.gametools.network/ranks/bf6/r_lg.png"
    first = state.state

    # Neuer Rang, neues Bild: Zeitstempel und Adresse wechseln
    higher = copy.deepcopy(PROFILE)
    higher["playerProfiles"][0]["playerCard"]["rankImage"]["large"] = (
        "https://cdn.gametools.network/ranks/bf6/neu_lg.png"
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/bf6/stats/", json=STATS)
    aioclient_mock.get(f"{BASE}/bf6/profile/", json=higher)
    mock_world(aioclient_mock)
    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert image.image_url == "https://cdn.gametools.network/ranks/bf6/neu_lg.png"
    assert hass.states.get(entity_id).state != first
