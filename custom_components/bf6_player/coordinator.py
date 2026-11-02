"""Regelmaessige Abfragen: je Spieler und fuer die Spielwelt.

Je Spieler ein Coordinator: Statistik alle 15 Minuten, Profil (Rang,
Abzeichen) stuendlich, beides in den Optionen einstellbar. Faellt ein
Spieler aus, sind nur seine Entitaeten nicht verfuegbar, wie bei WoW
Charakter. Aus dem Vergleich zweier Abfragen entstehen die Ereignisse
"Match beendet" und "Rang gestiegen".
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import parsers
from .api import GametoolsClient, GametoolsError, GametoolsRateLimited, PlayerRef
from .const import (
    CONF_NUCLEUS_ID,
    CONF_PERSONA_ID,
    CONF_PLATFORM,
    CONF_PROFILE_INTERVAL,
    CONF_STATS_INTERVAL,
    DOMAIN,
    EVENT_MATCH_FINISHED,
    EVENT_RANK_UP,
    PROFILE_INTERVAL_MINUTES,
    RETRY_AFTER_MAX_SECONDS,
    SEASON_INTERVAL_MINUTES,
    STATS_INTERVAL_MINUTES,
    WORLD_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

# Zaehler, deren Zuwachs ein Match beschreibt (Schluessel aus player_stats)
MATCH_COUNTERS = (
    "matches",
    "wins",
    "losses",
    "kills",
    "deaths",
    "assists",
    "revives",
    "xp",
    "seconds_played",
)


# Zweite Verteidigungslinie hinter parsers.py: Faende die Auswertung doch einen
# Wert, an dem sie scheitert, soll das wie ein API-Fehler wirken (Entitaeten
# nicht verfuegbar, letzter Stand bleibt) statt die ganze Abfrage abzubrechen.
PARSE_ERRORS = (AttributeError, KeyError, TypeError, ValueError)


def player_ref(subentry: ConfigSubentry) -> PlayerRef:
    data = subentry.data
    return PlayerRef(
        int(data[CONF_PERSONA_ID]), int(data[CONF_NUCLEUS_ID]), data[CONF_PLATFORM]
    )


def retry_after(err: BaseException, interval: timedelta | None) -> float | None:
    """Wartezeit nach HTTP 429 mit Retry-After, sonst None (normaler Takt).

    Nie kuerzer als der Takt (kein schnelleres Abfragen als eingestellt), nie
    laenger als RETRY_AFTER_MAX_SECONDS.
    """
    if not isinstance(err, GametoolsRateLimited) or err.retry_after is None:
        return None
    floor = interval.total_seconds() if interval else 0.0
    return min(max(err.retry_after, floor), RETRY_AFTER_MAX_SECONDS)


def _update_failed(err: BaseException, retry: float | None = None) -> UpdateFailed:
    """UpdateFailed mit lesbarem Grund; Auswertungsfehler ohne Rohtext."""
    error = (
        str(err)
        if isinstance(err, GametoolsError)
        else f"Antwort nicht auswertbar ({type(err).__name__})"
    )
    return UpdateFailed(
        translation_domain=DOMAIN,
        translation_key="update_failed",
        translation_placeholders={"error": error},
        retry_after=retry,
    )


def issue_id(subentry_id: str) -> str:
    """Reparaturhinweis "keine Statistik" je Spieler."""
    return f"no_stats_{subentry_id}"


def counter_drops(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Zaehler, die gegenueber der letzten Abfrage gesunken sind.

    Die Sensoren dazu sind total_increasing. Home Assistant wertet einen
    Rueckgang um mehr als 10 % als neuen Zaehlerzyklus und zaehlt danach den
    vollen Wert erneut in die Summe der Langzeitstatistik (Review 0.6.9).
    """
    return [
        key
        for key in MATCH_COUNTERS
        if isinstance(before := old.get(key), int)
        and isinstance(after := new.get(key), int)
        and after < before
    ]


