"""Assemble focused contact sheets with the existing release sheet renderer."""
from copy import deepcopy
import hashlib
import html
import json
from pathlib import Path
import shutil
import sys

from PIL import Image

OUT = Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent))
from assemble_release_evidence_1_8_7 import make_capture_sheet


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


sources = [json.loads((OUT/name).read_text()) for name in ['isolated-run.json','month-recapture-run.json']]
captures = {}
reports = []
for index, source in enumerate(sources):
    evidence = Path(source['run_root'])/'hdo-release-evidence-1.8.7'
    report_file = evidence/'runtime-report-initial.json'
    report = json.loads(report_file.read_text())
    assert report['status'] == 'passed' and report['release_validation_claimed'] is False
    assert report['identity']['candidate']['installed_member_parity'] == 'passed'
    archived_report = OUT/'native-reports'/('run-{}.json'.format(index+1))
    archived_report.parent.mkdir(exist_ok=True)
    shutil.copyfile(report_file,archived_report)
    reports.append({'file':str(archived_report.relative_to(OUT)),'sha256':digest(archived_report),
                    'run_root':source['run_root'],'pid':report['identity']['pid']})
    for capture_id, entry in report['captures'].items():
        entry = deepcopy(entry)
        original = evidence/entry['file']
        assert digest(original) == entry['sha256']
        entry['source_file'] = str(original)
        entry['source_report'] = str(archived_report.relative_to(OUT))
        captures[capture_id] = entry

(OUT/'captures').mkdir(exist_ok=True)
for capture_id, entry in captures.items():
    original = Path(entry['source_file'])
    target = OUT/'captures'/(capture_id+'.png')
    if entry['capture_method'].startswith('QScreen.grabWindow'):
        # Match the client-area composition from the native QWidget captures.
        # This excludes macOS window chrome; dashboard pixels remain untouched.
        with Image.open(original) as im:
            inset = round(32*entry['device_pixel_ratio'])
            im.crop((0,inset,im.width,im.height)).save(target)
        entry['presentation_crop_top_css_px'] = 32
    else:
        shutil.copyfile(original,target)
    entry['file'] = str(target.relative_to(OUT))
    entry['presentation_sha256'] = digest(target)

captions = {
    'MONTH-EVENT':'Month: date and actions left; event right; verse below stats',
    'MONTH-EMPTY':'Month: one compact row when no event is available',
    'YEAR-EVENT':'Year: left-aligned stack and a visible vertical divider',
    'YEAR-EMPTY':'Year: compact empty status; verse stays in the footer',
    'MONTH-NARROW':'Narrow Month: date/actions and event stack naturally',
    'YEAR-NARROW':'Narrow Year: verse stacks below a horizontal divider',
    'MONTH-LONG':'Long Month title: Edit follows the metadata',
    'YEAR-LONG':'Long Year title and complete verse wrap naturally',
    'MONTH-NO-VERSE':'Month with verse disabled: no reserved verse card',
    'YEAR-NO-VERSE':'Year with verse disabled: no column or divider',
    'YEAR-EMPTY-NO-VERSE':'Year without events or verse: content determines height',
}
for capture_id,entry in captures.items():
    captions.setdefault(capture_id,entry['theme']+' · '+entry['mode']+' · neutral action buttons')

groups = [
    ('01-month-and-year.png','Month and Year · Anking',['MONTH-EVENT','YEAR-EVENT','MONTH-EMPTY','YEAR-EMPTY']),
    ('02-year-dark-themes.png','Year · Dark themes · Anking',['YEAR-SAPPHIRE-GLASS-DARK','YEAR-EVENT','YEAR-EMERALD-DARK','YEAR-HIGH-CONTRAST-DARK']),
    ('03-year-light-themes.png','Year · Light themes · Anking',['YEAR-SAPPHIRE-GLASS-LIGHT','YEAR-GRAPHITE-LIGHT','YEAR-EMERALD-LIGHT','YEAR-HIGH-CONTRAST-LIGHT']),
    ('04-wrapping-and-narrow.png','Wrapping and narrower panels · Anking',['MONTH-LONG','YEAR-LONG','MONTH-NARROW','YEAR-NARROW']),
    ('05-verse-disabled.png','Verse disabled · Anking',['MONTH-NO-VERSE','YEAR-NO-VERSE','YEAR-EMPTY-NO-VERSE']),
]
sheets = []
for filename,title,ids in groups:
    sheets.append(make_capture_sheet(OUT,filename,title,ids,2,(960,660),'full',
        subtitle='Footer refinement · native Anki 26.8.1 · 100% interface scale',captions=captions))

verification = {'status':'passed','scope':'Focused footer presentation; not full release acceptance',
    'capture_count':len(captures),'sheet_count':len(sheets),'candidate_sha256':sources[0]['candidate_sha256'],
    'native_reports':reports,'captures':captures,'contact_sheets':sheets,
    'preview_verification':'preview-verification.json',
    'prelaunch_exclusion_records':['prelaunch-processes.json','month-prelaunch-processes.json'],
    'checks':{'existing_focused_tests':94,'static_asset_tests_after_neutral_button':15,
              'browser_layout_states':44,'month_year_switch_cycles':6,
              'month_event_footer_css_px':captures['MONTH-EVENT']['dom']['footerContent']['height'],
              'month_empty_footer_css_px':captures['MONTH-EMPTY']['dom']['footerContent']['height']}}
(OUT/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')

items=[]
for sheet in sheets:
    items.append('<figure><a href="{f}"><img src="{f}" loading="lazy"></a><figcaption>{t}</figcaption></figure>'.format(f=sheet['file'],t=html.escape(sheet['title'])))
links=[]
for capture_id,entry in captures.items():
    links.append('<li><a href="{}">{}</a> — {}</li>'.format(entry['file'],capture_id,html.escape(captions[capture_id])))
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Updated footer captures · Anking</title><style>body{font:16px/1.5 system-ui;background:#f4f6f9;color:#18212f;max-width:1320px;margin:40px auto;padding:0 24px}h1{font-size:28px}figure{margin:32px 0}img{display:block;width:100%;border-radius:8px}figcaption{margin:10px 0 20px}a{color:#205caa}li{margin:6px 0}</style>
<h1>Updated footer captures · Anking</h1><p>Reviewed cards now shares Most missed’s neutral surface and border. Year uses a visible divider and a left-aligned date, actions, and event stack. Month keeps its standalone verse below statistics.</p>
<p>The Year footer stacks below 660 CSS pixels of calendar content width; its divider becomes horizontal. All captures use 100% interface scale.</p>
'''+''.join(items)+'<h2>Full-size screenshots</h2><ul>'+''.join(links)+'</ul><p>Focused native visual verification; not full release acceptance. <a href="verification.json">Evidence details</a></p></html>')
print(json.dumps({'captures':len(captures),'sheets':[s['file'] for s in sheets],'index':str(OUT/'index.html')},indent=2))
