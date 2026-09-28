"""Compose a static theme poster from retained, genuine native Anki captures."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/'layout.json').read_text())
W,H=CFG['size']; im=Image.new('RGB',(W,H),CFG['background']);d=ImageDraw.Draw(im)
FONT='/System/Library/Fonts/Supplemental/'
def font(size,bold=False):return ImageFont.truetype(FONT+('Arial Bold.ttf' if bold else 'Arial.ttf'),size)
def text(pos,copy,size,fill=None,bold=False,anchor=None):
    d.text(pos,copy,font=font(size,bold),fill=fill or CFG['ink'],anchor=anchor,stroke_width=0)
# Editorial heading; all UI imagery below remains an unmodified native capture.
d.rounded_rectangle((112,88,126,133),radius=7,fill='#568cc2')
text((148,88),'HOME SCREEN DASHBOARD',42,bold=True)
text((108,163),'Your Anki. Your style.',112,bold=True)
text((112,300),'Your study history, beautifully in view.',44,fill='#5d6670')
for row in CFG['themes']:
    y=row['label_y'];accent=row['accent']
    d.ellipse((144,y+10,166,y+32),fill=accent)
    text((184,y),row['name'],44,bold=True)
    text((2016,y+4),'YEAR VIEW',29,fill='#737c85',anchor='ra')
    raw=Image.open(ROOT.parent/'raw'/row['file']).convert('RGB')
    crop=tuple(CFG['native_crop']); box=raw.crop(crop)
    width=1872;height=round(box.height*width/box.width)
    box=box.resize((width,height),Image.Resampling.LANCZOS)
    py=y+66
    shadow=Image.new('RGBA',(W,H));sd=ImageDraw.Draw(shadow)
    sd.rounded_rectangle((144,py+10,2016,py+height+10),radius=20,fill=(15,25,40,40))
    shadow=shadow.filter(ImageFilter.GaussianBlur(16))
    im=Image.alpha_composite(im.convert('RGBA'),shadow).convert('RGB');d=ImageDraw.Draw(im)
    mask=Image.new('L',box.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius=20,fill=255)
    im.paste(box,(144,py),mask)
    d.rounded_rectangle((144,py,2015,py+height-1),radius=20,outline='#d0d3d4',width=2)
# One installation call to action, aligned with the gallery.
d.line((144,2538,2016,2538),fill='#cbd0d3',width=2)
text((144,2593),'For Anki Desktop',40,fill='#606a73')
text((2016,2580),'AnkiWeb: 808247776',57,bold=True,anchor='ra')
im.save(ROOT/'home-screen-dashboard-theme-poster.png',dpi=(300,300))
im.resize((1080,1350),Image.Resampling.LANCZOS).save(ROOT/'home-screen-dashboard-poster-preview.png')
im.resize((1080,1350),Image.Resampling.LANCZOS).save(ROOT/'home-screen-dashboard-poster-preview.jpg',quality=95,subsampling=0)
im.resize((480,600),Image.Resampling.LANCZOS).save(ROOT/'preview.png')
print('Created 2160 × 2700 theme poster and smaller previews.')
