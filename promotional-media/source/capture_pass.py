"""Capture saved appearances while Anki's GUI event loop remains available."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

OUT=Path(__file__).resolve().parents[1]
RUN=Path(json.loads((OUT/'source/candidate.json').read_text())['run_root'])
pid=json.loads((RUN/'promo-process.json').read_text())['pid']
identity=json.loads((RUN/'QA_IDENTITY.json').read_text())
title=identity['profile']+' - Anki'
captures=[('Sapphire Glass','month'),('Emerald','year'),('Graphite','year'),('Sapphire Glass','year')]
for attempt in range(3):
    for theme,view in captures:
        name=theme.lower().replace(' ','-')+'-'+view
        (RUN/'promo-command.json').write_text(json.dumps(dict(action='configure',theme=theme,view=view)))
        time.sleep(3.2)
        subprocess.run(['/private/tmp/hdo-window-capture',str(pid),str(OUT/'raw'/f'{name}.png'),title],check=True)
    data=json.loads((OUT/'evidence/capture-manifest.json').read_text())
    relevant=[data['captures'][t.lower().replace(' ','-')+'-'+v] for t,v in captures]
    assert all(c['dom']['metrics'].get('queue.total')=='94' for c in relevant), 'Dashboard is not ready'
    if len({json.dumps(c['dom']['metrics'],sort_keys=True) for c in relevant})==1:
        assert len({hashlib.sha256((OUT/c['file']).read_bytes()).hexdigest() for c in relevant})==4, 'Native appearances did not redraw'
        break
else:raise RuntimeError('Unable to capture consistent metrics before the ETA minute changes')
manifest=OUT/'evidence/capture-manifest.json'
data=json.loads(manifest.read_text())
for value in data['captures'].values():
    value['sha256']=hashlib.sha256((OUT/value['file']).read_bytes()).hexdigest()
data['external_capture_pass']=dict(pid=pid,method='ScreenCaptureKit with the native GUI event loop unblocked')
manifest.write_text(json.dumps(data,indent=2))
print({k:v['dom']['metrics'].get('queue.eta') for k,v in data['captures'].items()})
