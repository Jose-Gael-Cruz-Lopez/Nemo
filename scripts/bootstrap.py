"""Create or repair private local settings without disclosing existing settings.

This script deliberately uses only the standard library, so it can run before
the application's dependencies are installed. It edits only the local operator
token; sponsor credentials and other settings are preserved verbatim.
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN_NAME = "REEFTRACE_LOCAL_TOKEN"
_TOKEN_LINE = re.compile(
    r"^(?P<head>[ \t]*(?:export[ \t]+)?REEFTRACE_LOCAL_TOKEN)(?P<tail>.*)$"
)
_ENV_ASSIGNMENT = re.compile(r"^[ \t]*(?:export[ \t]+)?[A-Za-z_][A-Za-z_0-9]*[ \t]*=[ \t]*(.*)$")


@dataclass(frozen=True)
class BootstrapResult:
    env_path: Path
    env_created: bool
    token_created: bool


def _line_parts(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def _value_parts(value: str) -> tuple[bool, str, str]:
    """Return blankness, the quote wrapper, and an unchanged comment suffix."""
    if not value or value.isspace():
        return True, "", ""
    if value.startswith("#"):
        return True, "", " " + value
    if value[0] not in "\"'":
        comment = re.search(r"[ \t]+#", value)
        return False, "", value[comment.start():] if comment else ""
    quote = value[0]
    escaped = False
    for index, character in enumerate(value[1:], start=1):
        if character == quote and not escaped:
            suffix = value[index + 1:]
            if suffix.strip() and not suffix.lstrip().startswith("#"):
                raise ValueError("The local token has text after its closing quote; fix .env first.")
            return not value[1:index].strip(), quote, suffix
        if character == "\\" and not escaped:
            escaped = True
        else:
            escaped = False
    raise ValueError("The local token has an unclosed or multiline quote; fix .env first.")


def _closing_quote(text: str, quote: str) -> bool:
    escaped = False
    for character in text:
        if character == quote and not escaped:
            return True
        if character == "\\" and not escaped:
            escaped = True
        else:
            escaped = False
    return False


def _with_token(contents: str, *, force_new: bool = False) -> tuple[str, bool]:
    lines = contents.splitlines(keepends=True)
    matches: list[tuple[int, re.Match[str], str]] = []
    foreign_quote = ""
    for index, line in enumerate(lines):
        text, newline = _line_parts(line)
        if foreign_quote:
            if _closing_quote(text, foreign_quote):
                foreign_quote = ""
            continue
        match = _TOKEN_LINE.match(text)
        if match and (not match["tail"] or match["tail"][0] in " \t=#"):
            matches.append((index, match, newline))
        elif (assignment := _ENV_ASSIGNMENT.match(text)):
            value = assignment[1]
            if value and value[0] in "\"'" and not _closing_quote(value[1:], value[0]):
                foreign_quote = value[0]
    if foreign_quote:
        raise ValueError("An environment value has an unclosed quote; fix .env first.")
    if len(matches) > 1:
        raise ValueError("Multiple local token assignments exist; keep exactly one in .env first.")
    if not matches:
        newline = "\r\n" if "\r\n" in contents else "\n"
        separator = "" if not contents or contents.endswith(("\n", "\r")) else newline
        token = secrets.token_urlsafe(32)
        return contents + separator + TOKEN_NAME + "=" + token + newline, True

    index, match, newline = matches[0]
    tail = match["tail"]
    assignment = re.fullmatch(r"(?P<before>[ \t]*)=(?P<after>[ \t]*)(?P<value>.*)", tail)
    if assignment:
        blank, quote, suffix = _value_parts(assignment["value"])
        if not blank and not force_new:
            return contents, False
        prefix = match["head"] + assignment["before"] + "=" + assignment["after"]
        token = secrets.token_urlsafe(32)
        lines[index] = prefix + quote + token + quote + suffix + newline
    elif not tail.strip() or tail.lstrip().startswith("#"):
        # python-dotenv treats a bare key as unset; supply its assignment.
        token = secrets.token_urlsafe(32)
        suffix = tail if not tail.startswith("#") else " " + tail
        lines[index] = match["head"] + "=" + token + suffix + newline
    else:
        raise ValueError("The local token assignment is malformed; fix .env first.")
    return "".join(lines), True


def _atomic_write(target: Path, contents: bytes, expected: bytes | None) -> None:
    """Write privately, without exposing a partial file or clobbering creation."""
    descriptor, temporary_name = tempfile.mkstemp(prefix=".reeftrace-env-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if expected is None:
            # A concurrent bootstrap cannot replace the first complete file.
            os.link(temporary, target)
        else:
            if target.is_symlink() or target.read_bytes() != expected:
                raise ValueError(".env changed during setup; rerun bootstrap after saving it.")
            os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def bootstrap(root: Path | str = ROOT) -> BootstrapResult:
    """Ensure one nonblank local token, preserving every other .env setting.

    Existing nonblank tokens are never rotated. Duplicate or ambiguous token
    declarations fail before writing. Created/repaired files have mode 0600;
    a pre-existing file that needs no changes is left entirely untouched.
    """
    root = Path(root).resolve()
    target = root / ".env"
    if target.is_symlink():
        raise ValueError(".env is a symbolic link; set up its local token explicitly first.")
    exists = target.exists()
    original = target.read_bytes() if exists else (root / ".env.example").read_bytes()
    updated, token_created = _with_token(original.decode("utf-8"), force_new=not exists)
    if not exists or token_created:
        _atomic_write(target, updated.encode("utf-8"), original if exists else None)
    (root / "data" / "local").mkdir(parents=True, exist_ok=True)
    return BootstrapResult(target, env_created=not exists, token_created=token_created)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository directory")
    args = parser.parse_args(argv)
    try:
        result = bootstrap(args.root)
    except (OSError, ValueError) as error:
        print("Local setup failed: " + str(error), file=sys.stderr)
        return 1
    if result.env_created:
        print("Created private .env with a new local operator token.")
    elif result.token_created:
        print("Added a private local operator token; all other .env settings were preserved.")
    else:
        print(".env already has a local operator token; left unchanged.")
    print("Read REEFTRACE_LOCAL_TOKEN locally and enter it in the dashboard; do not publish it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
