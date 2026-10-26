#!/usr/bin/env python3
"""Manage one AI-APF block in an explicitly selected AGENTS instruction file.

Examples:
  python3 configure_plan_entry.py status --agents-file /path/to/AGENTS.md
  python3 configure_plan_entry.py enable --agents-file /path/to/AGENTS.md \
      --skill-file /path/to/ai-apf/SKILL.md --dry-run
  python3 configure_plan_entry.py disable --agents-file /path/to/AGENTS.md

This does not install a skill, configure hooks, or verify a Codex host session.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


BEGIN = "<!-- ai-apf:begin -->"
END = "<!-- ai-apf:end -->"


class EntryError(Exception):
    pass


def emit_json(value, stream):
    """Keep JSON usable even when a Windows console cannot encode a path."""
    message = json.dumps(value, ensure_ascii=False, indent=2)
    try:
        message.encode(stream.encoding or "utf-8")
    except UnicodeEncodeError:
        message = json.dumps(value, ensure_ascii=True, indent=2)
    print(message, file=stream)


def selected_path(value):
    """Make the caller's path absolute without following symlinks."""
    return Path(os.path.abspath(os.path.expanduser(value)))


def is_link_or_reparse(path):
    """Reject links and Windows reparse points before touching instruction files.

    Junctions need not be reported by Path.is_symlink(), especially on older
    Python versions. On Windows lstat exposes the reparse-point file attribute.
    """
    try:
        details = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(details.st_mode):
        return True
    if os.name == "nt":
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(getattr(details, "st_file_attributes", 0) & flag)
    return False


def reject_symlinks(path):
    for part in reversed((path, *path.parents)):
        if is_link_or_reparse(part):
            raise EntryError(f"Refusing a symlink or reparse-point target or parent: {part}")


def inspect_target(path):
    if path.name not in {"AGENTS.md", "AGENTS.override.md"}:
        raise EntryError("--agents-file must name AGENTS.md or AGENTS.override.md.")
    reject_symlinks(path)
    if path.exists() and not path.is_file():
        raise EntryError(f"The selected instruction path is not a regular file: {path}")
    if path.name == "AGENTS.md":
        override = path.with_name("AGENTS.override.md")
        if is_link_or_reparse(override):
            raise EntryError(f"A sibling override is a symlink or reparse point; inspect it first: {override}")
        if override.exists() and (not override.is_file() or override.stat().st_size > 0):
            raise EntryError(
                f"AGENTS.md is shadowed by {override}. Select the existing effective "
                "override explicitly after inspecting it; no file was changed."
            )
    return path.read_bytes() if path.exists() else None


def managed_span(text):
    """Return the single complete marker block, including its final line ending."""
    counts = (text.count("ai-apf:begin"), text.count("ai-apf:end"))
    if counts == (0, 0):
        return None
    if counts != (1, 1):
        raise EntryError("Malformed or duplicate AI-APF markers; repair them manually first.")
    start = re.search(r"(?m)^[ \t]*" + re.escape(BEGIN) + r"[ \t]*\r?$", text)
    end = re.search(r"(?m)^[ \t]*" + re.escape(END) + r"[ \t]*\r?$", text)
    if not start or not end or end.start() <= start.end():
        raise EntryError("AI-APF markers must be ordered and on their own complete lines.")
    stop = end.end()
    if text[stop:stop + 1] == "\n":
        stop += 1
    return start.start(), stop


def checked_skill(value):
    if not value:
        raise EntryError("enable requires --skill-file pointing to the actual ai-apf SKILL.md.")
    path = selected_path(value).resolve(strict=True)
    if path.name != "SKILL.md" or not path.is_file():
        raise EntryError(f"--skill-file is not a regular SKILL.md: {path}")
    content = path.read_text(encoding="utf-8")
    header = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|\Z)", content, re.DOTALL)
    if not header or not re.search(
        r"(?m)^name:\s*(?:ai-apf|'ai-apf'|\"ai-apf\")\s*$", header.group(1)
    ):
        raise EntryError("The selected SKILL.md must have frontmatter name: ai-apf.")
    return path


