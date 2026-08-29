import os

BASE_URL = os.getenv("TARGET_BASE_URL", "https://httpbin.org")
SESSION_FILE = "session_state.json"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://labs.google",
    "Referer": "https://labs.google/",
}
