"""Disposable-profile media capture helper. Never installed in a normal base.

Uses actual collection data, production configuration and native compositor pixels.
Commands are explicit JSON files under the identity-gated disposable run root.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import random
import subprocess
import time
import traceback
import zipfile
from datetime import datetime, timedelta

from aqt import mw, gui_hooks
from aqt.qt import QApplication, QTimer, QPoint, QPixmap, Qt
from aqt.theme import Theme, theme_manager
from anki.collection import AddNoteRequest

RUN = Path(os.environ['HDO_PROMO_RUN']).resolve()
OUT = Path(os.environ['HDO_PROMO_OUT']).resolve()
IDENTITY = json.loads((RUN / 'QA_IDENTITY.json').read_text())
REPORT = json.loads((OUT/'evidence/capture-manifest.json').read_text()) if (OUT/'evidence/capture-manifest.json').exists() else {'captures': {}, 'recordings': {}, 'status': 'starting'}
TIMERS = []


def write_report():
    (OUT / 'evidence/capture-manifest.json').write_text(json.dumps(REPORT, indent=2))


def guard():
    assert str(RUN).startswith('/private/tmp/anki-release-qa.')
    assert mw.pm.name == IDENTITY['profile']
    assert IDENTITY['profile'] in mw.windowTitle()
    assert Path(mw.col.path).resolve().is_relative_to(RUN)
    assert Path(__file__).resolve().is_relative_to(RUN)
    assert os.environ['ANKI_SINGLE_INSTANCE_KEY'] == IDENTITY['single_instance_key']
    profile = mw.pm.profile
    assert not any(profile.get(k) for k in ('syncKey', 'syncUser', 'autoSync', 'syncMedia'))
    args = subprocess.check_output(['ps', '-p', str(os.getpid()), '-o', 'args='], text=True)
    assert str(RUN) in args and IDENTITY['profile'] in args
    excluded = json.loads((RUN/'excluded-pids.json').read_text())
    assert os.getpid() not in excluded
    for pid in excluded:
        os.kill(pid, 0)
    REPORT['identity'] = dict(pid=os.getpid(), profile=mw.pm.name,
        window_title=mw.windowTitle(), collection_inside_disposable_base=True,
        sync='disabled-and-disconnected', excluded_pids=excluded,
        instance_key_fingerprint=IDENTITY['single_instance_key_fingerprint'])
    installed=RUN/'addons21/home_dashboard_overhaul'
    if installed.exists():
        with zipfile.ZipFile(OUT/'source/candidate.ankiaddon') as z:
            assert all((installed/n).read_bytes()==z.read(n) for n in z.namelist())
        REPORT['identity']['candidate_byte_parity']=True


def later(ms, fn):
    def safe():
        try:
            fn()
        except Exception:
            REPORT['status'] = 'error'
            REPORT['error'] = traceback.format_exc()
            write_report()
    QTimer.singleShot(ms, safe)


def seed():
    guard()
    if mw.col.db.scalar('SELECT count(*) FROM cards'):
        assert (RUN/'demo-seeded.json').exists(), 'Unexpected collection data'
        REPORT['fixture'] = json.loads((RUN/'demo-seeded.json').read_text())
        return
    rng = random.Random(808247776)
    # Collection history and scheduler origin belong only to this disposable demo.
    mw.col.crt = int((datetime.now()-timedelta(days=365)).replace(hour=4, minute=0, second=0, microsecond=0).timestamp())
    mw.col.sched.reset()
    parent = mw.col.decks.id('Study Plan')
    decks = [mw.col.decks.id('Study Plan::'+s) for s in ('Core Concepts', 'Practice Review', 'Daily Recall')]
    model = mw.col.models.current()
    requests = []
    for i in range(1200):
        n = mw.col.new_note(model)
        n.fields[0] = 'Practice concept {:04d}'.format(i+1)
        n.fields[1] = 'A sample answer for demonstration.'
        requests.append(AddNoteRequest(note=n, deck_id=decks[i % 3]))
    mw.col.add_notes(requests)
    ids = mw.col.db.list('SELECT id FROM cards ORDER BY id')
    cutoff = mw.col.sched.day_cutoff
    today = datetime.fromtimestamp(cutoff-86400).date()
    # Creation-time edits can leave backend timing cached during fixture setup.
    day = (today-datetime.fromtimestamp(mw.col.crt).date()).days
    logs=[]
    reviewed_ids=set()
    for ago in range(240, -1, -1):
        d=today-timedelta(days=ago)
        count=186 if ago == 0 else (0 if rng.random()<0.13 else rng.randint(45,220))
        # Reviews take place before today's capture; historical sessions vary.
        start=int(datetime.combine(d, datetime.min.time()).replace(hour=10).timestamp()*1000)
        choices=ids[:186] if ago==0 else rng.sample(ids[:260]+ids[280:],count)
        for j,cid in enumerate(choices):
            reviewed_ids.add(cid)
            passed=rng.random()>0.095
            logs.append((start+j*14500, cid, -1, 3 if passed else 1,
                         14 if passed else -60, 12, 2500, rng.randint(5500,10500), 1))
    updates=[]
    for i,cid in enumerate(ids):
        new=260<=i<280
        due=0 if new else day if 186<=i<260 else day+1+(i%35)
        updates.append((0 if new else 2,0 if new else 2,due,0 if new else 14,2500,35 if cid in reviewed_ids else 0,cid))
    def write():
        mw.col.db.executemany('UPDATE cards SET type=?, queue=?, due=?, ivl=?, factor=?, reps=? WHERE id=?', updates)
        mw.col.db.executemany('INSERT INTO revlog (id,cid,usn,ease,ivl,lastIvl,factor,time,type) VALUES (?,?,?,?,?,?,?,?,?)',logs)
    mw.col.db.transact(write)
    mw.col.decks.select(parent)
    mw.col.sched.reset()
    REPORT['fixture']=dict(seed=808247776, scheduling_date=today.isoformat(), cards=len(ids),
                           review_rows=len(logs), completed_today=186, expected_remaining=94,
                           deck_names=['Study Plan::'+s for s in ('Core Concepts','Practice Review','Daily Recall')])
    (RUN/'demo-seeded.json').write_text(json.dumps(REPORT['fixture'],indent=2))


DOM = r'''(()=>{const r=document.querySelector('#hdo-dashboard');
const rect=n=>{if(!n)return null;const b=n.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height}};
return {root:rect(r), view:r?.dataset.hdoCalendarView,theme:r?.dataset.hdoTheme,
metrics:Object.fromEntries([...document.querySelectorAll('[data-hdo-metric]')].map(n=>[n.dataset.hdoMetric,n.textContent.trim()])),
progress:rect(document.querySelector('.hdo-progress-card')),session:rect(document.querySelector('.hdo-session-card')),
yearButton:rect(document.querySelector('[data-hdo-view="year"]')),
calendar:rect(document.querySelector('.hdo-calendar-shell')),
text:document.body.innerText, width:innerWidth,height:innerHeight,
scrollHeight:document.documentElement.scrollHeight,
todayCount:document.querySelectorAll('.is-today').length,
selected:[...document.querySelectorAll('.is-selected')].map(n=>n.dataset.date||n.dataset.hdoDate||''),
verses:[...document.querySelectorAll('.hdo-verse')].map(n=>({text:n.innerText,rect:rect(n)})),
};})()'''


def shot(name):
    guard()
    target=OUT/'raw'/f'{name}.png'
    title=mw.windowTitle()
    def captured(state):
        # Force a native widget paint before requesting the compositor image.
        # QtWebEngine can otherwise retain the prior surface while occluded.
        mw.grab().save(str(RUN/'qt-current-proof.png'),'PNG')
        def work():
            subprocess.run(['/private/tmp/hdo-window-capture',str(os.getpid()),str(target),title],check=True,capture_output=True)
        def done(future):
            try:
                future.result()
                guard()
                pix=QPixmap();pix.loadFromData(target.read_bytes());pix.setDevicePixelRatio(2)
                assert not pix.isNull()
                frame=mw.frameGeometry();origin=mw.deckBrowser.web.mapToGlobal(QPoint(0,0))
                REPORT['captures'][name]=dict(file=f'raw/{name}.png',sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    pixels=[pix.width(),pix.height()],dpr=2,
                    frame=[frame.x(),frame.y(),frame.width(),frame.height()],
                    web_offset=[origin.x()-frame.x(),origin.y()-frame.y()],dom=state,
                    method='ScreenCaptureKit isolated window compositor',scheduling_date=REPORT['fixture']['scheduling_date'])
                if name!='standard':
                    c=mw._home_dashboard_overhaul_controller
                    (OUT/'source'/f'config-{name}.json').write_text(json.dumps(c.config,indent=2))
                REPORT['status']='ready';write_report()
            except Exception:
                REPORT['error']=traceback.format_exc();REPORT['status']='error';write_report()
        mw.taskman.run_in_background(work,done)
    mw.deckBrowser.web.evalWithCallback(DOM,captured)


def configure(theme='Sapphire Glass',view='month',bible=None,name=None):
    guard()
    if mw.state!='deckBrowser':mw.moveToState('deckBrowser')
    c=mw._home_dashboard_overhaul_controller
    config=copy.deepcopy(c.config)
    config['appearance'].update(preset=theme,mode='dark',text_scale=100)
    config['heatmap'].update(calendar_view=view,show_due_forecast=False)
    config['visibility'].update(bible=(view=='year') if bible is None else bible,events=(view=='month'))
    config['bible']['rotation_mode']='manual'
    config['events']['items']=[{'id':'demo-practice-exam','date':REPORT['fixture']['scheduling_date'],'name':'Practice exam','archived':False}]
    c.save_config(config,preferred_verse=config['bible']['quotes'][4])
    width,height=mw.width(),mw.height()
    mw.resize(width+1,height)
    later(80,lambda:mw.resize(width,height))
    later(2000,lambda:shot(name or theme.lower().replace(' ','-')+'-'+view))




def poll():
    command=RUN/'promo-command.json'
    if not command.exists():return
    data=json.loads(command.read_text());command.unlink()
    try:
        guard()
        action=data['action']
        if action=='configure':configure(data['theme'],data['view'],data.get('bible'),data.get('name'))
        elif action=='cycle':
            configure('Sapphire Glass','month',False)
            later(2600,lambda:configure('Emerald','year'))
            later(5200,lambda:configure('Graphite','year'))
            later(7800,lambda:configure('Sapphire Glass','year'))
            later(10400,lambda:configure('Sapphire Glass','month',True,'sapphire-glass-month-verse'))
        elif action=='shot':shot(data['name'])
        elif action=='quit':mw.close()
        else:raise ValueError(action)
    except Exception:
        REPORT['error']=traceback.format_exc();REPORT['status']='error';write_report()


def start():
    guard()
    mw.pm.set_theme(Theme.DARK);theme_manager.apply_style()
    seed()
    mw.resize(1440,936)
    mw.move(40,45)
    mw.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    mw.show();mw.raise_();mw.activateWindow()
    mw.reset()
    REPORT.pop('error',None);REPORT['status']='ready';write_report()
    timer=QTimer(mw);timer.timeout.connect(poll);timer.start(150);TIMERS.append(timer)
    if hasattr(mw,'_home_dashboard_overhaul_controller'):
        later(2000,lambda:configure('Sapphire Glass','year',False,'sapphire-year-study'))
    else:
        later(2500,lambda:shot('standard'))


def opened():later(1500,start)
gui_hooks.profile_did_open.append(opened)
