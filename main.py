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

    choice = console.input("\n[bold blue]Select action[/bold blue] [dim]([bold white]1[/bold white]/2/3/4)[/dim]: ").strip() or "1"

    if choice == "1":
        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
    elif choice == "2":
        session_mgr.record_authenticated_traffic(target_url=target_url)
    elif choice == "4":
        session_mgr.capture_interactive_session(target_url=target_url)
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
