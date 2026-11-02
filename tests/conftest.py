"""Gemeinsame Fixtures."""

import pytest
from homeassistant.config_entries import ConfigSubentryData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bf6_player.const import DOMAIN, MAIN_TITLE, SUBENTRY_PLAYER


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Custom Integrations in jedem Test laden."""
    return


# Module, die die Spielwelt-Abfragen selbst nachbauen (eigene Antworten)
OWN_WORLD_MOCKS = {"test_api", "test_spielwelt", "test_sensoren"}


@pytest.fixture(autouse=True)
def auto_mock_world(request, aioclient_mock):
    """Jeder geladene Haupteintrag fragt die Spielwelt ab: nachbauen."""
    if request.module.__name__.rsplit(".", 1)[-1] not in OWN_WORLD_MOCKS:
        mock_world(aioclient_mock)
        # Profil der Spieler; die Statistik baut jeder Test selbst nach.
        aioclient_mock.get("https://api.gametools.network/bf6/profile/", json=PROFILE)


def main_entry(*subentries: ConfigSubentryData) -> MockConfigEntry:
    """Haupteintrag wie aus dem Einrichtungsdialog, optional mit Spielern."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MAIN_TITLE,
        unique_id=DOMAIN,
        data={},
        subentries_data=list(subentries),
    )


def player_subentry(
    persona_id: int = 1000000001,
    nucleus_id: int = 2000000001,
    platform: str = "ea",
    name: str = "Testspieler",
) -> ConfigSubentryData:
    """Untereintrag eines Spielers wie aus dem Dialog "Spieler hinzufuegen"."""
    return ConfigSubentryData(
        data={
            "name": name,
            "persona_id": persona_id,
            "nucleus_id": nucleus_id,
            "platform": platform,
        },
        subentry_type=SUBENTRY_PLAYER,
        title=name,
        unique_id=str(persona_id),
    )


# Antworten im Aufbau der gametools API (echte Antworten vom 01./02.11.2026);
# Namen, IDs und Zahlen sind erfunden.
PERSONA_ID = 1000000001
NUCLEUS_ID = 2000000001

SEARCH = {
    "results": [
        {
            "platform": "ea",
            "nucleusId": str(NUCLEUS_ID),
            "visibility": "EVERYONE",
            "personaId": str(PERSONA_ID),
            "username": "testspieler",
            "createdAt": "2015-03-01T10:00:00Z",
            "displayName": "Testspieler",
            "status": "ACTIVE",
            "platformId": "cem_ea_id",
        },
        {
            "platform": "steam",
            "nucleusId": "2000000002",
            "visibility": "NO_ONE",
            "personaId": "1000000002",
            "username": "testspieler",
            "createdAt": "2024-05-06T07:08:09Z",
            "displayName": "Testspieler",
            "status": "ACTIVE",
            "platformId": "steam",
        },
        # Ohne gueltige IDs: faellt weg
        {"platform": "pc", "personaId": "", "nucleusId": None},
    ]
}

