import json
import os
import httpx
from cloakbrowser import launch
from config import SESSION_FILE, DEFAULT_HEADERS

class SessionManager:
    def __init__(self, session_file=SESSION_FILE):
        self.session_file = session_file

    def capture_interactive_session(self, target_url: str, wait_selector: str = "body", timeout_ms: int = 180000):
        """
        Launches an interactive CloakBrowser window with humanize mode enabled.
        Allows you to manually log in or complete authentication prompts.
        Saves the resulting cookies and storage state to disk.
        """
        print(f"[+] Launching CloakBrowser session at: {target_url}")
        browser = launch(headless=False, humanize=False)
        try:
            context = browser.new_context()
            page = context.new_page()

            page.goto(target_url)
            print("[!] Interactive browser window open.")
            print("[!] Log in manually. Press Enter in the terminal once your session is active.")
            
            # Interactive prompt in terminal to signal login completion
            input("[Press ENTER here when you are logged in and ready to save the session] ")

            # Capture storage state (cookies, local storage, session tokens)
            storage = context.storage_state()
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(storage, f, indent=2)

            print(f"[+] Real session state saved to '{self.session_file}'")
        finally:
            try:
                if browser.is_connected():
                    browser.close()
            except Exception:
                pass

    def get_authenticated_client(self) -> httpx.Client:
        """Returns an HTTPX client populated with stored cookies and headers."""
        if not os.path.exists(self.session_file):
            raise FileNotFoundError(
                f"Session file '{self.session_file}' not found. "
                "Call capture_interactive_session() first."
            )

        with open(self.session_file, "r", encoding="utf-8") as f:
            storage = json.load(f)

        if isinstance(storage, list):
            cookies_list = storage
        elif isinstance(storage, dict):
            cookies_list = storage.get("cookies", [])
        else:
            cookies_list = []

        client = httpx.Client(headers=DEFAULT_HEADERS, timeout=30.0)

        for cookie in cookies_list:
            client.cookies.set(
                name=cookie["name"],
                value=cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

        return client

    def fetch_bearer_token(self, client: httpx.Client = None) -> str:
        """
        Calls the session authentication endpoint using session cookies
        to retrieve the OAuth Bearer token.
        """
        if client is None:
            client = self.get_authenticated_client()

        res = client.get("https://labs.google/fx/api/auth/session")
        if res.status_code != 200:
            raise RuntimeError(f"Failed to fetch session token: HTTP {res.status_code} - {res.text}")

        data = res.json()
        # Look for access token in typical NextAuth session response keys
        token = data.get("accessToken") or data.get("access_token") or data.get("token")
        return token

    def get_authenticated_api_client(self) -> httpx.Client:
        """
        Returns an HTTPX client populated with session cookies AND the 
        OAuth Bearer authorization header required for backend API calls.
        """
        client = self.get_authenticated_client()
        token = self.fetch_bearer_token(client=client)
        if token:
            client.headers["Authorization"] = f"Bearer {token}"
            print(f"[+] OAuth Bearer token successfully attached.")
        else:
            print("[!] Warning: Could not find explicit Bearer token in session response.")
        return client

    def record_authenticated_traffic(self, target_url: str, output_file: str = "captured_requests.json"):
        """
        Launches an interactive browser window with stored session cookies pre-loaded.
        Monitors and records all API (XHR/Fetch) requests while the user interacts with the page.
        Saves the captured requests to disk when finished.
        """
        if not os.path.exists(self.session_file):
            raise FileNotFoundError(f"Session file '{self.session_file}' not found.")

        with open(self.session_file, "r", encoding="utf-8") as f:
            storage = json.load(f)

        cookies_raw = storage if isinstance(storage, list) else storage.get("cookies", [])
        
        # Format cookies for Playwright
        cookies = []
        for c in cookies_raw:
            cookie_dict = {
                "name": c["name"],
                "value": c["value"],
            }
            if c["name"].startswith("__Host-") or not c.get("domain"):
                cookie_dict["url"] = "https://labs.google"
            else:
                cookie_dict["domain"] = c["domain"]
                cookie_dict["path"] = c.get("path", "/")

            if "secure" in c and c["secure"] is not None:
                cookie_dict["secure"] = bool(c["secure"])
            if "httpOnly" in c and c["httpOnly"] is not None:
                cookie_dict["httpOnly"] = bool(c["httpOnly"])
            if "sameSite" in c and c["sameSite"]:
                s = str(c["sameSite"]).capitalize()
                if s in ["Strict", "Lax", "None"]:
                    cookie_dict["sameSite"] = s
            cookies.append(cookie_dict)

        print(f"[+] Pre-loading {len(cookies)} cookies into browser session...")
        browser = launch(headless=False, humanize=False)
        captured = []

        try:
            context = browser.new_context()
            context.add_cookies(cookies)
            page = context.new_page()

            def on_request(req):
                if req.resource_type in ["xhr", "fetch"]:
                    post_data_str = None
                    try:
                        post_data_str = req.post_data
                    except Exception:
                        try:
                            buf = req.post_data_buffer
                            if buf:
                                import base64
                                post_data_str = f"[binary data: {len(buf)} bytes, base64: {base64.b64encode(buf).decode('ascii')[:100]}...]"
                        except Exception:
                            post_data_str = None

                    entry = {
                        "url": req.url,
                        "method": req.method,
                        "headers": dict(req.headers),
                        "post_data": post_data_str,
                    }
                    captured.append(entry)
                    print(f"  [REQ] {req.method} -> {req.url}")
                    # Auto-save immediately so no requests are lost on Ctrl+C or browser close
                    try:
                        with open(output_file, "w", encoding="utf-8") as f:
                            json.dump(captured, f, indent=2)
                    except Exception:
                        pass

            page.on("request", on_request)

            print(f"[+] Navigating to: {target_url}")
            page.goto(target_url)

            print("\n" + "=" * 60)
            print("[!] BROWSER WINDOW IS ACTIVE WITH YOUR LOGGED-IN SESSION")
            print("[!] Perform your actions now (upload images, change settings, generate media, etc.)")
            print("[!] All XHR/Fetch network requests are being recorded in real-time.")
            print("=" * 60 + "\n")

            input("[Press ENTER in this terminal when you have completed your test actions] ")

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(captured, f, indent=2)

            print(f"\n[+] Successfully saved {len(captured)} network request(s) to '{output_file}'")

        finally:
            try:
                if browser.is_connected():
                    browser.close()
            except Exception:
                pass
