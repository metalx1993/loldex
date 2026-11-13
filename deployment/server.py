"""A2 host-side POSIX release store. No network, scheduling or catalogue writes.

One atomic private active.json is the publication authority. Public requests
redirect to retained immutable /releases/<id>/ paths, not a mutable symlink.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

from deployment.package import read_package, parse_manifest, validate_payload

RELEASE_ID = re.compile(r"r-[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
TOKEN_KEYS = {"version", "generation", "release_id", "previous_release_id", "commit"}


class DeploymentError(ValueError):
    pass


class Conflict(DeploymentError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise DeploymentError("duplicate JSON key")
            out[key] = value
        return out
    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as exc:
        raise DeploymentError("invalid publication JSON") from exc


def validate_token(token):
    if not isinstance(token, dict) or set(token) != TOKEN_KEYS:
        raise DeploymentError("invalid publication token shape")
    if type(token["version"]) is not int or token["version"] != 1:
        raise DeploymentError("unsupported publication token")
    generation = token["generation"]
    if type(generation) is not int or not 0 <= generation <= 9007199254740991:
        raise DeploymentError("invalid publication generation")
    rid, previous, commit = (token[k] for k in ("release_id", "previous_release_id", "commit"))
    if rid is None:
        if generation != 0 or previous is not None or commit is not None:
            raise DeploymentError("invalid uninitialized publication token")
    elif not isinstance(rid, str) or not RELEASE_ID.fullmatch(rid) or generation == 0 or not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise DeploymentError("invalid active release binding")
    if previous is not None and (not isinstance(previous, str) or not RELEASE_ID.fullmatch(previous)):
        raise DeploymentError("invalid previous release")
    return token


def _regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise DeploymentError("expected a regular file with no hard links")


def _no_symlink_parents(path):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise DeploymentError("deployment paths cannot contain symlinks; supply the real path")


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class ReleaseStore:
    def __init__(self, public_root, control_root):
        self.public = Path(public_root)
        self.control = Path(control_root)
        if not self.public.is_absolute() or not self.control.is_absolute():
            raise DeploymentError("deployment roots must be absolute")
        _no_symlink_parents(self.public)
        _no_symlink_parents(self.control)
        if self.public != self.public.resolve() or self.control != self.control.resolve():
            raise DeploymentError("deployment roots must be canonical real paths")
        if self.public == self.control or self.public in self.control.parents or self.control in self.public.parents:
            raise DeploymentError("control and public roots must be separate non-overlapping directories")
        self.public.mkdir(parents=True, exist_ok=True)
        self.control.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.releases = self.public / "releases"
        if self.releases.is_symlink():
            raise DeploymentError("release root cannot be a symlink")
        self.releases.mkdir(exist_ok=True)
        if self.control.stat().st_dev != self.releases.stat().st_dev:
            raise DeploymentError("staging and releases must share one filesystem")
        self.active = self.control / "active.json"

    @contextmanager
    def _lock(self):
        lockpath = self.control / ".publish.lock"
        if lockpath.exists() or lockpath.is_symlink():
            _regular(lockpath)
        fd = os.open(lockpath, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def status(self):
        if not self.active.exists() and not self.active.is_symlink():
            return {"version": 1, "generation": 0, "release_id": None, "previous_release_id": None, "commit": None}
        _regular(self.active)
        raw = self.active.read_bytes()
        token = validate_token(strict_json(raw))
        if canonical(token) != raw:
            raise DeploymentError("publication token is not canonical")
        return token

    def _release_path(self, release_id):
        if not isinstance(release_id, str) or not RELEASE_ID.fullmatch(release_id):
            raise DeploymentError("invalid release identifier")
        return self.releases / release_id

    def verify(self, release_id):
        root = self._release_path(release_id)
        if root.is_symlink() or not root.is_dir():
            raise DeploymentError("release is missing or not a real directory")
        files = {}
        manifest = None
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise DeploymentError("release contains a symlink")
            if path.is_dir():
                continue
            _regular(path)
            relative = path.relative_to(root).as_posix()
            if relative == "release.json":
                manifest = parse_manifest(path.read_bytes())
            else:
                files[relative] = path.read_bytes()
        if manifest is None or manifest["release_id"] != release_id:
            raise DeploymentError("release manifest binding mismatch")
        validate_payload(manifest, files)
        return manifest

    def install(self, raw_package):
        manifest, files = read_package(raw_package)
        rid = manifest["release_id"]
        target = self._release_path(rid)
        with self._lock():
            if target.exists() or target.is_symlink():
                if self.verify(rid) != manifest:
                    raise DeploymentError("existing immutable release differs")
                return rid
            stage = Path(tempfile.mkdtemp(prefix="stage-", dir=self.control))
            try:
                for relative, data in sorted({**files, "release.json": canonical(manifest)}.items()):
                    path = stage / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    path.chmod(0o444)
                for directory in sorted((p for p in stage.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                    _fsync_dir(directory)
                _fsync_dir(stage)
                # No active authority changes here. A partial upload is private.
                os.rename(stage, target)
                target.chmod(0o755)
                _fsync_dir(self.releases)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        return rid

    def activate(self, release_id, expected_token):
        validate_token(expected_token)
        with self._lock():
            current = self.status()
            if current != expected_token:
                raise Conflict("publication changed; read current token before retrying")
            manifest = self.verify(release_id)
            if current["release_id"] == release_id:
                if current["commit"] != manifest["commit"]:
                    raise DeploymentError("active commit binding differs")
                return current
            new = {"version": 1, "generation": current["generation"] + 1,
                   "release_id": release_id, "previous_release_id": current["release_id"], "commit": manifest["commit"]}
            validate_token(new)
            fd, temporary = tempfile.mkstemp(prefix="active.tmp.", dir=self.control)
            renamed = False
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(canonical(new))
                    stream.flush()
                    os.fsync(stream.fileno())
                # The sole publication commit point. Later durability errors do
                # not make the old generation authoritative again.
                os.replace(temporary, self.active)
                renamed = True
                _fsync_dir(self.control)
            finally:
                if not renamed:
                    try:
                        os.unlink(temporary)
                    except FileNotFoundError:
                        pass
            return new

    def rollback(self, release_id, expected_token):
        """Explicit retained target, same verification/CAS; never auto-rewind."""
        return self.activate(release_id, expected_token)

    def probe(self):
        """Exercise local host primitives privately, without changing authority.

        This proves filesystem/lock primitives only. Apache routing, external
        caches and HTTP behavior still need destination-host smoke tests.
        """
        import sys
        with self._lock():
            before = self.status()
            fd, name = tempfile.mkstemp(prefix="probe-", dir=self.control)
            source, target = Path(name), Path(name + ".target")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(b"verified replacement")
                    stream.flush()
                    os.fsync(stream.fileno())
                with target.open("xb") as stream:
                    stream.write(b"old content")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(source, target)
                _fsync_dir(self.control)
                if target.read_bytes() != b"verified replacement" or self.status() != before:
                    raise DeploymentError("host probe failed")
            finally:
                for path in (source, target):
                    if path.exists():
                        path.unlink()
            return {"version": 1, "python": sys.version.split()[0], "posix_lock": True,
                    "same_filesystem": True, "replace_and_fsync": True, "active": before,
                    "http_verified": False, "cron_ready": False}
