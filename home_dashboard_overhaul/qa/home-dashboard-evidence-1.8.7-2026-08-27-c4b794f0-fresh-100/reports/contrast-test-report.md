# Contrast test report

Status: **PASSED**

Passed 582 of 582 gated pairs; failed 0. The lowest passing ratio was 3.006:1.

| Check family | Pairs | Result |
|---|---:|---|
| High Contrast primary text | 6 | PASS |
| calendar footer text | 24 | PASS |
| complete heat date text | 48 | PASS |
| empty past date text | 8 | PASS |
| event marker on completion heat | 48 | PASS |
| event marker on reviews due | 24 | PASS |
| future date text | 8 | PASS |
| important control boundary | 8 | PASS |
| interface text | 72 | PASS |
| out-of-month date text | 8 | PASS |
| primary button text | 24 | PASS |
| reviews due bottom marker | 24 | PASS |
| reviews due date text | 24 | PASS |
| secondary control text | 24 | PASS |
| selected control boundary | 8 | PASS |
| selected outline on completion heat | 48 | PASS |
| selected outline on future date | 8 | PASS |
| selected outline on reviews due | 24 | PASS |
| semantic metric text | 64 | PASS |
| today ring on completion heat | 48 | PASS |
| today ring on future date | 8 | PASS |
| today ring on reviews due | 24 | PASS |

The layered calendar checks model the rendered state: data fill first, then the one-pixel surface halo and selected/today ring, or the gold event fill with text-primary outline and surface halo.

Default and restrained accent-border ratios are retained as advisory measurements because neither token is the sole focus or calendar-selection indicator. Gated important boundaries use `ui-border-strong` or the independent focus/state rings and clear 3:1.
