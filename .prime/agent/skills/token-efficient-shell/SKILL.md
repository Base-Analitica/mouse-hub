---
name: token-efficient-shell
description: Use project-local RTK for verbose shell output when a compact summary preserves the needed information; keep exact output and diagnostics unfiltered.
---

# Token-efficient shell

Use `scripts/agent/rtk` explicitly for supported, verbose commands:

- `git status|diff|log`, `rg|grep`, `find`, `ls|tree`
- `pytest`, linters and builds

Do not stack another output filter. Prefer the native command for exact patches, byte-sensitive data, protocol output, or small results. For failures, inspect the tee path printed by RTK before rerunning; it keeps raw failure output under `.tools/rtk/state/tee/`. `scripts/agent/rtk gain` shows local savings. RTK is optional: if unavailable, run the native command.

Setup once per checkout: `scripts/agent/bootstrap-rtk`.
