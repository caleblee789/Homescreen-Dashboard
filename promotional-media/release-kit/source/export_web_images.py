"""Export matching optimized web images and untouched full-size native captures."""
from pathlib import Path
import hashlib,json,shutil
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
CAP=json.loads((ROOT/'evidence/capture-manifest.json').read_text())
MAPPING={'dashboard-sapphire-year':'sapphire-year-study','dashboard-emerald-month':'emerald-month-event','dashboard-graphite-year':'graphite-year-verse','dashboard-sapphire-year-verse':'sapphire-year-verse','dashboard-emerald-year':'emerald-year-verse'}
def main():
 out=ROOT/'docs/images/1.8.7';out.mkdir(parents=True,exist_ok=True);report={}
 for name,key in MAPPING.items():
  c=CAP['captures'][key];source=ROOT/c['file'];assert hashlib.sha256(source.read_bytes()).hexdigest()==c['sha256']
  full=out/f'{name}-full.png';shutil.copy2(source,full)
  im=Image.open(source).convert('RGB')
  # Keep native Anki navigation and deck list, trim only title and empty lower canvas.
  bottom=1690 if c['dom']['view']=='month' else 1380
  box=(220,64,2660,bottom);web=im.crop(box);web.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  target=out/f'{name}-web.jpg';web.save(target,quality=92,subsampling=0,optimize=True)
  report[name]={'source':c['file'],'full_original_sha256':c['sha256'],'full_bytes':full.stat().st_size,'web_bytes':target.stat().st_size,'web_dimensions':list(web.size),'web_native_crop':list(box)}
 (ROOT/'evidence/web-image-exports.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Exported five optimized web images and five unchanged full-size originals.')
if __name__=='__main__':main()
