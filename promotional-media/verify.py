"""Focused deliverable checks; no application tests or normal-profile access."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zipfile

import imageio_ffmpeg
from PIL import Image, ImageChops, ImageStat

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cfg=json.loads((ROOT/'timeline.json').read_text())
    cap=json.loads((ROOT/'evidence/capture-manifest.json').read_text())
    candidate=json.loads((ROOT/'source/candidate.json').read_text())
    listing=json.loads((ROOT/'evidence/ankiweb-listing.json').read_text())
    assert listing['title']=='Home Screen Dashboard' and listing['install_code']=='808247776'
    assert candidate['sha256']==sha(ROOT/'source/candidate.ankiaddon')
    with zipfile.ZipFile(ROOT/'source/candidate.ankiaddon') as z:
        assert len(z.namelist())==25
        assert not any('promotional-media' in n or n.endswith(('.mp4','.gif')) for n in z.namelist())
    names=['sapphire-glass-month','emerald-year','graphite-year','sapphire-glass-year','sapphire-glass-month-verse']
    captures=[cap['captures'][n] for n in names]
    assert len({json.dumps(c['dom']['metrics'],sort_keys=True) for c in captures})==1,'Capture statistics differ'
    assert len({c['scheduling_date'] for c in captures})==1
    assert len({tuple(c['pixels']) for c in captures})==1
    for n,c in zip(names,captures):
        assert sha(ROOT/c['file'])==c['sha256']
        assert c['method']=='ScreenCaptureKit isolated window compositor'
        assert c['dom']['metrics']['queue.total']=='94'
        assert c['dom']['metrics']['today.answers']=='186'
        if 'year' in n:
            assert c['dom']['view']=='year'
            assert any(v['rect']['height']>0 and v['text'] for v in c['dom']['verses'])
            assert json.loads((ROOT/f'source/config-{n}.json').read_text())['visibility']['bible']
    assert len({c['sha256'] for c in captures[1:4]})==3,'Theme captures are identical'
    interaction=cap['calendar_interaction']
    assert sha(ROOT/interaction['file'])==interaction['sha256']
    assert interaction['speed_factor']==1 and interaction['bible_visible']
    assert cfg['calendar']['stable_year_seconds']-cfg['calendar']['source_start_seconds']<=1
    assert cfg['calendar']['observed_change_seconds']-cfg['calendar']['source_start_seconds']<0.7
    assert interaction['native_pixel_transition_verified']
    assert cfg['scenes'][0]['start']==0 and cfg['scenes'][-1]['end']==420
    assert all(a['end']==b['start'] for a,b in zip(cfg['scenes'],cfg['scenes'][1:]))
    movie=OUT/'home-screen-dashboard.mp4'
    reader=imageio_ffmpeg.read_frames(str(movie));meta=next(reader);reader.close()
    count,duration=imageio_ffmpeg.count_frames_and_secs(str(movie))
    assert count==420 and abs(duration-14)<0.002
    assert meta['size']==(1440,1080) and meta['fps']==30 and meta['codec']=='h264'
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    info=subprocess.run([ff,'-hide_banner','-i',str(movie)],text=True,capture_output=True).stderr
    assert 'Audio:' not in info and 'yuv420p' in info
    atoms=[]
    with movie.open('rb') as f:
        while True:
            head=f.read(8)
            if len(head)<8:break
            size,kind=struct.unpack('>I4s',head);extra=8
            if size==1:size=struct.unpack('>Q',f.read(8))[0];extra=16
            atoms.append(kind.decode('ascii'))
            if not size:break
            f.seek(size-extra,1)
    assert atoms.index('moov')<atoms.index('mdat'),'MP4 is not fast-start'
    gif=Image.open(OUT/'home-screen-dashboard.gif');ms=0
    assert gif.size==(960,720) and gif.info.get('loop')==0
    first=None;last=None
    for i in range(gif.n_frames):
        gif.seek(i);ms+=gif.info.get('duration',0)
        if i==0:first=gif.convert('RGB').copy()
        last=gif.convert('RGB').copy()
    assert ms==11000,f'GIF runtime is {ms} ms'
    assert sum(ImageStat.Stat(ImageChops.difference(first,last)).mean)<1,'GIF loop seam differs'
    assert Image.open(OUT/'home-screen-dashboard-poster.png').size==(1440,1080)
    report=dict(status='passed',mp4=dict(frames=count,duration=duration,size=list(meta['size']),fps=meta['fps'],
        codec=meta['codec'],pixel_format='yuv420p',audio_streams=0,fast_start=True),
        gif=dict(duration_ms=ms,size=[960,720],nominal_fps=15,loop=0,stored_frames=gif.n_frames),
        statistics_identical=True,bible_visible_in_all_year_themes=True,candidate_media_excluded=True,
        files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [OUT/'home-screen-dashboard.mp4',OUT/'home-screen-dashboard.gif',OUT/'home-screen-dashboard-poster.png']})
    (ROOT/'evidence/export-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
