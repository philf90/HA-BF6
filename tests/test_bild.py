"""Tests fuer das Rang-Abzeichen als Bild-Entitaet (0.5.0, eigenes Laden 0.6.11).

Seit 0.6.11 laedt die Entitaet das Bild selbst: keine Weiterleitung (Review
B24), nur Status 200 mit image/*, hoechstens IMAGE_MAX_BYTES, Zwischenspeicher
je Adresse ohne private Attribute von Home Assistant (Review B11).
"""

import copy
from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.bf6_player.const import DOMAIN

from .conftest import PROFILE, STATS, main_entry, mock_world, player_subentry

BASE = "https://api.gametools.network"
BILD = "https://cdn.gametools.network/ranks/bf6/r_lg.png"
NEU = "https://cdn.gametools.network/ranks/bf6/neu_lg.png"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def _setup(hass: HomeAssistant, aioclient_mock) -> str:
    aioclient_mock.get(f"{BASE}/bf6/stats/", json=STATS)
    entry = main_entry(player_subentry())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return er.async_get(hass).async_get_entity_id(
        "image", DOMAIN, "1000000001-rank_badge"
    )


async def _abrufen(hass: HomeAssistant, hass_client, entity_id: str):
    """Bild ueber die Adresse abrufen, die auch das Frontend nutzt."""
    client = await hass_client()
    url = hass.states.get(entity_id).attributes["entity_picture"]
    return await client.get(url)


def _cdn_calls(aioclient_mock, url: str = BILD) -> int:
    return sum(1 for c in aioclient_mock.mock_calls if str(c[1]) == url)


async def test_rank_badge(hass: HomeAssistant, aioclient_mock, hass_client, freezer):
    aioclient_mock.get(BILD, content=PNG, headers={"Content-Type": "image/png"})
    entity_id = await _setup(hass, aioclient_mock)
    state = hass.states.get(entity_id)
    assert state.attributes["entity_picture"].startswith(
        f"/api/image_proxy/{entity_id}"
    )
    resp = await _abrufen(hass, hass_client, entity_id)
    assert resp.status == 200
    assert resp.headers["Content-Type"] == "image/png"
    assert await resp.read() == PNG
    # Zweiter Abruf aus dem Zwischenspeicher
    await _abrufen(hass, hass_client, entity_id)
    assert _cdn_calls(aioclient_mock) == 1
    first = state.state

    # Neuer Rang, neues Bild: Zeitstempel wechselt, das neue Bild wird geladen
    higher = copy.deepcopy(PROFILE)
    higher["playerProfiles"][0]["playerCard"]["rankImage"]["large"] = NEU
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/bf6/stats/", json=STATS)
    aioclient_mock.get(f"{BASE}/bf6/profile/", json=higher)
    aioclient_mock.get(NEU, content=b"neu", headers={"Content-Type": "image/webp"})
    mock_world(aioclient_mock)
    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    image = hass.data["entity_components"]["image"].get_entity(entity_id)
    assert image.badge_url == NEU
    assert hass.states.get(entity_id).state != first
    resp = await _abrufen(hass, hass_client, entity_id)
    assert resp.headers["Content-Type"] == "image/webp"
    assert await resp.read() == b"neu"


async def test_redirect_is_not_followed(
    hass: HomeAssistant, aioclient_mock, hass_client
):
    """B24: Eine Weiterleitung, etwa ins eigene Netz, ergibt kein Bild."""
    aioclient_mock.get(
        BILD, status=302, headers={"Location": "http://192.168.1.1/admin.png"}
    )
    entity_id = await _setup(hass, aioclient_mock)
    session = async_get_clientsession(hass)
    original = session._request
    aufrufe = []

    async def spion(method, url, **kwargs):
        aufrufe.append((str(url), kwargs.get("allow_redirects")))
        return await original(method, url, **kwargs)

    object.__setattr__(session, "_request", spion)
    resp = await _abrufen(hass, hass_client, entity_id)
    assert resp.status != 200
    # Angefragt nur die gepruefte Adresse, ausdruecklich ohne Weiterleitung
    assert aufrufe == [(BILD, False)]


async def test_only_images(hass: HomeAssistant, aioclient_mock):
    """Keine Antwort ohne image/* als Bild; sie landet auch nicht im
    Zwischenspeicher. Home Assistant prueft den Typ in der Bild-Adresse noch
    einmal, deshalb hier direkt an der Entitaet: Ohne eigene Pruefung bliebe
    die HTML-Antwort bis zum naechsten Rangwechsel gespeichert."""
    aioclient_mock.get(BILD, text="<html>", headers={"Content-Type": "text/html"})
    entity_id = await _setup(hass, aioclient_mock)
    image = hass.data["entity_components"]["image"].get_entity(entity_id)
    assert await image.async_image() is None
    aioclient_mock.clear_requests()
    aioclient_mock.get(BILD, content=PNG, headers={"Content-Type": "image/png"})
    assert await image.async_image() == PNG
    assert image.content_type == "image/png"


async def test_too_large(hass: HomeAssistant, aioclient_mock, hass_client):
    aioclient_mock.get(BILD, content=PNG, headers={"Content-Type": "image/png"})
    entity_id = await _setup(hass, aioclient_mock)
    with patch("custom_components.bf6_player.image.IMAGE_MAX_BYTES", len(PNG) - 1):
        assert (await _abrufen(hass, hass_client, entity_id)).status != 200


async def test_connection_error(hass: HomeAssistant, aioclient_mock, hass_client):
    aioclient_mock.get(BILD, exc=TimeoutError())
    entity_id = await _setup(hass, aioclient_mock)
    assert (await _abrufen(hass, hass_client, entity_id)).status != 200
    # Kein Fehlschlag im Zwischenspeicher: der naechste Abruf versucht es neu
    aioclient_mock.clear_requests()
    aioclient_mock.get(BILD, content=PNG, headers={"Content-Type": "image/png"})
    resp = await _abrufen(hass, hass_client, entity_id)
    assert resp.status == 200
    assert await resp.read() == PNG
