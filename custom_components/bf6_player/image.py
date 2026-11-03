"""Rang-Abzeichen je Spieler als Bild-Entitaet."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import Bf6ConfigEntry
from .coordinator import Bf6PlayerCoordinator
from .entity import Bf6PlayerEntity, async_add_player_entities
from .parsers import image_url

_LOGGER = logging.getLogger(__name__)

# Zeitlimit wie bei den Bild-Entitaeten von Home Assistant (GET_IMAGE_TIMEOUT)
IMAGE_TIMEOUT = 10
# Groesstes Abzeichen; das echte ist 259 KB gross (PNG, 02.11.2026)
IMAGE_MAX_BYTES = 2 * 1024 * 1024


async def lies_bild(
    resp: aiohttp.ClientResponse, limit: int
) -> tuple[bytes | None, str]:
    """Ganze Antwort lesen, hoechstens limit Bytes; (Inhalt, Grund) bei Ablehnung.

    Liest in Bloecken bis zum Ende des Datenstroms. 0.6.11 nutzte
    resp.content.read(limit + 1); das liefert nur, was gerade im Puffer liegt
    (gegen den CDN 13.690 bis 23.829 von 258.834 Bytes), und das abgeschnittene
    PNG blieb im Zwischenspeicher. Stimmt die Laenge nicht mit Content-Length
    ueberein, gilt das Bild als unvollstaendig.
    """
    try:
        erwartet = int(resp.headers.get("Content-Length", ""))
    except ValueError:
        erwartet = None
    if erwartet is not None and erwartet > limit:
        return None, f"groesser als {limit} Bytes"
    inhalt = bytearray()
    async for block in resp.content.iter_chunked(64 * 1024):
        inhalt.extend(block)
        if len(inhalt) > limit:
            return None, f"groesser als {limit} Bytes"
    if erwartet is not None and len(inhalt) != erwartet:
        return None, f"unvollstaendig ({len(inhalt)} von {erwartet} Bytes)"
    if not inhalt:
        return None, "leer"
    return bytes(inhalt), ""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Bf6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_player_entities(
        hass,
        entry,
        async_add_entities,
        lambda coordinator: [Bf6RankImage(hass, coordinator)],
    )


class Bf6RankImage(Bf6PlayerEntity, ImageEntity):
    """Abzeichen des aktuellen Rangs.

    Die Adresse kommt aus dem Profil und ist schon geprueft
    (parsers.image_url: nur https://cdn.gametools.network). Seit 0.6.11 laedt
    die Entitaet das Bild selbst (async_image) statt ueber image_url von Home
    Assistant: Dieser Weg folgt Weiterleitungen, die Pruefung der Adresse
    gaelte dann nur fuer die erste (Review B24), und der Cache liess sich nur
    ueber das private Attribut _cached_image zuruecksetzen (Review B11).
    """

    def __init__(self, hass: HomeAssistant, coordinator: Bf6PlayerCoordinator) -> None:
        Bf6PlayerEntity.__init__(self, coordinator, "rank_badge")
        ImageEntity.__init__(self, hass)
        self._url = self._current_url()
        self._attr_image_last_updated = dt_util.utcnow() if self._url else None
        # (Adresse, Inhalt) des zuletzt geladenen Bilds
        self._bild: tuple[str, bytes] | None = None

    @property
    def badge_url(self) -> str | None:
        """Adresse des aktuellen Abzeichens (fuer Diagnose und Tests)."""
        return self._url

    def _current_url(self) -> str | None:
        data = self.coordinator.data or {}
        return (data.get("profile") or {}).get("rank_image")

    @callback
    def _handle_coordinator_update(self) -> None:
        url = self._current_url()
        if url != self._url:
            self._url = url
            # Neuer Zeitstempel: das Frontend fragt das Bild neu ab
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Abzeichen laden, ohne Weiterleitung, nur Bilder bis IMAGE_MAX_BYTES."""
        url = self._url
        if url is None:
            return None
        if self._bild is not None and self._bild[0] == url:
            return self._bild[1]
        if image_url(url) is None:
            # Nur zur Sicherheit: die Auswertung laesst nichts anderes durch
            return None
        try:
            async with async_get_clientsession(self.hass).get(
                url,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=IMAGE_TIMEOUT),
            ) as resp:
                content_type = resp.headers.get("Content-Type", "").split(";")[0]
                if resp.status != 200 or not content_type.startswith("image/"):
                    _LOGGER.warning(
                        "Rang-Abzeichen nicht geladen: HTTP %s, %s",
                        resp.status,
                        content_type or "ohne Content-Type",
                    )
                    return None
                inhalt, grund = await lies_bild(resp, IMAGE_MAX_BYTES)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Rang-Abzeichen nicht geladen: %s", type(err).__name__)
            return None
        if inhalt is None:
            _LOGGER.warning("Rang-Abzeichen nicht geladen: %s", grund)
            return None
        self._attr_content_type = content_type
        self._bild = (url, inhalt)
        return inhalt
