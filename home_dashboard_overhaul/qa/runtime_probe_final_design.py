"""Focused final-design capture adapter for the existing isolated Deck Browser harness.

Install beside _probe_base.py and _fixtures.py only in a helper-created QA base.
The production candidate remains byte-identical to its archive.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
from aqt import gui_hooks, mw
from aqt.qt import QApplication, QTimer
from home_dashboard_overhaul.models import ValueState, VerseContent
from . import _probe_base as base
from ._fixtures import sample_snapshot

base.ENABLED = str(base.RUN_ROOT).startswith('/private/tmp/anki-release-qa.') and base.EXPECTED_PROFILE.startswith('Codex QA HDO Full Screen ')
base.REFERENCE_DATE = '2026-08-17'
base.OUTPUT_ROOT = base.RUN_ROOT / 'final-design-fullscreen'
base.CAPTURE_ROOT = base.OUTPUT_ROOT / 'raw-native'
base.REPORT_PATH = base.OUTPUT_ROOT / ('runtime-' + base.STAGE + '.json')
base.REPORT = {'status':'running','captures':{},'errors':[], 'native_only':True, 'release_acceptance_claimed':False}
original_gate = base._identity_gate

def candidate_identity():
    marker=json.loads(base.RUN_MARKER.read_text())
    path=Path(marker['candidate'])
    base._require(base._sha256(path)==base.EXPECTED_SHA256,'candidate hash changed')
    base._require(os.environ.get('ANKI_SINGLE_INSTANCE_KEY')==base.EXPECTED_INSTANCE_KEY,'instance key mismatch')
    with zipfile.ZipFile(path) as z:
        files=[n for n in z.namelist() if not n.endswith('/')]
        for name in files:
            base._require(hashlib.sha256(z.read(name)).hexdigest()==base._sha256(base.ADDON_ROOT/name),'installed member differs: '+name)
    return {'candidate':str(path),'candidate_sha256':base.EXPECTED_SHA256,'member_count':len(files),'installed_member_parity':'passed'}

def gate():
    original_gate()
    cmd=subprocess.check_output(['/bin/ps','-p',str(os.getpid()),'-o','args='],text=True)
    base._require(str(base.RUN_ROOT) in cmd and base.EXPECTED_PROFILE in cmd,'disposable process arguments mismatch')
    base.REPORT['identity']['process_arguments_verified']=True
    base.REPORT['identity']['anki_version']=json.loads(base.RUN_MARKER.read_text())['anki_version']

def fit_fullscreen(case,done,attempt=0):
    if not mw.isFullScreen():
        mw.showFullScreen()
    QApplication.processEvents()
    def check():
        screen=mw.windowHandle().screen()
        frame=mw.frameGeometry()
        geometry=screen.geometry()
        available=screen.availableGeometry()
        fills_screen=any(abs(frame.x()-area.x())<=2 and abs(frame.y()-area.y())<=2 and abs(frame.width()-area.width())<=2 and abs(frame.height()-area.height())<=2 for area in (geometry,available))
        ready=mw.isFullScreen() and fills_screen
        if ready:
            done()
        elif attempt<24:
            fit_fullscreen(case,done,attempt+1)
        else:
            base._error(case['id'],RuntimeError('native Anki full-screen state did not settle: isFullScreen={} frame={} screen={} available={}'.format(mw.isFullScreen(),[frame.x(),frame.y(),frame.width(),frame.height()],[geometry.x(),geometry.y(),geometry.width(),geometry.height()],[available.x(),available.y(),available.width(),available.height()])))
    QTimer.singleShot(350,check)

PALETTES={'Sapphire Glass':['Sapphire','Amethyst','Glacier','Sea Glass'], 'Graphite':['Slate','Steel','Plum','Mint'], 'Emerald':['Emerald','Jade','Moss','Lagoon'], 'High Contrast':['Cyan','Gold','Magenta','Monochrome']}
def cases():
    rows=[]
    for theme,palettes in PALETTES.items():
        for palette in palettes:
            for mode in ['dark','light']:
                for view in ['month','year']:
                    for scale in [100,125]:
                        rows.append(dict(id='-'.join([palette,mode,view,str(scale)]),theme=theme,palette=palette,mode=mode,view=view,width=1440,scale=scale,state='standard',fixture='populated',selected=base.REFERENCE_DATE))
    for view in ['month','year']:
        for scale in [100,125]:
            for state in ['long','empty-verse','legacy-hidden-flags','empty-events','loading']:
                rows.append(dict(id=view+'-'+state+'-'+str(scale),theme='Sapphire Glass',palette='Sapphire',mode='dark',view=view,width=1180 if state=='below-width' else 620 if state.startswith('narrow') else 1440,scale=scale,state=state,fixture='loading' if state=='loading' else 'populated',special='loading-initial' if state=='loading' else '',selected=base.REFERENCE_DATE))
    for c in list(rows):
        if c['state']=='long' or (c['state']=='standard' and c['theme']=='Sapphire Glass' and c['palette']=='Sapphire' and c['mode']=='dark'):
            rows.append(dict(c,id=c['id']+'-bottom',bottom=True))
    if base.STAGE=='restart':
        return [dict(rows[1],id='restart-year')]
    selected=os.environ.get('HDO_FINAL_IDS','')
    return [c for c in rows if c['id'] in selected.split(',')] if selected else rows

def config(case):
    c=base._base_config(case['theme'],case['mode'],case['view'])
    c['appearance']['text_scale']=case['scale']
    c['heatmap']['show_due_forecast']=False
    c['heatmap']['presets_by_theme'][case['theme']]=case['palette']
    state=case['state']
    if state=='legacy-hidden-flags':
        for key in c['visibility']: c['visibility'][key]=False
    return c

def fixture(case):
    s=sample_snapshot(date(2026,8,17))
    if case['state']=='empty-verse': s=replace(s,verse=VerseContent('', ''))
    if case['state']=='empty-events':
        s=replace(s,facts=replace(s.facts,events=ValueState.available(()),days={iso:replace(day,events=ValueState.available(())) for iso,day in s.facts.days.items()}))
    if case['state']=='long':
        events=tuple(replace(e,name='Comprehensive Pediatric NBME Readiness Assessment and Long-Range Study Planning Session') for e in s.facts.events.value)
        s=replace(s,facts=replace(s.facts,events=ValueState.available(events), today=ValueState.available(replace(s.facts.today.value,answers=12486,new_cards_studied=1048)),long_term=ValueState.available(replace(s.facts.long_term.value,lifetime_cards_studied=1082640))),verse=VerseContent('Do not be anxious about anything, but in every situation, by prayer and petition, with thanksgiving, present your requests to God. And the peace of God, which transcends all understanding, will guard your hearts and your minds in Christ Jesus.','Philippians 4:6–7'))
    return s

DOM=r'''(()=>{const r=document.querySelector('#hdo-dashboard');if(!r)return {ready:false};const q=s=>r.querySelector(s),qa=s=>[...r.querySelectorAll(s)],rect=n=>{if(!n)return null;let b=n.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height,right:b.right,bottom:b.bottom}};return {ready:true,root:rect(r),calendar:rect(q('.hdo-calendar-card')),rail:rect(q('.hdo-insight-rail')),cards:qa('.hdo-statistics-card').map(rect),verse:rect(q('.hdo-bible-card')),footerVerse:!!q('.hdo-calendar-footer-content .hdo-bible-card'),context:rect(q('.hdo-calendar-context')),cells:qa('.hdo-calendar-day').length,loading:r.classList.contains('hdo-dashboard--loading'),scale:getComputedStyle(r).getPropertyValue('--hdo-scale'),scrollX:scrollX,viewport:innerWidth,scrollWidth:document.scrollingElement.scrollWidth,clearance:r.dataset.hdoFooterClearance,headlines:qa('.hdo-metric-headline').map(n=>({value:rect(n.querySelector('dd')),label:rect(n.querySelector('dt')),stacked:n.classList.contains('hdo-metric-headline--stacked')})),clipped:qa('.hdo-event-title,.hdo-verse-body,.hdo-context-actions button').filter(n=>n.scrollWidth>n.clientWidth+2&&getComputedStyle(n).overflowX==='hidden').map(n=>n.className)}})()'''

def prepare(case,done):
    js='window.scrollTo('+('1e6' if case['state']=='narrow-right' else '0')+','+('1e6' if case.get('bottom') else '0')+')'
    mw.deckBrowser.web.eval(js)
    QTimer.singleShot(350,done)

def validate(case,s):
    base._require(s.get('ready'),'dashboard missing')
    base._require(abs(s['root']['width']-1160)<1,'fixed width changed')
    if not s['loading']:
        base._require(not s['clipped'],'clipped content')
        for headline in s['headlines']:
            v,l=headline['value'],headline['label']
            base._require(l['y']>=v['bottom']+3 if headline['stacked'] else abs(v['y']+v['height']/2-l['y']-l['height']/2)<1,'headline caption alignment changed')
        cards=s['cards']
        if len(cards)==4:
            base._require(abs(cards[0]['width']-174)<1,'card width changed')
            base._require(abs(cards[0]['y']-cards[1]['y'])<1 and abs(cards[2]['y']-cards[3]['y'])<1,'cards lost paired rows')
            base._require(cards[2]['y']>cards[0]['y'],'cards no longer 2x2')
        if s['calendar']:base._require(s['footerVerse'],'verse escaped footer')
        if s['calendar']:base._require(s['cells']==(42 if case['view']=='month' else 365),'calendar cells changed')
    if case['state']=='narrow-right':base._require(s['scrollX']>400,'right edge unreachable')


def capture(case,state):
    gate()
    screen=mw.windowHandle().screen()
    frame=mw.frameGeometry()
    geometry=screen.geometry()
    available=screen.availableGeometry()
    fills_screen=any(abs(frame.x()-area.x())<=2 and abs(frame.y()-area.y())<=2 and abs(frame.width()-area.width())<=2 and abs(frame.height()-area.height())<=2 for area in (geometry,available))
    base._require(mw.isFullScreen() and fills_screen,'capture window is not native full screen')
    QApplication.processEvents()
    # Capture the owned widget, never pixels from the foreground desktop.
    pix=mw.grab()
    base._require(not pix.isNull(),'null native capture')
    base.CAPTURE_ROOT.mkdir(parents=True,exist_ok=True)
    path=base.CAPTURE_ROOT/(case['id']+'.png')
    base._require(pix.save(str(path),'PNG'),'capture save failed')
    sampled_colors=base._sample_color_count(pix)
    base._require(sampled_colors>=8,'blank native capture: {} sampled colors'.format(sampled_colors))
    base.REPORT['captures'][case['id']]={**case,'file':str(path.relative_to(base.OUTPUT_ROOT)),'sha256':base._sha256(path),'capture_method':'QMainWindow.grab-owned-isolated-window','native_fullscreen':True,'sampled_colors':sampled_colors,'screen_logical_pixels':[geometry.width(),geometry.height()],'available_logical_pixels':[available.width(),available.height()],'window_logical_pixels':[frame.width(),frame.height()],'physical_pixels':[pix.width(),pix.height()],'dom':state}
    base._write_report()

def start():
    gate()
    if base.STAGE=='restart':
        saved=mw.addonManager.getConfig(base._controller.package)
        base._require(saved['heatmap']['calendar_view']=='year','Year view did not persist')
        base.REPORT['persistence']='passed'
    base._cases=cases();base._case_index=0
    base.REPORT['expected_ids']=[c['id'] for c in base._cases]
    base._write_report();base._next_case()

def finish():
    gate()
    base._require(len(base.REPORT['captures'])==len(base._cases),'incomplete matrix')
    c=deepcopy(base._controller.config);c['heatmap']['calendar_view']='year'
    mw.addonManager.writeConfig(base._controller.package,c)
    base.REPORT['status']='passed';base._write_report()
    QTimer.singleShot(200,QApplication.instance().quit)


def interactions():
    import aqt
    from home_dashboard_overhaul.models import BrowseTarget, BrowseTargetKind, DayInsight
    gate()
    controller=base._controller
    result={}
    base.REPORT['interactions']=result
    def fail(exc): base._error('native-interactions',exc)
    def navigation_done(value):
        try:
            base._require(isinstance(value,dict) and all(value.values()),'navigation or keyboard behavior failed: '+str(value))
            result.update(value)
            # Create one real disposable card for the two Browser entry points.
            note=mw.col.new_note(mw.col.models.by_name('Basic'))
            note['Front']='Final dashboard disposable interaction check';note['Back']='QA only'
            mw.col.add_note(note,1)
            card_id=note.card_ids()[0]
            key=controller._key();controller.cache_key=key;controller.selected_date=base.REFERENCE_DATE
            reviewed=BrowseTarget(BrowseTargetKind.REVIEWED,'cid:'+str(card_id),True,(card_id,))
            missed=BrowseTarget(BrowseTargetKind.MOST_MISSED,'cid:'+str(card_id),True,(card_id,))
            controller.browse_target_cache[(key,base.REFERENCE_DATE)]=reviewed
            controller.insight_cache[(key,base.REFERENCE_DATE)]=DayInsight(base.REFERENCE_DATE,missed)
            browser_action('[data-hdo-primary-action]','reviewed_cards',lambda:browser_action('[data-hdo-most-missed]','most_missed',settings_action))
        except Exception as exc:fail(exc)
    def browser_action(selector,name,done):
        def verify():
            try:
                gate()
                browser=aqt.dialogs._dialogs['Browser'][1]
                base._require(browser is not None and browser.isVisible(),name+' Browser did not open')
                result[name]='opened native Browser with disposable card target'
                browser.close()
                QTimer.singleShot(500,done)
            except Exception as exc:fail(exc)
        QTimer.singleShot(1200,verify)
        mw.deckBrowser.web.eval("document.querySelector("+json.dumps(selector)+").click()")
    def settings_action():
        dialog_action('.hdo-settings','settings',event_action)
    def event_action():
        controller.config['events']['items']=[{'id':'fixture-event','name':'Pediatric NBME','date':'2026-08-28','archived':False}]
        dialog_action('.hdo-event-edit','event_edit',done)
    def dialog_action(selector,name,continuation):
        def verify():
            try:
                gate()
                dialog=controller._active_settings_dialog
                base._require(dialog is not None and dialog.isVisible(),name+' Settings did not open')
                if name=='event_edit':
                    editors=[w for w in QApplication.topLevelWidgets() if type(w).__name__=='EventEditDialog' and w.isVisible()]
                    base._require(len(editors)==1,'event editor did not open')
                    editors[0].reject()
                result[name]='native dialog opened'
                dialog.reject()
                QTimer.singleShot(350,continuation)
            except Exception as exc:fail(exc)
        QTimer.singleShot(1600,verify)
        mw.deckBrowser.web.eval("document.querySelector("+json.dumps(selector)+").click()")
    def done():
        try:
            controller.set_calendar_view('year')
            base.REPORT['status']='passed';base._write_report()
            QTimer.singleShot(200,QApplication.instance().quit)
        except Exception as exc:fail(exc)
    script=r'''(()=>{const q=s=>document.querySelector(s),title=()=>q('[data-hdo-calendar-title]').textContent;let checks={};q('[data-hdo-view="month"]').click();checks.month_switch=q('.hdo-calendar-grid').querySelectorAll('.hdo-calendar-day').length===42;let before=title();q('[data-hdo-calendar="previous"]').click();checks.previous=title()!==before;q('[data-hdo-calendar="next"]').click();checks.next=title()===before;let cell=q('.hdo-calendar-day[data-date="2026-08-16"]');cell.click();checks.date_selection=q('[data-hdo-context-date]').textContent.includes('16');cell.focus();cell.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));checks.keyboard_navigation=document.activeElement.dataset.date==='2026-08-17';q('[data-hdo-calendar="today"]').click();checks.today=q('[data-hdo-context-date]').textContent.includes('17');q('[data-hdo-view="year"]').click();checks.year_switch=q('.hdo-calendar-grid').querySelectorAll('.hdo-calendar-day').length===365;checks.shared_footer=!!q('.hdo-calendar-footer-content .hdo-bible-card');return checks;})()'''
    mw.deckBrowser.web.evalWithCallback(script,navigation_done)


base._candidate_install_identity=candidate_identity
base._identity_gate=gate
base._fixture=fixture
base._config_for=config
base._fit_native_frame=fit_fullscreen
base._prepare_dom=prepare
base.DOM_REPORT_SCRIPT=DOM
base._validate_dom=validate
base._capture=capture
base._start_case_matrix=start
base._run_multi_deck_smoke=lambda done:done()
base._finish_stage=interactions if base.STAGE=="restart" else finish
if base.ENABLED:
    gui_hooks.profile_did_open.append(base._profile_opened)
    QTimer.singleShot(1100,base._begin)
