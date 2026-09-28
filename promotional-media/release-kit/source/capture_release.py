"""Recapture the exact AnkiWeb package with saved production configurations."""
import hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN=Path(json.loads((ROOT/'source/candidate.json').read_text())['run_root'])
pid=json.loads((RUN/'promo-process.json').read_text())['pid']
identity=json.loads((RUN/'QA_IDENTITY.json').read_text()); title=identity['profile']+' - Anki'
cases=[('Sapphire Glass','year',False,'sapphire-year-study'),('Emerald','month',True,'emerald-month-event'),('Sapphire Glass','year',True,'sapphire-year-verse'),('Emerald','year',True,'emerald-year-verse'),('Graphite','year',True,'graphite-year-verse')]
for attempt in range(3):
 for theme,view,bible,name in cases:
  (RUN/'promo-command.json').write_text(json.dumps(dict(action='configure',theme=theme,view=view,bible=bible,name=name)))
  time.sleep(3.5)
  subprocess.run(['/private/tmp/hdo-window-capture',str(pid),str(ROOT/'raw'/f'{name}.png'),title],check=True)
 data=json.loads((ROOT/'evidence/capture-manifest.json').read_text())
 relevant=[data['captures'][c[3]] for c in cases]
 if len({json.dumps(c['dom']['metrics'],sort_keys=True) for c in relevant})==1:break
else:raise RuntimeError('Displayed metrics changed during the capture pass')
for c in relevant:
 c['sha256']=hashlib.sha256((ROOT/c['file']).read_bytes()).hexdigest()
 assert c['dom']['metrics']['today.answers']=='186'
 assert c['dom']['metrics']['queue.total']=='94'
assert len({c['sha256'] for c in relevant})==5
assert not relevant[0]['dom']['verses']
assert 'Practice exam' in relevant[1]['dom']['text']
data['status']='captured';data.pop('error',None)
(ROOT/'evidence/capture-manifest.json').write_text(json.dumps(data,indent=2)+'\n')
print('Five native release captures complete, with identical metrics and real saved options.')
