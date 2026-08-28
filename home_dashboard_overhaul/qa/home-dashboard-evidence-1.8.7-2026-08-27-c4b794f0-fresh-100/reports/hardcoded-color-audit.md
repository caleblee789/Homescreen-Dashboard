# Hardcoded-color audit

Status: **PASSED**

Scanned 25 production and active fixture files and classified 521 raw-color matches. Category 6 component hardcoding: **0**.

| Category | Classification | Matches |
|---:|---|---:|
| 1 | Core theme token | 360 |
| 2 | Stable semantic token | 32 |
| 3 | Data visualization token | 99 |
| 4 | Shadow or overlay | 11 |
| 5 | Asset, configuration, or comparison-frame exception | 19 |
| 6 | Unintentional component-level hardcoding | 0 |

Raw product literals are centralized in `themes.py`. Shipped JSON occurrences are the persisted, user-editable custom Bible color default; Qt named-color occurrences are application-palette lookups. Active fixture CSS is scanned, while opaque contact-sheet comparison framing is classified as an outside-viewport exception.

## Classified exceptions

- `config.json:58` — `#1E90FF` — persisted user-configurable custom verse-color default
- `default_verses.json:2` — `#1E90FF` — persisted user-configurable custom verse-color default
- `default_verses.json:358` — `white` — quoted content word; not a rendered color declaration
- `qa/generate_final_release_contact_sheets.py:543` — `#f8fafc` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:544` — `#a8b4c7` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:583` — `#111827` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:600` — `#e5e7eb` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:601` — `#64748b` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:605` — `#172033` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:655` — `#111827` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:676` — `#e5e7eb` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:677` — `#64748b` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:681` — `#172033` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:730` — `#111827` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:747` — `#e5e7eb` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:748` — `#64748b` — QA-only fixture or comparison framing outside the represented viewport
- `qa/generate_final_release_contact_sheets.py:752` — `#172033` — QA-only fixture or comparison framing outside the represented viewport
- `settings.py:271` — `white` — Qt application-palette lookup; not a raw rendered color
- `settings.py:272` — `black` — Qt application-palette lookup; not a raw rendered color
