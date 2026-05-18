"""Tests for wm.panel.summary — PanelReport assembly."""

from __future__ import annotations

import json

from wm.panel.summary import (
    FAIL,
    PARTIAL,
    UNKNOWN,
    WORKING,
    HealthCheck,
    PanelReport,
    build_panel,
)


class TestHealthCheck:
    def test_to_dict_with_detail(self):
        hc = HealthCheck(name="db", status=WORKING, detail="3 tables OK")
        d = hc.to_dict()
        assert d == {"name": "db", "status": "WORKING", "detail": "3 tables OK"}

    def test_to_dict_no_detail(self):
        hc = HealthCheck(name="imports", status=UNKNOWN)
        d = hc.to_dict()
        assert d["detail"] is None


class TestPanelReport:
    def test_to_dict_schema_version(self):
        report = PanelReport()
        d = report.to_dict()
        assert d["schema_version"] == "wm.panel_report.v1"

    def test_to_dict_generated_at_is_utc_iso(self):
        report = PanelReport()
        d = report.to_dict()
        assert d["generated_at"].endswith("Z")

    def test_to_dict_health_serialised(self):
        report = PanelReport(health=[HealthCheck("x", FAIL, "boom")])
        d = report.to_dict()
        assert d["health"][0] == {"name": "x", "status": "FAIL", "detail": "boom"}

    def test_to_dict_is_json_serialisable(self):
        report = PanelReport()
        json.dumps(report.to_dict())  # must not raise


class TestBuildPanel:
    def test_returns_panel_report(self):
        report = build_panel()
        assert isinstance(report, PanelReport)

    def test_has_health_entries(self):
        report = build_panel()
        assert len(report.health) >= 1

    def test_all_health_statuses_are_known_values(self):
        report = build_panel()
        allowed = {WORKING, PARTIAL, FAIL, UNKNOWN}
        for hc in report.health:
            assert hc.status in allowed, f"Unknown status {hc.status!r} for {hc.name}"

    def test_living_catalog_check_present(self):
        report = build_panel()
        names = {hc.name for hc in report.health}
        assert "living.catalog" in names

    def test_living_readiness_keys_are_living_dot_prefixed(self):
        report = build_panel()
        for key in report.living_readiness:
            assert key.startswith("living."), key

    def test_feature_counts_non_empty(self):
        report = build_panel()
        assert report.feature_counts, "expected feature_counts from feature_status.json"

    def test_to_dict_round_trip(self):
        report = build_panel()
        d = report.to_dict()
        raw = json.dumps(d)
        loaded = json.loads(raw)
        assert loaded["schema_version"] == "wm.panel_report.v1"
        assert isinstance(loaded["living_readiness"], dict)
        assert isinstance(loaded["feature_counts"], dict)
