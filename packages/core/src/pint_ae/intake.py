"""Input discovery and classification.

A client sends a folder, a zip, or a list of files — not a single invoice. This
module turns any of those into a deterministic stream of `InputItem`s with an
explicit classification, so nothing is silently skipped and nothing crashes.

It intentionally does not parse XML: `parse()` classifies documents later and
reports a precise error. The intake layer only answers "can this byte stream be
handed to the parser, and if not, why".
"""

from __future__ import annotations

import hashlib
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

#: Classifications used by the intake layer and the JSON contract.
ACCEPTED = "accepted"
UNSUPPORTED_DOCUMENT = "unsupported-document"
NOT_XML = "not-xml"
XML_SYNTAX_ERROR = "xml-syntax-error"
UNREADABLE = "unreadable"
DUPLICATE = "duplicate"
TOO_LARGE = "too-large"
EMPTY = "empty"

#: Classifications that mean "this file could not be validated".
FAILED_CLASSIFICATIONS = frozenset({UNREADABLE, TOO_LARGE, XML_SYNTAX_ERROR})
#: Classifications that are informational and do not affect the exit code on their own.
SOFT_CLASSIFICATIONS = frozenset({DUPLICATE, NOT_XML, UNSUPPORTED_DOCUMENT, EMPTY})


@dataclass(frozen=True)
class IntakeLimits:
    """Guard rails for untrusted input."""

    max_file_bytes: int = 25 * 1024 * 1024
    max_zip_entries: int = 10_000
    max_total_bytes: int = 500 * 1024 * 1024


@dataclass
class InputItem:
    """One candidate document, with everything needed to validate or skip it."""

    display: str
    size: int = 0
    data: bytes | None = None
    classification: str = ACCEPTED
    detail: str = ""
    sha256: str = field(default="")

    @property
    def failed(self) -> bool:
        return self.classification in FAILED_CLASSIFICATIONS


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _looks_like_xml(data: bytes) -> bool:
    head = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    return head.startswith(b"<")


def _read_file(path: Path, display: str, limits: IntakeLimits) -> InputItem:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return InputItem(display, classification=UNREADABLE, detail=str(exc))
    if size == 0:
        return InputItem(display, size=0, classification=EMPTY, detail="file is empty")
    if size > limits.max_file_bytes:
        return InputItem(
            display,
            size=size,
            classification=TOO_LARGE,
            detail=f"{size} bytes exceeds the {limits.max_file_bytes} byte limit",
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        return InputItem(display, size=size, classification=UNREADABLE, detail=str(exc))
    return InputItem(display, size=size, data=data, sha256=_hash(data))


def _zip_items(path: Path, limits: IntakeLimits) -> Iterator[InputItem]:
    """Yield items for a zip archive without extracting anything to disk."""
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        yield InputItem(str(path), classification=UNREADABLE, detail=f"bad zip: {exc}")
        return

    with archive:
        entries = archive.infolist()
        if len(entries) > limits.max_zip_entries:
            yield InputItem(
                str(path),
                classification=TOO_LARGE,
                detail=f"{len(entries)} entries exceeds the {limits.max_zip_entries} entry limit",
            )
            return

        for info in sorted(entries, key=lambda i: i.filename):
            if info.is_dir():
                continue
            display = f"{path}#{info.filename}"
            member = info.filename
            if member.startswith("/") or ".." in Path(member).parts:
                yield InputItem(display, classification=UNREADABLE, detail="unsafe archive path")
                continue
            if info.flag_bits & 0x1:
                yield InputItem(
                    display,
                    classification=UNREADABLE,
                    detail="encrypted zip entries are not supported",
                )
                continue
            if info.file_size > limits.max_file_bytes:
                yield InputItem(
                    display,
                    size=info.file_size,
                    classification=TOO_LARGE,
                    detail=f"{info.file_size} bytes exceeds the {limits.max_file_bytes} byte limit",
                )
                continue
            try:
                data = archive.read(info)
            except (RuntimeError, OSError, zipfile.BadZipFile) as exc:
                yield InputItem(display, classification=UNREADABLE, detail=str(exc))
                continue
            yield InputItem(display, size=len(data), data=data, sha256=_hash(data))


def _walk_directory(root: Path, limits: IntakeLimits) -> Iterator[InputItem]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            display = str(path)
            yield _read_file(path, display, limits)


def expand(
    paths: Iterable[Path | str],
    limits: IntakeLimits | None = None,
) -> list[InputItem]:
    """Expand files, directories, globs and zips into a deduplicated item list.

    The result is deterministic: inputs keep their order, directory content is
    sorted by relative path, zip members are sorted by name.
    """
    limits = limits or IntakeLimits()
    items: list[InputItem] = []
    seen: dict[str, str] = {}
    total = 0

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            items.append(
                InputItem(str(path), classification=UNREADABLE, detail="path does not exist")
            )
            continue
        if path.is_dir():
            candidates: list[InputItem] = list(_walk_directory(path, limits))
        elif path.suffix.lower() == ".zip":
            candidates = list(_zip_items(path, limits))
        else:
            candidates = [_read_file(path, str(path), limits)]

        for item in candidates:
            if item.classification == ACCEPTED and item.data is not None:
                if not _looks_like_xml(item.data):
                    item.classification = NOT_XML
                    item.detail = "content does not start with '<'"
                elif item.sha256 in seen:
                    item.classification = DUPLICATE
                    item.detail = f"same content as {seen[item.sha256]}"
                else:
                    seen[item.sha256] = item.display
            if item.data is not None:
                total += item.size
                if total > limits.max_total_bytes:
                    items.append(
                        InputItem(
                            item.display,
                            size=item.size,
                            classification=TOO_LARGE,
                            detail=f"total input exceeds {limits.max_total_bytes} bytes",
                        )
                    )
                    return items
            items.append(item)
    return items
