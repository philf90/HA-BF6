"""Robustheit der Auswertung gegen unerwartete API-Werte (0.6.8).

parsers.py verspricht: Fehlende oder unpassende Felder ergeben None oder eine
leere Liste statt eines Fehlers. Bis 0.6.7 hielten das _int ("²"),
_datetime (Millisekunden, riesige Zahlen), image_url (Port ausserhalb des
Bereichs) und ratio (NaN, Infinity) nicht ein. Der Fuzz-Test veraendert die
Testantworten zufaellig, aber reproduzierbar (fester Seed).
"""

import copy
import math
import random
from datetime import UTC, datetime

import pytest

from custom_components.bf6_player import parsers

from .conftest import EVENTS, PROFILE, PROFILE_REDUZIERT, SEARCH, STATS, STATUS

# Werte, an denen die Auswertung bis 0.6.7 scheiterte oder scheitern koennte
TRICKY = [
    "²",
    "١٢",
    "",
    " ",
    "12a",
    "-5",
    -1,
    0,
    10**400,
    1.5,
    float("nan"),
    float("inf"),
    -float("inf"),
    1e308,
    1730000000000,
    10**20,
    -(10**20),
    True,
    None,
    [],
    {},
    "https://cdn.gametools.network:99999/x.png",
    "https://cdn.gametools.network:abc/x.png",
    "2026-13-45T99:99:99Z",
    "\u202e\u0000",
    "x" * 1000,
]

PARSERS = [
    (parsers.player_stats, STATS),
    (parsers.player_profile, PROFILE),
    (parsers.player_profile, PROFILE_REDUZIERT),
    (parsers.player_results, SEARCH),
    (parsers.season, EVENTS),
    (parsers.portal_status, STATUS),
]


def _mutate(value, rng: random.Random, rate: float, root: bool = True):
    """Blaetter (und gelegentlich ganze Zweige) durch TRICKY-Werte ersetzen.

    Die Wurzel bleibt ein Objekt: Das sichert api.py zu ("kein JSON-Objekt").
    """
    if not root and rng.random() < rate / 4:
        return rng.choice(TRICKY)
    if isinstance(value, dict):
        return {key: _mutate(item, rng, rate, False) for key, item in value.items()}
    if isinstance(value, list):
        return [_mutate(item, rng, rate, False) for item in value]
    return rng.choice(TRICKY) if rng.random() < rate else value


def _floats_finite(value) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_floats_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_floats_finite(item) for item in value)
    return True


@pytest.mark.parametrize(("parse", "sample"), PARSERS)
def test_fuzzed_answers_do_not_raise(parse, sample) -> None:
    rng = random.Random(f"{parse.__name__}-{len(str(sample))}")
    for _ in range(400):
        data = _mutate(copy.deepcopy(sample), rng, rate=rng.choice([0.05, 0.3, 1.0]))
        result = parse(data)
        assert _floats_finite(result), result


@pytest.mark.parametrize(("parse", "sample"), PARSERS)
def test_tricky_value_in_every_field(parse, sample) -> None:
    """Jedes Feld der obersten Ebene einzeln mit jedem TRICKY-Wert."""
    for key in sample:
        for value in TRICKY:
            parse({**sample, key: value})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("²", None),
        ("١٢", None),
        (" 42 ", 42),
        ("-5", None),
        (float("nan"), None),
        (float("inf"), None),
    ],
)
def test_int_only_ascii_digits(value, expected) -> None:
    assert parsers._int(value) == expected


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (10, float("nan"), None),
        (float("nan"), 10, None),
        (10, float("inf"), None),
        (10**400, 1, None),
        (1e308, 1e-308, None),
        (10, 4, 2.5),
    ],
)
def test_ratio_only_finite(numerator, denominator, expected) -> None:
    assert parsers.ratio(numerator, denominator) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1760313600, datetime(2025, 10, 13, tzinfo=UTC)),
        # Dieselbe Zeit in Millisekunden
        (1760313600000, datetime(2025, 10, 13, tzinfo=UTC)),
        (10**20, None),
        (-(10**20), None),
        ("kein Datum", None),
    ],
)
def test_datetime_seconds_or_milliseconds(value, expected) -> None:
    assert parsers._datetime(value) == expected


def test_season_in_milliseconds() -> None:
    events = copy.deepcopy(EVENTS)
    for event in events["events"]:
        for edge in event.get("validUntil", {}).values():
            if isinstance(edge.get("value"), int):
                edge["value"] *= 1000
    assert parsers.season(events) == parsers.season(EVENTS)


@pytest.mark.parametrize(
    "url",
    [
        "https://cdn.gametools.network:99999/x.png",
        "https://cdn.gametools.network:abc/x.png",
    ],
)
def test_image_url_invalid_port(url) -> None:
    assert parsers.image_url(url) is None
