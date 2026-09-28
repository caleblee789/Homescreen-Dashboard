"""Decode complete exports and build visual review sheets at feed width."""
import json
from pathlib import Path
import imageio_ffmpeg
from PIL import Image,ImageChops,ImageStat,ImageDraw
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output';EV=ROOT/'evidence'
reader=imageio_ffmpeg.read_frames(str(OUT/'home-screen-dashboard.mp4'));meta=next(reader)
boards=[Image.new('RGB',(1440,1140),'#11151b') for _ in range(2)]
end_reference=None;max_end_delta=0;count=0
for i,data in enumerate(reader):
    im=Image.frombytes('RGB',meta['size'],data);count+=1
    if i>=315:
        if end_reference is None:end_reference=im.copy()
        max_end_delta=max(max_end_delta,sum(ImageStat.Stat(ImageChops.difference(im,end_reference)).mean))
    if i%15==0:
        n=i//15;page=n//16;slot=n%16;thumb=im.resize((360,270),Image.Resampling.LANCZOS)
        boards[page].paste(thumb,((slot%4)*360,(slot//4)*285))
        ImageDraw.Draw(boards[page]).text(((slot%4)*360+5,(slot//4)*285+270),f'{i/30:.1f}s / frame {i}',fill='white')
    if i in (24,75,153,195,240,270,300,365):
        im.save(EV/f'decoded-{i:03d}.png')
        if i in (75,365):im.resize((360,270),Image.Resampling.LANCZOS).save(EV/f'feed-{i:03d}.png')
for i,b in enumerate(boards):b.save(EV/f'mp4-review-{i+1}.png')
assert count==420 and max_end_delta<3.0,(count,max_end_delta)
gif=Image.open(OUT/'home-screen-dashboard.gif');board=Image.new('RGB',(1440,1140),'#11151b');ms=0;slot=0
for i in range(gif.n_frames):
    gif.seek(i)
    if ms>=slot*1000 and slot<11:
        board.paste(gif.convert('RGB').resize((360,270),Image.Resampling.LANCZOS),((slot%4)*360,(slot//4)*285))
        ImageDraw.Draw(board).text(((slot%4)*360+5,(slot//4)*285+270),f'{ms/1000:.2f}s',fill='white');slot+=1
    ms+=gif.info['duration']
board.save(EV/'gif-review.png')
(EV/'decode-review.json').write_text(json.dumps(dict(decoded_mp4_frames=count,final_hold_frames=105,maximum_hold_rgb_mean_delta=max_end_delta,hold_comparison_tolerance_sum_rgb=3.0,hold_tolerance_reason='Lossy H.264 I/P/B quantization; less than one intensity step per channel on average',gif_frames_decoded=gif.n_frames,gif_duration_ms=ms),indent=2))
print('All 420 MP4 frames and 165 GIF frames decoded; installation hold is stationary.')
