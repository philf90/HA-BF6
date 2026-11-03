"""Tests fuer parsers.py: Kennzahlen und Listen aus den API-Antworten."""

import copy
from datetime import UTC, datetime

import pytest

from custom_components.bf6_player import parsers

from .conftest import (
    EVENTS,
    PROFILE,
    PROFILE_REDUZIERT,
    SEARCH,
    STATS,
    STATS_EMPTY,
    STATUS,
)


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


def test_modes_deduplicated() -> None:
    """Gleiche Zahlen unter zwei Modi (live am 02.11.2026: gm_oblit und
    gm_oblitall) stehen einmal, der zweite Name unter "aliases"; ungespielte
    Modi und Modi mit anderen Zahlen bleiben getrennt."""
    mode = {"kills": 20, "deaths": 12, "wins": 0, "losses": 1, "matches": 1}
    data = {
        "gameModes": [
            {"gamemodeName": "Obliteration", "id": "gm_a", **mode, "secondsPlayed": 9},
            {
                "gamemodeName": "Obliteration X",
                "id": "gm_b",
                **mode,
                "secondsPlayed": 9,
            },
            {"gamemodeName": "Obliteration", "id": "gm_c", **mode, "secondsPlayed": 9},
            {"gamemodeName": "Anders", "id": "gm_d", **mode, "secondsPlayed": 10},
            {"gamemodeName": "Leer A", "id": "gm_e", "matches": 0},
            {"gamemodeName": "Leer B", "id": "gm_f", "matches": 0},
        ]
    }
    result = parsers.modes(data)
    assert [m["name"] for m in result] == ["Obliteration", "Anders", "Leer A", "Leer B"]
    assert result[0]["aliases"] == ["Obliteration X"]
    assert result[0]["kd"] == 1.67
    assert result[1]["aliases"] == []


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


def test_profile_reduced() -> None:
    """Privates Konto (0.6.5): Rang, Rangname und Bild aus der verkuerzten
    Antwort; das flache "badges" bleibt ungenutzt, weil es nicht der Zahl im
    Spiel entsprach."""
    assert parsers.player_profile(PROFILE_REDUZIERT) == {
        "rank": 77,
        "rank_name": "Testoberst",
        "rank_image": "https://cdn.gametools.network/ranks/bf6/p_lg.png",
        "dog_tags": None,
        "badges": None,
        "ranked": [],
    }
    # Bildadressen auch hier nur von cdn.gametools.network
    fremd = copy.deepcopy(PROFILE_REDUZIERT)
    fremd["other"][0]["playerProfiles"][0]["rankImage"]["large"] = (
        "https://evil.example/r.png"
    )
    assert parsers.player_profile(fremd)["rank_image"] is None
    # Leere oder kaputte Formen: nichts, kein Fehler
    for leer in (
        {"other": []},
        {"other": [{}]},
        {"other": "x"},
        {"other": [{"playerProfiles": []}]},
    ):
        assert parsers.player_profile(leer)["rank"] is None


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
    [("1000000001", 1000000001), (12, 12), (12.0, 12), (True, None), ("x", None)],
)
def test_int(value, expected) -> None:
    assert parsers._int(value) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://cdn.gametools.network/ranks/bf6/r.png", True),
        ("http://cdn.gametools.network/ranks/bf6/r.png", False),
        ("https://192.168.1.1/admin", False),
        ("https://cdn.gametools.network.example.com/x.png", False),
        ("https://user:pw@cdn.gametools.network/x.png", False),
        ("https://cdn.gametools.network:8123/x.png", False),
        ("javascript:alert(1)", False),
        ("file:///etc/passwd", False),
        ("", False),
        (None, False),
        ("https://[::1/x", False),
    ],
)
def test_image_url(url, expected) -> None:
    assert (parsers.image_url(url) is not None) is expected
    assert parsers.image_url(url) in (url, None)


def test_images_filtered_in_stats_and_profile() -> None:
    data = {
        **STATS,
        "weapons": [
            {"weaponName": "A", "kills": 2, "image": "https://10.0.0.1/a.png"},
            {
                "weaponName": "B",
                "kills": 1,
                "image": "https://cdn.gametools.network/b.webp",
            },
        ],
    }
    weapons = parsers.player_stats(data)["weapons"]
    assert [w["image"] for w in weapons] == [
        None,
        "https://cdn.gametools.network/b.webp",
    ]
    profile = {
        "playerProfiles": [{"playerCard": {"rankImage": {"large": "http://evil/x"}}}]
    }
    assert parsers.player_profile(profile)["rank_image"] is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Normal_Name-123", "Normal_Name-123"),
        ("  [Clan] Nämé ★  ", "[Clan] Nämé ★"),
        ("a\nb\x00c\td", "abcd"),
        (chr(0x202E) + "abc" + chr(0x2066), "abc"),
        ("\n\x00", None),
        ("x" * 100, "x" * 64),
        (42, None),
    ],
)
def test_clean_name(value, expected) -> None:
    assert parsers.clean_name(value) == expected


# --- Fehlende Bilder (0.7.1) -------------------------------------------------


def test_image_problem():
    assert parsers.image_problem("https://cdn.gametools.network/a.png") is None
    assert parsers.image_problem("") == "empty"
    assert parsers.image_problem("   ") == "empty"
    assert parsers.image_problem(None) == "empty"
    assert parsers.image_problem(17) == "empty"
    assert parsers.image_problem("https://eaassets.example/a.png") == (
        "host:eaassets.example"
    )
    assert parsers.image_problem("http://cdn.gametools.network/a.png") == "invalid"
    assert parsers.image_problem("https://cdn.gametools.network:8443/a") == "invalid"
    assert parsers.image_problem("https://cdn.gametools.network:abc/a") == "invalid"


def test_missing_images_only_with_kills_sorted():
    data = {
        "weapons": [
            {
                "weaponName": "Mit Bild",
                "kills": 900,
                "image": "https://cdn.gametools.network/w.png",
            },
            {"weaponName": "Fremd", "kills": 50, "image": "https://evil.example/w.png"},
        ],
        "vehicles": [
            {"vehicleName": "Ohne Kill", "kills": 0, "image": ""},
        ],
        "gadgets": [
            {"gadgetName": "Frag Grenade", "kills": 342, "image": ""},
            {"gadgetName": "Ohne Feld", "kills": 7},
        ],
    }
    assert parsers.missing_images(data) == [
        {"list": "gadgets", "name": "Frag Grenade", "kills": 342, "problem": "empty"},
        {
            "list": "weapons",
            "name": "Fremd",
            "kills": 50,
            "problem": "host:evil.example",
        },
        {"list": "gadgets", "name": "Ohne Feld", "kills": 7, "problem": "empty"},
    ]
    assert len(parsers.missing_images(data, limit=1)) == 1
    assert parsers.missing_images({}) == []
    assert parsers.missing_images({"gadgets": "kaputt"}) == []
