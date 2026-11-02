"""Tests fuer die mitgelieferten Karten (0.6.0): Auslieferung, Laden im
Frontend und Abgleich der Karten mit der Integration."""

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.bf6_player import CARD_DIR, CARD_PATH, CARD_SUPPORT, CARDS
from custom_components.bf6_player.const import DOMAIN, PLATFORM_ICONS, PLATFORM_NAMES

MANIFEST = Path(__file__).parents[1] / "custom_components" / DOMAIN / "manifest.json"
VERSION = json.loads(MANIFEST.read_text())["version"]
COMMON = (CARD_DIR / "bf6-common.js").read_text(encoding="utf-8")
IMPORT = (
    "await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, "
    "import.meta.url))"
)


def _element(card: str) -> str:
    return card.removesuffix(".js")


@pytest.mark.parametrize(
    ("card", "element"),
    [(card, _element(card)) for card in CARDS]
    + [("bf6-card-editor.js", "bf6-card-editor")],
)
async def test_card_is_served(
    hass: HomeAssistant, hass_client, card: str, element: str
) -> None:
    assert await async_setup_component(hass, "http", {"http": {}})
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client()
    resp = await client.get(f"{CARD_PATH}/{card}")
    assert resp.status == 200
    text = await resp.text()
    if card == "bf6-card-editor.js":
        assert f'customElements.define("{element}"' in text
    else:
        assert f'C.registrieren("{element}", ' in text


async def test_common_is_served(hass: HomeAssistant, hass_client) -> None:
    assert await async_setup_component(hass, "http", {"http": {}})
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client()
    resp = await client.get(f"{CARD_PATH}/bf6-common.js")
    assert resp.status == 200
    assert "export class Bf6Card extends HTMLElement" in await resp.text()
    # Andere Dateien der Integration sind nicht erreichbar
    assert (await client.get(f"{CARD_PATH}/manifest.json")).status == 404
    assert (await client.get(f"{CARD_PATH}/../manifest.json")).status == 404


async def test_card_loaded_in_frontend(hass: HomeAssistant) -> None:
    """Mit Frontend: nur die Karten als Modul, mit Version im Pfad."""
    assert await async_setup_component(hass, "http", {"http": {}})
    hass.config.components.add("frontend")
    with patch("homeassistant.components.frontend.add_extra_js_url") as add:
        assert await async_setup_component(hass, DOMAIN, {})
    assert [c.args for c in add.call_args_list] == [
        (hass, f"{CARD_PATH}/{card}?v={VERSION}") for card in CARDS
    ]


async def test_card_without_frontend(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "http", {"http": {}})
    with patch("homeassistant.components.frontend.add_extra_js_url") as add:
        assert await async_setup_component(hass, DOMAIN, {})
    add.assert_not_called()


async def test_setup_without_http(hass: HomeAssistant) -> None:
    """Ohne http (z. B. in Tests anderer Teile) laeuft die Einrichtung weiter."""
    with patch("homeassistant.components.frontend.add_extra_js_url") as add:
        assert await async_setup_component(hass, DOMAIN, {})
    add.assert_not_called()


def test_all_frontend_files_listed() -> None:
    """Jede Datei unter frontend/ ist ausgeliefert, keine fehlt."""
    files = {p.name for p in CARD_DIR.iterdir()}
    assert files == set(CARDS) | set(CARD_SUPPORT)


@pytest.mark.parametrize("card", [*CARDS, "bf6-card-editor.js"])
def test_card_loads_common_with_own_version(card: str) -> None:
    """Gemeinsame Teile mit derselben Version im Pfad wie die Karte selbst,
    damit nach einem Update nicht alte und neue Dateien gemischt werden."""
    text = (CARD_DIR / card).read_text(encoding="utf-8")
    assert IMPORT in text


@pytest.mark.parametrize("card", CARDS)
def test_card_has_both_languages(card: str) -> None:
    text = (CARD_DIR / card).read_text(encoding="utf-8")
    block = re.search(r"static TEXT = \{(.*?)\n  \};", text, re.DOTALL)[1]
    assert re.search(r"^\s+de: \{", block, re.MULTILINE)
    assert re.search(r"^\s+en: \{", block, re.MULTILINE)


def _js_map(name: str) -> dict[str, str]:
    block = re.search(rf"export const {name} = \{{\n(.*?)\n\}};", COMMON, re.DOTALL)
    return dict(re.findall(r'^  (\w+): "([^"]+)",$', block[1], re.MULTILINE))


def test_platforms_match_integration() -> None:
    """Symbole und Namen der Plattformen wie in const.py (icons.json)."""
    assert _js_map("PLATTFORM_SYMBOL") == PLATFORM_ICONS
    assert _js_map("PLATTFORM_NAME") == PLATFORM_NAMES