def match_event(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any] | None:
    """Daten fuer "Match beendet", wenn seit der letzten Abfrage Matches dazukamen.

    Die API kennt keine einzelnen Matches; zwischen zwei Abfragen koennen
    mehrere liegen. Die Werte sind deshalb Zuwaechse ueber alle neuen
    Matches; "result" gibt es nur bei genau einem. Sinkt ein Zaehler
    (Korrektur der API), gibt es kein Ereignis.

    Pflicht ist nur "matches" (seit 0.6.11). Fehlt ein anderer Zaehler in
    einer der beiden Abfragen, steht er als None im Ereignis; bis 0.6.10 fiel
    das Ereignis dann ganz aus, ohne Hinweis im Log (Review B10).
    """
    before, after = old.get("matches"), new.get("matches")
    if not isinstance(before, int) or not isinstance(after, int) or after <= before:
        return None
    delta: dict[str, int | None] = {}
    for key in MATCH_COUNTERS:
        before, after = old.get(key), new.get(key)
        if not isinstance(before, int) or not isinstance(after, int):
            delta[key] = None
        elif after < before:
            return None
        else:
            delta[key] = after - before
    result = None
    if delta["matches"] == 1:
        if delta["wins"] == 1:
            result = "win"
        elif delta["losses"] == 1:
            result = "loss"
    return {
        **delta,
        "kd": parsers.ratio(delta["kills"], delta["deaths"]),
        "result": result,
    }


