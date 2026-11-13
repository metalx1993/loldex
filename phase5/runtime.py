"""POSIX CORE persistence and caller integration. No publication or deletion.

Finalized observations are explicit immutable delivery artifacts. Retrying an
artifact never reacquires or rebuilds it. This module is not a recovery journal.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile

from .acquisition import acquire, AcquisitionFailed
from .canonical import canonical_bytes, canonicalize
from .genesis import build_genesis_inventory, genesis_body
from .observation import build_observation
from .state import serialize_state_file, state_token, validate_envelope
from .transition import evaluate, Admission


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda v: (_ for _ in ()).throw(ValueError("non-finite JSON")))


def read_state(path, genesis):
    path = Path(path)
    if not path.exists():
        return canonicalize(genesis)
    data = path.read_bytes()
    strict_json(data)  # reject duplicate raw keys before the frozen validator
    return validate_envelope(data)


@contextmanager
def state_lock(path):
    """Stable lock inode; never lock the replaceable state inode itself."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _atomic_state(path, body):
    path = Path(path)
    payload = serialize_state_file(body)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".tmp.", dir=path.parent)
    committed = False
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        committed = True
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if not committed:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def apply_observation(path, observation, genesis):
    """API-entry token captured before lock; exact retry has no report/mutation."""
    observation = canonicalize(observation)
    arrival = state_token(read_state(path, genesis))
    with state_lock(path):
        committed = read_state(path, genesis)
        result = evaluate(committed, observation, arrival)
        if result.admission == Admission.APPLIED:
            _atomic_state(path, result.next_body)
        return result


class ObservationBuilder:
    """One live caller path per base token; retry the returned bytes, not build()."""

    def __init__(self):
        self._used = set()

    def build(self, base, repositories):
        token_bytes = canonical_bytes(state_token(base))
        if token_bytes in self._used:
            raise ValueError("second acquisition/build for the same base token forbidden")
        self._used.add(token_bytes)
        bundles = {}
        for source, (repository, revision) in repositories.items():
            try:
                bundles[source] = acquire(repository, source, revision)
            except AcquisitionFailed:
                bundles[source] = None
        return build_observation(base, bundles)


def cycle(path, repositories, repo_root, observation_path):
    """Sequential local cycle with a write-once finalized delivery artifact.

    An existing artifact is delivered exactly; it is never rebuilt. Caller may
    use a new artifact path only with a new committed base. After interruption
    before artifact finalization, resume is an explicit operator decision, not
    automatic reacquisition. Cross-process reservation/recovery is out of scope.
    """
    genesis = genesis_body(build_genesis_inventory(repo_root))
    artifact = Path(observation_path)
    if Path(path).resolve() == artifact.resolve():
        raise ValueError("state and observation paths must differ")
    # Serialize live builders under the same state lock; acquire after base capture.
    with state_lock(path):
        committed = read_state(path, genesis)
        if artifact.exists():
            raw = artifact.read_bytes()
            observation = strict_json(raw)
            if canonical_bytes(observation) != raw:
                raise ValueError("delivery artifact is not canonical")
        else:
            observation = ObservationBuilder().build(committed, repositories)
            artifact.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation: finalized observation is never overwritten.
            with artifact.open("xb") as stream:
                stream.write(canonical_bytes(observation))
                stream.flush()
                os.fsync(stream.fileno())
        result = evaluate(committed, observation, state_token(committed))
        if result.admission == Admission.APPLIED:
            _atomic_state(path, result.next_body)
        return result
