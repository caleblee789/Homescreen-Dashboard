"""Focused footer captures using the existing isolated native capture harness.

This presentation matrix is not a full release acceptance run. Fixture deck
names and sample facts belong solely to the disposable QA collection.
"""
from dataclasses import replace
import json
import os
import subprocess

from aqt import mw
from aqt.qt import QApplication, QPoint, QTimer
from home_dashboard_overhaul.models import BrowseTarget, BrowseTargetKind, ValueState, VerseContent
from . import _release_probe as release
from . import _probe_base as base

original_gate = base._identity_gate
original_fixture = base._fixture
original_validate = base._validate_dom
original_capture = base._capture
original_config = base._config_for
original_prepare_dom = base._prepare_dom
card_ids = ()


def identity_gate():
    original_gate()
    command = subprocess.check_output(['/bin/ps', '-p', str(os.getpid()), '-o', 'args='], text=True).strip()
    base._require(str(base.RUN_ROOT) in command and base.EXPECTED_PROFILE in command,
                  'process arguments do not match the disposable base and profile')
    base.REPORT['identity']['process_arguments_verified'] = True


def prepare_deck(continuation):
    global card_ids
    identity_gate()
    deck = mw.col.decks.get(1)
    mw.col.decks.rename(deck, 'Anking')
    model = mw.col.models.by_name('Basic')
    for index in range(14):
        note = mw.col.new_note(model)
        note['Front'] = 'Footer capture sample {}'.format(index + 1)
        note['Back'] = 'Disposable presentation fixture'
        mw.col.add_note(note, 1)
    card_ids = tuple(mw.col.db.list('select id from cards order by id limit 3'))
    base.REPORT['presentation_fixture'] = {'deck_name':'Anking', 'card_count':14,
        'source':'existing representative dashboard sample facts',
        'collection':'fresh disposable profile', 'release_validation_claimed':False}
    continuation()


def cases():
    rows = []
    def add(case_id, view='year', theme='Graphite', mode='dark', state='event', narrow=False):
        item = release._production_case(case_id, view=view, theme=theme, mode=mode,
            palette={'Sapphire Glass':'Sapphire','Graphite':'Plum','Emerald':'Emerald','High Contrast':'Cyan'}[theme],
            special='bible-disabled' if state in {'no-verse','empty-no-verse'} else '',
            layout='intermediate' if narrow else 'wide',
            container_width=1040 if narrow else None,
            tags=('focused-footer','Anking',state))
        item['footer_state'] = state
        rows.append(item)
    add('MONTH-EVENT', 'month', 'Sapphire Glass')
    add('MONTH-EMPTY', 'month', 'Sapphire Glass', state='empty')
    add('YEAR-EVENT')
    add('YEAR-EMPTY', state='empty')
    for theme in ['Sapphire Glass','Graphite','Emerald','High Contrast']:
        for mode in ['dark','light']:
            if theme == 'Graphite' and mode == 'dark':
                continue
            add('YEAR-{}-{}'.format(theme.replace(' ','-').upper(), mode.upper()),theme=theme,mode=mode)
    for view in ['month','year']:
        add(view.upper()+'-NO-VERSE', view=view, state='no-verse')
        add(view.upper()+'-NARROW', view=view, narrow=True)
        add(view.upper()+'-LONG', view=view, state='long')
    add('YEAR-EMPTY-NO-VERSE',state='empty-no-verse')
    selected = os.environ.get('HDO_FOOTER_CAPTURE_IDS', '').split(',')
    return [row for row in rows if row['id'] in selected] if selected != [''] else rows


def fixture(case):
    snapshot = original_fixture(case)
    state = case.get('footer_state')
    events = tuple(snapshot.facts.events.value or ())
    if state in {'empty','empty-no-verse'}:
        events = ()
    elif state == 'long':
        events = tuple(replace(item, name='Comprehensive Pediatric NBME Readiness Assessment and Long-Range Study Planning Session') for item in events)
        # Reuse a complete verse from the dashboard-owned bundled library.
        if case['view'] == 'year':
            raw = json.loads((base.ADDON_ROOT / 'default_verses.json').read_text())
            quote = next(value for value in raw['quote'] if 'Philippians 4:6' in value)
            body, reference = quote.split('<br>- ', 1)
            snapshot = replace(snapshot, verse=VerseContent(body.strip(), reference.strip()))
    days = {}
    for iso, day in snapshot.facts.days.items():
        target = BrowseTarget(BrowseTargetKind.MOST_MISSED, 'cid:'+','.join(map(str,card_ids)), True, card_ids)
        days[iso] = replace(day,
            events=ValueState.available(tuple(item for item in events if item.date == iso)),
            most_missed_target=target if iso == base.REFERENCE_DATE else day.most_missed_target)
    return replace(snapshot, facts=replace(snapshot.facts, days=days, events=ValueState.available(events)))


def start_matrix():
    base._cases = cases()
    base._case_index = 0
    base.REPORT['production_matrix'] = {'case_ids':[c['id'] for c in base._cases],
        'case_count':len(base._cases), 'host':'actual isolated Anki Deck Browser',
        'renderer':'byte-matched installed production renderer', 'ui_scale_percent':100}
    base.REPORT['authority'] = 'focused-native-footer-presentation'
    base.REPORT['release_validation_claimed'] = False
    base._write_report()
    QTimer.singleShot(200, base._next_case)


def target_frame(case):
    available = base._qa_screen().availableGeometry()
    return min(1120 if case.get('container_width') else 1280, available.width()), min(900, available.height())


