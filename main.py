import sys
import json
import uvicorn
from session import SessionManager
from client import FlowClient

def main():
    session_mgr = SessionManager()

    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://labs.google/fx/tools/flow"

    print("--- Google Flow API & Network Suite ---")
    print(f"[+] Target URL: {target_url}")
    print("\nSelect mode:")
    print("  [1] Start Custom Local API Server (http://127.0.0.1:8000 with terminal showcase & Swagger UI)")
    print("  [2] Record Network Traffic (opens browser with session, logs all API/XHR requests as you interact)")
    print("  [3] Test FlowClient API Wrapper (fetches user credits & user projects via HTTP API)")
    print("  [4] Capture New Session (login manually to export fresh cookies)")
    
    choice = input("\nEnter choice (1/2/3/4) [default: 1]: ").strip() or "1"

    if choice == "1":
        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
    elif choice == "2":
        session_mgr.record_authenticated_traffic(target_url=target_url)
    elif choice == "4":
        session_mgr.capture_interactive_session(target_url=target_url)
    else:
        try:
            print("\n[+] Initializing FlowClient...")
            flow_client = FlowClient(session_mgr=session_mgr)
            
            # Fetch user credits
            print("\n[+] Fetching user credits balance...")
            credits_data = flow_client.get_credits()
            print("[+] Credits Response:", json.dumps(credits_data, indent=2))

            # Fetch user projects
            print("\n[+] Searching user projects...")
            projects_data = flow_client.search_user_projects(page_size=5)
            print("[+] Projects Search Response:", json.dumps(projects_data, indent=2))

        except Exception as e:
            print(f"[-] Error testing API client: {e}")

if __name__ == "__main__":
    main()
