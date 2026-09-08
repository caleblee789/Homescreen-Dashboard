from pathlib import Path
import json, os, subprocess, sys
base = Path('/private/tmp/anki-release-qa.9gwt43qn')
marker = json.loads((base/'QA_IDENTITY.json').read_text())
stage = sys.argv[1]
assert stage in ('initial', 'restart')
for pid in (37774, 38373):
    os.kill(pid, 0)
env = dict(os.environ, **marker['launch']['env'])
env.update({
    'HDO_RELEASE_RUN_ROOT': str(base),
    'HDO_RELEASE_PROFILE': marker['profile'],
    'HDO_RELEASE_CANDIDATE_SHA256': marker['candidate_sha256'],
    'HDO_RELEASE_INSTANCE_KEY': marker['single_instance_key'],
    'HDO_RELEASE_EXCLUDED_PID': '37774',
    'HDO_RELEASE_PROBE_STAGE': stage,
    'HDO_SETTINGS_WORKFLOW_STAGE': stage,
    'HDO_SETTINGS_WORKFLOW_WINDOWED': '1',
    'PYTHONDONTWRITEBYTECODE': '1',
})
mode = 'fullscreen' if len(sys.argv) > 2 and sys.argv[2] == 'fullscreen' else 'windowed'
if mode == 'fullscreen':
    env.pop('HDO_SETTINGS_WORKFLOW_WINDOWED', None)
with (base/('anki-'+mode+'-'+stage+'.log')).open('w') as log:
    proc = subprocess.Popen(marker['launch']['argv'], env=env, stdout=log, stderr=subprocess.STDOUT)
    (base/('launch-'+mode+'-'+stage+'.json')).write_text(json.dumps({'pid': proc.pid, 'argv': marker['launch']['argv'], 'excluded_pids': [37774, 38373]}, indent=2))
    print('Isolated Anki PID', proc.pid, flush=True)
    result = proc.wait()
for pid in (37774, 38373):
    os.kill(pid, 0)
print('Exited', result, '; excluded Anki processes are still running', flush=True)
sys.exit(result)
