"""Tests fuer parsers.py: Kennzahlen und Listen aus den API-Antworten."""

from datetime import UTC, datetime

import pytest

from custom_components.bf6_player import parsers

from .conftest import EVENTS, PROFILE, SEARCH, STATS, STATS_EMPTY, STATUS


def test_core_values() -> None:
    stats = parsers.player_stats(STATS)
    assert stats["has_results"] is True
    assert stats["kills"] == 1000
    assert stats["deaths"] == 400
    assert stats["losses"] == 20
    assert stats["matches"] == 50
    assert stats["seconds_played"] == 54000
    assert stats["xp"] == 500000
    # Selbst gerechnet, nicht aus killDeath/killsPerMinute uebernommen
    assert stats["kd"] == 2.5
    assert stats["kpm"] == 1.11  # 1000 / (54000 / 60)
    assert stats["win_rate"] == 60.0
    assert stats["accuracy"] == 25.0
    assert stats["headshot_rate"] == 15.0
    assert stats["human_kill_rate"] == 80.0


def test_unknown_ids_have_no_results() -> None:
    stats = parsers.player_stats(STATS_EMPTY)
    assert stats["has_results"] is False
    assert stats["kd"] is None  # 0 Deaths: kein Wert statt Division durch 0
    assert stats["kpm"] is None
    assert stats["win_rate"] is None
    assert stats["weapons"] == []
    assert stats["favorite_class"] is None


@pytest.mark.parametrize("data", [None, {}, {"kills": "viele", "XP": "x", "maps": 3}])
def test_garbage_does_not_raise(data) -> None:
    stats = parsers.player_stats(data)
    assert stats["has_results"] is False
    assert stats["kills"] is None
    assert stats["xp"] is None


def test_top_weapons() -> None:
    weapons = parsers.player_stats(STATS)["weapons"]
    assert [w["name"] for w in weapons] == [
        "Karabiner B",
        "Gewehr A",
        "MP 5",
        "MP 4",
        "MP 3",
    ]
    first = weapons[0]
    assert first["accuracy"] == 20.0
    assert first["headshot_rate"] == 10.0
    assert first["kpm"] == 2.5  # 500 / (12000 / 60)
    assert weapons[1]["image"].endswith("/a.webp")


def test_vehicles_and_gadgets_without_zero_kills() -> None:
    stats = parsers.player_stats(STATS)
    assert [v["name"] for v in stats["vehicles"]] == ["Panzer"]
    assert stats["gadgets"] == [
        {"name": "Werfer", "type": "Launchers", "kills": 12, "image": None}
    ]


def test_classes_without_aggregate() -> None:
    stats = parsers.player_stats(STATS)
    assert [c["name"] for c in stats["classes"]] == ["Support", "Assault"]
    assert stats["classes"][0]["kd"] == 2.67
    assert stats["classes"][0]["kpm"] == 1.2
    assert stats["favorite_class"] == "Support"


def test_maps_deduplicated() -> None:
    result = parsers.player_stats(STATS)["maps"]
    names = [m["name"] for m in result]
    assert "All" not in names
    assert names[:2] == ["Karte Eins", "Karte Zwei"]
    assert result[1]["aliases"] == ["Karte Zwei BR"]
    assert result[1]["win_rate"] == 20.0
    # Ungespielte Karten mit gleichen Nullen werden nicht zusammengelegt
    assert {"Karte Drei", "Karte Vier"} <= set(names)


def test_modes_without_official() -> None:
    result = parsers.player_stats(STATS)["modes"]
    assert [m["name"] for m in result] == ["Conquest", "Rush"]
    assert result[0]["kd"] == 3.0
    assert result[0]["win_rate"] == 66.67


def test_player_results() -> None:
    results = parsers.player_results(SEARCH)
    assert len(results) == 2
    assert results[0] == {
        "persona_id": 1000000001,
        "nucleus_id": 2000000001,
        "platform": "ea",
        "name": "Testspieler",
        "created": datetime(2015, 3, 1, 10, 0, tzinfo=UTC),
        "public": True,
    }
    assert results[1]["public"] is False
    assert parsers.player_results({"results": []}) == []
    assert parsers.player_results(None) == []


def test_profile() -> None:
    assert parsers.player_profile(PROFILE) == {
        "rank": 42,
        "rank_name": "Testrang",
        "rank_image": "https://cdn.gametools.network/ranks/bf6/r_lg.png",
        "dog_tags": 12,
        "badges": 7,
        "ranked": [
            {"season": "CompetitiveSeason5", "mode": "Redsec Quads", "rank": "Unranked"}
        ],
    }


def test_profile_empty() -> None:
    profile = parsers.player_profile({"playerProfiles": [{"badgeSummary": {}}]})
    assert profile["rank"] is None
    assert profile["badges"] is None
    assert profile["ranked"] == []
    assert parsers.player_profile(None)["rank_name"] is None


def test_season() -> None:
    assert parsers.season(EVENTS) == {
        "number": 5,
        "start": datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        "end": datetime(2027, 1, 19, 11, 59, tzinfo=UTC),
        "battle_pass": 5,
    }


def test_season_missing() -> None:
    inactive = {"events": [{"name": "Season5", "active": False}]}
    assert parsers.season(inactive) is None
    assert parsers.season(None) is None


def test_portal_status() -> None:
    assert parsers.portal_status(STATUS) == {
        "servers": 1000,
        "players": 500,
        "queue": 3,
    }
    assert parsers.portal_status({}) == {
        "servers": None,
        "players": None,
        "queue": None,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [("794397421", 794397421), (12, 12), (12.0, 12), (True, None), ("x", None)],
)
def test_int(value, expected) -> None:
    assert parsers._int(value) == expected
