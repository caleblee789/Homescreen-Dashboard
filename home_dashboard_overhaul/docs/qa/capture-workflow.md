# Capture workflow

The capture system has one operational source of truth:
[`qa/capture_plan.json`](../../qa/capture_plan.json). It declares ordered case
families, semantic case data, named profiles, and contact-sheet ownership. The
pure-Python loader in [`qa/capture_plan.py`](../../qa/capture_plan.py) expands
the axes and fails closed on duplicate IDs, missing stages, unknown groups,
profile drift, or incomplete presentation coverage.

This replaces the previous coordination model in which capture IDs, numeric
totals, profile exclusions, and contact-sheet offsets were repeated in the
release probe, one-off profile helpers, the assembler, and tests. In that
model, inserting or retiring one UI state could leave a helper stale or move
unrelated frames into the wrong positional sheet. The contracts still state
what acceptance requires, while the plan is now the only executable registry
for selection, ordering, counts, and presentation ownership.

Each completed evidence directory is immutable while retained. Create a new
run/output directory for changed UI, validate it completely, and keep only the
newest complete repository-owned capture set when cleanup is explicitly
requested. Never overwrite a partial or completed output in place.

## Changing UI coverage

1. Update the UI surface authority, visual matrix, and capture-evidence contract
   for the new interface. These remain independent acceptance statements; the
   loader checks their axes, IDs, family counts, and stage totals against the
   execution plan.
2. Add, remove, or revise the corresponding family/case in
   `qa/capture_plan.json`. Each case owns a semantic `sheet_group`; sheet order
   and titles live under `presentation.sheet_groups`.
3. Run the plan check:

   ```sh
   python3 home_dashboard_overhaul/qa/capture_plan.py --json
   ```

   Counts are derived. Do not add count constants or positional list slices to
   a probe, helper, assembler, or test.
4. Build a fresh helper in a new directory. The helper embeds the selected
   profile, ordered IDs, plan hash, and expected stage counts:

   ```sh
   python3 home_dashboard_overhaul/qa/prepare_capture_helper.py \
     --profile full \
     --output /private/tmp/hdo-capture-helper-full
   ```

5. Install the exact candidate and helper only in a fresh, sync-disabled,
   identity-gated Anki profile. Run the stages listed in the helper manifest;
   the probe still requires `HDO_RELEASE_RUN_ROOT`, `HDO_RELEASE_PROFILE`,
   `HDO_RELEASE_CANDIDATE_SHA256`, `HDO_RELEASE_INSTANCE_KEY`,
   `HDO_RELEASE_EXCLUDED_PID`, and `HDO_RELEASE_PROBE_STAGE`.
6. Assemble into a new output path. The assembler reads the same plan and
   derives capture order and contact-sheet groups without offsets:

   ```sh
   python3 home_dashboard_overhaul/qa/assemble_release_evidence_1_8_6.py \
     --profile full \
     --run-root /private/tmp/anki-release-qa.EXAMPLE \
     --output /path/to/new/evidence
   ```

## Profiles and focused revision

- `full` is the complete release gate.
- `settings` covers every current Settings page, interaction state, and
  Settings restart state.
- `wide-100` selects cases semantically: wide production layouts, full-width
  Settings at 100% application font, and both relevant restart states. Its
  full-screen adapter contains only window/capture behavior; it does not own a
  second list of UI IDs.

For fast diagnosis or a changed-surface rerun, repeat `--only` when preparing
the helper:

```sh
python3 home_dashboard_overhaul/qa/prepare_capture_helper.py \
  --profile wide-100 \
  --only PROD-MONTH-STABLE \
  --only SET-DIRTY \
  --output /private/tmp/hdo-capture-helper-focused
```

Focused output is diagnostic evidence, not a complete release gate. The final
assembler accepts only a complete named profile with its required initial and
restart reports, exact candidate hash, plan identity, isolation gates, and
exact-once raw capture set.

The assembler has an explicit `--allow-legacy-unversioned-reports` escape hatch
only for reconstructing externally archived 1.8.6 reports created before
runtime reports carried a plan hash. New evidence must use the strict default;
profile-specific evidence can never use the legacy path. Reconstructed output
is labelled `reconstructed-legacy`, not `passed`.

## Extension rules

- Put selection dimensions in the plan as axes or semantic fields (`layout`,
  `width`, `font_percent`, `component`), not in filename parsing.
- Let profiles filter those fields. A new wide case then joins `wide-100`
  automatically; a new narrow case remains outside it automatically.
- Give every new case one presentation group. Empty groups disappear for a
  narrower profile, while the full plan still verifies exact-once coverage.
- Keep fixture creation and UI-specific assertions in the runtime probe. The
  plan owns what to capture; the probe owns how to construct and prove it.
- Never reuse a raw frame unless candidate hash, plan hash, profile, case ID,
  stage, dimensions, and recorded postconditions all match.
