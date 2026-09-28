"""Launch only the prepared disposable profile; baseline first, candidate second."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import plistlib

OUT=Path(__file__).resolve().parents[1]
meta=json.loads((OUT/'source/candidate.json').read_text())
run=Path(meta['run_root'])
assert str(run).startswith('/private/tmp/anki-release-qa.')
identity=json.loads((run/'QA_IDENTITY.json').read_text())
stage=sys.argv[1]
assert stage in ('standard','dashboard')
app=run/'Dashboard Media Demo.app'
contents=app/'Contents'
if not app.exists():
    (contents/'MacOS').mkdir(parents=True)
    original=Path('/Applications/Anki.app/Contents')
    info=plistlib.loads((original/'Info.plist').read_bytes())
    info.update(CFBundleIdentifier='org.codex.dashboard-media.nt0lfleb',
                CFBundleName='Dashboard Media Demo',CFBundleDisplayName='Dashboard Media Demo',
                CFBundleExecutable='DashboardMediaDemo')
    (contents/'Info.plist').write_bytes(plistlib.dumps(info))
    shutil.copy2(original/'MacOS/Anki',contents/'MacOS/DashboardMediaDemo')
    (contents/'Resources').symlink_to(original/'Resources')
    (contents/'Frameworks').symlink_to(original/'Frameworks')
    subprocess.run(['codesign','--force','--sign','-',str(app)],check=True)
identity['launch']['argv'][0]=str(contents/'MacOS/DashboardMediaDemo')
(run/'QA_IDENTITY.json').write_text(json.dumps(identity,indent=2))
helper=run/'addons21/zz_dashboard_promo';helper.mkdir(parents=True,exist_ok=True)
shutil.copy2(OUT/'source/capture_addon.py',helper/'__init__.py')
(helper/'manifest.json').write_text(json.dumps({'name':'Disposable Dashboard Promo Capture','package':'zz_dashboard_promo'}))
if stage=='dashboard':
    target=run/'addons21/home_dashboard_overhaul';target.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT/'source/candidate.ankiaddon') as z:z.extractall(target)
processes=subprocess.check_output(['ps','-axo','pid=,command='],text=True)
excluded=[]
for line in processes.splitlines():
    if (' -b /private/tmp/anki-release-qa.' in line and ' -p ' in line) or line.strip().endswith('/Applications/Anki.app/Contents/MacOS/Anki'):
        assert str(run) not in line,'The disposable profile is already running'
        excluded.append(int(line.strip().split(None,1)[0]))
(run/'excluded-pids.json').write_text(json.dumps(excluded))
env=dict(os.environ,**identity['launch']['env'])
env.update(HDO_PROMO_RUN=str(run),HDO_PROMO_OUT=str(OUT),PYTHONDONTWRITEBYTECODE='1')
env['QTWEBENGINE_CHROMIUM_FLAGS']='--disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-background-timer-throttling'
with (run/f'launch-{stage}.log').open('w') as log:
    proc=subprocess.Popen(identity['launch']['argv'],env=env,stdout=log,stderr=subprocess.STDOUT)
    (run/'promo-process.json').write_text(json.dumps({'pid':proc.pid,'stage':stage,'excluded_pids':excluded}))
print(json.dumps({'pid':proc.pid,'stage':stage,'run_root':str(run),'excluded_pids':excluded}))
sys.stdout.flush()
sys.exit(proc.wait())
