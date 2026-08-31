import os
import sys
import json
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any, List

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console(force_terminal=True, highlight=False)

def parse_cookie_email(cookies: List[Dict[str, Any]]) -> Optional[str]:
    """Extracts and unquotes email address from EMAIL or user cookie if present."""
    for c in cookies:
        if c.get("name") in ["EMAIL", "user_email", "ACCOUNT_EMAIL"]:
            raw_val = c.get("value", "")
            unquoted = urllib.parse.unquote(raw_val).strip('"').strip("'")
            if "@" in unquoted:
                return unquoted
    return None

def get_session_summary(session_file: str = "session_state.json") -> Dict[str, Any]:
    """Reads session_state.json and extracts structured profile and token details."""
    summary = {
        "exists": False,
        "name": None,
        "email": None,
        "cookie_email": None,
        "access_token": None,
        "token_preview": None,
        "cookie_count": 0,
        "exported_at": None,
        "is_authenticated": False,
    }

    if not os.path.exists(session_file):
        return summary

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary["exists"] = True
        cookies = []
        if isinstance(data, list):
            cookies = data
        elif isinstance(data, dict):
            cookies = data.get("cookies", [])
            user = data.get("user") or {}
            summary["name"] = user.get("name")
            summary["email"] = user.get("email")
            
            token = data.get("access_token") or data.get("accessToken")
            if token:
                summary["access_token"] = token
                if len(token) > 18:
                    summary["token_preview"] = f"{token[:8]}...{token[-6:]}"
                else:
                    summary["token_preview"] = token

            summary["exported_at"] = data.get("exportedAt")

        summary["cookie_count"] = len(cookies)
        summary["cookie_email"] = parse_cookie_email(cookies)
        summary["is_authenticated"] = bool(summary["access_token"] or summary["cookie_count"] > 0)

    except Exception as e:
        summary["error"] = str(e)

    return summary

def format_timestamp(iso_str: Optional[str]) -> str:
    """Formats an ISO timestamp to human-friendly string."""
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y - %H:%M:%S UTC")
    except Exception:
        return iso_str

def print_header(target_url: str = "https://labs.google/fx/tools/flow"):
    """Renders the top application branding header."""
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)

    title_text = Text.assemble(
        ("✦ GOOGLE FLOW ", "bold blue"),
        ("STUDIO API WRAPPER", "bold white"),
        (" (Omni 1.1 Flash)", "dim")
    )
    version_text = Text("v1.1.0 • Local Suite", style="dim")
    grid.add_row(title_text, version_text)

    panel = Panel(
        grid,
        border_style="blue",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)

def print_session_card(session_summary: Dict[str, Any], live_credits: Optional[Dict[str, Any]] = None):
    """Renders a clean profile and session diagnostics panel."""
    table = Table(box=box.SIMPLE_HEAD, show_header=False, expand=True, padding=(0, 1))
    table.add_column("Key", style="bold bright_black", width=18)
    table.add_column("Value", style="white")

    if not session_summary.get("exists") or not session_summary.get("is_authenticated"):
        status_val = Text("○ Unauthenticated (No active session found)", style="yellow")
        table.add_row("Session Status", status_val)
        table.add_row("Tip", "Run Tampermonkey 1-Click Sync or select option [4]")
        panel = Panel(
            table,
            title="[bold red]Authentication Diagnostics[/bold red]",
            title_align="left",
            border_style="dim",
            box=box.ROUNDED,
        )
        console.print(panel)
        return

    # User identity
    name = session_summary.get("name") or "Authenticated User"
    email = session_summary.get("email") or session_summary.get("cookie_email") or "Active Google Account"
    cookie_alias = session_summary.get("cookie_email")

    user_text = Text.assemble(
        (f"{name} ", "bold white"),
        (f"<{email}>", "dim cyan" if not cookie_alias or cookie_alias == email else "dim blue")
    )
    table.add_row("👤 Account", user_text)

    if cookie_alias and cookie_alias != email:
        table.add_row("🍪 Cookie Alias", Text(cookie_alias, style="dim"))

    # Token status
    if session_summary.get("access_token"):
        tok_preview = session_summary.get("token_preview", "Active")
        tok_val = Text.assemble(
            ("● Active ", "green"),
            (f"(OAuth 2.0 Bearer: {tok_preview})", "dim")
        )
    else:
        tok_val = Text("● Cookie Session Only (Bearer token will be refreshed on request)", "dim green")
    table.add_row("🔑 Token Status", tok_val)

    # Live Credits if provided
    if live_credits:
        creds = live_credits.get("credits", "N/A")
        tier = live_credits.get("userPaygateTier", "N/A")
        cred_text = Text.assemble(
            (f"{creds} Credits", "bold green" if str(creds).isdigit() and int(creds) > 0 else "bold yellow"),
            (f"  •  Tier: {tier}", "dim")
        )
        table.add_row("💳 Live Credits", cred_text)

    # Cookies count & Export time
    cookies_count = session_summary.get("cookie_count", 0)
    export_time = format_timestamp(session_summary.get("exported_at"))
    table.add_row(
        "📦 Session Store",
        Text.assemble(
            (f"{cookies_count} cookies loaded", "dim"),
            (f"  •  Last Synced: {export_time}", "dim")
        )
    )

    panel = Panel(
        table,
        title="[bold green]● Active Session Diagnostics[/bold green]",
        title_align="left",
        border_style="green",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)

