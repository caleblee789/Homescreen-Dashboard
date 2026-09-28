"""Focused media, provenance and draft-link validation; no product tests."""
from pathlib import Path
import hashlib,json,re,zipfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 cap=json.loads((ROOT/'evidence/capture-manifest.json').read_text())
 candidate=json.loads((ROOT/'source/candidate.json').read_text())
 assert sha(ROOT/'source/candidate.ankiaddon')==candidate['sha256']
 assert candidate['sha256']==sha(ROOT/'source/ankiweb-package.ankiaddon')
 with zipfile.ZipFile(ROOT/'source/candidate.ankiaddon') as z:
  assert len(z.namelist())==25
  assert not any('promotional-media' in n for n in z.namelist())
 names=['sapphire-year-study','emerald-month-event','sapphire-year-verse','emerald-year-verse','graphite-year-verse']
 cases=[cap['captures'][n] for n in names]
 assert len({json.dumps(c['dom']['metrics'],sort_keys=True) for c in cases})==1
 assert len({c['scheduling_date'] for c in cases})==1
 assert len({tuple(c['frame']) for c in cases})==1
 assert len({tuple(c['dom']['selected']) for c in cases})==1
 for name,c in zip(names,cases):
  assert sha(ROOT/c['file'])==c['sha256']
  assert Image.open(ROOT/c['file']).size==(2880,1936)
  config=json.loads((ROOT/'source'/f'config-{name}.json').read_text())
  assert c['dom']['metrics']['queue.total']=='94' and c['dom']['metrics']['today.answers']=='186'
  assert config['visibility']['bible']==(name!='sapphire-year-study')
  if name!='sapphire-year-study':assert c['dom']['verses']
 assert cases[0]['dom']['view']=='year' and not cases[0]['dom']['verses']
 assert cases[1]['dom']['view']=='month' and 'Practice exam' in cases[1]['dom']['text']
 for name in ['home-screen-dashboard-feature-poster','home-screen-dashboard-theme-gallery']:
  assert Image.open(ROOT/'output'/f'{name}.png').size==(1080,1350)
  assert Image.open(ROOT/'output'/f'{name}-master.png').size==(2160,2700)
  assert Image.open(ROOT/'review'/f'{name}-360.png').size==(360,450)
 exports=json.loads((ROOT/'evidence/web-image-exports.json').read_text())
 for name,e in exports.items():
  full=ROOT/'docs/images/1.8.7'/f'{name}-full.png';web=ROOT/'docs/images/1.8.7'/f'{name}-web.jpg'
  assert sha(full)==e['full_original_sha256']
  assert web.stat().st_size<full.stat().st_size
 for p in (ROOT/'drafts').glob('*'):
  s=p.read_text();assert 'Home Screen Dashboard' in s and '808247776' in s and 'High Contrast' in s
  assert 'Windows and Linux have not yet been validated' in s
  assert 'third-year medical' not in s
 readme=(ROOT/'drafts/README.md').read_text()
 for target in re.findall(r'\]\(([^)]+)\)',readme):
  if not target.startswith('https://'):
   target=target.split('#')[0]
   assert (ROOT/target).exists() or (REPO/target).exists() or target in json.loads((ROOT/'evidence/repository-link-targets.json').read_text()),target
 html=(ROOT/'drafts/ankiweb-description.html').read_text()
 urls=re.findall(r'(?:src|href)="(https://raw.githubusercontent.com/[^"]+)"',html)
 assert len(urls)==4
 for url in urls:assert (ROOT/'docs/images/1.8.7'/url.rsplit('/',1)[1]).exists()
 report={'status':'passed','media_ready_for_review':True,'publication_authorized':False,'package_source':'AnkiWeb 808247776','package_sha256':candidate['sha256'],'captures':5,'identical_metrics_dates_geometry_and_selection':True,'poster_dimensions':[1080,1350],'master_dimensions':[2160,2700],'full_size_originals_retained':True,'staged_image_targets_present':True,'planned_image_urls_live':False,'remaining_gate':'AnkiWeb and GitHub 1.8.7 assets differ; explicit user publication approval is required.'}
 (ROOT/'evidence/draft-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
