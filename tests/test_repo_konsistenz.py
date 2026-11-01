"""Konsistenz von Version, Doku, Uebersetzungen und Manifest.

Uebernommen aus WoW Charakter (philf90/HA-WOW): Jede Abweichung faellt hier
auf, bevor ein Release entsteht.
"""

import json
import re
from pathlib import Path

import pytest

from custom_components.bf6_player import const

ROOT = Path(__file__).parents[1]
BASE = ROOT / "custom_components" / "bf6_player"
README = (ROOT / "README.md").read_text(encoding="utf-8")
MANIFEST = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
VERSION = MANIFEST["version"]
MINOR = ".".join(VERSION.split(".")[:2])


def test_version_in_readme_and_release_notes() -> None:
    assert f"Version {VERSION}." in README, "README nennt die Version nicht"
    notes = ROOT / ".github" / "release-notes" / f"v{VERSION}.md"
    assert notes.is_file(), f"{notes.name} fehlt"
    text = notes.read_text(encoding="utf-8")
    assert "## Neu" in text or "## Behoben" in text or "## Geändert" in text
    assert "## Teststand" in text, f"{notes.name}: Abschnitt Teststand fehlt"


def test_readme_test_count_matches(request: pytest.FixtureRequest) -> None:
    """Die Zahl im Teststand muss stimmen; nur beim vollen Lauf pruefbar."""
    items = request.session.items
    if len({Path(str(i.fspath)).name for i in items}) < len(
        list((ROOT / "tests").glob("test_*.py"))
    ):
        pytest.skip("nur beim Lauf aller Testdateien")
    match = re.search(
        rf"\*\*{re.escape(MINOR)}\.x:\*\* (\d+) automatische Tests", README
    )
    assert match, f"Teststand fuer {MINOR}.x fehlt im README"
    assert int(match.group(1)) == len(items), (
        f"README nennt {match.group(1)} Tests, gesammelt sind {len(items)}"
    )


def _flatten(data, prefix=""):
    if isinstance(data, dict):
        for key, value in data.items():
            yield from _flatten(value, f"{prefix}{key}.")
    else:
        yield prefix.rstrip("."), data


def test_translation_files_match() -> None:
    """strings.json = en.json; de.json hat dieselben Schluessel und Platzhalter."""
    strings = json.loads((BASE / "strings.json").read_text(encoding="utf-8"))
    en = json.loads((BASE / "translations/en.json").read_text(encoding="utf-8"))
    de_text = (BASE / "translations/de.json").read_text(encoding="utf-8")
    de = dict(_flatten(json.loads(de_text)))
    assert strings == en, "strings.json und en.json weichen ab"
    en_flat = dict(_flatten(en))
    assert set(en_flat) == set(de), set(en_flat) ^ set(de)
    for key, text in en_flat.items():
        wanted = set(re.findall(r"\{(\w+)\}", text))
        assert wanted == set(re.findall(r"\{(\w+)\}", de[key])), key


def test_manifest_hacs_and_domain_match() -> None:
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert MANIFEST["domain"] == const.DOMAIN == BASE.name
    assert hacs["name"] == MANIFEST["name"]
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert f"custom_components/{const.DOMAIN}/manifest.json" in release
    script = (ROOT / ".github" / "scripts" / "pruefe_pr.py").read_text()
    assert f'"custom_components/{const.DOMAIN}/manifest.json"' in script
