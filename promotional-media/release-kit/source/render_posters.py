"""Render approved-brand poster layouts from complete native package captures."""
from pathlib import Path
import hashlib,json
from PIL import Image,ImageDraw,ImageFont,ImageChops,ImageFilter
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'source/poster-layout.json').read_text())
CAP=json.loads((ROOT/'evidence/capture-manifest.json').read_text())
SCALE=2;SIZE=(2160,2700);BG='#f3f2ee';INK='#192430';MUTED='#606a73'
FONT='/System/Library/Fonts/Supplemental/'
def ft(n,b=False):return ImageFont.truetype(FONT+('Arial Bold.ttf' if b else 'Arial.ttf'),round(n*SCALE))
def txt(im,x,y,s,n=24,b=False,c=INK,anchor=None):
 d=ImageDraw.Draw(im);d.text((x*SCALE,y*SCALE),s,font=ft(n,b),fill=c,anchor=anchor)
def line(im,y):ImageDraw.Draw(im).line((64*SCALE,y*SCALE,1016*SCALE,y*SCALE),fill='#cbd0d3',width=2)
def native(key):
 c=CAP['captures'][key];p=ROOT/c['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==c['sha256']
 im=Image.open(p).convert('RGB');r=c['dom']['root'];off=c['web_offset'];dpr=c['dpr']
 crop=(round((r['x']+off[0])*dpr)-16,round((r['y']+off[1])*dpr)-16,round((r['x']+r['width']+off[0])*dpr)+16,round((r['y']+r['height']+off[1])*dpr)+16)
 crop=(max(0,crop[0]),max(0,crop[1]),min(im.width,crop[2]),min(im.height,crop[3]))
 part=im.crop(crop)
 # Trim empty native canvas only, retaining every panel and its real content.
 mask=ImageChops.difference(part,Image.new('RGB',part.size,'#2b2b2b')).convert('L').point(lambda p:255 if p>16 else 0)
 bbox=mask.getbbox();assert bbox
 x,y,x2,y2=bbox;part=part.crop((max(0,x-14),max(0,y-14),min(part.width,x2+14),min(part.height,y2+14)))
 return part,crop
USED={}
def panel(im,key,y,width=952,maxh=450):
 source,crop=native(key);ratio=min(width/source.width,maxh/source.height)*SCALE
 w,h=round(source.width*ratio),round(source.height*ratio);x=(SIZE[0]-w)//2;py=round(y*SCALE)
 pic=source.resize((w,h),Image.Resampling.LANCZOS)
 shadow=Image.new('RGBA',SIZE);d=ImageDraw.Draw(shadow);d.rounded_rectangle((x,py+8,x+w,py+h+8),radius=16,fill=(20,30,40,38));shadow=shadow.filter(ImageFilter.GaussianBlur(13))
 im=Image.alpha_composite(im.convert('RGBA'),shadow).convert('RGB')
 mask=Image.new('L',(w,h));ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),radius=16,fill=255);im.paste(pic,(x,py),mask)
 USED[key]={'native_window_crop':crop,'poster_rect':[x,py,w,h]}
 return im,y+h/SCALE

def base():
 im=Image.new('RGB',SIZE,BG);d=ImageDraw.Draw(im)
 d.rounded_rectangle((128,96,232,104),radius=4,fill='#568cc2')
 txt(im,62,70,CFG['branding']['poster_header'],60,True)
 txt(im,64,154,CFG['branding']['poster_subtitle'],32,c=MUTED)
 return im

def footer(im,y,gallery=False):
 line(im,y)
 note='Also includes High Contrast · Optional Bible verse' if gallery else '4 themes, including High Contrast · Free & open source'
 txt(im,64,y+18,note,22)
 txt(im,64,y+57,'Install with code 808247776',44,True)
 txt(im,64,y+114,'Tools → Add-ons → Get Add-ons',24,c=MUTED)
 txt(im,64,y+151,'For Anki Desktop 26.8',22,c=MUTED)
 txt(im,1016,y+154,'Demo study data',18,c=MUTED,anchor='ra')
 if gallery:txt(im,1016,y+18,'Free & open source',19,c=MUTED,anchor='ra')
 return im

def save(im,name):
 out=ROOT/'output';out.mkdir(exist_ok=True)
 im.save(out/f'{name}-master.png',dpi=(300,300))
 im.resize((1080,1350),Image.Resampling.LANCZOS).save(out/f'{name}.png')
 im.resize((1080,1350),Image.Resampling.LANCZOS).save(out/f'{name}.jpg',quality=95,subsampling=0,optimize=True)
 im.resize((360,450),Image.Resampling.LANCZOS).save(ROOT/'review'/f'{name}-360.png')

def main():
 required=['sapphire-year-study','emerald-month-event','sapphire-year-verse','emerald-year-verse','graphite-year-verse']
 missing=[n for n in required if n not in CAP['captures']]
 if missing:raise SystemExit('Fresh native captures are required: '+', '.join(missing))
 assert CAP['captures'][CFG['lead'][0]]['dom']['verses']
 assert 'Practice exam' in CAP['captures'][required[1]]['dom']['text']
 im=base()
 txt(im,64,246,'Sapphire Glass / Year view',26,c=MUTED)
 im,bottom=panel(im,CFG['lead'][0],286,maxh=294)
 txt(im,64,631,'Emerald / Month view',26,c=MUTED)
 im,bottom=panel(im,'emerald-month-event',676,maxh=434)
 txt(im,64,1126,'Bible verse panel is optional.',21,c=MUTED)
 im=footer(im,1160);save(im,'home-screen-dashboard-feature-poster')
 im=base()
 for key,label,accent,y in CFG['gallery']:
  ImageDraw.Draw(im).ellipse((128,round((y+9)*2),148,round((y+19)*2)),fill=accent)
  txt(im,86,y,label,25,True);txt(im,1016,y+2,'YEAR VIEW',20,c=MUTED,anchor='ra')
  im,bottom=panel(im,key,y+39,width=880,maxh=247)
 im=footer(im,1160,gallery=True);save(im,'home-screen-dashboard-theme-gallery')
 (ROOT/'evidence/poster-crops.json').write_text(json.dumps(USED,indent=2)+'\n')
 print('Feature poster and secondary theme gallery rendered from exact-package native captures.')
if __name__=='__main__':main()
