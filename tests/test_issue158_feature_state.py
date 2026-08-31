"""Regressões da issue #158: feature.json é estado local do Spec Kit."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FEATURE_STATE = ROOT / ".specify" / "feature.json"
FEATURE_RELATIVE = ".specify/feature.json"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _working_tree_snapshot() -> tuple[str, str]:
    status = _git("status", "--short", "--untracked-files=all")
    diff = _git("diff", "--name-only")
    return status.stdout, diff.stdout


def _assert_local_state_did_not_change(snapshot: tuple[str, str]) -> None:
    assert _working_tree_snapshot() == snapshot


def test_feature_json_is_not_tracked_but_remains_ignored() -> None:
    tracked = _git("ls-files", "--error-unmatch", FEATURE_RELATIVE)
    assert tracked.returncode != 0, "feature.json não pode voltar ao índice do Git"

    ignored = _git("check-ignore", "--no-index", "--quiet", FEATURE_RELATIVE)
    assert ignored.returncode == 0, ".specify/.gitignore deve ignorar feature.json"


def test_local_feature_state_can_be_created_and_edited_without_diff() -> None:
    original = FEATURE_STATE.read_bytes() if FEATURE_STATE.exists() else None
    snapshot = _working_tree_snapshot()
    try:
        FEATURE_STATE.write_text(
            '{"feature_directory":"specs/local-only"}\n',
            encoding="utf-8",
        )
        _assert_local_state_did_not_change(snapshot)

        FEATURE_STATE.write_text(
            '{"feature_directory":"specs/another-local-only"}\n',
            encoding="utf-8",
        )
        _assert_local_state_did_not_change(snapshot)
    finally:
        if original is None:
            FEATURE_STATE.unlink(missing_ok=True)
        else:
            FEATURE_STATE.write_bytes(original)


def test_bulk_git_add_does_not_offer_ignored_feature_state() -> None:
    original = FEATURE_STATE.read_bytes() if FEATURE_STATE.exists() else None
    snapshot = _working_tree_snapshot()
    try:
        FEATURE_STATE.write_text(
            '{"feature_directory":"specs/not-a-commit"}\n',
            encoding="utf-8",
        )
        staged_preview = _git("add", "--dry-run", "--all")
        assert FEATURE_RELATIVE not in staged_preview.stdout
        assert FEATURE_RELATIVE not in staged_preview.stderr
    finally:
        if original is None:
            FEATURE_STATE.unlink(missing_ok=True)
        else:
            FEATURE_STATE.write_bytes(original)

    _assert_local_state_did_not_change(snapshot)
