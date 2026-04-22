"""
Phase 5: Report Delivery Module
================================
Takes the Excel report produced by Phase 4 and delivers it two ways:

    LOCAL MODE (always runs):
        - Organizes reports into reports/weekly/YYYY/ subfolders
        - Maintains reports/latest.xlsx pointing to the newest report
        - Generates reports/index.html for easy browsing

    SHAREPOINT MODE (optional, runs if SHAREPOINT_* env vars are set):
        - Uploads the Excel file to a configured document library
        - Tags it with metadata (data-period end date)
        - Falls back silently if network/auth fails

Design principles:
    1. Local delivery ALWAYS succeeds first -- never let SharePoint auth
       block the user from having a local copy
    2. Never crash the pipeline. Log errors, return structured results.
    3. Credentials come from .env ONLY -- never accept them as CLI args
       or function params that could end up in shell history

Run:
    python src/delivery.py

Outputs:
    reports/weekly/2024/weekly_report_2024-12-31.xlsx   (organized)
    reports/latest.xlsx                                   (pointer copy)
    reports/index.html                                    (browsable list)
    (Optional) SharePoint document library upload
"""

from __future__ import annotations

import json
import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


REPORTS_DIR = Path("reports")
INDEX_PATH = REPORTS_DIR / "index.html"
LATEST_PATH = REPORTS_DIR / "latest.xlsx"


# =============================================================================
# LOCAL DELIVERY (always runs)
# =============================================================================
def organize_local(report_path: Path, reports_dir: Path = REPORTS_DIR) -> dict:
    """
    Move/copy the report into a year-based subfolder, update the 'latest'
    pointer, and regenerate the HTML index.

    Returns a dict with paths for the Phase 6 / logs.
    """
    report_path = Path(report_path)
    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")

    # Parse the data-date from the filename (e.g., weekly_report_2024-12-31.xlsx)
    # This determines which year-folder the report lives in.
    date_str = _extract_date_from_name(report_path.name)
    year = date_str[:4] if date_str else str(datetime.now().year)

    # Destination: reports/weekly/YYYY/
    dest_dir = reports_dir / "weekly" / year
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / report_path.name

    # Copy rather than move, so the source location stays intact if someone
    # wants to inspect it. A production tool might choose move for space.
    if report_path.resolve() != dest_path.resolve():
        shutil.copy2(report_path, dest_path)

    # Update the "latest" pointer -- a plain copy works cross-platform
    # (symlinks are fragile on Windows without admin privileges)
    shutil.copy2(dest_path, LATEST_PATH)

    # Regenerate the HTML index
    index_path = generate_index(reports_dir)

    return {
        "organized_path": str(dest_path),
        "latest_path":    str(LATEST_PATH),
        "index_path":     str(index_path),
    }


def _extract_date_from_name(filename: str) -> Optional[str]:
    """Find a YYYY-MM-DD pattern inside a filename."""
    import re
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else None


def generate_index(reports_dir: Path = REPORTS_DIR) -> Path:
    """
    Walk reports/weekly/* and produce a clean HTML page listing every report
    grouped by year, most recent first.
    """
    reports_dir = Path(reports_dir)
    weekly_root = reports_dir / "weekly"

    # Collect (year, report_path, date_str) tuples
    entries: list[tuple[str, Path, str]] = []
    if weekly_root.exists():
        for year_dir in sorted(weekly_root.iterdir(), reverse=True):
            if not year_dir.is_dir():
                continue
            for report in sorted(year_dir.glob("*.xlsx"), reverse=True):
                date = _extract_date_from_name(report.name) or ""
                entries.append((year_dir.name, report, date))

    html = _render_index_html(entries)
    INDEX_PATH.write_text(html, encoding="utf-8")
    return INDEX_PATH


