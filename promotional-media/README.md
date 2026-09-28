# Home Screen Dashboard promotional media

The previous capture inputs, exports, and review evidence were removed. The
rendering and capture tools remain for a future media run; their old package
and image identities are not current evidence.

To prepare fresh inputs, build a new candidate and capture it in a disposable,
sync-disabled Anki profile using the `launch-isolated-anki` workflow. Place the
new PNGs and interaction recording under `raw/` with the names expected by
`timeline.json`, or update that file for the new inputs. The helpers in
`source/` can prepare the isolated run and collect native captures. Never use
the normal Anki profile for this work.

Install `requirements.txt` into an isolated Python environment, then run
`render.py` to create the MP4, GIF, poster, previews, and storyboard. Run
`verify.py` and `review.py` against the regenerated outputs before reuse.

The separate `release-kit/source/` tools can create a new release kit from
fresh captures and a verified candidate. The `poster/` generator likewise
requires new native image inputs. Generated media and reports are intentionally
absent from this cleanup state.
