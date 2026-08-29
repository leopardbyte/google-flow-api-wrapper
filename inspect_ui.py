import json
from cloakbrowser import launch
from session import SessionManager

def main():
    sm = SessionManager()
    
    with open(sm.session_file, "r", encoding="utf-8") as f:
        storage = json.load(f)
    cookies_raw = storage if isinstance(storage, list) else storage.get("cookies", [])
    cookies = []
    for c in cookies_raw:
        cd = {
            "name": c["name"],
            "value": c["value"],
            "url": "https://labs.google"
        }
        cookies.append(cd)

    print("[+] Launching CloakBrowser to inspect UI elements...")
    browser = launch(headless=False)
    context = browser.new_context()
    context.add_cookies(cookies)
    page = context.new_page()

    page.goto("https://labs.google/fx/tools/flow", wait_until="networkidle")
    page.wait_for_timeout(3000)

    # Click "New project" button to enter the Video Studio editor
    print("[+] Clicking 'New project' to enter the Studio Editor...")
    new_proj_btn = page.locator("button:has-text('New project')").first
    if new_proj_btn.count() > 0:
        new_proj_btn.click()
        page.wait_for_timeout(4000)

    # Scan DOM for primary Studio Editor elements
    print("[+] Scanning Studio Editor DOM elements...")
    primary_elements = page.evaluate("""() => {
        const results = [];
        const selector = "button, input, textarea, select, div[role='button'], div[role='textbox'], [contenteditable='true']";
        document.querySelectorAll(selector).forEach((el, index) => {
            results.push({
                index: index,
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || '',
                text: (el.innerText || el.textContent || '').trim().slice(0, 80),
                placeholder: el.getAttribute('placeholder') || '',
                aria_label: el.getAttribute('aria-label') || '',
                id: el.id || '',
                class: el.className || '',
                data_testid: el.getAttribute('data-testid') || ''
            });
        });
        return results;
    }""")

    # Click the Settings / Model Picker button to open the Radix modal popup
    print("[+] Clicking Settings/Model picker button to open Modal...")
    settings_btn = page.locator("button[id^='radix-'], button:has-text('Nano Banana')").first
    if settings_btn.count() > 0:
        settings_btn.click()
        page.wait_for_timeout(2000)

    print("[+] Scanning Modal Popover elements...")
    modal_elements = page.evaluate("""() => {
        const results = [];
        const selector = "[role='dialog'], [role='popover'], [role='menu'], [role='option'], button, div[role='button']";
        document.querySelectorAll(selector).forEach((el, index) => {
            results.push({
                index: index,
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || el.textContent || '').trim().slice(0, 80),
                aria_label: el.getAttribute('aria-label') || '',
                role: el.getAttribute('role') || '',
                class: el.className || ''
            });
        });
        return results;
    }""")

    combined_map = {
        "studio_canvas_elements": primary_elements,
        "modal_popover_elements": modal_elements
    }

    with open("ui_map.json", "w", encoding="utf-8") as f:
        json.dump(combined_map, f, indent=2)

    print(f"[+] Successfully mapped Studio Canvas & Modal Popover elements!")
    print("[+] Saved combined DOM map to: ui_map.json")

    input("\nPress ENTER in terminal after inspecting the browser window...")
    browser.close()

if __name__ == "__main__":
    main()
