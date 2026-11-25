from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass

from comment_policy import executable_code_path, prohibited_comments


def git(*args, data=None):
    command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", *args]
    result = subprocess.run(command, input=data, capture_output=True)
    if result.returncode:
        message = result.stderr.decode(errors="replace").strip()
        raise ValueError(message or f"Git exited with status {result.returncode}")
    return result.stdout


@dataclass
class Change:
    path: str
    blob: str
    old_path: str
    old_blob: str | None


def source_changes(revisions):
    raw = git("diff", "--raw", "-z", "--no-abbrev", "--find-renames",
              "--no-ext-diff", "--no-textconv", *revisions, "--")
    fields = iter(raw.split(b"\0")[:-1])
    for record in fields:
        old_mode, new_mode, old_oid, new_oid, status = record[1:].split()
        old_path = os.fsdecode(next(fields))
        path = os.fsdecode(next(fields)) if status[:1] in (b"R", b"C") else old_path
        if status == b"U":
            raise ValueError(f"Unresolved merge in {path!r}")
        if not new_mode.startswith(b"100") or not executable_code_path(path):
            continue
        old_blob = old_oid.decode() if old_mode.startswith(b"100") else None
        yield Change(path, new_oid.decode(), old_path, old_blob)


DOCUMENTATION_ATTRIBUTE = "source-comment-documentation"
EXCLUDED_ATTRIBUTES = {"linguist-generated", "linguist-vendored"}


def source_attributes(paths, head):
    if not paths:
        return {}
    data = b"".join(os.fsencode(path) + b"\0" for path in paths)
    source = f"--source={head}" if head else "--cached"
    raw = git("check-attr", source, "-z", "--stdin", *sorted(EXCLUDED_ATTRIBUTES),
              DOCUMENTATION_ATTRIBUTE, data=data)
    result = {}
    fields = iter(raw.split(b"\0")[:-1])
    for path, attribute, value in zip(fields, fields, fields):
        if value in (b"set", b"true"):
            result.setdefault(os.fsdecode(path), set()).add(attribute.decode())
    return result


HUNK = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def unchanged_ranges(old_blob, new_blob):
    patch = git("diff", "--no-ext-diff", "--no-textconv", "--no-color", "--text",
                "--unified=0", "--inter-hunk-context=0", "--word-diff=none", old_blob, new_blob, "--")
    old_line = new_line = 1
    for match in HUNK.finditer(patch):
        old_start, old_count, new_start, new_count = (int(value or 1) for value in match.groups())
        old_start += old_count == 0
        new_start += new_count == 0
        if new_line < new_start:
            yield new_line, new_start, old_line - new_line
        old_line, new_line = old_start + old_count, new_start + new_count
    yield new_line, float("inf"), old_line - new_line


def read_source(oid, path):
    data = git("cat-file", "blob", oid)
    if b"\0" in data:
        raise ValueError(f"Cannot check binary content at {path!r} as source code")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"Cannot read {path!r} as UTF-8") from error


def new_violations(change, documentation_input):
    current = sorted(prohibited_comments(change.path, read_source(change.blob, change.path),
                                         documentation_input=documentation_input))
    if not current:
        return []
    if not change.old_blob or not executable_code_path(change.old_path):
        return current
    original = set(prohibited_comments(change.old_path, read_source(change.old_blob, change.old_path),
                                       documentation_input=documentation_input))
    if not original:
        return current
    matching = iter(unchanged_ranges(change.old_blob, change.blob))
    begin, end, offset = next(matching)
    violations = []
    for start, stop in current:
        while start >= end:
            begin, end, offset = next(matching)
        if not (begin <= start and stop < end and (start + offset, stop + offset) in original):
            violations.append((start, stop))
    return violations


def check(args):
    root = git("rev-parse", "--show-toplevel").removesuffix(b"\n")
    os.chdir(os.fsdecode(root))
    if args.staged:
        head = None
        revisions = ["--cached"]
    else:
        base, head = [
            git("rev-parse", "--verify", "--end-of-options", rev + "^{tree}").decode().strip()
            for rev in (args.base, args.head)
        ]
        revisions = [base, head]
    changes = list(source_changes(revisions))
    attributes = source_attributes([change.path for change in changes], head)
    violations = 0
    for change in changes:
        active = attributes.get(change.path, set())
        if active & EXCLUDED_ATTRIBUTES:
            continue
        for start, _ in new_violations(change, DOCUMENTATION_ATTRIBUTE in active):
            path = change.path if change.path.isprintable() else ascii(change.path)
            print(f"comment-check: {path}:{start}: explanatory comment in changed code", file=sys.stderr)
            violations += 1
    return int(violations > 0)


def main():
    parser = argparse.ArgumentParser(description="Check changed source for explanatory comments.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="check the staged commit")
    mode.add_argument("--base", help="base revision to compare")
    parser.add_argument("--head", help="candidate revision to compare")
    args = parser.parse_args()
    if bool(args.base) != bool(args.head):
        parser.error("--base and --head must be used together")
    try:
        return check(args)
    except (OSError, ValueError) as error:
        for line in str(error).splitlines():
            print(f"Comment check failed: {line}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
