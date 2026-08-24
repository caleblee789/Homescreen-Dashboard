# Hardcoded-color audit

Status: **PASSED**

Scanned 25 production and active fixture files and classified 289 raw-color matches. Category 6 component hardcoding: **0**.

| Category | Classification | Matches |
|---:|---|---:|
| 1 | Core theme token | 166 |
| 2 | Stable semantic token | 32 |
| 3 | Data visualization token | 63 |
| 4 | Shadow or overlay | 9 |
| 5 | Asset, configuration, or comparison-frame exception | 19 |
| 6 | Unintentional component-level hardcoding | 0 |

Raw product literals are centralized in `themes.py`. Shipped JSON occurrences are the persisted, user-editable custom Bible color default; Qt named-color occurrences are application-palette lookups. Active fixture CSS is scanned, while opaque contact-sheet comparison framing is classified as an outside-viewport exception.

## Classified exceptions

- `config.json:58` — `#1E90FF` — persisted user-configurable custom verse-color default
- `default_verses.json:2` — `#1E90FF` — persisted user-configurable custom verse-color default
- `default_verses.json:358` — `white` — quoted content word; not a rendered color declaration
- `qa/generate_final_release_contact_sheets.py:537` — `#f8fafc` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:538` — `#a8b4c7` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:577` — `#111827` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:594` — `#e5e7eb` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:595` — `#64748b` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:599` — `#172033` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:649` — `#111827` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:670` — `#e5e7eb` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:671` — `#64748b` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:675` — `#172033` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:724` — `#111827` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:741` — `#e5e7eb` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:742` — `#64748b` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:746` — `#172033` — QA-only fixture or comparison framing outside the represented viewport
- `settings.py:256` — `white` — Qt application-palette lookup; not a raw rendered color
- `settings.py:257` — `black` — Qt application-palette lookup; not a raw rendered color
