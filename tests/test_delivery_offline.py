"""
Offline tests for Phase 5 delivery module. Tests everything we can without
real SharePoint credentials:
    - Local file organization into year folders
    - Latest.xlsx pointer update
    - HTML index generation
    - SharePoint graceful skip when env vars absent
    - SharePoint error diagnosis mapping

Run:
    python tests/test_delivery_offline.py
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Clear any real SharePoint vars so we're testing in isolation
for var in ["SHAREPOINT_SITE_URL", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET",
            "SHAREPOINT_USERNAME", "SHAREPOINT_PASSWORD"]:
    os.environ.pop(var, None)

import delivery
from delivery import (
    organize_local, generate_index, upload_to_sharepoint,
    _extract_date_from_name, _sharepoint_configured,
    _diagnose_sharepoint_error,
)


def _make_fake_report(dirpath: Path, name: str) -> Path:
    """Create a dummy xlsx file so the organizer has something to move."""
    p = dirpath / name
    p.write_bytes(b"FAKE-XLSX-CONTENT")
    return p


def test_extract_date():
    assert _extract_date_from_name("weekly_report_2024-12-31.xlsx") == "2024-12-31"
    assert _extract_date_from_name("report_2023-06-15_v2.xlsx") == "2023-06-15"
    assert _extract_date_from_name("no_date_here.xlsx") is None
    print("[PASS] test_extract_date passed")


def test_organize_local_creates_year_folder():
    with tempfile.TemporaryDirectory() as tmp:
        reports_dir = Path(tmp) / "reports"
        reports_dir.mkdir()
        # Save originals for restoration
        orig_reports = delivery.REPORTS_DIR
        orig_index = delivery.INDEX_PATH
        orig_latest = delivery.LATEST_PATH
        delivery.REPORTS_DIR = reports_dir
        delivery.INDEX_PATH  = reports_dir / "index.html"
        delivery.LATEST_PATH = reports_dir / "latest.xlsx"

        try:
            report = _make_fake_report(reports_dir, "weekly_report_2024-12-31.xlsx")
            result = organize_local(report, reports_dir)

            # Year folder exists and contains the file
            assert (reports_dir / "weekly" / "2024" / "weekly_report_2024-12-31.xlsx").exists()

            # Latest pointer exists and has the same content
            assert delivery.LATEST_PATH.exists()
            assert delivery.LATEST_PATH.read_bytes() == b"FAKE-XLSX-CONTENT"

            # Index was regenerated
            assert delivery.INDEX_PATH.exists()
            assert "weekly_report_2024-12-31.xlsx" in delivery.INDEX_PATH.read_text()
        finally:
            delivery.REPORTS_DIR = orig_reports
            delivery.INDEX_PATH  = orig_index
            delivery.LATEST_PATH = orig_latest

    print("[PASS] test_organize_local_creates_year_folder passed")


def test_index_lists_multiple_years():
    with tempfile.TemporaryDirectory() as tmp:
        reports_dir = Path(tmp) / "reports"
        reports_dir.mkdir()
        orig_reports = delivery.REPORTS_DIR
        orig_index = delivery.INDEX_PATH
        orig_latest = delivery.LATEST_PATH
        delivery.REPORTS_DIR = reports_dir
        delivery.INDEX_PATH  = reports_dir / "index.html"
        delivery.LATEST_PATH = reports_dir / "latest.xlsx"

        try:
            # Organize reports across two years
            r1 = _make_fake_report(reports_dir, "weekly_report_2023-03-15.xlsx")
            r2 = _make_fake_report(reports_dir, "weekly_report_2024-01-07.xlsx")
            r3 = _make_fake_report(reports_dir, "weekly_report_2024-12-31.xlsx")
            organize_local(r1, reports_dir)
            organize_local(r2, reports_dir)
            organize_local(r3, reports_dir)

            html = delivery.INDEX_PATH.read_text()
            assert "2023" in html
            assert "2024" in html
            assert "weekly_report_2023-03-15.xlsx" in html
            assert "weekly_report_2024-12-31.xlsx" in html
            # Latest pointer should be the most recently organized one
            # (regardless of date -- organize_local updates it each call)
            assert delivery.LATEST_PATH.read_bytes() == b"FAKE-XLSX-CONTENT"
        finally:
            delivery.REPORTS_DIR = orig_reports
            delivery.INDEX_PATH  = orig_index
            delivery.LATEST_PATH = orig_latest

    print("[PASS] test_index_lists_multiple_years passed")


def test_sharepoint_not_configured():
    """With no env vars set, _sharepoint_configured must be False."""
    assert _sharepoint_configured() is False

    with tempfile.TemporaryDirectory() as tmp:
        report = _make_fake_report(Path(tmp), "weekly_report_2024-12-31.xlsx")
        result = upload_to_sharepoint(report)

    assert result["status"] == "skipped"
    assert "not configured" in result["reason"].lower()
    print("[PASS] test_sharepoint_not_configured passed")


def test_sharepoint_configured_requires_all_pieces():
    """Setting only SITE_URL is not enough -- need CLIENT_ID + secret/password too."""
    os.environ["SHAREPOINT_SITE_URL"] = "https://example.sharepoint.com/sites/test"
    try:
        assert _sharepoint_configured() is False

        os.environ["SHAREPOINT_CLIENT_ID"] = "fake-id"
        assert _sharepoint_configured() is False  # still missing secret

        os.environ["SHAREPOINT_CLIENT_SECRET"] = "fake-secret"
        assert _sharepoint_configured() is True
    finally:
        for var in ["SHAREPOINT_SITE_URL", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET"]:
            os.environ.pop(var, None)
    print("[PASS] test_sharepoint_configured_requires_all_pieces passed")


def test_error_diagnosis():
    """Verify common SharePoint error strings map to helpful hints."""
    assert "auth" in _diagnose_sharepoint_error("Server returned 401 Unauthorized").lower()
    assert "permission" in _diagnose_sharepoint_error("403 Forbidden").lower()
    assert "site" in _diagnose_sharepoint_error("404 Not Found: site URL").lower()
    assert "network" in _diagnose_sharepoint_error("Failed to resolve hostname").lower()
    # Unknown error should still return SOME hint
    assert len(_diagnose_sharepoint_error("wild error")) > 0
    print("[PASS] test_error_diagnosis passed")


if __name__ == "__main__":
    test_extract_date()
    test_organize_local_creates_year_folder()
    test_index_lists_multiple_years()
    test_sharepoint_not_configured()
    test_sharepoint_configured_requires_all_pieces()
    test_error_diagnosis()
    print("\nAll Phase 5 offline tests passed. Safe to run the real delivery.")
