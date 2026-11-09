"""AI Shorts Studio local/cloud backend. Requires FFmpeg and internet for gTTS."""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from gtts import gTTS
import tempfile, subprocess, json, shutil, os

ROOT=Path(__file__).parent
app=FastAPI(title='AI Shorts Studio')

@app.get('/health')
def health():
    return {'status':'ok'}

def ff(*args):
    p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*map(str,args)],capture_output=True,text=True,timeout=240)
    if p.returncode: raise RuntimeError(p.stderr[-1200:])

def render_audio(scenes,folder):
    parts=[]
    for i,s in enumerate(scenes):
        duration=float(s['duration']); duration=max(.5,min(30,duration))
        mp3=folder/f'voice{i}.mp3'; wav=folder/f'voice{i}.wav'
        gTTS(text=str(s['text'])[:500] or ' ',lang='ko').save(str(mp3))
        probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(mp3)],capture_output=True,text=True,check=True)
        original=float(probe.stdout.strip()); speed=max(.5,min(5,original/duration))
        # atempo supports 0.5..2; chain filters to support larger ratios
        filters=[]; v=speed
        while v>2: filters.append('atempo=2');v/=2
        while v<.5: filters.append('atempo=0.5');v/=.5
        filters.append(f'atempo={v:.5f}')
        filters.append(f'apad=whole_dur={duration:.4f}')
        filters.append(f'atrim=duration={duration:.4f}')
        ff('-i',mp3,'-af',','.join(filters),'-ar','44100','-ac','2',wav)
        parts.append(wav)
    concat=folder/'list.txt';concat.write_text(''.join(f"file '{p.name}'\n" for p in parts))
    joined=folder/'narration.wav';ff('-f','concat','-safe','0','-i',concat,'-c:a','pcm_s16le',joined)
    return joined

@app.post('/api/render')
async def render(video:UploadFile=File(...),scenes_json:str=Form(...)):
    try:
        scenes=json.loads(scenes_json)
        if not isinstance(scenes,list) or not 1<=len(scenes)<=30: raise ValueError('장면 개수 오류')
        if sum(float(s['duration']) for s in scenes)>180: raise ValueError('영상이 너무 깁니다')
        folder=Path(tempfile.mkdtemp(prefix='shorts_'))
        webm=folder/'silent.webm'
        with webm.open('wb') as out:
            while data:=await video.read(1024*1024):
                out.write(data)
                if out.tell()>150*1024*1024: raise ValueError('파일은 150MB 이하여야 합니다')
        audio=render_audio(scenes,folder)
        target=folder/'shorts_with_voice.mp4'
        ff('-i',webm,'-i',audio,'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',target)
        return FileResponse(target,media_type='video/mp4',filename='shorts_with_voice.mp4')
    except Exception as e:
        raise HTTPException(status_code=422,detail=str(e))

app.mount('/',StaticFiles(directory=str(ROOT),html=True),name='frontend')
