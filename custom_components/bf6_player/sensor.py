"""Sensoren je Spieler.

Zaehler (Kills, Matches, Spielzeit ...) als total_increasing und Quoten als
measurement: Home Assistant fuehrt fuer beide Langzeitstatistiken, daraus
entstehen Verlaeufe (die API liefert keine).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
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
from .coordinator import Bf6PlayerCoordinator
from .entity import Bf6PlayerEntity


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


def _count(key: str, value_key: str | None = None) -> Bf6SensorDescription:
    return Bf6SensorDescription(
        key=key,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=_stat(value_key or key),
    )


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
    _count("matches"),
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
    Bf6SensorDescription(key="favorite_class", value=_stat("favorite_class")),
    Bf6SensorDescription(
        key="top_weapon", value=_top("weapons"), attributes=_top_list("weapons")
    ),
    Bf6SensorDescription(
        key="top_vehicle", value=_top("vehicles"), attributes=_top_list("vehicles")
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Bf6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        add = partial(async_add_entities, config_subentry_id=subentry_id)
        entities: list[SensorEntity] = [
            Bf6Sensor(coordinator, description) for description in SENSORS
        ]
        entities.append(Bf6PlatformSensor(coordinator))
        add(entities)


class Bf6Sensor(Bf6PlayerEntity, SensorEntity):
    """Wert aus Statistik oder Profil eines Spielers."""

    entity_description: Bf6SensorDescription
    # Listen und Bildadressen nicht in die Datenbank (16-KB-Grenze, Verlauf
    # ohne Nutzen).
    _unrecorded_attributes = frozenset({"top", "ranked", "rank_image"})

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
