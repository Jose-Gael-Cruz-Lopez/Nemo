import os
import runpy
import stat
from pathlib import Path

import pytest

from scripts import bootstrap as setup


@pytest.fixture
def root(tmp_path):
    (tmp_path / ".env.example").write_text(
        "# Setup\nREEFTRACE_LOCAL_TOKEN=\nGEMINI_ENABLED=false\nPHOTON_ENABLED=false\n"
    )
    return tmp_path


def test_new_env_is_private_and_import_does_not_execute(root, monkeypatch, capsys):
    monkeypatch.chdir(root)
    runpy.run_path(str(Path(setup.__file__)))
    assert not (root / ".env").exists()
    assert not (root / "data").exists()
    result = setup.bootstrap(root)
    assert result.env_created and result.token_created
    contents = (root / ".env").read_text()
    assert "REEFTRACE_LOCAL_TOKEN=\n" not in contents
    assert "GEMINI_ENABLED=false\nPHOTON_ENABLED=false\n" in contents
    assert (root / "data/local").is_dir()
    if os.name != "nt":
        assert stat.S_IMODE((root / ".env").stat().st_mode) == 0o600
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("assignment", [
    "REEFTRACE_LOCAL_TOKEN=",
    "REEFTRACE_LOCAL_TOKEN=   ",
    "REEFTRACE_LOCAL_TOKEN= # keep this comment",
    "export REEFTRACE_LOCAL_TOKEN = '' # keep this comment",
    'REEFTRACE_LOCAL_TOKEN=""',
    'REEFTRACE_LOCAL_TOKEN="   " # keep this comment',
    "REEFTRACE_LOCAL_TOKEN",
])
def test_repair_blank_preserves_every_other_setting(root, monkeypatch, assignment):
    monkeypatch.setattr(setup.secrets, "token_urlsafe", lambda size: "new-local-token")
    before = "# credentials must survive\nGEMINI_API_KEY=private-chalk-value\n"
    after = "\nPHOTON_API_KEY='private-photon-value'\nUSER_SETTING=do-not-change\n"
    (root / ".env").write_text(before + assignment + after)
    result = setup.bootstrap(root)
    assert not result.env_created and result.token_created
    contents = (root / ".env").read_text()
    assert contents.startswith(before) and contents.endswith(after)
    assert "new-local-token" in contents
    if "# keep this comment" in assignment:
        assert "# keep this comment" in contents
    if os.name != "nt":
        assert stat.S_IMODE((root / ".env").stat().st_mode) == 0o600
    assert not list(root.glob(".reeftrace-env-*"))


def test_missing_token_appends_without_rewriting_crlf_or_last_line(root, monkeypatch):
    monkeypatch.setattr(setup.secrets, "token_urlsafe", lambda size: "new-local-token")
    original = b"# windows settings\r\nGEMINI_API_KEY=keep\r\nUSER_SETTING=last"
    (root / ".env").write_bytes(original)
    setup.bootstrap(root)
    assert (root / ".env").read_bytes() == (
        original + b"\r\nREEFTRACE_LOCAL_TOKEN=new-local-token\r\n"
    )


@pytest.mark.parametrize("assignment", [
    "REEFTRACE_LOCAL_TOKEN=existing-token # preserved",
    "export REEFTRACE_LOCAL_TOKEN='existing-token' # preserved",
    'REEFTRACE_LOCAL_TOKEN="existing-token"',
])
def test_nonblank_token_and_file_metadata_are_untouched(root, monkeypatch, assignment):
    original = "GEMINI_API_KEY=keep\n" + assignment + "\nPHOTON_API_KEY=keep\n"
    target = root / ".env"
    target.write_text(original)
    before = target.stat()
    monkeypatch.setattr(setup.secrets, "token_urlsafe", lambda size: pytest.fail("token rotated"))
    result = setup.bootstrap(root)
    assert not result.env_created and not result.token_created
    assert target.read_text() == original
    after = target.stat()
    assert (after.st_ino, after.st_mode, after.st_mtime_ns) == (
        before.st_ino, before.st_mode, before.st_mtime_ns
    )


@pytest.mark.parametrize("assignment", [
    "REEFTRACE_LOCAL_TOKEN=\nREEFTRACE_LOCAL_TOKEN=existing",
    'REEFTRACE_LOCAL_TOKEN="unclosed',
    "REEFTRACE_LOCAL_TOKEN='' trailing-text",
    "REEFTRACE_LOCAL_TOKEN unexpected-text",
])
def test_ambiguous_assignment_fails_without_touching_env(root, assignment):
    original = "GEMINI_API_KEY=private-value\n" + assignment + "\n"
    target = root / ".env"
    target.write_text(original)
    with pytest.raises(ValueError):
        setup.bootstrap(root)
    assert target.read_text() == original
    assert not (root / "data").exists()
    assert not list(root.glob(".reeftrace-env-*"))


def test_console_output_never_discloses_generated_or_existing_secrets(root, monkeypatch, capsys):
    monkeypatch.setattr(setup.secrets, "token_urlsafe", lambda size: "private-generated-token")
    (root / ".env").write_text(
        "REEFTRACE_LOCAL_TOKEN=\nGEMINI_API_KEY=private-chalk-key\n"
    )
    assert setup.main(["--root", str(root)]) == 0
    assert setup.main(["--root", str(root)]) == 0
    output = capsys.readouterr()
    assert "private-generated-token" not in output.out + output.err
    assert "private-chalk-key" not in output.out + output.err


def test_concurrent_change_does_not_get_overwritten(root, monkeypatch):
    target = root / ".env"
    target.write_text("REEFTRACE_LOCAL_TOKEN=\nGEMINI_API_KEY=keep\n")
    original_write = setup._atomic_write

    def edit_before_replace(path, contents, expected):
        path.write_text("REEFTRACE_LOCAL_TOKEN=human-saved-token\nGEMINI_API_KEY=keep\n")
        return original_write(path, contents, expected)

    monkeypatch.setattr(setup, "_atomic_write", edit_before_replace)
    with pytest.raises(ValueError, match="changed during setup"):
        setup.bootstrap(root)
    assert "human-saved-token" in target.read_text()
    assert not list(root.glob(".reeftrace-env-*"))


def test_token_like_text_inside_another_multiline_value_is_not_modified(root, monkeypatch):
    monkeypatch.setattr(setup.secrets, "token_urlsafe", lambda size: "new-local-token")
    original = "PHOTON_API_KEY='multiline\nREEFTRACE_LOCAL_TOKEN=keep-this-text\nend'\n"
    (root / ".env").write_text(original)
    setup.bootstrap(root)
    assert (root / ".env").read_text() == original + "REEFTRACE_LOCAL_TOKEN=new-local-token\n"


def test_unclosed_other_multiline_value_is_not_appended_into(root):
    original = "PHOTON_API_KEY='unclosed\n"
    (root / ".env").write_text(original)
    with pytest.raises(ValueError, match="unclosed quote"):
        setup.bootstrap(root)
    assert (root / ".env").read_text() == original


def test_env_symlink_is_not_followed_or_replaced(root):
    external = root / "existing-settings"
    external.write_text("REEFTRACE_LOCAL_TOKEN=\n")
    (root / ".env").symlink_to(external)
    with pytest.raises(ValueError, match="symbolic link"):
        setup.bootstrap(root)
    assert external.read_text() == "REEFTRACE_LOCAL_TOKEN=\n"
    assert (root / ".env").is_symlink()