def _render_index_html(entries: list[tuple[str, Path, str]]) -> str:
    """Produce a simple, clean browsable HTML index of reports."""
    # Group by year
    by_year: dict[str, list[tuple[Path, str]]] = {}
    for year, path, date in entries:
        by_year.setdefault(year, []).append((path, date))

    year_sections = []
    for year, items in by_year.items():
        rows = "\n".join(
            f'            <tr>'
            f'<td>{date}</td>'
            f'<td><a href="weekly/{year}/{p.name}" target="_blank">{p.name}</a></td>'
            f'<td class="num">{p.stat().st_size / 1024:.1f} KB</td>'
            f'</tr>'
            for p, date in items
        )
        year_sections.append(f"""
        <section>
          <h2>{year}</h2>
          <table>
            <thead><tr><th>Date</th><th>File</th><th class="num">Size</th></tr></thead>
            <tbody>
{rows}
            </tbody>
          </table>
        </section>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Weekly 80/20 Reports</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         max-width: 880px; margin: 40px auto; padding: 0 20px; color: #1F2A44; }}
  h1 {{ border-bottom: 2px solid #1F2A44; padding-bottom: 8px; }}
  h2 {{ margin-top: 32px; color: #4A5D7E; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #E5E7EB; }}
  th {{ background: #F4F6FA; font-weight: 600; font-size: 14px; color: #4A5D7E; }}
  tr:hover {{ background: #FAFAFA; }}
  a {{ color: #1F6FEB; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; color: #6B7280; }}
  .latest {{ background: #D6F0DC; padding: 12px 16px; border-radius: 6px; margin: 20px 0; }}
  .latest a {{ font-weight: 600; }}
  footer {{ margin-top: 40px; color: #9CA3AF; font-size: 13px; text-align: center; }}
</style>
</head>
<body>
<h1>Weekly 80/20 Analytics Reports</h1>

<div class="latest">
  <strong>Latest:</strong> <a href="latest.xlsx">latest.xlsx</a>
  &nbsp;&middot;&nbsp; {len(entries)} report(s) total
</div>
{"".join(year_sections) if year_sections else "<p><em>No reports yet.</em></p>"}

<footer>
  Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} by the AI-Assisted Data Quality Pipeline
</footer>
</body>
</html>"""


# =============================================================================
# SHAREPOINT DELIVERY (optional)
# =============================================================================
def _sharepoint_configured() -> bool:
    """True if enough env vars are set to attempt a SharePoint upload."""
    return bool(
        os.getenv("SHAREPOINT_SITE_URL")
        and os.getenv("SHAREPOINT_CLIENT_ID")
        and (os.getenv("SHAREPOINT_CLIENT_SECRET") or os.getenv("SHAREPOINT_USERNAME"))
    )


def upload_to_sharepoint(local_path: Path) -> dict:
    """
    Upload a report to SharePoint using whatever auth credentials are
    present in the environment. Returns a result dict -- never raises.

    Preferred auth order:
        1. App-only (CLIENT_ID + CLIENT_SECRET)  -- recommended for automation
        2. User credentials (USERNAME + password)-- legacy fallback
    """
    if not _sharepoint_configured():
        return {"status": "skipped", "reason": "SharePoint env vars not configured"}

    try:
        # Lazy import so the pipeline works for users who don't install
        # the SharePoint library. Only imported when we actually need it.
        from office365.runtime.auth.client_credential import ClientCredential
        from office365.runtime.auth.user_credential import UserCredential
        from office365.sharepoint.client_context import ClientContext
    except ImportError:
        return {
            "status": "error",
            "reason": "Office365-REST-Python-Client not installed. "
                      "Run: pip install Office365-REST-Python-Client",
        }

    site_url = os.getenv("SHAREPOINT_SITE_URL")
    library  = os.getenv("SHAREPOINT_DOC_LIBRARY", "Shared Documents")

    # Build the right credential object based on what's available
    client_id     = os.getenv("SHAREPOINT_CLIENT_ID")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
    username      = os.getenv("SHAREPOINT_USERNAME")
    password      = os.getenv("SHAREPOINT_PASSWORD")

    try:
        if client_id and client_secret:
            credentials = ClientCredential(client_id, client_secret)
            auth_mode = "app-only"
        elif username and password:
            credentials = UserCredential(username, password)
            auth_mode = "user"
        else:
            return {"status": "skipped",
                    "reason": "Insufficient SharePoint credentials in env"}

        ctx = ClientContext(site_url).with_credentials(credentials)

        # Test connection by fetching site info BEFORE uploading the file.
        # Fails fast with a clear error if auth is wrong.
        web = ctx.web.get().execute_query()
        _ = web.title  # touch a property to confirm the fetch worked

        # Upload
        local_path = Path(local_path)
        with open(local_path, "rb") as f:
            file_content = f.read()

        target_folder = ctx.web.get_folder_by_server_relative_url(library)
        uploaded = target_folder.upload_file(local_path.name, file_content).execute_query()

        return {
            "status":     "success",
            "auth_mode":  auth_mode,
            "site_title": web.title,
            "library":    library,
            "file_name":  local_path.name,
            "server_url": uploaded.serverRelativeUrl,
        }

    except Exception as e:
        # SharePoint auth errors are the most common failure. We catch
        # everything and return structured info so the pipeline continues.
        return {
            "status": "error",
            "reason": str(e)[:200],
            "hint":   _diagnose_sharepoint_error(str(e)),
        }


def _diagnose_sharepoint_error(msg: str) -> str:
    """Map common error text to an actionable hint."""
    lower = msg.lower()
    if "unauthorized" in lower or "401" in lower:
        return ("Authentication failed. Check that SHAREPOINT_CLIENT_ID and "
                "SHAREPOINT_CLIENT_SECRET are correct and that the app has "
                "been granted permissions on the target site.")
    if "forbidden" in lower or "403" in lower:
        return ("Authentication succeeded but the app lacks permissions. "
                "Grant 'Sites.ReadWrite.All' in Azure AD and have an admin "
                "consent to it.")
    if "not found" in lower or "404" in lower:
        return ("Site or document library not found. Verify "
                "SHAREPOINT_SITE_URL and SHAREPOINT_DOC_LIBRARY values.")
    if "name resolution" in lower or "failed to resolve" in lower:
        return "Network / DNS issue. Check that the SharePoint URL is reachable."
    return "See the error message above and check your .env values."


# =============================================================================
# ORCHESTRATOR
# =============================================================================
def deliver(report_path: Optional[str] = None) -> dict:
    """
    Run both delivery paths. Local always runs; SharePoint runs if configured.
    Returns a structured result dict for logging / Phase 6 integration.
    """
    # Find the most recent report if not explicitly provided
    if report_path is None:
        candidates = sorted(REPORTS_DIR.glob("weekly_report_*.xlsx"), reverse=True)
        if not candidates:
            raise FileNotFoundError(
                "No reports/weekly_report_*.xlsx found. Run Phase 4 first:\n"
                "  python src/reporter.py"
            )
        report_path = candidates[0]
    report_path = Path(report_path)

    print(f"Delivering report: {report_path.name}")
    print()

    # --- Local delivery (always) ------------------------------------------
    print("[Local]  Organizing into reports/weekly/...")
    local_result = organize_local(report_path)
    print(f"[Local]  Copied to:     {local_result['organized_path']}")
    print(f"[Local]  Latest ptr:    {local_result['latest_path']}")
    print(f"[Local]  Index page:    {local_result['index_path']}")
    print()

    # --- SharePoint delivery (optional) -----------------------------------
    print("[SharePoint]  Attempting upload...")
    sp_result = upload_to_sharepoint(report_path)
    status = sp_result["status"]

    if status == "success":
        print(f"[SharePoint]  ✓ Uploaded to '{sp_result['site_title']}' "
              f"via {sp_result['auth_mode']} auth")
        print(f"[SharePoint]  Server URL:   {sp_result['server_url']}")
    elif status == "skipped":
        print(f"[SharePoint]  Skipped:      {sp_result['reason']}")
        print(f"[SharePoint]  (Set SHAREPOINT_* env vars in .env to enable.)")
    else:
        print(f"[SharePoint]  ✗ Failed:     {sp_result['reason']}")
        if sp_result.get("hint"):
            print(f"[SharePoint]  Hint:         {sp_result['hint']}")

    print()
    result = {
        "report_path": str(report_path),
        "local":       local_result,
        "sharepoint":  sp_result,
        "delivered_at": datetime.now().isoformat(timespec="seconds"),
    }

    # Write a delivery log so you have a record for audit / debugging
    log_path = REPORTS_DIR / "delivery_log.json"
    existing = []
    if log_path.exists():
        try:
            existing = json.loads(log_path.read_text())
        except Exception:
            existing = []
    existing.append(result)
    log_path.write_text(json.dumps(existing, indent=2))
    print(f"Delivery log appended to {log_path}")

    return result


if __name__ == "__main__":
    deliver()
