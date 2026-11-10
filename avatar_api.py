"""fal Kling video generation routes for AI Shorts Studio.
Requires FAL_KEY in Render environment. No secrets in client code.
"""
import os
import re
import json
import urllib.request
import urllib.error
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

router = APIRouter(prefix='/api/avatar', tags=['avatar'])
MODEL = 'fal-ai/kling-video/v3/standard/image-to-video'
QUEUE = 'https://queue.fal.run/' + MODEL

class AvatarRequest(BaseModel):
    image_url: str = Field(min_length=12, max_length=2048)
    prompt: str = Field(min_length=3, max_length=2000)
    duration: int = Field(default=5)
    approved_paid_generation: bool = False


def call(url, method='GET', data=None):
    key = os.getenv('FAL_KEY', '').strip()
    if not key:
        raise HTTPException(503, 'Render 환경변수 FAL_KEY가 설정되지 않았습니다.')
    headers = {'Authorization': 'Key ' + key, 'Accept': 'application/json'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.loads(response.read(1024*1024))
 
except urllib.error.HTTPError as e:
    msg = e.read(1500).decode('utf-8', 'replace')
    if e.code in (401, 403):
        raise HTTPException(
            502,
            'fal.ai 인증 또는 모델 접근 권한 오류 '
            f'(HTTP {e.code}): {msg}'
        )
    raise HTTPException(
        502,
        f'fal.ai 요청 실패 (HTTP {e.code}): {msg}'
    )

    except Exception as e:
        raise HTTPException(502, '영상 서비스 연결 오류: ' + str(e))

@router.get('/config')
def config():
    return {'configured': bool(os.getenv('FAL_KEY')), 'model': MODEL, 'billing': 'External provider credits may be charged'}

@router.post('/start')
def start(body: AvatarRequest, x_avatar_token: str = Header(default='')):
    import hmac
    secret = os.getenv('AVATAR_ACCESS_TOKEN', '')
    if not secret or not hmac.compare_digest(x_avatar_token, secret):
        raise HTTPException(401, '접근 토큰이 올바르지 않습니다.')
    if not body.approved_paid_generation:
        raise HTTPException(400, '유료 생성 승인 체크가 필요합니다.')
    if body.duration not in (5, 10):
        raise HTTPException(400, '현재 5초 또는 10초만 지원합니다.')
    if not body.image_url.startswith('https://'):
        raise HTTPException(400, '공개 HTTPS 이미지 주소가 필요합니다.')
    # Motion only. Korean narration and accurate lip sync require separate audio/lipsync integration.
    prompt = 'Photorealistic fictional adult Korean woman, preserve identity from reference image. ' + body.prompt
    result = call(QUEUE, 'POST', {'start_image_url': body.image_url, 'prompt': prompt,
                                   'duration': str(body.duration), 'generate_audio': False})
    rid = result.get('request_id')
    if not rid:
        raise HTTPException(502, '영상 생성 작업 ID를 받지 못했습니다.')
    return {'request_id': rid, 'status': 'IN_QUEUE'}

@router.get('/status/{request_id}')
def status(request_id: str):
    if not re.fullmatch(r'[A-Za-z0-9-]{8,100}', request_id):
        raise HTTPException(400, '잘못된 작업 ID')
    state = call(QUEUE + '/requests/' + request_id + '/status')
    state_name = state.get('status', 'UNKNOWN')
    if state_name == 'COMPLETED':
        result = call(QUEUE + '/requests/' + request_id)
        return {'status': 'COMPLETED', 'video_url': (result.get('video') or {}).get('url')}
    return {'status': state_name, 'details': state.get('error')}


@router.get('/diagnostics/fal')
def diagnose_fal():
    """Non-generating fal.ai authentication probe."""
    key = os.getenv('FAL_KEY', '').strip()

    if not key:
        return {
            'key_present': False,
            'result': 'MISSING_KEY'
        }

    # Deliberately nonexistent request ID.
    # This endpoint checks status; it does not create a video.
    url = (
        'https://queue.fal.run/'
        + MODEL
        + '/requests/'
        + '00000000-0000-0000-0000-000000000000'
        + '/status'
    )

    req = urllib.request.Request(
        url,
        headers={
            'Authorization': 'Key ' + key,
            'Accept': 'application/json'
        },
        method='GET'
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            code = response.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        return {
            'key_present': True,
            'result': 'NETWORK_ERROR'
        }

    return {
        'key_present': True,
        'http_status': code,
        'result': (
            'AUTH_REJECTED' if code in (401, 403)
            else 'PROBE_RESPONSE'
        )
    }

    """Check fal.ai authentication without generating video."""
    key = os.getenv('FAL_KEY', '').strip()
    if not key:
        return {
            'key_present': False,
            'authentication': 'NOT_TESTED',
            'reason': 'FAL_KEY is missing'
        }

    url = 'https://queue.fal.run/' + MODEL
    req = urllib.request.Request(
        url,
        headers={
            'Authorization': 'Key ' + key,
            'Accept': 'application/json'
        },
        method='GET'
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return {
                'key_present': True,
                'http_status': response.status,
                'authentication': 'CHECK_RESPONSE'
            }
    except urllib.error.HTTPError as e:
        return {
            'key_present': True,
            'http_status': e.code,
            'authentication': 'CHECK_RESPONSE',
            'reason': 'Model endpoint response'
        }
    except Exception:
        return {
            'key_present': True,
            'authentication': 'INCONCLUSIVE',
            'reason': 'Connection failed'
        }
