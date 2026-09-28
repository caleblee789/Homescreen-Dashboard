"""Reproduce the MP4, GIF and poster from immutable native captured sources."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent


def ease(t):
    t = max(0, min(1, t))
    return t*t*(3-2*t)


class Renderer:
    def __init__(self, config, cache):
        self.cfg = config
        self.size = tuple(config['canvas'])
        self.cache = cache
        self.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        self.images = {k: Image.open(ROOT/v).convert('RGB') for k,v in config['sources'].items() if k != 'calendar'}
        self.fonts = {}
        c=config['crops']['dashboard']; x,y,x2,y2=c
        subprocess.run([self.ffmpeg,'-y','-loglevel','error',
            '-ss',str(config['calendar']['source_start_seconds']),'-i',str(ROOT/config['sources']['calendar']),
            '-vf',f'crop={x2-x}:{y2-y}:{x}:{y},scale=1440:960:flags=lanczos,fps=30',
            '-frames:v','90',str(cache/'calendar-%03d.png')],check=True)

    def font(self,size):
        if size not in self.fonts:
            self.fonts[size]=ImageFont.truetype(self.cfg['caption']['font'],size)
        return self.fonts[size]

    def image(self,key,crop=None):
        c=crop or self.cfg['crops']['dashboard']
        height=min(960,round((c[3]-c[1])/(c[2]-c[0])*1440))
        im=self.images[key].resize((1440,height),Image.Resampling.LANCZOS,box=tuple(c))
        canvas=Image.new('RGB',self.size,self.cfg['background'])
        canvas.paste(im,(0,120+(960-height)//2))
        return canvas

    def caption(self,canvas,text):
        d=ImageDraw.Draw(canvas)
        d.text(tuple(self.cfg['caption']['center']),text,font=self.font(self.cfg['caption']['size']),
               fill=self.cfg['caption']['color'],anchor='mm')
        return canvas

    def utility(self,t):
        a=self.cfg['crops']['dashboard'];b=self.cfg['crops']['utility']
        e=ease(t/9)
        return self.image('month',[u+(v-u)*e for u,v in zip(a,b)])

    def calendar(self,t):
        im=Image.new('RGB',self.size,self.cfg['background'])
        im.paste(Image.open(self.cache/f'calendar-{min(90,int(t)+1):03d}.png').convert('RGB'),(0,120))
        g=self.cfg['calendar']['pointer_guide']
        if t<g['hide_frame']:
            lo,hi=g['move_frames'];e=ease((t-lo)/(hi-lo))
            sx,sy=g['start'];tx,ty=g['target']
            px=sx+(tx-sx)*e;py=sy+(ty-sy)*e
            crop=self.cfg['crops']['dashboard']
            x=(px-crop[0])*1440/(crop[2]-crop[0]);y=120+(py-crop[1])*960/(crop[3]-crop[1])
            # Editorial pointer guide; no changes to the native UI pixels or timing.
            overlay=Image.new('RGBA',im.size);d=ImageDraw.Draw(overlay)
            if g['click_frame']<=t<g['click_frame']+6:
                r=10+(t-g['click_frame'])*2
                d.ellipse([x-r,y-r,x+r,y+r],outline=(220,237,255,170),width=2)
            pts=[(x,y),(x+2,y+27),(x+9,y+20),(x+16,y+34),(x+22,y+31),(x+15,y+18),(x+26,y+17)]
            d.polygon(pts,fill='#ffffff',outline='#172132',width=2)
            im=Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB')
        return im

    def theme(self,t):
        return self.image(self.cfg['scenes'][3]['order'][min(2,int(t)//30)])

    def install(self):
        im=self.image('year')
        d=ImageDraw.Draw(im);p=self.cfg['installation'];scene=self.cfg['scenes'][4]
        # Installation panel above the dashboard, leaving the Year verse visible.
        d.rounded_rectangle(p['panel'],radius=20,fill='#172433',outline='#30475e',width=1)
        for text,size,y,color in [(scene['name'],p['name_size'],p['name_y'],'#f6f8fc'),
                                  (scene['code'],p['code_size'],p['code_y'],'#90c7ff'),
                                  (scene['support'],p['support_size'],p['support_y'],'#b7c6d5')]:
            d.text((720,y),text,font=self.font(size),fill=color,anchor='mm')
        return im

    def frame(self,n):
        s=next(s for s in self.cfg['scenes'] if s['start']<=n<s['end']);t=n-s['start']
        if s['id']=='reveal':
            im=self.image('month')
            if t<s['wipe_frames']:
                before=self.image('standard')
                width=round(1440*s['before_fraction']*(1-ease(t/s['wipe_frames'])))
                im.paste(before.crop((0,120,width,1080)),(0,120))
                ImageDraw.Draw(im).line((width,120,width,1080),fill='#b6cce0',width=2)
        elif s['id']=='utility':im=self.utility(t)
        elif s['id']=='calendar':im=self.calendar(t)
        elif s['id']=='themes':im=self.theme(t)
        else:return self.install()
        return self.caption(im,s['caption'])

    def gif_frame(self,n):
        if n<15:im=self.caption(self.image('month'),'Your Anki, upgraded.')
        elif n<60:im=self.caption(self.utility((n-15)*2),'Know what’s left today.')
        elif n<105:im=self.caption(self.calendar((n-60)*2),'Month + Year views')
        elif n<150:im=self.caption(self.theme((n-105)*2),'Make it yours.')
        else:im=self.caption(self.image('month'),'Your Anki, upgraded.')
        return im.resize(tuple(self.cfg['gif']['canvas']),Image.Resampling.LANCZOS)

    def encode(self,path,frames,fps,size,extra):
        command=[self.ffmpeg,'-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24',
                 '-video_size',f'{size[0]}x{size[1]}','-framerate',str(fps),'-i','pipe:0','-an']+extra+[str(path)]
        p=subprocess.Popen(command,stdin=subprocess.PIPE)
        try:
            for frame in frames:p.stdin.write(frame.tobytes())
        finally:p.stdin.close()
        if p.wait():raise RuntimeError('Encoding failed')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=ROOT/'timeline.json')
    ap.add_argument('--preview-only',action='store_true');args=ap.parse_args()
    cfg=json.loads(args.config.read_text());out=ROOT/'output';out.mkdir(exist_ok=True)
    assert cfg['frames']==420 and cfg['fps']==30 and cfg['canvas']==[1440,1080]
    with tempfile.TemporaryDirectory(prefix='hdo-promo-render-') as temp:
        r=Renderer(cfg,Path(temp))
        preview_indices=[0,24,75,153,195,240,270,300,365]
        board=Image.new('RGB',(1440,1080),'#11151b')
        for i,n in enumerate(preview_indices):
            im=r.frame(n);im.save(out/f'preview-{n:03d}.png')
            board.paste(im.resize((480,360),Image.Resampling.LANCZOS),((i%3)*480,(i//3)*360))
        board.save(out/'storyboard.png')
        r.caption(r.image('month'),'Your Anki, upgraded.').save(out/'home-screen-dashboard-poster.png')
        if args.preview_only:return
        r.encode(out/'home-screen-dashboard.mp4',(r.frame(i) for i in range(420)),30,(1440,1080),
                 ['-vf','scale=out_color_matrix=bt709:out_range=tv','-c:v','libx264','-crf','17','-preset','slow',
                  '-pix_fmt','yuv420p','-profile:v','high','-level:v','4.2','-colorspace','bt709',
                  '-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart'])
        r.encode(out/'home-screen-dashboard.gif',(r.gif_frame(i) for i in range(165)),15,(960,720),
                 ['-filter_complex','split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
                  '-loop','0','-gifflags','+transdiff'])
    print('Rendered MP4, GIF, poster and storyboard in',out)


if __name__=='__main__':main()