def test_images_only_from_gametools_cdn() -> None:
    """Die Karten pruefen Bildadressen selbst noch einmal (wie IMAGE_HOSTS)."""
    function = re.search(r"export function bild\(url\) \{(.*?)\n\}", COMMON, re.DOTALL)
    assert 'u.protocol === "https:"' in function[1]
    assert 'u.hostname === "cdn.gametools.network"' in function[1]


def test_text_is_escaped() -> None:
    """esc() ersetzt alle fuer HTML bedeutsamen Zeichen."""
    function = re.search(r"export function esc\(value\) \{(.*?)\n\}", COMMON, re.DOTALL)
    for char, entity in (
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&#39;"),
    ):
        assert f'.replace(/{char}/g, "{entity}")' in function[1], char


# Dunkle Werte der Theme-Variablen, die die Karten nutzen, aus
# philf90/home-assistant design/palette.yaml (Abschnitt theme.variablen,
# Commit cfb46ad). Das Theme "nachtblau" setzt sie je Modus; ohne Theme gilt
# der Rueckfall in var() (DESIGN.md, "Karten umstellen").
NACHTBLAU_DUNKEL = {
    "nachtblau-huelle-oben": "#1b2231",
    "nachtblau-huelle-unten": "#171d29",
    "nachtblau-huelle-rand": "rgba(255, 255, 255, 0.05)",
    "nachtblau-schatten": "rgba(0, 0, 0, 0.7)",
    "nachtblau-unterkachel": "rgba(255, 255, 255, 0.028)",
    "nachtblau-unterkachel-rand": "rgba(255, 255, 255, 0.06)",
    "nachtblau-neutral-kachel": "rgba(255, 255, 255, 0.05)",
    "nachtblau-flaeche-vertieft": "#10151d",
    "nachtblau-text": "#f2f5f8",
    "nachtblau-titel": "#e7ecf3",
    "nachtblau-label": "#b4c0cf",
    "nachtblau-text-sekundaer": "#8794a5",
    "nachtblau-gruen": "#a6d49e",
    "nachtblau-amber": "#e6b566",
    "nachtblau-rot": "#f0736a",
    "nachtblau-blau": "#7fb3d5",
    "nachtblau-tuerkis": "#7fd0d5",
    "nachtblau-violett": "#b399d4",
    "nachtblau-rose": "#e6a0c4",
}
_VAR = re.compile(
    r"var\(--(nachtblau-[a-z-]+), ((?:rgba?\([^)]*\))|#[0-9a-fA-F]{3,8})\)"
)
_FARBE = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(")


@pytest.mark.parametrize("datei", sorted(p.name for p in CARD_DIR.glob("*.js")))
def test_colors_follow_theme(datei: str) -> None:
    """Heller Modus (0.6.3): Jede Farbe ist eine Variable des Themes mit dem
    dunklen Palettenwert als Rueckfall, feste Farben gibt es nicht. So folgen
    die Karten mit dem Theme "nachtblau" dem hellen und dem dunklen Modus."""
    text = (CARD_DIR / datei).read_text(encoding="utf-8")
    for name, rueckfall in _VAR.findall(text):
        assert NACHTBLAU_DUNKEL.get(name) == rueckfall, name
    rest = _VAR.sub("", text)
    assert not _FARBE.findall(rest), datei


def test_number_and_unit_stay_together() -> None:
    """Zahl und Prozentzeichen mit geschuetztem Leerzeichen (0.6.3): bei
    344 px brach "21,4 %" in der Arsenal-Karte zwischen Zahl und Zeichen um."""
    function = re.search(r"export function prozent\(.*?\n\}", COMMON, re.DOTALL)
    assert "\\u00a0%" in function[0]
    for datei in CARD_DIR.glob("*.js"):
        text = datei.read_text(encoding="utf-8")
        assert ")} %" not in text, datei.name
        assert not re.search(r"\)\} \$\{(esc\()?this\._t\(", text), datei.name


def test_light_outline_only_dark_and_only_thumbnails() -> None:
    """Lichtrand (0.6.4) um Waffen- und Fahrzeugbilder, im hellen Modus
    ueber nachtblau-dunkel-anteil durchsichtig; das Rang-Abzeichen im Kopf
    bekommt ihn nicht (Entscheidung vom 02.11.2026)."""
    rand = re.search(r"export const LICHTRAND = \[(.*?)\]", COMMON, re.DOTALL)[1]
    assert rand.count("${NUR_DUNKEL(") == 2
    nur_dunkel = re.search(r"const NUR_DUNKEL = .*", COMMON)[0]
    assert "var(--nachtblau-dunkel-anteil, 100%)" in nur_dunkel
    assert re.search(r"\.thumb \{[^}]*filter: \$\{LICHTRAND\}", COMMON)
    assert not re.search(r"\.symbol img \{[^}]*LICHTRAND", COMMON)
