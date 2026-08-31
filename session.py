import json
import os
import httpx
from typing import Optional
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

            # Attempt to fetch live OAuth session profile directly inside browser context
            try:
                auth_data = page.evaluate("() => fetch('/fx/api/auth/session').then(r => r.json()).catch(() => null)")
                if auth_data:
                    token = auth_data.get("accessToken") or auth_data.get("access_token") or auth_data.get("token")
                    if token:
                        storage["access_token"] = token
                        storage["accessToken"] = token
                    if auth_data.get("user"):
                        storage["user"] = auth_data["user"]
            except Exception:
                pass

            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(storage, f, indent=2)

            cookie_count = len(storage.get("cookies", []))
            print(f"[+] Real session state saved to '{self.session_file}' ({cookie_count} cookies captured, OAuth token: {bool(storage.get('access_token'))})")
        finally:
            try:
                if browser.is_connected():
                    browser.close()
            except Exception:
                pass

    def import_cookie_data(self, data_input) -> dict:
        """
        Imports cookie list, Cookie-Editor JSON, or Playwright storage state.
        Preserves existing valid OAuth tokens and user info, verifies session with Google,
        and saves complete session to session_state.json.
        """
        existing_data = {}
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except Exception:
                existing_data = {}

        if isinstance(data_input, str):
            try:
                data = json.loads(data_input.strip())
            except Exception as e:
                raise ValueError(f"Invalid JSON string: {e}")
        else:
            data = data_input

        if isinstance(data, list):
            cookies = data
            origins = existing_data.get("origins", [])
            user = existing_data.get("user")
            access_token = existing_data.get("access_token") or existing_data.get("accessToken")
        elif isinstance(data, dict):
            cookies = data.get("cookies", [])
            origins = data.get("origins", existing_data.get("origins", []))
            user = data.get("user", existing_data.get("user"))
            access_token = data.get("access_token") or data.get("accessToken") or existing_data.get("access_token")
        else:
            raise ValueError("Input must be a JSON array of cookies or a storage dictionary.")

        # Clean / normalize cookies for Playwright & httpx
        formatted_cookies = []
        for c in cookies:
            cookie_dict = {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", "labs.google"),
                "path": c.get("path", "/"),
            }
            if "secure" in c and c["secure"] is not None:
                cookie_dict["secure"] = bool(c["secure"])
            if "httpOnly" in c and c["httpOnly"] is not None:
                cookie_dict["httpOnly"] = bool(c["httpOnly"])
            if "sameSite" in c and c["sameSite"]:
                s = str(c["sameSite"]).capitalize()
                if s in ["Strict", "Lax", "None"]:
                    cookie_dict["sameSite"] = s
            if "expires" in c and c["expires"] is not None and c["expires"] > 0:
                cookie_dict["expires"] = float(c["expires"])
            elif "expirationDate" in c and c["expirationDate"] is not None:
                cookie_dict["expires"] = float(c["expirationDate"])

            formatted_cookies.append(cookie_dict)

        storage_data = {
            "cookies": formatted_cookies,
            "origins": origins,
            "access_token": access_token,
            "accessToken": access_token,
            "user": user
        }

        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(storage_data, f, indent=2)

        # Attempt to verify and retrieve fresh token/user
        try:
            client = self.get_authenticated_client()
            res = client.get("https://labs.google/fx/api/auth/session")
            if res.status_code == 200:
                auth_info = res.json()
                if auth_info.get("accessToken"):
                    storage_data["access_token"] = auth_info["accessToken"]
                    storage_data["accessToken"] = auth_info["accessToken"]
                if auth_info.get("user"):
                    storage_data["user"] = auth_info["user"]
                with open(self.session_file, "w", encoding="utf-8") as f:
                    json.dump(storage_data, f, indent=2)
        except Exception:
            pass

        return storage_data

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

    def fetch_bearer_token(self, client: httpx.Client = None) -> Optional[str]:
        """
        Calls the session authentication endpoint using session cookies
        to retrieve the OAuth Bearer token, or falls back to stored access_token.
        """
        if client is None:
            try:
                client = self.get_authenticated_client()
            except Exception:
                client = None

        if client is not None:
            try:
                res = client.get("https://labs.google/fx/api/auth/session")
                if res.status_code == 200:
                    data = res.json()
                    token = data.get("accessToken") or data.get("access_token") or data.get("token")
                    if token:
                        return token
            except Exception:
                pass

        # Fallback: check stored access_token in session_state.json
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    storage = json.load(f)
                    if isinstance(storage, dict):
                        token = storage.get("access_token") or storage.get("accessToken")
                        if token:
                            return token
            except Exception:
                pass

        return None

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