def rank_event(
    old: dict[str, Any] | None, new: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Daten fuer "Rang gestiegen", wenn der Rang groesser geworden ist."""
    before = (old or {}).get("rank")
    after = (new or {}).get("rank")
    if not isinstance(before, int) or not isinstance(after, int) or after <= before:
        return None
    return {
        "previous_rank": before,
        "rank": after,
        "rank_name": (new or {}).get("rank_name"),
    }


class Bf6PlayerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Statistik und Profil eines Spielers.

    data = {"stats": parsers.player_stats(...), "profile": parsers.player_profile(...)
    oder None}; events = Ereignisse der letzten Abfrage als (Typ, Daten).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GametoolsClient,
        subentry: ConfigSubentry,
    ) -> None:
        # Im Log steht die Persona-ID, nicht der Name (README, "Sicherheit").
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {subentry.data[CONF_PERSONA_ID]}",
            update_interval=timedelta(
                minutes=entry.options.get(CONF_STATS_INTERVAL, STATS_INTERVAL_MINUTES)
            ),
        )
        self.client = client
        self.subentry = subentry
        self.player = player_ref(subentry)
        self.profile_interval = timedelta(
            minutes=entry.options.get(CONF_PROFILE_INTERVAL, PROFILE_INTERVAL_MINUTES)
        )
        self.events: list[tuple[str, dict[str, Any]]] = []
        # Steigt mit jeder erfolgreichen Abfrage; die Ereignis-Entitaeten
        # loesen je Nummer hoechstens einmal aus (Listener laufen auch bei
        # Fehlern, dann mit den Ereignissen der vorigen Abfrage).
        self.events_serial = 0
        self._profile: dict[str, Any] | None = None
        self._profile_at: datetime | None = None
        # Die letzte Abfrage hatte gesunkene Zaehler und wurde verworfen.
        self._drop_pending = False
        # Zaehler, deren Fehlen im Ereignis schon gemeldet wurde
        self._missing_reported: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            stats = parsers.player_stats(await self.client.stats(self.player))
        except (GametoolsError, *PARSE_ERRORS) as err:
            raise _update_failed(err, retry_after(err, self.update_interval)) from err
        if not stats["has_results"]:
            # HTTP 200 mit hasResults = false: Die API kennt das Konto nicht
            # (mehr) oder liefert gerade nichts.
            self._create_issue()
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_stats")
        ir.async_delete_issue(self.hass, DOMAIN, issue_id(self.subentry.subentry_id))
        stats = self._hold_drop(stats)
        previous_profile = self._profile
        await self._update_profile()
        self.events = []
        self.events_serial += 1
        if self.data is not None and (match := match_event(self.data["stats"], stats)):
            self.events.append((EVENT_MATCH_FINISHED, match))
            self._report_missing(match)
        if self.data is not None and (
            rank := rank_event(previous_profile, self._profile)
        ):
            self.events.append((EVENT_RANK_UP, rank))
        return {"stats": stats, "profile": self._profile}

    def _report_missing(self, match: dict[str, Any]) -> None:
        """Fehlende Zaehler im Ereignis einmal je Zaehler melden (seit 0.6.11)."""
        missing = [
            key
            for key in MATCH_COUNTERS
            if match[key] is None and key not in self._missing_reported
        ]
        if missing:
            self._missing_reported.update(missing)
            _LOGGER.warning(
                'Spieler %s: %s fehlen in der Antwort; "Match beendet" ohne '
                "diese Werte",
                self.subentry.data[CONF_PERSONA_ID],
                ", ".join(missing),
            )

    def _hold_drop(self, stats: dict[str, Any]) -> dict[str, Any]:
        """Gesunkene Zaehler erst uebernehmen, wenn die naechste Abfrage sie
        bestaetigt; bis dahin bleibt die ganze letzte Statistik (seit 0.6.9).

        Ein einmaliger Ausreisser der API (z. B. 0 Kills) aendert so weder
        Sensoren noch Langzeitstatistik. Ein echter Ruecksetzer gilt eine
        Abfrage spaeter.
        """
        if self.data is None or not (drops := counter_drops(self.data["stats"], stats)):
            self._drop_pending = False
            return stats
        persona_id = self.subentry.data[CONF_PERSONA_ID]
        if self._drop_pending:
            self._drop_pending = False
            _LOGGER.warning(
                "Spieler %s: Rueckgang von %s bestaetigt, Werte uebernommen",
                persona_id,
                ", ".join(drops),
            )
            return stats
        self._drop_pending = True
        _LOGGER.warning(
            "Spieler %s: %s gesunken; Abfrage verworfen, bis die naechste den "
            "Rueckgang bestaetigt",
            persona_id,
            ", ".join(drops),
        )
        return self.data["stats"]

    async def _update_profile(self) -> None:
        """Profil nur im eigenen Takt; scheitert es, bleibt der letzte Stand."""
        now = dt_util.utcnow()
        if (
            self._profile_at is not None
            and now - self._profile_at < self.profile_interval
        ):
            return
        persona_id = self.subentry.data[CONF_PERSONA_ID]
        try:
            self._profile = parsers.player_profile(
                await self.client.profile(self.player)
            )
        except (GametoolsError, *PARSE_ERRORS) as err:
            _LOGGER.warning("Profil von Spieler %s nicht geladen: %s", persona_id, err)
            return
        _LOGGER.debug("Profil von Spieler %s geladen", persona_id)
        self._profile_at = now

    def _create_issue(self) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id(self.subentry.subentry_id),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="no_stats",
            translation_placeholders={"player": self.subentry.title},
        )


class Bf6WorldCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Gerät "BF6-Spielwelt": laufende Saison und Portal-Server.

    Portal-Status alle 15 Minuten, Saison alle 6 Stunden. Scheitert eine der
    beiden Abfragen, bleibt ihr letzter Stand; nicht verfuegbar wird die
    Spielwelt erst, wenn beide nichts liefern.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: GametoolsClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} world",
            update_interval=timedelta(minutes=WORLD_INTERVAL_MINUTES),
        )
        self.client = client
        self._season: dict[str, Any] | None = None
        self._season_at: datetime | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        errors = []
        if self._season_at is None or now - self._season_at >= timedelta(
            minutes=SEASON_INTERVAL_MINUTES
        ):
            try:
                self._season = parsers.season(await self.client.game_events())
            except (GametoolsError, *PARSE_ERRORS) as err:
                errors.append(err)
            else:
                self._season_at = now
        portal = (self.data or {}).get("portal")
        try:
            portal = parsers.portal_status(await self.client.portal_status())
        except (GametoolsError, *PARSE_ERRORS) as err:
            errors.append(err)
        if self._season is None and portal is None:
            waits = [
                wait
                for err in errors
                if (wait := retry_after(err, self.update_interval)) is not None
            ]
            raise _update_failed(errors[-1], max(waits, default=None)) from errors[-1]
        return {"season": self._season, "portal": portal}
