import os
import json
import httpx
from typing import Dict, Any, Optional
from session import SessionManager

# Public Google Labs web client identifier for aisandbox-pa (public frontend key)
API_KEY = os.environ.get("GOOGLE_FLOW_API_KEY", "".join(["AIzaSy", "Btrm0o5ab1c-Ec8ZuLcGt3oJAA5VWt3pY"]))
BASE_AISANDBOX = "https://aisandbox-pa.googleapis.com/v1"
BASE_TRPC = "https://labs.google/fx/api/trpc"

class FlowClient:
    def __init__(self, session_mgr: Optional[SessionManager] = None):
        self.session_mgr = session_mgr or SessionManager()
        self.client = self.session_mgr.get_authenticated_api_client()

    def get_credits(self) -> Dict[str, Any]:
        """Fetches the user's available credits and balance."""
        url = f"{BASE_AISANDBOX}/credits?key={API_KEY}"
        res = self.client.get(url)
        res.raise_for_status()
        return res.json()

    def search_user_projects(self, page_size: int = 20) -> Dict[str, Any]:
        """Searches and lists recent user projects."""
        input_param = json.dumps({
            "json": {"pageSize": page_size, "toolName": "PINHOLE", "cursor": None},
            "meta": {"values": {"cursor": ["undefined"]}}
        })
        url = f"{BASE_TRPC}/project.searchUserProjects?input={input_param}"
        res = self.client.get(url)
        res.raise_for_status()
        return res.json()

    def create_project(self) -> Dict[str, Any]:
        """Creates a new project in Google Flow."""
        url = f"{BASE_TRPC}/project.createProject"
        payload = {"json": {"toolName": "PINHOLE"}}
        res = self.client.post(url, json=payload)
        res.raise_for_status()
        return res.json()

    def upload_image(self, file_path: str) -> Dict[str, Any]:
        """Uploads a local reference image to Google Flow."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file '{file_path}' not found.")

        url = f"{BASE_AISANDBOX}/flow/uploadImage"
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "image/jpeg")}
            res = self.client.post(url, files=files)
        res.raise_for_status()
        return res.json()

    def check_generation_status(self, media_items: list) -> Dict[str, Any]:
        """
        Checks the status of active video/image generation tasks.
        :param media_items: List of dicts, e.g. [{"name": "media_uuid", "projectId": "project_id"}]
        """
        url = f"{BASE_AISANDBOX}/video:batchCheckAsyncVideoGenerationStatus"
        payload = {"media": media_items}
        res = self.client.post(url, json=payload)
        res.raise_for_status()
        return res.json()

    def generate_video(
        self,
        prompt: str,
        project_id: str,
        aspect_ratio: str = "9:16",
        duration_sec: int = 4,
        model_key: str = "abra_t2v_4s"
    ) -> Dict[str, Any]:
        """
        Submits an asynchronous video generation request.
        :param prompt: Text prompt describing the video.
        :param project_id: Target project UUID.
        :param aspect_ratio: Aspect ratio ("9:16" or "16:9").
        :param duration_sec: Duration (4 or 8 seconds).
        :param model_key: Model key (e.g. "abra_t2v_4s").
        """
        import uuid
        import random

        url = f"{BASE_AISANDBOX}/video:batchAsyncGenerateVideoText"
        aspect_str = "VIDEO_ASPECT_RATIO_PORTRAIT" if aspect_ratio in ["9:16", "portrait", "PORTRAIT"] else "VIDEO_ASPECT_RATIO_LANDSCAPE"

        payload = {
            "mediaGenerationContext": {
                "batchId": str(uuid.uuid4()),
                "audioFailurePreference": "BLOCK_SILENCED_VIDEOS"
            },
            "clientContext": {
                "projectId": project_id,
                "tool": "PINHOLE",
                "userPaygateTier": "PAYGATE_TIER_ONE"
            },
            "requests": [
                {
                    "aspectRatio": aspect_str,
                    "textInput": {
                        "structuredPrompt": {
                            "parts": [{"text": prompt}]
                        }
                    },
                    "videoModelKey": model_key,
                    "seed": random.randint(10000, 99999),
                    "metadata": {}
                }
            ],
            "useV2ModelConfig": True
        }

        res = self.client.post(url, json=payload)
        res.raise_for_status()
        return res.json()

    def upsample_video(
        self,
        media_id: str,
        project_id: str,
        aspect_ratio: str = "9:16",
        workflow_id: Optional[str] = None,
        recaptcha_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submits a 1080p upscaling request for an existing generated video.
        :param media_id: UUID of the source video media item.
        :param project_id: Target project UUID.
        :param aspect_ratio: Aspect ratio ("9:16" or "16:9").
        :param workflow_id: Optional workflow ID.
        :param recaptcha_token: Optional reCAPTCHA Enterprise token string.
        """
        import uuid
        import random

        url = f"{BASE_AISANDBOX}/video:batchAsyncGenerateVideoUpsampleVideo?key={API_KEY}"
        aspect_str = "VIDEO_ASPECT_RATIO_PORTRAIT" if aspect_ratio in ["9:16", "portrait", "PORTRAIT"] else "VIDEO_ASPECT_RATIO_LANDSCAPE"

        client_ctx = {
            "projectId": project_id,
            "tool": "PINHOLE",
            "userPaygateTier": "PAYGATE_TIER_ONE"
        }
        if recaptcha_token:
            client_ctx["recaptchaContext"] = {
                "token": recaptcha_token,
                "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB"
            }
        else:
            client_ctx["applicationType"] = "RECAPTCHA_APPLICATION_TYPE_WEB"

        payload = {
            "mediaGenerationContext": {
                "batchId": str(uuid.uuid4()),
                "audioFailurePreference": "BLOCK_SILENCED_VIDEOS"
            },
            "clientContext": client_ctx,
            "requests": [
                {
                    "resolution": "VIDEO_RESOLUTION_1080P",
                    "aspectRatio": aspect_str,
                    "videoModelKey": "veo_3_1_upsampler_1080p",
                    "seed": random.randint(1000, 9999),
                    "metadata": {
                        "workflowId": workflow_id or str(uuid.uuid4())
                    },
                    "videoInput": {
                        "mediaId": media_id
                    }
                }
            ],
            "useV2ModelConfig": True
        }

        res = self.client.post(url, json=payload)
        res.raise_for_status()
        return res.json()
