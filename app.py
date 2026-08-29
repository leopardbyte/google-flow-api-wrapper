import os
import json
import time
import base64
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from session import SessionManager
from client import FlowClient

app = FastAPI(
    title="Google Flow (Omni 1.1 Flash) Local API",
    description="Local REST API server & automation wrapper for Google Flow AI Video Studio",
    version="1.1.0"
)

# Initialize Session & Client
session_mgr = SessionManager()

class VideoGenerationRequest(BaseModel):
    prompt: str
    project_id: Optional[str] = None
    mode: str = "frames"                     # "frames" or "ingredients" (Default: "frames")
    aspect_ratio: str = "16:9"               # "16:9" or "9:16"
    resolution: str = "360p"                 # "360p" or "720p"
    duration_sec: int = 6                    # 4, 6, 8, 10
    count: int = 1                           # 1, 2, 3, 4 (x1, x2, x3, x4)
    model_name: str = "Omni 1.1 Flash"
    image_path: Optional[str] = None         # Generic reference image / start frame path
    image_base64: Optional[str] = None       # Generic reference image / start frame base64
    start_frame_path: Optional[str] = None   # Explicit start frame local path
    start_frame_base64: Optional[str] = None # Explicit start frame base64 string
    end_frame_path: Optional[str] = None     # Explicit end frame local path
    end_frame_base64: Optional[str] = None   # Explicit end frame base64 string
    headless: bool = True                    # Run silently in background (default True)
    max_wait: int = 360                      # Maximum seconds to wait for video rendering (default 360s)

class StatusCheckRequest(BaseModel):
    media_items: List[Dict[str, str]]

def get_flow_client() -> FlowClient:
    return FlowClient(session_mgr=session_mgr)

@app.on_event("startup")
def print_terminal_showcase():
    try:
        client = get_flow_client()
        credits_info = client.get_credits()
        credits = credits_info.get("credits", "N/A")
        tier = credits_info.get("userPaygateTier", "N/A")

        session_res = client.client.get("https://labs.google/fx/api/auth/session")
        user_info = session_res.json().get("user", {}) if session_res.status_code == 200 else {}
        user_name = user_info.get("name", "Authenticated User")
        user_email = user_info.get("email", "N/A")

    except Exception:
        credits = "Error fetching"
        tier = "N/A"
        user_name = "Session Active"
        user_email = "N/A"

    print("\n" + "=" * 65)
    print(" 🚀 GOOGLE FLOW (OMNI 1.1 FLASH) - LOCAL REST API SERVER")
    print("=" * 65)
    print(f" 👤 Account    : {user_name} ({user_email})")
    print(f" 💳 Live Credits: {credits} credits (Tier: {tier})")
    print(f" 🌐 Local Server: http://127.0.0.1:8000")
    print(f" 📖 Interactive OpenAPI Docs: http://127.0.0.1:8000/docs")
    print("-" * 65)
    print(" 📋 AVAILABLE LOCAL ENDPOINTS:")
    print("   • GET  /                    -> Server Health & Summary")
    print("   • GET  /api/credits         -> Get live credit balance")
    print("   • GET  /api/projects        -> List user projects")
    print("   • POST /api/create-project  -> Create a new project")
    print("   • POST /api/generate            -> Generate video (JSON payload, optional start/end frames)")
    print("   • POST /api/generate-with-image -> Generate video with HTTP file upload (Multipart Form)")
    print("   • POST /api/check-status        -> Check status of generation tasks")
    print("=" * 65 + "\n")

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Google Flow (Omni 1.1 Flash) Local API Wrapper",
        "docs_url": "http://127.0.0.1:8000/docs"
    }

@app.get("/api/credits")
def get_credits():
    """Returns the live credit balance and tier details."""
    try:
        client = get_flow_client()
        return client.get_credits()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects")
