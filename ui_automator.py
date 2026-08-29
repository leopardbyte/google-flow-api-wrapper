import os
import time
import json
from cloakbrowser import launch
from session import SessionManager

class FlowUIAutomator:
    def __init__(self, session_mgr: SessionManager = None):
        self.session_mgr = session_mgr or SessionManager()

    def generate_video_ui(
        self,
        prompt: str,
        mode: str = "frames",
        aspect_ratio: str = "16:9",
        resolution: str = "360p",
        duration_sec: int = 6,
        count: int = 1,
        model_name: str = "Omni 1.1 Flash",
        image_path: str = None,
        start_frame_path: str = None,
        end_frame_path: str = None,
        headless: bool = True,
        output_dir: str = ".",
        max_wait: int = 360
    ) -> dict:
        """
        Automates Google Flow video generation directly via DOM UI controls.
        Handles prompt entry, setting selection (model, mode/sub-tabs: Frames vs Ingredients, aspect ratio, resolution, duration, batch count),
        reference image upload, generation submission, and automatic .mp4 file download.
        """
        # Pre-initialize target values to guarantee variable scope
        mode_target = "Ingredients" if "ingredient" in str(mode).lower() else "Frames"
        aspect_target = "9:16" if aspect_ratio in ["9:16", "portrait", "PORTRAIT"] else "16:9"
        res_target = "720p" if "720" in str(resolution) else "360p"

        # Load session cookies
        with open(self.session_mgr.session_file, "r", encoding="utf-8") as f:
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

        print(f"[+] Launching CloakBrowser UI Automator (headless={headless}, humanize=False)...")
        launch_args = ["--start-maximized"] if not headless else []
        browser = launch(headless=headless, humanize=False, args=launch_args)
        
        context_kwargs = {"accept_downloads": True}
        if not headless:
            context_kwargs["no_viewport"] = True
        else:
            context_kwargs["viewport"] = {"width": 1920, "height": 1080}

        context = browser.new_context(**context_kwargs)
        context.add_cookies(cookies)
        page = context.new_page()

        try:
            print("[+] Navigating to Google Flow Studio...")
            page.goto("https://labs.google/fx/tools/flow", wait_until="networkidle")
            page.wait_for_timeout(3000)

            # Auto-dismiss Google cookie consent banner if present
            try:
                cookie_banner_btn = page.locator(".glue-cookie-notification-bar button, button:has-text('Accept all'), button:has-text('I agree'), button:has-text('Reject all')").first
                if cookie_banner_btn.count() > 0 and cookie_banner_btn.is_visible():
                    print("[+] Auto-dismissing Google Cookie Banner...")
                    cookie_banner_btn.click(force=True)
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # Click 'New project'
            print("[+] Entering Studio Editor (Clicking 'New project')...")
            new_proj = page.locator("button:has-text('New project')").first
            if new_proj.count() > 0:
                new_proj.click(force=True)
                page.wait_for_timeout(3500)

            # Open Settings Modal (Targeting the settings pill on the right of the prompt bar, avoiding the '+' button)
            print("[+] Opening Settings & Model Selector Modal...")
            settings_btn = page.locator(
                "button:has-text('Video'), "
                "button:has-text('Omni'), "
                "button:has-text('360p'), "
                "button:has-text('720p'), "
                "button:has-text('Nano Banana'), "
                "button:has-text('Image')"
            ).filter(has_not_text="+").filter(has_not_text="Agent").last

            if settings_btn.count() > 0:
                print(f"  • Clicking Settings Pill: '{settings_btn.text_content().strip().replace(chr(10), ' ')}'")
                settings_btn.click(force=True)
                page.wait_for_timeout(1500)

                # 1. Select Video Mode Tab (Top tab row: Image vs Video)
                video_tab = page.locator("[role='dialog'] button:has-text('Video'), [role='menu'] button:has-text('Video'), button:has-text('Video')").last
                if video_tab.count() > 0:
                    print("  • Selected Video Mode tab")
                    video_tab.click()
                    page.wait_for_timeout(500)

                # 2. Select Sub-Tab: Frames vs Ingredients
                mode_tab = page.locator(f"[role='dialog'] button:has-text('{mode_target}'), [role='menu'] button:has-text('{mode_target}'), button:has-text('{mode_target}')").last
                if mode_tab.count() > 0:
                    print(f"  • Selected {mode_target} sub-tab")
                    mode_tab.click()
                    page.wait_for_timeout(500)

                # 3. Select Aspect Ratio (9:16 vs 16:9)
                aspect_btn = page.locator(f"[role='dialog'] button:has-text('{aspect_target}'), button:has-text('{aspect_target}')").last
                if aspect_btn.count() > 0:
                    print(f"  • Selected Aspect Ratio: {aspect_target}")
                    aspect_btn.click()
                    page.wait_for_timeout(400)

                # 4. Model Selection (e.g. Omni 1.1 Flash)
                model_btn = page.locator(f"[role='dialog'] button:has-text('{model_name}'), button:has-text('{model_name}')").first
                if model_btn.count() > 0:
                    print(f"  • Active Model: {model_name}")
                else:
                    dropdown_trigger = page.locator("[role='dialog'] button:has-text('Omni'), [role='dialog'] button:has-text('Flash')").first
                    if dropdown_trigger.count() > 0:
                        dropdown_trigger.click()
                        page.wait_for_timeout(500)
                        target_opt = page.locator(f"[role='option']:has-text('{model_name}'), button:has-text('{model_name}')").first
                        if target_opt.count() > 0:
                            target_opt.click()
                            page.wait_for_timeout(400)

                # 5. Select Resolution (360p vs 720p)
                res_btn = page.locator(f"[role='dialog'] button:has-text('{res_target}'), button:has-text('{res_target}')").last
                if res_btn.count() > 0:
                    print(f"  • Selected Resolution: {res_target}")
                    res_btn.click()
                    page.wait_for_timeout(400)

                # 6. Select Duration (4s, 6s, 8s, 10s)
                dur_target = f"{duration_sec}s"
                dur_btn = page.locator(f"[role='dialog'] button:has-text('{dur_target}'), button:has-text('{dur_target}')").last
                if dur_btn.count() > 0:
                    print(f"  • Selected Duration: {dur_target}")
                    dur_btn.click()
                    page.wait_for_timeout(400)

                # 7. Select Batch Count (x1, x2, x3, x4) - default x1
                count_str = f"x{count}"
                count_btn = page.locator(f"[role='dialog'] button:has-text('{count_str}'), button:has-text('{count_str}')").last
                if count_btn.count() > 0:
                    print(f"  • Selected Batch Count: {count_str}")
                    count_btn.click()
                    page.wait_for_timeout(400)

                # Close modal by pressing Escape
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

            # Resolve frame inputs
            eff_start = start_frame_path or image_path
            eff_end = end_frame_path
            files_to_upload = [os.path.abspath(p) for p in [eff_start, eff_end] if p and os.path.exists(p)]

            # Pre-upload image files if provided
            if files_to_upload:
                print(f"[+] Pre-uploading {len(files_to_upload)} image asset(s) to Studio...")
                file_input = page.locator("input[type='file']").first
                if file_input.count() > 0:
                    if len(files_to_upload) == 1:
                        file_input.set_input_files(files_to_upload[0])
                    else:
                        file_input.set_input_files(files_to_upload)
                    
                    print("  • Polling for asset upload & ingestion to finish (up to 40s)...")
                    upload_start = time.time()
                    while (time.time() - upload_start) < 40:
                        page.wait_for_timeout(3000)
                        if page.locator("img[src*='media'], div[data-type='asset']").count() >= len(files_to_upload) or (time.time() - upload_start) >= 20:
                            print(f"  ✨ Image asset upload ready ({int(time.time() - upload_start)}s)")
                            break

                # Post-upload settle delay (ensure assets are fully registered in project library)
                print("  • Waiting 2.5s for asset registry to sync...")
                page.wait_for_timeout(2500)

            # Handle Frame Slots binding for Frames mode
            if mode_target == "Frames":
                # Helper to select asset in picker modal
                def select_modal_asset(target_filepath: str, fallback_index: int = 0):
                    page.wait_for_timeout(1200)
                    filename = os.path.basename(target_filepath)
                    stem = os.path.splitext(filename)[0]

                    # Extract unique identifier to avoid common prefixes like 'Gemini_Generated_Image_'
                    if "_" in stem:
                        unique_key = stem.split("_")[-1]
                    else:
                        unique_key = stem[-12:]

                    # 1. Try searching asset by unique key in modal search bar
                    search_box = page.locator("input[placeholder*='Search assets'], input[placeholder*='Search']").last
                    searched = False
                    if search_box.count() > 0 and search_box.is_visible():
                        print(f"  • Filtering modal asset with unique key: '{unique_key}'...")
                        search_box.click()
                        search_box.fill("")
                        search_box.press_sequentially(unique_key, delay=40)
                        page.wait_for_timeout(1000)
                        searched = True

                    # 2. Locate and click target item inside modal
                    if searched:
                        # With search active, the filtered top result is our target
                        target_row = page.locator(
                            f"div:has-text('{unique_key}'), "
                            "[role='dialog'] [role='option'], "
                            "[role='dialog'] [role='listitem'], "
                            "div:has(> img):has-text('Gemini'), "
                            "div:has(> img):has-text('Generated'), "
                            "[role='dialog'] button:has(img)"
                        ).first

                        if target_row.count() > 0:
                            target_row.click(force=True)
                            page.wait_for_timeout(600)
                        else:
                            asset_thumbnails = page.locator("[role='dialog'] img, img[src*='media'], img[src*='blob']").filter(has_not=page.locator("xpath=ancestor::button[contains(., 'Add')]"))
                            if asset_thumbnails.count() > 0:
                                asset_thumbnails.first.click(force=True)
                                page.wait_for_timeout(600)
                    else:
                        # Fallback without search
                        modal_list_items = page.locator(
                            "[role='dialog'] [role='option'], "
                            "[role='dialog'] [role='listitem'], "
                            "div:has(> img):has-text('Gemini'), "
                            "div:has(> img):has-text('Generated'), "
                            "[role='dialog'] button:has(img)"
                        )
                        if modal_list_items.count() > fallback_index:
                            modal_list_items.nth(fallback_index).click(force=True)
                            page.wait_for_timeout(600)

                    # 3. Click 'Add to Prompt' button
                    add_btn = page.locator("button:has-text('Add to Prompt'), button:has-text('Add to prompt'), button:has-text('Add')").last
                    if add_btn.count() > 0 and add_btn.is_visible():
                        add_btn.click(force=True)
                        page.wait_for_timeout(1500)
                        return True
                    return False

                # 1. Bind Start Frame
                if eff_start and os.path.exists(eff_start):
                    print(f"[+] Binding Start Frame slot: {os.path.basename(eff_start)}...")
                    start_btn = page.locator(
                        "button:has-text('Start'), "
                        ":text-is('Start'), "
                        "[aria-label*='Start'], "
                        "div:has-text('Start')"
                    ).filter(has_not_text="Start creating").last

                    if start_btn.count() > 0:
                        start_btn.click(force=True)
                        if select_modal_asset(eff_start, fallback_index=0):
                            print("  ✨ Attached Start Frame!")
                    else:
                        print("  [-] Could not locate 'Start' slot button in prompt bar.")

                # 2. Bind End Frame
                if eff_end and os.path.exists(eff_end):
                    page.wait_for_timeout(1200)
                    print(f"[+] Binding End Frame slot: {os.path.basename(eff_end)}...")
                    end_btn = page.locator(
                        "button:has-text('End'), "
                        ":text-is('End'), "
                        "[aria-label*='End'], "
                        "div:has-text('End')"
                    ).last

                    if end_btn.count() > 0:
                        end_btn.click(force=True)
                        if select_modal_asset(eff_end, fallback_index=1):
                            print("  ✨ Attached End Frame!")
                    else:
                        print("  [-] Could not locate 'End' slot button in prompt bar.")

            elif files_to_upload:
                # Tag reference image in Ingredients mode via '@' menu
                print("  • Tagging reference asset via '@' menu -> 'Add to Prompt' button...")
                prompt_box = page.locator("div[role='textbox'], [contenteditable='true'], textarea").first
                prompt_box.click()
                page.wait_for_timeout(500)
                for attempt in range(4):
                    prompt_box.press_sequentially("@", delay=100)
                    page.wait_for_timeout(1500)
                    add_btn = page.locator("button:has-text('Add to Prompt'), button:has-text('Add to prompt')").first
                    if add_btn.count() > 0 and add_btn.is_visible():
                        add_btn.click(force=True)
                        page.wait_for_timeout(600)
                        prompt_box.press_sequentially(" ", delay=50)
                        break
                    else:
                        page.keyboard.press("Backspace")
                        page.wait_for_timeout(3000)

            # Focus Prompt Text Box
            print("[+] Focusing prompt text box...")
            prompt_box = page.locator("div[role='textbox'], [contenteditable='true'], textarea").first
            prompt_box.click()
            page.wait_for_timeout(500)

            print(f"[+] Typing prompt text: '{prompt}'...")
            prompt_box.press_sequentially(prompt, delay=20)
            page.wait_for_timeout(500)

            # Submit Prompt by pressing Enter
            print("[+] Submitting prompt by pressing ENTER key...")
            prompt_box.press("Enter")
            page.wait_for_timeout(1500)

            print("[+] Generation submitted! Polling for finished video card & download in UI...")

            # Wait for video generation to complete and download (up to max_wait seconds)
            download_file_path = None
            start_time = time.time()

            while (time.time() - start_time) < max_wait:
                time.sleep(1.5)
                elapsed = int(time.time() - start_time)

                # Check if generated video is ready (has active media.getMediaUrlRedirect src)
                has_ready_video = page.evaluate("""() => {
                    const videos = Array.from(document.querySelectorAll('video'));
                    return videos.some(v => v.src && (v.src.includes('media.getMediaUrlRedirect') || v.src.includes('blob:')));
                }""")

                if not has_ready_video:
                    print(f"  [UI Progress] Rendering / Processing... ({elapsed}s)")
                    continue

                print(f"[+] Generated video is ready ({elapsed}s)! Locating video container on canvas...")
                card_el = page.locator("button:has(video), div[data-tile-id], a:has(video), div[role='button'][aria-roledescription='draggable']:has(video)").first
                if card_el.count() == 0:
                    card_el = page.locator("video").first

                try:
                    card_el.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass

                # Step 1: Right-click the video card container using coordinate click
                print("[+] Right-clicking generated video card to open context menu...")
                c_box = card_el.bounding_box()
                if c_box:
                    page.mouse.click(c_box['x'] + c_box['width'] / 2, c_box['y'] + c_box['height'] / 2, button="right")
                else:
                    card_el.click(button="right", force=True)
                page.wait_for_timeout(600)

                # Step 2: Locate 'Download' menu item in open context menu
                download_item = page.locator("[role='menuitem']:has-text('Download'), div[role='menuitem']:has-text('Download'), button:has-text('Download')").first

                if download_item.count() > 0 and download_item.is_visible():
                    print("  • Hovering over 'Download' menu item to reveal upscale options...")
                    download_item.hover(timeout=1500, force=True)
                    page.wait_for_timeout(500)

                    # Step 3: Select upscaled resolution (720p for 360p generation, 1080p for 720p/1080p)
                    target_res = "720p" if res_target == "360p" else "1080p"
                    flyout_target = page.locator(
                        f"[role='menuitem']:has-text('{target_res}'), "
                        f"div[role='menuitem']:has-text('{target_res}'), "
                        f"button[role='menuitem']:has-text('{target_res}'), "
                        f"div[data-radix-popper-content-wrapper] [role='menuitem']:has-text('{target_res}')"
                    ).first

                    if not (flyout_target.count() > 0 and flyout_target.is_visible()):
                        download_item.click(force=True)
                        page.wait_for_timeout(500)
                        flyout_target = page.locator(
                            f"[role='menuitem']:has-text('{target_res}'), "
                            f"div[role='menuitem']:has-text('{target_res}'), "
                            f"button[role='menuitem']:has-text('{target_res}'), "
                            f"div[data-radix-popper-content-wrapper] [role='menuitem']:has-text('{target_res}')"
                        ).first

                    if flyout_target.count() > 0 and flyout_target.is_visible():
                        print(f"[+] Found menu item! Clicking '{target_res} Upscaled'...")
                        filename = f"video_ui_{int(time.time())}.mp4"
                        save_path = os.path.abspath(os.path.join(output_dir, filename))

                        with page.expect_download(timeout=240000) as download_info:
                            flyout_target.click(force=True)

                        download = download_info.value
                        download.save_as(save_path)

                        print(f"  ✨ Video downloaded successfully (Upscaled)! Saved to: {save_path}")
                        download_file_path = save_path
                        break
                    else:
                        print(f"  [Notice] Flyout upscale option '{target_res}' not found, retrying...")
                else:
                    print("  [Notice] Download menu item not visible yet, retrying context menu...")

                    if download_file_path:
                        break

                if download_file_path:
                    break

                elapsed = int(time.time() - start_time)
                print(f"  [UI Progress] Rendering / Processing... ({elapsed}s)")

            browser.close()

            if download_file_path:
                return {
                    "status": "COMPLETED",
                    "saved_file": download_file_path,
                    "prompt": prompt,
                    "mode": mode_target,
                    "resolution": res_target,
                    "duration_sec": duration_sec,
                    "aspect_ratio": aspect_target
                }
            else:
                return {
                    "status": "TIMED_OUT",
                    "message": f"Video submitted but render check timed out after {max_wait}s."
                }

        except Exception as e:
            print(f"[-] UI Automator Error: {e}")
            browser.close()
            return {"status": "ERROR", "error": str(e)}

if __name__ == "__main__":
    automator = FlowUIAutomator()
    res = automator.generate_video_ui(
        prompt="a cute kitten playing with a red yarn ball in a cozy room",
        aspect_ratio="16:9",
        resolution="360p",
        duration_sec=6,
        count=1
    )
    print("\nResult:", json.dumps(res, indent=2))

