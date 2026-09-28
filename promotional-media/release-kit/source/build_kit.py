"""Regenerate all local assets and package a review kit; never publish."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
for script in ['render_posters.py','export_web_images.py','prepare_web_copy.py','validate_kit.py']:
 subprocess.run([sys.executable,str(ROOT/'source'/script)],check=True)
shutil.copy2(ROOT/'drafts/README.md',ROOT/'README.md')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='kit-sha256.json' and '__pycache__' not in p.parts)
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
path=ROOT/'evidence/kit-sha256.json';path.write_text(json.dumps(manifest,indent=2)+'\n');files.append(path)
archive=ROOT/'home-screen-dashboard-review-kit.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files:z.write(p,Path('home-screen-dashboard-release-kit')/p.relative_to(ROOT))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
# Keep the earlier shared draft link current as well.
shutil.copy2(archive,ROOT/'home-screen-dashboard-draft-kit.zip')
print(json.dumps({'review_kit':str(archive),'bytes':archive.stat().st_size,'files':len(files),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2))
