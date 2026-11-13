"""Verified, immutable acquisition from local Git object databases (D1).

The working tree is never an input. Every tree and selected blob is verified
against its content address before the immutable bundle is returned.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess

from .vocabulary import SOURCE_UNIVERSE

ROOTS = {"GTFOBins": "_gtfobins", "LOLBAS": "yml", "WADComs": "_wadcoms", "LOLDrivers": "yaml", "LOLAD": ""}
LOLBAS_FOLDERS = ("OSBinaries", "OSLibraries", "OSScripts", "OtherMSBinaries")
MAX_OBJECT = 32 * 1024 * 1024
MAX_BYTES = 128 * 1024 * 1024
MAX_FILES = 20000


class AcquisitionFailed(ValueError):
    """The supplied repository/revision cannot prove one complete usable bundle."""


@dataclass(frozen=True)
class AcquiredFile:
    name: str
    content: bytes


@dataclass(frozen=True)
class VerifiedBundle:
    source: str
    revision: str
    tree: str
    files: tuple[AcquiredFile, ...]


def _git(repo, *args):
    try:
        p = subprocess.run(["git", "--no-replace-objects", "-C", str(repo), *args],
                           check=True, capture_output=True, timeout=30,
                           env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_LAZY_FETCH": "1"})
        if len(p.stdout) > MAX_OBJECT:
            raise AcquisitionFailed("object exceeds acquisition limit")
        return p.stdout
    except (subprocess.SubprocessError, OSError) as exc:
        raise AcquisitionFailed("cannot read verified git object") from exc


def selected(source, relative):
    """D1 candidate predicate. POSIX paths; case-sensitive; no recursion."""
    parts = relative.split("/")
    if source == "LOLAD":
        return relative == "index.html"
    if source == "LOLBAS":
        return len(parts) == 2 and parts[0] in LOLBAS_FOLDERS and parts[1].endswith(".yml")
    if len(parts) != 1:
        return False
    return source == "GTFOBins" or relative.endswith(".md" if source == "WADComs" else ".yaml")


def acquire(repo, source, revision="HEAD"):
    """Resolve once, verify commit/tree/blobs, return only immutable bytes.

    No clone/fetch or use of local working-tree files occurs. Dirty/sparse
    working trees cannot create false absence. Missing objects fail acquisition.
    """
    if source not in SOURCE_UNIVERSE:
        raise ValueError("unknown source")
    if not isinstance(revision, str) or revision.startswith("-"):
        raise AcquisitionFailed("invalid revision")
    commit = _git(repo, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise AcquisitionFailed("CORE requires a full SHA-1 commit identity")

    def obj(kind, oid):
        try:
            length = int(_git(repo, "cat-file", "-s", oid))
        except ValueError as exc:
            raise AcquisitionFailed("invalid object size") from exc
        if length > MAX_OBJECT:
            raise AcquisitionFailed("object exceeds acquisition limit")
        body = _git(repo, "cat-file", kind, oid)
        actual = hashlib.sha1(kind.encode() + b" " + str(len(body)).encode() + b"\0" + body).hexdigest()
        if actual != oid:
            raise AcquisitionFailed("object content does not match its identity")
        return body

    raw_commit = obj("commit", commit)
    match = re.match(rb"tree ([0-9a-f]{40})\n", raw_commit)
    if match is None:
        raise AcquisitionFailed("commit has no tree")
    tree = match[1].decode()
    files, dirs = [], set()
    size = 0
    visited = 0

    def walk(oid, prefix="", depth=0):
        nonlocal size, visited
        if depth > 64:
            raise AcquisitionFailed("tree nesting exceeds acquisition limit")
        body = obj("tree", oid)
        pos = 0
        names = set()
        while pos < len(body):
            try:
                space = body.index(b" ", pos)
                end = body.index(b"\0", space)
                mode = body[pos:space].decode("ascii")
                name = body[space + 1:end].decode("utf-8", "strict")
                oid2 = body[end + 1:end + 21].hex()
                if len(oid2) != 40 or name in ("", ".", "..") or "/" in name or name in names:
                    raise ValueError("invalid tree record")
            except (ValueError, UnicodeError) as exc:
                raise AcquisitionFailed("malformed or non-UTF-8 tree") from exc
            names.add(name)
            pos = end + 21
            visited += 1
            if visited > MAX_FILES * 10:
                raise AcquisitionFailed("tree exceeds acquisition limit")
            path = prefix + name
            if mode == "40000":
                dirs.add(path)
                walk(oid2, path + "/", depth + 1)
            else:
                root = ROOTS[source]
                if root and not path.startswith(root + "/"):
                    continue
                relative = path[len(root) + 1:] if root else path
                if not selected(source, relative):
                    continue
                if mode not in ("100644", "100755"):
                    raise AcquisitionFailed("selected candidate is not a regular blob")
                data = obj("blob", oid2)
                size += len(data)
                if size > MAX_BYTES or len(files) >= MAX_FILES:
                    raise AcquisitionFailed("bundle exceeds acquisition limit")
                files.append(AcquiredFile(relative, data))

    walk(tree)
    root = ROOTS[source]
    if root and root not in dirs:
        raise AcquisitionFailed("required acquisition root absent")
    if source == "LOLBAS" and any("yml/" + f not in dirs for f in LOLBAS_FOLDERS):
        raise AcquisitionFailed("required LOLBAS folder absent")
    if source == "LOLAD" and not files:
        raise AcquisitionFailed("index.html absent")
    return VerifiedBundle(source, commit, tree, tuple(sorted(files, key=lambda f: f.name)))