STATS = {
    "userId": str(NUCLEUS_ID),
    "userName": "testspieler",
    "id": str(PERSONA_ID),
    "humanPrecentage": 80.0,
    "score": 100000,
    "kills": 1000,
    "deaths": 400,
    "wins": 30,
    "loses": 20,
    "assists": 300,
    "killsPerMinute": 1.11,
    "headShots": 150,
    "winPercent": 60.0,
    "headshots": 15.0,
    "killDeath": 2.5,
    "accuracy": 25.0,
    "revives": 120,
    "matchesPlayed": 50,
    "secondsPlayed": 54000,
    "shotsFired": 20000,
    "shotsHit": 5000,
    "dividedKills": {"human": 800, "ads": 600},
    "XP": [{"total": 500000, "performance": 100000, "accolades": 20000}],
    "weapons": [
        {
            "type": "Assault Rifles",
            "weaponName": "Gewehr A",
            "image": "https://cdn.gametools.network/weapons/bf6/a.webp",
            "id": "wp_ar_a",
            "kills": 300,
            "headshotKills": 60,
            "shotsHit": 1500,
            "shotsFired": 6000,
            "timeEquipped": 9000,
        },
        {
            "type": "Carbines",
            "weaponName": "Karabiner B",
            "id": "wp_cb_b",
            "kills": 500,
            "headshotKills": 50,
            "shotsHit": 2000,
            "shotsFired": 10000,
            "timeEquipped": 12000,
        },
        {"type": "Pistols", "weaponName": "Pistole C", "id": "wp_p_c", "kills": 0},
    ]
    + [
        {"type": "SMG", "weaponName": f"MP {n}", "id": f"wp_smg_{n}", "kills": n}
        for n in range(1, 6)
    ],
    "vehicles": [
        {"type": "Ground Combat", "vehicleName": "Panzer", "kills": 40, "timeIn": 600},
        {"type": "Air Combat", "vehicleName": "Jet", "kills": 0, "timeIn": 60},
    ],
    "gadgets": [{"type": "Launchers", "gadgetName": "Werfer", "kills": 12}],
    "classes": [
        {
            "className": "All",
            "id": "kit",
            "kills": 1000,
            "deaths": 400,
            "secondsPlayed": 50000,
        },
        {
            "className": "Assault",
            "id": "kit_assault",
            "kills": 200,
            "deaths": 100,
            "secondsPlayed": 10000,
        },
        {
            "className": "Support",
            "id": "kit_support",
            "kills": 800,
            "deaths": 300,
            "secondsPlayed": 40000,
        },
    ],
    "maps": [
        {
            "mapName": "All",
            "id": "lvlmp",
            "wins": 30,
            "losses": 20,
            "matches": 50,
            "secondsPlayed": 50000,
        },
        {
            "mapName": "Karte Eins",
            "id": "lvl1",
            "wins": 10,
            "losses": 5,
            "matches": 15,
            "secondsPlayed": 15000,
        },
        {
            "mapName": "Karte Zwei",
            "id": "lvl2",
            "wins": 2,
            "losses": 8,
            "matches": 10,
            "secondsPlayed": 9000,
        },
        # Doppelt wie "Fort Lyndon" und "REDSEC" am 01.11.2026
        {
            "mapName": "Karte Zwei BR",
            "id": "lvl2br",
            "wins": 2,
            "losses": 8,
            "matches": 10,
            "secondsPlayed": 9000,
        },
        {
            "mapName": "Karte Drei",
            "id": "lvl3",
            "wins": 0,
            "losses": 0,
            "matches": 0,
            "secondsPlayed": 0,
        },
        {
            "mapName": "Karte Vier",
            "id": "lvl4",
            "wins": 0,
            "losses": 0,
            "matches": 0,
            "secondsPlayed": 0,
        },
    ],
    "gameModes": [
        {
            "gamemodeName": "Conquest",
            "id": "gm_cq",
            "kills": 600,
            "deaths": 200,
            "wins": 20,
            "losses": 10,
            "matches": 30,
        },
        {
            "gamemodeName": "Official",
            "id": "gm_official",
            "kills": 1000,
            "deaths": 400,
            "wins": 30,
            "losses": 20,
            "matches": 50,
        },
        {
            "gamemodeName": "Rush",
            "id": "gm_rush",
            "kills": 400,
            "deaths": 200,
            "wins": 10,
            "losses": 10,
            "matches": 20,
        },
    ],
    "hasResults": True,
    "platform": "pc",
}

# Unbekannte IDs: HTTP 200, hasResults false, alles 0 (live am 02.11.2026)
STATS_EMPTY = {
    "userId": "1",
    "userName": None,
    "id": "1",
    "kills": 0,
    "deaths": 0,
    "wins": 0,
    "loses": 0,
    "matchesPlayed": 0,
    "secondsPlayed": 0,
    "weapons": [],
    "maps": [],
    "hasResults": False,
}

PROFILE = {
    "playerProfiles": [
        {
            "stats": [{"name": "score_total", "value": 100000}],
            "playerCard": {
                "rank": 42,
                "badges": 9,
                "rankImage": {
                    "small": "https://cdn.gametools.network/ranks/bf6/r_sm.png",
                    "large": "https://cdn.gametools.network/ranks/bf6/r_lg.png",
                },
            },
            "totalDogTags": {"intValue": 12},
            "badgeSummary": {"totalBadges": 7, "badges": []},
            "competitiveRanks": [
                {
                    "type": "CompetitiveSeason5",
                    "mode": "GraniteSquad0",
                    "modeName": "Redsec Quads",
                    "rankName": "Unranked",
                    "rankImage": None,
                }
            ],
            "rankName": "Testrang",
        }
    ]
}

EVENTS = {
    "events": [
        {
            "name": "Season4",
            "active": False,
            "validUntil": {
                "start": {"value": 1784635200},
                "end": {"value": 1791892799},
            },
        },
        {
            "name": "Season5",
            "active": True,
            "validUntil": {
                "start": {"value": 1791892800},
                "end": {"value": 1800359940},
            },
        },
        {
            "name": "BP05",
            "active": True,
            "validUntil": {
                "start": {"value": 1791892800},
                "end": {"value": 1800359940},
            },
        },
        {
            "name": "S05_weekly_group",
            "active": True,
            "validUntil": {
                "start": {"value": 1791892800},
                "end": {"value": 1800359940},
            },
        },
    ]
}

STATUS = {
    "regions": {
        "ALL": {
            "region": "ALL",
            "amounts": {"queueAmount": 3, "serverAmount": 1000, "soldierAmount": 500},
        },
        "EU": {"region": "EU", "amounts": {"serverAmount": 400}},
    }
}


def mock_world(aioclient_mock, events=EVENTS, status=STATUS) -> None:
    """Abfragen der Spielwelt nachbauen (jeder geladene Haupteintrag)."""
    aioclient_mock.get("https://api.gametools.network/bf6/gameevents/", json=events)
    aioclient_mock.get("https://api.gametools.network/bf6/status/", json=status)
