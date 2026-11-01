"""Gemeinsame Fixtures."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bf6_player.const import DOMAIN, MAIN_TITLE


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Custom Integrations in jedem Test laden."""
    return


def main_entry() -> MockConfigEntry:
    """Haupteintrag wie aus dem Einrichtungsdialog."""
    return MockConfigEntry(domain=DOMAIN, title=MAIN_TITLE, unique_id=DOMAIN, data={})
