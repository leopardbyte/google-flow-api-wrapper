import sys
import json
import uvicorn
from session import SessionManager
from client import FlowClient
from terminal_ui import (
    console,
    print_header,
    print_session_card,
    print_menu,
    print_projects_table,
    get_session_summary,
)
from rich.panel import Panel
from rich.text import Text

def main():
    session_mgr = SessionManager()
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://labs.google/fx/tools/flow"

    console.clear()
    print_header(target_url=target_url)

    # Get local session diagnostics
    session_summary = get_session_summary(session_file=session_mgr.session_file)

    # If session is active, attempt a quick live credits check for display
    live_credits = None
    if session_summary.get("is_authenticated"):
        try:
            flow_client = FlowClient(session_mgr=session_mgr)
            live_credits = flow_client.get_credits()
        except Exception:
            live_credits = None

    print_session_card(session_summary, live_credits=live_credits)
    print_menu()

    choice = console.input("\n[bold blue]Select action[/bold blue] [dim]([bold white]1[/bold white]/2/3/4/5)[/dim]: ").strip() or "1"

    if choice == "1":
        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
    elif choice == "2":
        session_mgr.record_authenticated_traffic(target_url=target_url)
    elif choice == "4":
        session_mgr.capture_interactive_session(target_url=target_url)
    elif choice == "5":
        console.print("\n[bold blue]✦ Import Cookies / Storage State[/bold blue]")
        console.print("[dim]Tip: In Chrome/Edge on https://labs.google/fx/tools/flow, click Cookie-Editor -> 'Export' -> 'Export as JSON', then paste here.[/dim]\n")
        
        clipboard_content = None
        try:
            import subprocess
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True, text=True, timeout=3)
            cb_text = proc.stdout.strip()
            if cb_text.startswith("[") or cb_text.startswith("{"):
                clipboard_content = cb_text
        except Exception:
            pass

        raw_json = None
        if clipboard_content:
            console.print("[bold green]Found JSON on clipboard![/bold green]")
            use_cb = console.input("[bold white]Import from clipboard? (Y/n): [/bold white]").strip().lower()
            if use_cb != "n":
                raw_json = clipboard_content

        if not raw_json:
            console.print("[dim]Paste your cookie JSON below and press Enter:[/dim]")
            raw_json = console.input("[bold cyan]JSON: [/bold cyan]").strip()

        try:
            saved_state = session_mgr.import_cookie_data(raw_json)
            c_count = len(saved_state.get("cookies", []))
            u_email = (saved_state.get("user") or {}).get("email", "Authenticated")
            tok = bool(saved_state.get("access_token"))
            console.print(Panel(
                f"[bold green]✓ Successfully imported {c_count} cookies![/bold green]\nUser: {u_email} • Token: {'Active' if tok else 'Refreshed on request'}\nSaved to '{session_mgr.session_file}'",
                border_style="green",
                title="Session Imported"
            ))
        except Exception as e:
            console.print(Panel(f"[bold red]Import Error:[/bold red] {e}", border_style="red"))
    elif choice == "3":
        try:
            console.print("\n[bold blue]✦ Initializing FlowClient API...[/bold blue]")
            flow_client = FlowClient(session_mgr=session_mgr)

            # 1. User Credits & Balance
            console.print("[dim]Fetching live user credit balance...[/dim]")
            credits_data = flow_client.get_credits()
            creds = credits_data.get("credits", "N/A")
            tier = credits_data.get("userPaygateTier", "N/A")

            cred_panel = Panel(
                Text.assemble(
                    ("Live Credits: ", "bold bright_black"),
                    (f"{creds} credits", "bold green" if str(creds).isdigit() and int(creds) > 0 else "bold yellow"),
                    ("  •  Paygate Tier: ", "bold bright_black"),
                    (f"{tier}", "bold white")
                ),
                title="[bold green]● Google Flow Balance[/bold green]",
                border_style="green",
            )
            console.print(cred_panel)

            # 2. Search Projects
            console.print("\n[dim]Searching user projects (recent 10)...[/dim]")
            projects_data = flow_client.search_user_projects(page_size=10)
            print_projects_table(projects_data)

        except Exception as e:
            console.print(Panel(f"[bold red]API Error:[/bold red] {e}", border_style="red", title="FlowClient Error"))

if __name__ == "__main__":
    main()
