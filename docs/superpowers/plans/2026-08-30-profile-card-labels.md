# Profile Card Labels and Empty Header Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute task-by-task with the project Spec Kit artifacts and preserve the RED → GREEN cycle.

**Goal:** Implement issues #85 and #86 together as a UI-only change that presents human labels for official profiles and removes the empty card header without changing persistence or state semantics.

**Architecture:** Keep `ProfileStore` and all domain state unchanged. Add a small presentation mapping in `ProfilesPage`, use the original profile key/object for all identity-sensitive callbacks, and compose one title-plus-conditional-badge header instead of the icon/badge placeholder row.

**Tech Stack:** Python 3.10+, PyQt5 5.15.11, pytest, Xvfb, Pillow, existing packaging scripts.

**Spec:** `specs/034-profile-card-labels/spec.md`

## Global Constraints

- Work only in `/home/pedro/.jcode/scratch/issue85-86-profile-cards` on `fix/profile-card-labels-empty-header`.
- Do not modify `mouse_hub/core`, `mouse_hub/platform`, persistence schema, hardware behavior, or dependencies.
- Preserve `profile_cards` internal keys, `active_profile()` semantics, Apply/Edit callbacks, and custom names.
- Use offscreen fakes for tests, regenerate only the three affected screenshot artifacts, and never merge.
- Write repository-facing prose in pt-BR and commits in conventional English.

## File Map

- `app/mouse_hub_app.py`: UI-only display mapping and card header composition.
- `tests/test_issue85_86_profile_cards.py`: focused RED/GREEN contract for labels, identity, states, and geometry.
- `docs/screenshots/5_perfis.png`, `small_perfis.png`, `preview.png`: generated public artifacts.
- `specs/034-profile-card-labels/`: Spec Kit traceability and observed evidence.

## Execution Tasks

1. Confirm the clean worktree and baseline 544-test result.
2. Write focused tests for official labels, custom fallback, original callback identity, no empty header, active badge transitions, and both viewports.
3. Run the focused tests before production edits and record the expected RED.
4. Add the UI-only display mapping and merge the title into a header with a conditionally visible active badge.
5. Run focused GREEN and the existing profile/UI regression tests.
6. Capture twice in temporary directories, compare all 15 files byte-for-byte, then update only the three affected PNGs.
7. Run smoke, compileall, diff-check, package and full suite.
8. Request read-only review, address findings, update Spec Kit evidence, commit, push, open PR with both `Closes` lines, and verify all three real CI checks on final HEAD.

## Requirement Checkpoints

| Requirement | Concrete evidence |
| --- | --- |
| Official labels and custom fallback | Focused title assertions for all four keys and a custom profile. |
| Storage identity preserved | Callback capture plus existing `ProfileStore` and active-profile regressions. |
| No empty header | Layout inspection rejects `ic`, empty visible header labels, and residual structural row. |
| Active state honest | Unknown/active/switch matrix verifies badge visibility and raw key identity. |
| Responsive UI | Parametrized geometry checks at 1050×680 and 760×560. |
| Public artifacts | Two capture runs, 15-file byte comparison, dimensions and bboxes. |
| Delivery gates | Focused/regression/full tests, smoke, compileall, package, diff-check and three real CI checks. |
