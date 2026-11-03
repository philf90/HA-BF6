"""Verhalten der Dashboard-Karten, ausgefuehrt in Node.js (0.6.10).

Die uebrigen Kartentests lesen den Quelltext; so blieb bis 0.6.9 unbemerkt,
dass die Klassen-Karte die Spielzeit ungeprueft in style="flex:..." setzte
(Review B8). Hier rendert tests/karten_lauf.mjs jede Karte mit einem
nachgebauten hass-Objekt, einmal mit normalen Werten und einmal mit einem
Text, der aus jedem HTML-Attribut ausbrechen wuerde. Ausserdem zaehlt es, wie
oft die Karten alle Entitaeten durchlaufen (Review B7).

Braucht Node.js. Fehlt es, wird lokal uebersprungen; in der CI (Variable CI)
schlaegt der Test fehl, damit er dort nie still ausfaellt.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from custom_components.bf6_player import CARD_DIR, CARDS

NODE = shutil.which("node")
LAUF = Path(__file__).with_name("karten_lauf.mjs")
BOESE_ROH = "<img src=x"
ELEMENTE = [card.removesuffix(".js") for card in CARDS]

pytestmark = pytest.mark.skipif(
    NODE is None and not os.environ.get("CI"),
    reason="Node.js fehlt (in der CI Pflicht)",
)


@pytest.fixture(scope="module")
def ergebnis(tmp_path_factory) -> dict:
    if NODE is None:
        pytest.fail("Node.js fehlt in der CI")
    ziel = tmp_path_factory.mktemp("karten")
    for datei in CARD_DIR.glob("*.js"):
        shutil.copy(datei, ziel / datei.name)
    # Als ES-Module laden, unabhaengig von der Node-Version
    (ziel / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    shutil.copy(LAUF, ziel / LAUF.name)
    lauf = subprocess.run(
        [NODE, str(ziel / LAUF.name)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


def test_all_cards_are_run(ergebnis) -> None:
    assert sorted(ergebnis["karten"]) == sorted(ELEMENTE)


@pytest.mark.parametrize("element", ELEMENTE)
def test_card_renders(ergebnis, element: str) -> None:
    html = ergebnis["karten"][element]["normal"]
    # mdi:alert zeigt _render() nur, wenn _inhalt() eine Ausnahme warf
    assert "mdi:alert" not in html
    assert "<ha-card>" in html
    if element != "bf6-world-card":
        assert "Testspieler" in html, "Karte hat keinen Spieler gefunden"


@pytest.mark.parametrize("element", ELEMENTE)
def test_no_html_from_entity_values(ergebnis, element: str) -> None:
    """Namen, Attribute und Spielzeit mit '"><img src=x onerror=...>'."""
    html = ergebnis["karten"][element]["boese"]
    assert "mdi:alert" not in html
    assert BOESE_ROH not in html


def test_classes_card_uses_numbers_in_style(ergebnis) -> None:
    """B8: Eine Spielzeit, die keine Zahl ist, zaehlt als 0 und bekommt keinen
    Balken; die Klasse mit echter Zahl behaelt ihren (bis 0.6.9 zwei Balken,
    einer davon mit dem Text im style-Attribut)."""
    boese = ergebnis["karten"]["bf6-classes-card"]["boese"]
    normal = ergebnis["karten"]["bf6-classes-card"]["normal"]
    assert boese.count('style="flex:') == 1
    assert 'style="flex:1800;' in boese
    assert normal.count('style="flex:') == 2
    assert 'style="flex:7200;' in normal


def test_index_built_once_for_many_updates(ergebnis) -> None:
    """B7: 100 Zustandsaenderungen mit 8 Karten durchlaufen die Entitaeten
    kein weiteres Mal (bis 0.6.9: bei jeder Aenderung je Karte)."""
    index = ergebnis["index"]
    assert index["durchlaeufe_erster_aufbau"] == 1
    assert index["durchlaeufe_100_updates_8_karten"] == 0
    assert index["gleiche_liste"] is True


def test_index_follows_registry_changes(ergebnis) -> None:
    index = ergebnis["index"]
    assert index["spieler"] == [
        {
            "name": "Testspieler",
            "modell": "Battlefield 6 · Steam",
            "kills": "sensor.spieler_kills",
        }
    ]
    assert index["welt"] == "BF6-Spielwelt"
    assert index["name_nach_umbenennen"] == "Neuer Name"
    assert index["spieler_ohne_kills_sensor"] == 0
    assert index["ohne_entities"] == 0


def test_shared_lists_are_frozen(ergebnis) -> None:
    """Alle Karten teilen die Listen; eine Aenderung wuerde einen Fehler werfen."""
    assert ergebnis["index"]["eingefroren"] is True


def test_arsenal_card_shows_gadgets(ergebnis) -> None:
    """Seit 0.7.0 dritte Gruppe (Review E1), auch ohne Einstellung "show"."""
    html = ergebnis["karten"]["bf6-arsenal-card"]["normal"]
    assert '<span class="gname">Gadgets</span>' in html
    assert "G-Testspieler" in html


def test_world_card_shows_queue(ergebnis) -> None:
    html = ergebnis["karten"]["bf6-world-card"]["normal"]
    assert '<span class="l">Warte\u00adschlange</span><span class="n">3</span>' in html


# --- B26: Rang-Abzeichen ueber den Bild-Proxy (0.7.1) ------------------------

PROXY_BILD = "/api/image_proxy/image.spieler_rang_abzeichen?token=0a1b2c3d"
KOPF_KARTEN = [e for e in ELEMENTE if e not in ("bf6-squad-card", "bf6-world-card")]


@pytest.mark.parametrize("element", KOPF_KARTEN)
def test_badge_via_image_proxy(ergebnis, element: str) -> None:
    """Bis 0.7.0 setzten die Karten rank_image (CDN) direkt ein; die
    Pruefungen der Bild-Entitaet galten dort nicht (Review B26)."""
    html = ergebnis["karten"][element]["normal"]
    assert f'<img src="{PROXY_BILD}" alt="">' in html
    assert "cdn.gametools.network/ranks" not in html


def test_no_badge_without_image(ergebnis) -> None:
    """Bild-Entitaet ohne Bild (unbekannt) oder unpassende Adresse: Symbol."""
    for fall in ("ohne_bild", "fremd", "pfad"):
        assert "<img" not in ergebnis["kopf"][fall], fall
        assert "<ha-icon" in ergebnis["kopf"][fall], fall
