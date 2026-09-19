# Frozen prediction records

Each `PREDICTIONS_<date>.csv` holds SKY scores computed from the
information set available on that date, together with a `.meta.json`
carrying a SHA-256 of the row payload and the date the file was frozen.

The point is falsifiability. A score that is re-tuned after seeing
outcomes proves nothing; a score written down before them can be wrong
in public. When forward returns become available, test against these
files rather than against a re-run — a re-run silently inherits every
input that has been updated since.

`information_set_date` is what the model could see.
`frozen_on` is when the file was written. When they differ, the gap is
the out-of-sample window.

## Records

- **2026-08-20** — SKY v2.3, 249 names, 15 gated. Frozen 2026-09-16,
  before any September price data was observed. The Aug 20 -> Sep 16
  window is therefore a genuine out-of-sample test, though a short one:
  four weeks is mostly noise, and a single macro event (the Sept 15-16
  FOMC) dominates it. Read the result as a sanity check, not a verdict.