def print_menu():
    """Renders the main interactive selection table."""
    table = Table(
        box=box.ROUNDED,
        expand=True,
        header_style="bold bright_black",
        border_style="blue",
        padding=(0, 1),
    )
    table.add_column("Key", justify="center", style="bold blue", width=6)
    table.add_column("Action / Mode", style="bold white", width=32)
    table.add_column("Description", style="dim")

    table.add_row(
        "1",
        "Start Local REST API Server",
        "Runs FastAPI server on http://127.0.0.1:8000 with Swagger UI & Tampermonkey sync"
    )
    table.add_row(
        "2",
        "Record Network Traffic",
        "Spawns browser with session to log all XHR/Fetch API calls in real-time"
    )
    table.add_row(
        "3",
        "Test FlowClient API Wrapper",
        "Fetches live account balance & queries your recent Google Flow projects"
    )
    table.add_row(
        "4",
        "Capture New Session",
        "Manual browser login capture fallback (Tampermonkey userscript recommended)"
    )

    panel = Panel(
        table,
        title="[bold blue]Select Execution Mode[/bold blue]",
        title_align="left",
        border_style="blue",
        box=box.ROUNDED,
        padding=(0, 0),
    )
    console.print(panel)

def print_server_dashboard(session_summary: Dict[str, Any], live_credits: Optional[Dict[str, Any]] = None):
    """Renders server startup information dashboard in app.py."""
    console.print()
    print_header()
    print_session_card(session_summary, live_credits)

    endpoints_table = Table(
        box=box.ROUNDED,
        expand=True,
        header_style="bold bright_black",
        border_style="blue",
        padding=(0, 1),
    )
    endpoints_table.add_column("Method", justify="center", width=8)
    endpoints_table.add_column("Endpoint", style="bold white", width=28)
    endpoints_table.add_column("Description", style="dim")

    endpoints_table.add_row("[blue]GET[/blue]", "/", "Health check & service summary")
    endpoints_table.add_row("[blue]GET[/blue]", "/api/credits", "Fetch live account credits and paygate tier")
    endpoints_table.add_row("[blue]GET[/blue]", "/api/projects", "List recent Google Flow projects")
    endpoints_table.add_row("[blue]GET[/blue]", "/api/session/status", "Verify current session validity & profile")
    endpoints_table.add_row("[green]POST[/green]", "/api/session/import", "1-Click session sync from Tampermonkey")
    endpoints_table.add_row("[green]POST[/green]", "/api/create-project", "Create a new project workspace")
    endpoints_table.add_row("[green]POST[/green]", "/api/generate", "Generate video (JSON with Start/End frames)")
    endpoints_table.add_row("[green]POST[/green]", "/api/generate-with-image", "Generate video via multipart file upload")
    endpoints_table.add_row("[green]POST[/green]", "/api/check-status", "Check status of active rendering tasks")

    links_grid = Table.grid(expand=True, padding=(0, 3))
    links_grid.add_column(ratio=1)
    links_grid.add_column(ratio=1)
    links_grid.add_row(
        Text.assemble(("🌐 Local Server: ", "bold bright_black"), ("http://127.0.0.1:8000", "bold cyan")),
        Text.assemble(("📖 OpenAPI Docs: ", "bold bright_black"), ("http://127.0.0.1:8000/docs", "bold cyan")),
    )

    combined_group = Table.grid(expand=True)
    combined_group.add_row(links_grid)
    combined_group.add_row(Text(""))
    combined_group.add_row(endpoints_table)

    panel = Panel(
        combined_group,
        title="[bold blue]🚀 Local REST API Server Active[/bold blue]",
        title_align="left",
        border_style="blue",
        box=box.ROUNDED,
        padding=(1, 1),
    )
    console.print(panel)
    console.print()

def print_projects_table(projects_data: Dict[str, Any]):
    """Formats and prints user projects in a clean table."""
    try:
        # trpc responses are typically { "result": { "data": { "json": { "projects": [...] } } } }
        items = []
        if isinstance(projects_data, dict):
            res_data = projects_data.get("result", {}).get("data", {}).get("json", {})
            if isinstance(res_data, dict):
                items = res_data.get("projects", [])
            elif isinstance(projects_data.get("projects"), list):
                items = projects_data.get("projects", [])

        if not items:
            console.print(Panel(Text(json.dumps(projects_data, indent=2), style="dim"), title="Projects Raw Output", border_style="dim"))
            return

        table = Table(
            box=box.ROUNDED,
            expand=True,
            header_style="bold blue",
            border_style="blue",
            padding=(0, 1),
        )
        table.add_column("#", justify="center", width=4, style="dim")
        table.add_column("Project ID", style="bold white", width=34)
        table.add_column("Title / Name", style="white")
        table.add_column("Created / Updated", style="dim", width=22)

        for idx, p in enumerate(items, 1):
            pid = p.get("projectId") or p.get("id") or "N/A"
            title = p.get("title") or p.get("name") or "Untitled Project"
            updated = p.get("updateTime") or p.get("createTime") or "N/A"
            table.add_row(str(idx), str(pid), str(title), str(updated)[:19])

        panel = Panel(
            table,
            title=f"[bold green]User Projects ({len(items)} found)[/bold green]",
            title_align="left",
            border_style="green",
            box=box.ROUNDED,
        )
        console.print(panel)

    except Exception as e:
        console.print(f"[red]Error rendering projects table: {e}[/red]")
        console.print(Panel(Text(json.dumps(projects_data, indent=2), style="dim")))
