"""Sensoren je Spieler.

Zaehler (Kills, Matches, Spielzeit ...) als total_increasing und Quoten als
measurement: Home Assistant fuehrt fuer beide Langzeitstatistiken, daraus
entstehen Verlaeufe (die API liefert keine).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Bf6ConfigEntry
from .const import CONF_PLATFORM, PLATFORM_NAMES
from .coordinator import Bf6PlayerCoordinator, Bf6WorldCoordinator
from .entity import Bf6PlayerEntity, Bf6WorldEntity, async_add_player_entities


@dataclass(frozen=True, kw_only=True)
class Bf6SensorDescription(SensorEntityDescription):
    """value liest aus coordinator.data["stats"] bzw. ["profile"]."""

    value: Callable[[dict[str, Any]], Any]
    attributes: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _stat(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda data: data["stats"].get(key)


def _profile(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda data: (data.get("profile") or {}).get(key)


def _top(key: str) -> Callable[[dict[str, Any]], Any]:
    def value(data: dict[str, Any]) -> Any:
        items = data["stats"].get(key) or []
        return items[0]["name"] if items else None

    return value


def _top_list(key: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return lambda data: {"top": data["stats"].get(key) or []}


def _rank_attributes(data: dict[str, Any]) -> dict[str, Any]:
    profile = data.get("profile") or {}
    return {
        "rank_name": profile.get("rank_name"),
        "dog_tags": profile.get("dog_tags"),
        "badges": profile.get("badges"),
        "rank_image": profile.get("rank_image"),
        "ranked": profile.get("ranked") or [],
    }


def _ranked(data: dict[str, Any]) -> dict[str, Any] | None:
    """Erster Eintrag aus competitiveRanks.

    Am 03.11.2026 beim Beispielkonto der API-Dokumentation genau einer
    (Saison "CompetitiveSeason5", Modus "Redsec Quads", "Unranked"). Kommen mehrere, steht der erste im Zustand und alle im
    Attribut "ranked".
    """
    ranked = (data.get("profile") or {}).get("ranked") or []
    return ranked[0] if ranked else None


def _ranked_rank(data: dict[str, Any]) -> str | None:
    return (_ranked(data) or {}).get("rank")


def _ranked_attributes(data: dict[str, Any]) -> dict[str, Any]:
    first = _ranked(data) or {}
    return {
        "season": first.get("season"),
        "mode": first.get("mode"),
        "ranked": (data.get("profile") or {}).get("ranked") or [],
    }


def _count(
    key: str,
    value_key: str | None = None,
    attributes: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Bf6SensorDescription:
    return Bf6SensorDescription(
        key=key,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=_stat(value_key or key),
        attributes=attributes,
    )


def _lists(*keys: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Listen aus der Auswertung als Attribute fuer die Karten (seit 0.6.0)."""
    return lambda data: {key: data["stats"].get(key) or [] for key in keys}


def _rate(key: str, digits: int = 1) -> Bf6SensorDescription:
    return Bf6SensorDescription(
        key=key,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=digits,
        value=_stat(key),
    )


