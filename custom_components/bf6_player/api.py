"""Schlanker Client fuer die gametools API (api.gametools.network).

Endpunkte und Parameter stammen aus der OpenAPI 1.3.0 unter /openapi.json;
das Verhalten ist am 01.11.2026 live geprueft (docs/bf6-api-recherche.html).
Die API braucht keinen Schluessel. Ein Abfragelimit ist nicht dokumentiert,
Antworten cacht Cloudflare 600 s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import API_BASE, REQUEST_TIMEOUT


class GametoolsError(Exception):
    """Allgemeiner Fehler der API oder der Verbindung."""


class GametoolsNotFound(GametoolsError):
    """HTTP 404, z. B. {"errors": ["Player not found"]} bei unbekanntem Namen.

    Unbekannte IDs liefern dagegen HTTP 200 mit hasResults = false (live
    geprueft am 02.11.2026); das wertet parsers.player_stats aus.
    """


class GametoolsRateLimited(GametoolsError):
    """HTTP 429. Die API nennt kein Limit; der Aufrufer wartet bis zum Takt."""


@dataclass(frozen=True)
class PlayerRef:
    """Eindeutiger Verweis auf ein Konto.

    Namen sind nicht eindeutig (zwei Steam-Konten mit demselben Namen am
    01.11.2026), deshalb fragt die Integration immer per ID ab. Nur die
    Persona-ID ohne Nucleus-ID ergab HTTP 500.
    """

    persona_id: int
    nucleus_id: int
    platform: str

    def params(self) -> dict[str, str]:
        return {
            "playerid": str(self.persona_id),
            "nucleus_id": str(self.nucleus_id),
            "platform": self.platform,
        }


class GametoolsClient:
    """Fragt die BF6-Endpunkte der gametools API ab."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        try:
            async with self._session.get(
                f"{API_BASE}{path}",
                params=params,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 404:
                    raise GametoolsNotFound(path)
                if resp.status == 429:
                    raise GametoolsRateLimited(path)
                if resp.status != 200:
                    raise GametoolsError(f"{path}: HTTP {resp.status}")
                data = await resp.json(content_type=None)
        except TimeoutError as err:
            raise GametoolsError(
                f"{path}: keine Antwort nach {REQUEST_TIMEOUT} s"
            ) from err
        except aiohttp.ClientError as err:
            raise GametoolsError(f"{path}: {type(err).__name__} {err}".strip()) from err
        except ValueError as err:
            # Antwort ist kein JSON, z. B. "Internal Server Error" als Text.
            raise GametoolsError(f"{path}: Antwort ist kein JSON") from err
        if not isinstance(data, dict):
            raise GametoolsError(f"{path}: Antwort ist kein JSON-Objekt")
        return data

    async def search_players(self, name: str, limit: int = 10) -> dict[str, Any]:
        """Konten zu einem Namen; Auswertung mit parsers.player_results."""
        return await self._get("/bf6/player/", {"name": name, "limit": str(limit)})

    async def stats(
        self, player: PlayerRef, separation: bool = False
    ) -> dict[str, Any]:
        """Statistik eines Kontos.

        format_values=false: Prozentwerte als Zahl statt als Text ("50%").
        seperation (so geschrieben in der API): zusaetzlich je Modus und
        Saison; die Antwort waechst dann von rund 33 KB auf rund 476 KB.
        """
        params = {
            **player.params(),
            "format_values": "false",
            "seperation": "true" if separation else "false",
        }
        return await self._get("/bf6/stats/", params)

    async def profile(self, player: PlayerRef) -> dict[str, Any]:
        """Rang, Dog Tags, Abzeichen und Ranked-Rang eines Kontos."""
        return await self._get("/bf6/profile/", player.params())

    async def game_events(self) -> dict[str, Any]:
        """Laufende Saison, Battle Pass und Events."""
        return await self._get("/bf6/gameevents/")

    async def portal_status(self) -> dict[str, Any]:
        """Server und Spieler der Portal-Server je Region."""
        return await self._get("/bf6/status/")
