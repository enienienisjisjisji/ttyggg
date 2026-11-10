"""fal.ai Kling image-to-video endpoints for AI Shorts Studio."""
import hmac
import json
import os
import re
import urllib.error
import urllib.request

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/avatar", tags=["avatar"])
MODEL = "fal-ai/kling-video/v3/standard/image-to-video"
QUEUE = "https://queue.fal.run/" + MODEL


class AvatarRequest(BaseModel):
    image_url: str = Field(min_length=12, max_length=2048)
    prompt: str = Field(min_length=3, max_length=2000)
    duration: int = 5
    approved_paid_generation: bool = False


def call(url, method="GET", data=None):
    key = os.getenv("FAL_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Render 환경변수 FAL_KEY가 설정되지 않았습니다.")
    headers = {"Authorization": "Key " + key, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read(1024 * 1024))
    except urllib.error.HTTPError as error:
        message = error.read(1500).decode("utf-8", "replace")
        if error.code in (401, 403):
            raise HTTPException(
                502,
                f"fal.ai 인증 또는 모델 접근 권한 오류 (HTTP {error.code}): {message}",
            ) from error
        raise HTTPException(
            502, f"fal.ai 요청 실패 (HTTP {error.code}): {message}"
        ) from error
    except Exception as error:
        raise HTTPException(502, "영상 서비스 연결 오류가 발생했습니다.") from error


@router.get("/config")
def config():
    return {
        "configured": bool(os.getenv("FAL_KEY", "").strip()),
        "model": MODEL,
        "billing": "External provider credits may be charged",
    }


@router.post("/start")
def start(body: AvatarRequest, x_avatar_token: str = Header(default="")):
    secret = os.getenv("AVATAR_ACCESS_TOKEN", "")
    if not secret or not hmac.compare_digest(x_avatar_token, secret):
        raise HTTPException(401, "접근 토큰이 올바르지 않습니다.")
    if not body.approved_paid_generation:
        raise HTTPException(400, "유료 생성 승인 체크가 필요합니다.")
    if body.duration not in (5, 10):
        raise HTTPException(400, "현재 5초 또는 10초만 지원합니다.")
    if not body.image_url.startswith("https://"):
        raise HTTPException(400, "공개 HTTPS 이미지 주소가 필요합니다.")
    prompt = (
        "Photorealistic fictional adult Korean woman, preserve identity from "
        "reference image. " + body.prompt
    )
    result = call(
        QUEUE,
        "POST",
        {
            "start_image_url": body.image_url,
            "prompt": prompt,
            "duration": str(body.duration),
            "generate_audio": False,
        },
    )
    request_id = result.get("request_id")
    if not request_id:
        raise HTTPException(502, "영상 생성 작업 ID를 받지 못했습니다.")
    return {"request_id": request_id, "status": "IN_QUEUE"}


@router.get("/status/{request_id}")
def status(request_id: str):
    if not re.fullmatch(r"[A-Za-z0-9-]{8,100}", request_id):
        raise HTTPException(400, "잘못된 작업 ID")
    state = call(QUEUE + "/requests/" + request_id + "/status")
    state_name = state.get("status", "UNKNOWN")
    if state_name == "COMPLETED":
        result = call(QUEUE + "/requests/" + request_id)
        return {
            "status": "COMPLETED",
            "video_url": (result.get("video") or {}).get("url"),
        }
    return {"status": state_name, "details": state.get("error")}


@router.get("/diagnostics/fal")
def diagnose_fal():
    """Non-billable configuration check; does not prove remote authentication."""
    return {
        "key_present": bool(os.getenv("FAL_KEY", "").strip()),
        "model": MODEL,
        "authentication": "NOT_TESTED",
        "note": "This endpoint does not submit a video generation request.",
    }
