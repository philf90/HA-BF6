"""Tests fuer Diagnose, Optionen und Reparaturhinweis (0.5.0)."""

import json

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from custom_components.bf6_player.const import DOMAIN
from custom_components.bf6_player.coordinator import issue_id
from custom_components.bf6_player.diagnostics import async_get_config_entry_diagnostics

from .conftest import (
    PROFILE,
    STATS,
    STATS_EMPTY,
    main_entry,
    mock_world,
    player_subentry,
)

BASE = "https://api.gametools.network"
STATS_URL = f"{BASE}/bf6/stats/"


async def _setup(hass, entry=None):
    entry = entry or main_entry(player_subentry())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_diagnostics_without_names_and_ids(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = await _setup(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(diag, default=str)
    assert "Testspieler" not in text
    assert "1000000001" not in text
    assert "2000000001" not in text
    player = diag["players"][0]
    assert player["subentry"]["platform"] == "ea"
    assert player["subentry"]["persona_id"] == "**REDACTED**"
    assert player["data"]["stats"]["kills"] == 1000
    assert player["last_update_success"] is True
    assert player["update_interval_s"] == 900
    assert player["profile_interval_s"] == 3600
    assert diag["world"]["data"]["portal"]["servers"] == 1000


async def test_options_change_intervals(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(STATS_URL, json=STATS)
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"stats_interval": 30, "profile_interval": 20}
    )
    assert result["errors"] == {"base": "profile_before_stats"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"stats_interval": 30, "profile_interval": 120}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    # Neu geladen mit den neuen Takten
    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    assert coordinator.update_interval.total_seconds() == 1800
    assert coordinator.profile_interval.total_seconds() == 7200


async def test_issue_when_no_stats_and_gone_when_back(
    hass: HomeAssistant, aioclient_mock
):
    aioclient_mock.get(STATS_URL, json=STATS_EMPTY)
    entry = await _setup(hass)
    subentry_id = next(iter(entry.subentries))
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id(subentry_id))
    assert issue is not None
    assert issue.translation_placeholders == {"player": "Testspieler · EA app"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATS_URL, json=STATS)
    aioclient_mock.get(f"{BASE}/bf6/profile/", json=PROFILE)
    mock_world(aioclient_mock)
    coordinator = entry.runtime_data.coordinators[subentry_id]
    await coordinator.async_refresh()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id(subentry_id)) is None


async def test_stale_issue_removed_on_start(hass: HomeAssistant, aioclient_mock):
    ir.async_create_issue(
        hass,
        DOMAIN,
        "no_stats_alt",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="no_stats",
        translation_placeholders={"player": "x"},
    )
    aioclient_mock.get(STATS_URL, json=STATS)
    await _setup(hass)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "no_stats_alt") is None