def make_block(skill, newline):
    lines = [
        BEGIN,
        "## AI-APF Plan default",
        "",
        "In host-confirmed Plan mode, apply the ai-apf skill at this absolute file path:",
        # Windows accepts forward slashes for native paths. Unlike a JSON
        # string containing backslashes, this is directly readable as written.
        json.dumps(skill.as_posix(), ensure_ascii=False),
        "Read this compact SKILL.md if its contents are not already available in the current "
        "context; reuse current context and prior decisions. Load reference modules only when relevant.",
        "For clear tasks, give the shortest useful plan or action allowed by the current "
        "mode; do not require a research interview.",
        "For material uncertainty, inspect available context first, then address the most "
        "consequential gap. Keep proposed interpretations open to user correction.",
        "Honor explicit ai-apf requests in the current mode. Reopen only branches affected "
        "by new evidence. Respect actual host permissions and the user's agreed scope.",
        "If the skill cannot be loaded, distinguish lightweight fallback from full skill "
        "activation; never claim that the full skill was loaded.",
        END,
        "",
    ]
    return newline.join(lines)


def prevent_new_override(path, before, after):
    if path.name != "AGENTS.override.md" or before or not after:
        return
    ordinary = path.with_name("AGENTS.md")
    if is_link_or_reparse(ordinary) or (ordinary.exists() and (
        not ordinary.is_file() or ordinary.stat().st_size > 0
    )):
        raise EntryError(
            f"Making this override nonempty would hide existing {ordinary}. "
            "Select the currently effective instruction file instead."
        )


def write_change(path, before, after):
    """Back up existing bytes before an atomic replacement; no backup for a no-op."""
    if inspect_target(path) != before:
        raise EntryError("The instruction file changed during inspection; run again.")
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlinks(path)
    mode = stat.S_IMODE(path.stat().st_mode) if before is not None else 0o600
    backup = None
    if before is not None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(path.name + ".ai-apf.bak." + stamp)
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(before)
            stream.flush()
            os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix=".ai-apf-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            # Windows has different permission semantics; fchmod was also
            # unavailable there before Python 3.13. Do not promise ACL copying.
            if os.name != "nt":
                os.fchmod(stream.fileno(), mode)
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        if inspect_target(path) != before:
            raise EntryError("The instruction file changed during preparation; run again.")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("status", "enable", "disable"))
    parser.add_argument("--agents-file", required=True, help="Explicit target instruction file.")
    parser.add_argument("--skill-file", help="Actual ai-apf SKILL.md; required by enable.")
    parser.add_argument("--dry-run", action="store_true", help="Report the change without writing or backing up.")
    args = parser.parse_args(argv)
    try:
        if args.skill_file and args.command != "enable":
            raise EntryError("--skill-file is only used with enable.")
        path = selected_path(args.agents_file)
        before = inspect_target(path)
        # Retain a UTF-8 BOM at the beginning, including while the managed
        # block is present, and restore the original bytes when disabled.
        bom = b"\xef\xbb\xbf" if before is not None and before.startswith(b"\xef\xbb\xbf") else b""
        text = before[len(bom):].decode("utf-8") if before is not None else ""
        span = managed_span(text)
        result = {
            "command": args.command,
            "agents_file": str(path),
            "entry": "present" if span else "absent",
            "file_exists": before is not None,
            "changed": False,
            "dry_run": args.dry_run,
            "host_activation": "not_verified",
        }
        if args.command == "status":
            emit_json(result, sys.stdout)
            return 0
        if args.command == "enable":
            skill = checked_skill(args.skill_file)
            block = make_block(skill, "\r\n" if "\r\n" in text else "\n")
            updated = text[:span[0]] + block + text[span[1]:] if span else block + text
            result["skill_file"] = str(skill)
        else:
            updated = text[:span[0]] + text[span[1]:] if span else text
        after = bom + updated.encode("utf-8")
        prevent_new_override(path, before, after)
        change = after != (before or b"")
        result["would_change"] = change
        if args.dry_run:
            if change:
                result["proposed_entry"] = "present" if args.command == "enable" else "absent"
                if args.command == "enable":
                    result["managed_block"] = block
        elif change:
            backup = write_change(path, before, after)
            result.update(changed=True, entry="present" if args.command == "enable" else "absent",
                          file_exists=True, backup_file=str(backup) if backup else None)
        emit_json(result, sys.stdout)
        return 0
    except (EntryError, OSError, UnicodeError) as exc:
        emit_json({"state": "blocked", "error": str(exc), "changed": False}, sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