def list_projects(page_size: int = 20):
    """Lists recent projects."""
    try:
        client = get_flow_client()
        return client.search_user_projects(page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/create-project")
def create_project():
    """Creates a new project space."""
    try:
        client = get_flow_client()
        return client.create_project()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from ui_automator import FlowUIAutomator

ui_automator = FlowUIAutomator(session_mgr=session_mgr)

@app.post("/api/generate")
def generate_video(req: VideoGenerationRequest):
    """
    Generates a video via DOM UI Automation with Omni 1.1 Flash.
    Supports text-to-video, single frame reference, and dual Start/End frame interpolation.
    """
    temp_files = []
    try:
        scratch_dir = os.path.join(os.getcwd(), "scratch")
        os.makedirs(scratch_dir, exist_ok=True)

        start_path = req.start_frame_path or req.image_path
        end_path = req.end_frame_path

        # Handle base64 decoded start/image input
        start_b64 = req.start_frame_base64 or req.image_base64
        if start_b64:
            tmp_start = os.path.abspath(os.path.join(scratch_dir, f"start_b64_{int(time.time())}.png"))
            with open(tmp_start, "wb") as f:
                f.write(base64.b64decode(start_b64.split(",")[-1]))
            temp_files.append(tmp_start)
            start_path = tmp_start

        # Handle base64 decoded end frame input
        if req.end_frame_base64:
            tmp_end = os.path.abspath(os.path.join(scratch_dir, f"end_b64_{int(time.time())}.png"))
            with open(tmp_end, "wb") as f:
                f.write(base64.b64decode(req.end_frame_base64.split(",")[-1]))
            temp_files.append(tmp_end)
            end_path = tmp_end

        print(f"\n[+] [API Request] Generating video via DOM UI Automator for prompt: '{req.prompt}' (Mode: {req.mode}, Model: {req.model_name}, Res: {req.resolution}, Duration: {req.duration_sec}s, Count: x{req.count}, StartFrame: {bool(start_path)}, EndFrame: {bool(end_path)})")
        result = ui_automator.generate_video_ui(
            prompt=req.prompt,
            mode=req.mode,
            aspect_ratio=req.aspect_ratio,
            resolution=req.resolution,
            duration_sec=req.duration_sec,
            count=req.count,
            model_name=req.model_name,
            start_frame_path=start_path,
            end_frame_path=end_path,
            headless=req.headless,
            output_dir=".",
            max_wait=req.max_wait
        )
        if result.get("status") == "ERROR":
            raise HTTPException(status_code=500, detail=result.get("error"))
        return result
    except Exception as e:
        print(f"[-] [API Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for tf in temp_files:
            if os.path.exists(tf):
                try:
                    os.remove(tf)
                except Exception:
                    pass

@app.post("/api/generate-with-image")
async def generate_with_image(
    prompt: str = Form(...),
    mode: str = Form("frames"),
    aspect_ratio: str = Form("16:9"),
    resolution: str = Form("360p"),
    duration_sec: int = Form(6),
    count: int = Form(1),
    model_name: str = Form("Omni 1.1 Flash"),
    headless: bool = Form(True),
    max_wait: int = Form(360),
    file: Optional[UploadFile] = File(None),
    start_file: Optional[UploadFile] = File(None),
    end_file: Optional[UploadFile] = File(None)
):
    """
    Generates a video with reference image(s) uploaded directly via HTTP multipart form data.
    Supports single reference file or distinct start_file and end_file.
    """
    scratch_dir = os.path.join(os.getcwd(), "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    temp_files = []

    try:
        eff_start_file = start_file or file
        start_path = None
        end_path = None

        if eff_start_file:
            start_path = os.path.abspath(os.path.join(scratch_dir, f"start_form_{int(time.time())}_{eff_start_file.filename}"))
            content = await eff_start_file.read()
            with open(start_path, "wb") as f:
                f.write(content)
            temp_files.append(start_path)

        if end_file:
            end_path = os.path.abspath(os.path.join(scratch_dir, f"end_form_{int(time.time())}_{end_file.filename}"))
            content = await end_file.read()
            with open(end_path, "wb") as f:
                f.write(content)
            temp_files.append(end_path)

        print(f"\n[+] [API Request (Multipart Form)] Generating video (Mode: {mode}, StartFile: {bool(start_path)}, EndFile: {bool(end_path)})")
        result = ui_automator.generate_video_ui(
            prompt=prompt,
            mode=mode,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            duration_sec=duration_sec,
            count=count,
            model_name=model_name,
            start_frame_path=start_path,
            end_frame_path=end_path,
            headless=headless,
            output_dir=".",
            max_wait=max_wait
        )
        if result.get("status") == "ERROR":
            raise HTTPException(status_code=500, detail=result.get("error"))
        return result
    except Exception as e:
        print(f"[-] [API Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for tf in temp_files:
            if os.path.exists(tf):
                try:
                    os.remove(tf)
                except Exception:
                    pass

@app.post("/api/check-status")
def check_status(req: StatusCheckRequest):
    """Checks the status of generation tasks."""
    try:
        client = get_flow_client()
        return client.check_generation_status(media_items=req.media_items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """Uploads a reference image file."""
    try:
        client = get_flow_client()
        temp_filename = f"temp_{file.filename}"
        with open(temp_filename, "wb") as f:
            content = await file.read()
            f.write(content)
        
        result = client.upload_image(file_path=temp_filename)
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)