base.DOM_REPORT_SCRIPT = base.DOM_REPORT_SCRIPT.replace('ready:true,', '''ready:true,
    nativeDeckNames:Array.from(document.querySelectorAll('a.deck')).map(n=>n.textContent.trim()),
    dateGroup:rect(q('.hdo-selected-date-line')),
    dateActions:rect(q('.hdo-context-actions')),
    footerContext:rect(q('.hdo-calendar-context')),
    footerContent:rect(q('.hdo-calendar-footer-content')),
    footerVerse:rect(q('.hdo-calendar-footer-content > .hdo-bible-card')),
    footerDivider:q('.hdo-calendar-footer-content > .hdo-bible-card') ? {
      vertical:parseFloat(getComputedStyle(bible).borderInlineStartWidth),
      horizontal:parseFloat(getComputedStyle(bible).borderBlockStartWidth),
      padding:parseFloat(getComputedStyle(bible).paddingInlineStart)
    } : null,
    footerBadge:rect(q('.hdo-date-state-chip')),
    footerButtons:qa('.hdo-context-action,.hdo-event-edit').filter(visible).map(n=>({
      label:n.textContent.trim(),rect:rect(n),background:getComputedStyle(n).backgroundColor,border:getComputedStyle(n).borderColor
    })),
    footerEvent:rect(q('.hdo-event-heading')),
    footerEdit:rect(q('.hdo-event-edit')),
    footerMeta:rect(q('.hdo-event-meta')),
    footerWrapped:!!q('.hdo-event-row--wrapped'),
    footerEventText:q('.hdo-event-title')?.textContent || '',
    footerEmpty:q('.hdo-event-empty')?.textContent || '',
''')


def validate(case, state):
    original_validate(case,state)
    base._require(state.get('nativeDeckNames') == ['Anking'], 'deck list must contain only Anking')
    buttons = state['footerButtons']
    base._require([b['label'] for b in buttons[:2]] == ['Reviewed cards','Most missed'], 'date actions are incomplete')
    base._require(all(abs(b['rect']['height']-28) < .1 for b in buttons), 'footer actions are not 28 CSS px')
    base._require(buttons[0]['background'] == buttons[1]['background'] and buttons[0]['border'] == buttons[1]['border'], 'Reviewed cards does not share the neutral button surface')
    base._require(abs(state['footerBadge']['height']-21) < .1, 'status badge is not distinct from buttons')
    if case['view'] == 'year':
        base._require(abs(state['dateGroup']['left']-state['dateActions']['left']) < .1, 'date actions drifted')
        base._require(state['dateActions']['top'] > state['dateGroup']['bottom'], 'date actions do not follow date')
        if state['footerVerse']:
            divider = state['footerDivider']
            stacked = bool(case.get('container_width'))
            base._require(divider['vertical'] == (0 if stacked else 1) and divider['horizontal'] == (1 if stacked else 0), 'divider orientation is incorrect')
            if not stacked:
                base._require(abs(state['footerVerse']['left']-state['footerContext']['right']-18) < 1, 'left divider spacing is not 18px')
                base._require(divider['padding'] == 18, 'right divider spacing is not 18px')
                base._require(abs(state['footerVerse']['top']-state['dateGroup']['top']) < 1, 'verse is not top aligned')
    else:
        base._require(state['footerDivider'] is None, 'Month has a footer divider')
    if case['footer_state'] in {'empty','empty-no-verse'}:
        base._require(state['footerEdit'] is None and state['footerEvent'] is None and state['footerMeta'] is None, 'empty state has event placeholders')
        base._require(state['footerEmpty'] == 'No upcoming events', 'incorrect empty context')
    elif state['footerWrapped']:
        base._require(state['footerEdit']['top'] >= state['footerMeta']['bottom'] + 3, 'wrapped Edit is not below metadata')
        base._require(abs(state['footerEdit']['left']-state['footerMeta']['left']) < .1, 'wrapped Edit is not aligned with event text')
    else:
        base._require(abs(state['footerEdit']['top']-state['footerEvent']['top']) < .1, 'Edit is not vertically aligned')
        base._require(abs(state['footerEdit']['left']-state['footerEvent']['right']-8) < 1, 'Edit is detached from its title')


def capture(case,state):
    frame = mw.frameGeometry()
    origin = mw.deckBrowser.web.mapToGlobal(QPoint(0,0))
    state['nativeWebOffsetInFrame'] = {'x':origin.x()-frame.x(),'y':origin.y()-frame.y()}
    original_capture(case,state)


def prepare_dom(case, callback):
    def settle():
        mw.deckBrowser.web.eval('window.scrollTo(0,0)')
        QTimer.singleShot(600,callback)
    original_prepare_dom(case,settle)


def finish():
    try:
        identity_gate()
        base._require(set(base.REPORT['captures']) == {c['id'] for c in cases()}, 'footer matrix is incomplete')
        base.REPORT.update(status='passed', capture_completion_status='complete')
        base._write_report()
        QTimer.singleShot(450, QApplication.instance().quit)
    except Exception as exc:
        base._error('footer-finish',exc)


base._identity_gate = identity_gate
base._run_multi_deck_smoke = prepare_deck
base._start_case_matrix = start_matrix
base._target_frame = target_frame
base._fixture = fixture
base._validate_dom = validate
base._capture = capture
base._prepare_dom = prepare_dom
base._finish_stage = finish