SENSORS: tuple[Bf6SensorDescription, ...] = (
    _count("kills"),
    _count("deaths"),
    _count("assists"),
    _count("revives"),
    _count("matches", attributes=_lists("maps", "modes")),
    _count("wins"),
    _count("losses"),
    _count("xp"),
    Bf6SensorDescription(
        key="time_played",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=_stat("seconds_played"),
    ),
    Bf6SensorDescription(
        key="kd",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value=_stat("kd"),
    ),
    Bf6SensorDescription(
        key="kpm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value=_stat("kpm"),
    ),
    _rate("win_rate"),
    _rate("accuracy"),
    _rate("headshot_rate"),
    _rate("human_kill_rate"),
    Bf6SensorDescription(
        key="rank",
        state_class=SensorStateClass.MEASUREMENT,
        value=_profile("rank"),
        attributes=_rank_attributes,
    ),
    # Seit 0.7.0 eigene Sensoren (Review E2); die Attribute am Rang bleiben
    Bf6SensorDescription(
        key="dog_tags",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=_profile("dog_tags"),
    ),
    Bf6SensorDescription(
        key="badges",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=_profile("badges"),
    ),
    Bf6SensorDescription(
        key="ranked_rank",
        value=_ranked_rank,
        attributes=_ranked_attributes,
    ),
    Bf6SensorDescription(
        key="favorite_class",
        value=_stat("favorite_class"),
        attributes=_lists("classes"),
    ),
    Bf6SensorDescription(
        key="top_weapon", value=_top("weapons"), attributes=_top_list("weapons")
    ),
    Bf6SensorDescription(
        key="top_vehicle", value=_top("vehicles"), attributes=_top_list("vehicles")
    ),
    # Seit 0.7.0 (Review E1, B20): Gadgets waren ausgewertet, aber ungenutzt
    Bf6SensorDescription(
        key="top_gadget", value=_top("gadgets"), attributes=_top_list("gadgets")
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Bf6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_player_entities(
        hass,
        entry,
        async_add_entities,
        lambda coordinator: [
            *(Bf6Sensor(coordinator, description) for description in SENSORS),
            Bf6PlatformSensor(coordinator),
        ],
    )
    world = entry.runtime_data.world
    if world is not None:
        async_add_entities(Bf6WorldSensor(world, d) for d in WORLD_SENSORS)


class Bf6Sensor(Bf6PlayerEntity, SensorEntity):
    """Wert aus Statistik oder Profil eines Spielers."""

    entity_description: Bf6SensorDescription
    # Listen und Bildadressen nicht in die Datenbank (16-KB-Grenze, Verlauf
    # ohne Nutzen).
    _unrecorded_attributes = frozenset(
        {"top", "ranked", "rank_image", "classes", "maps", "modes"}
    )

    def __init__(
        self, coordinator: Bf6PlayerCoordinator, description: Bf6SensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.coordinator.data is None or self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)


class Bf6PlatformSensor(Bf6PlayerEntity, SensorEntity):
    """Plattform des Kontos; das Symbol folgt der Plattform."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: Bf6PlayerCoordinator) -> None:
        super().__init__(coordinator, "platform")
        self._attr_options = list(PLATFORM_NAMES)
        # Symbol je Plattform: icons.json, Abschnitt "state" (aus PLATFORM_ICONS)
        self._platform = coordinator.subentry.data[CONF_PLATFORM]

    @property
    def available(self) -> bool:
        # Die Plattform ist gespeichert, nicht abgefragt.
        return True

    @property
    def native_value(self) -> str | None:
        return self._platform if self._platform in PLATFORM_NAMES else None


def _season(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda data: (data.get("season") or {}).get(key)


def _portal(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda data: (data.get("portal") or {}).get(key)


def _season_attributes(data: dict[str, Any]) -> dict[str, Any]:
    season = data.get("season") or {}
    start = season.get("start")
    return {
        "season": season.get("number"),
        "season_start": start.isoformat() if start else None,
        "battle_pass": season.get("battle_pass"),
    }


WORLD_SENSORS: tuple[Bf6SensorDescription, ...] = (
    Bf6SensorDescription(
        key="season_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=_season("end"),
        attributes=_season_attributes,
    ),
    Bf6SensorDescription(
        key="portal_servers",
        state_class=SensorStateClass.MEASUREMENT,
        value=_portal("servers"),
    ),
    Bf6SensorDescription(
        key="portal_players",
        state_class=SensorStateClass.MEASUREMENT,
        value=_portal("players"),
    ),
    # Seit 0.7.0 (Review E1, B20)
    Bf6SensorDescription(
        key="portal_queue",
        state_class=SensorStateClass.MEASUREMENT,
        value=_portal("queue"),
    ),
)


class Bf6WorldSensor(Bf6WorldEntity, SensorEntity):
    """Wert der Spielwelt: Saisonende, Portal-Server und -Spieler."""

    entity_description: Bf6SensorDescription

    def __init__(
        self, coordinator: Bf6WorldCoordinator, description: Bf6SensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.coordinator.data is None or self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)
