# Changelog of aisc-report-plugin-interface

## 2026-10-14: review pass (branch pass/report-2026-10-13)

- Tests only, no library change: retired the grep tests over docstrings and comments
  (`test_p2r2_english_only.py`, the `x-aisc-prose` docstring check, the vera-name grep) and three
  duplicate pins (import probe, fixture inventory, `ToolRun.target` field position). README no longer
  lists them.
- Check: `uv run --extra dev pytest -q` (147 passed).
