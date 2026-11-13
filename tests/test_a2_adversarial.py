"""Independent A2 attacks against archive, provenance and publication boundaries.

All releases and Git repositories are temporary and local. No transport, live
deployment, process restart, credentials or scheduler is exercised here.
"""
import copy
import gzip
import hashlib
import io
import json
import multiprocessing
from pathlib import Path
import subprocess
import tarfile

import pytest

from deployment.package import build_package, read_package
from deployment.server import Conflict, ReleaseStore


def release(marker, commit):
    return build_package({
        "index.html": ('<html><script src="./app.js"></script>' + marker + '</html>').encode(),
        "app.js": ("window.release='" + marker + "'; fetch('./catalog.json');").encode(),
        "catalog.json": json.dumps({"release": marker}).encode(),
    }, commit * 40)


@pytest.fixture
def store(tmp_path):
    # macOS /var is a symlink; the server requires explicitly resolved real roots.
    root = tmp_path.resolve()
    return ReleaseStore(root / "public", root / "control")


def test_old_document_keeps_its_old_assets_and_data_after_activation(store):
    a = store.install(release("A", "a"))
    first = store.activate(a, store.status())
    root_a = store.public / "releases" / a
    old_document = (root_a / "index.html").read_bytes()
    old_asset = (root_a / "app.js").read_bytes()
    old_data = (root_a / "catalog.json").read_bytes()
    b = store.install(release("B", "b"))
    store.activate(b, first)
    assert (root_a / "index.html").read_bytes() == old_document
    assert (root_a / "app.js").read_bytes() == old_asset
    assert (root_a / "catalog.json").read_bytes() == old_data
    assert (store.public / "releases" / b / "app.js").read_bytes() != old_asset


def test_stale_retry_of_current_target_does_not_bypass_compare_and_swap(store):
    original = store.status()
    rid = store.install(release("A", "a"))
    published = store.activate(rid, original)
    with pytest.raises(Conflict):
        store.activate(rid, original)
    assert store.status() == published
    assert store.activate(rid, published) == published


def test_rollback_aba_does_not_resurrect_old_publication_authority(store):
    a, b, c = [store.install(release(marker, commit))
               for marker, commit in (("A", "a"), ("B", "b"), ("C", "c"))]
    at_a = store.activate(a, store.status())
    at_b = store.activate(b, at_a)
    back_to_a = store.rollback(a, at_b)
    assert back_to_a["generation"] == at_a["generation"] + 2
    assert back_to_a["release_id"] == at_a["release_id"]
    with pytest.raises(Conflict):
        store.activate(c, at_a)
    assert store.status() == back_to_a


def _publisher(public, control, release_id, expected, barrier, outcomes):
    from deployment.server import ReleaseStore
    try:
        barrier.wait(timeout=10)
        token = ReleaseStore(public, control).activate(release_id, expected)
        outcomes.put(("applied", token))
    except Exception as exc:
        outcomes.put((type(exc).__name__, str(exc)))


def test_two_process_publishers_cannot_both_win_same_generation(store):
    a = store.install(release("A", "a"))
    b = store.install(release("B", "b"))
    expected = store.status()
    context = multiprocessing.get_context("fork")
    barrier, outcomes = context.Barrier(2), context.Queue()
    processes = [context.Process(target=_publisher,
        args=(store.public, store.control, rid, expected, barrier, outcomes)) for rid in (a, b)]
    for process in processes:
        process.start()
    try:
        results = [outcomes.get(timeout=15) for _ in processes]
        assert sorted(result[0] for result in results) == ["Conflict", "applied"]
        winner = next(result[1] for result in results if result[0] == "applied")
        assert store.status() == winner
        assert winner["generation"] == 1
    finally:
        for process in processes:
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        outcomes.close()


def test_precommit_replace_failure_preserves_active_authority(store, monkeypatch):
    import deployment.server as server
    a, b = store.install(release("A", "a")), store.install(release("B", "b"))
    first = store.activate(a, store.status())
    before = store.active.read_bytes()
    def fail_replace(*args):
        raise OSError("injected precommit replace failure")
    monkeypatch.setattr(server.os, "replace", fail_replace)
    with pytest.raises(OSError):
        store.activate(b, first)
    assert store.active.read_bytes() == before
    assert store.status() == first
    assert not list(store.control.glob("active.tmp.*"))


def test_postcommit_directory_fsync_failure_keeps_new_visibility(store, monkeypatch):
    import deployment.server as server
    a, b = store.install(release("A", "a")), store.install(release("B", "b"))
    first = store.activate(a, store.status())
    def fail_fsync(*args):
        raise OSError("injected postcommit durability failure")
    monkeypatch.setattr(server, "_fsync_dir", fail_fsync)
    with pytest.raises(OSError):
        store.activate(b, first)
    visible = store.status()
    assert visible["release_id"] == b
    assert visible["generation"] == first["generation"] + 1
    assert store.activate(b, visible) == visible
    with pytest.raises(Conflict):
        store.rollback(a, first)


@pytest.mark.parametrize("mutation", ["changed", "extra", "symlink"])
def test_tampered_retained_release_cannot_be_activated_or_rolled_back(store, mutation):
    rid = store.install(release("A", "a"))
    target = store.public / "releases" / rid
    if mutation == "changed":
        path = target / "app.js"
        path.chmod(0o644)
        path.write_bytes(b"tampered")
    elif mutation == "extra":
        (target / "undeclared.txt").write_text("extra")
    else:
        path = target / "app.js"
        path.unlink()
        path.symlink_to("/etc/passwd")
    before = store.status()
    with pytest.raises(ValueError):
        store.activate(rid, before)
    with pytest.raises(ValueError):
        store.rollback(rid, before)
    assert store.status() == before


def test_matching_hardlinked_payload_is_not_an_immutable_release_file(store):
    import os
    rid = store.install(release("A", "a"))
    payload = store.releases / rid / "app.js"
    alias = store.control / "outside-app.js"
    alias.write_bytes(payload.read_bytes())
    payload.unlink()
    os.link(alias, payload)
    before = store.status()
    with pytest.raises(ValueError):
        store.verify(rid)
    with pytest.raises(ValueError):
        store.activate(rid, before)
    assert store.status() == before


def test_dotdot_root_spelling_cannot_hide_private_control_inside_public_root(tmp_path):
    root = tmp_path.resolve()
    (root / "other").mkdir()
    public = root / "public"
    hidden_overlap = root / "other" / ".." / "public" / "control"
    with pytest.raises(ValueError):
        ReleaseStore(public, hidden_overlap)
    assert not (public / "control").exists()


@pytest.mark.parametrize("mutation", ["duplicate", "bool-generation", "noncanonical"])
def test_corrupted_control_state_is_never_reset_to_uninitialized(store, mutation):
    rid = store.install(release("A", "a"))
    token = store.activate(rid, store.status())
    raw = store.active.read_bytes()
    if mutation == "duplicate":
        raw = b'{"generation":1,' + raw[1:]
    elif mutation == "bool-generation":
        altered = copy.deepcopy(token)
        altered["generation"] = True
        raw = json.dumps(altered, sort_keys=True, separators=(",", ":")).encode()
    else:
        raw += b"\n"
    store.active.write_bytes(raw)
    with pytest.raises(ValueError):
        store.status()
    with pytest.raises(ValueError):
        store.activate(rid, token)
    assert store.active.read_bytes() == raw


def tar_with(raw, name, type_=tarfile.REGTYPE):
    members = []
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw)), mode="r:") as handle:
        for member in handle.getmembers():
            members.append((member.name, member.type, handle.extractfile(member).read()))
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as handle:
        for member_name, member_type, content in members + [(name, type_, b"hostile")]:
            info = tarfile.TarInfo(member_name)
            info.type = member_type
            info.mode = 0o644
            info.size = len(content) if member_type == tarfile.REGTYPE else 0
            if member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                info.linkname = "site/index.html"
            handle.addfile(info, io.BytesIO(content) if info.size else None)
    return gzip.compress(output.getvalue(), mtime=0)


@pytest.mark.parametrize("name,type_", [
    ("site/../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
    ("site/a\\b", tarfile.REGTYPE), ("site/index.html", tarfile.REGTYPE),
    ("release.json", tarfile.REGTYPE), ("site/link", tarfile.SYMTYPE),
    ("site/hard", tarfile.LNKTYPE), ("site/device", tarfile.FIFOTYPE),
])
def test_untrusted_archive_attack_is_rejected_before_publication(store, name, type_):
    before = store.status()
    raw = tar_with(release("A", "a"), name, type_)
    with pytest.raises(ValueError):
        store.install(raw)
    assert store.status() == before
    assert list(store.releases.iterdir()) == []


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True).stdout.decode().strip()


def _production_repo(tmp_path):
    from deployment.package import DATA_FILES, PRODUCTION_FILES
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    files = {name: b"{}" if name.endswith(".json") else b"release A" for name in PRODUCTION_FILES}
    manifest = {"version": 1, "entries": 0, "registry_checksum": "sha256:" + "0" * 64,
                "files": {name: "sha256:" + hashlib.sha256(files[name]).hexdigest() for name in DATA_FILES}}
    files["build-manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    for name, content in files.items():
        path = repo / "site" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "A")
    original = _git(repo, "rev-parse", "HEAD")
    (repo / "site/index.html").write_bytes(b"release B")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "B")
    replacement = _git(repo, "rev-parse", "HEAD")
    return repo, original, replacement


def test_git_replace_cannot_relabel_a_different_commit_as_release_source(tmp_path):
    from deployment.package import package_commit
    repo, original, replacement = _production_repo(tmp_path)
    _git(repo, "replace", original, replacement)
    manifest, published_files = read_package(package_commit(repo, original))
    assert manifest["commit"] == original
    assert published_files["index.html"] == b"release A"


@pytest.mark.parametrize("kind", ["commit", "tree"])
def test_corrupted_git_object_content_cannot_keep_the_claimed_release_identity(tmp_path, kind):
    from deployment.package import package_commit
    repo, original, replacement = _production_repo(tmp_path)
    if kind == "tree":
        original_oid = _git(repo, "rev-parse", original + "^{tree}")
        replacement_oid = _git(repo, "rev-parse", replacement + "^{tree}")
    else:
        original_oid, replacement_oid = original, replacement
    original_object = repo / ".git/objects" / original_oid[:2] / original_oid[2:]
    replacement_object = repo / ".git/objects" / replacement_oid[:2] / replacement_oid[2:]
    original_object.chmod(0o644)
    original_object.write_bytes(replacement_object.read_bytes())
    with pytest.raises(ValueError):
        package_commit(repo, original)


def _source_repo(tmp_path, wad_attack="Exploitation"):
    files = {
        "_gtfobins/tool": "functions:\n  shell:\n  - code: run\n",
        "yml/OSBinaries/Tool.yml": "Name: Tool.exe\nCommands:\n- Category: Execute\n  Command: run\n",
        "yml/OSLibraries/.keep": "", "yml/OSScripts/.keep": "", "yml/OtherMSBinaries/.keep": "",
        "yaml/driver.yaml": "Id: driver-id\nTags: [driver.sys]\n",
        "index.html": "<table><tr><th>Technique</th><th>Command</th><th>Type</th></tr><tr><td>One</td><td>run</td><td>CMD</td></tr></table>",
        "_wadcoms/One.md": "command: original\nattack_types: [" + wad_attack + "]\n",
    }
    repo = tmp_path / "upstream"
    repo.mkdir()
    _git(repo, "init", "-q")
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "sources")
    from phase5.vocabulary import SOURCE_UNIVERSE
    return repo, {source: (repo, "HEAD") for source in SOURCE_UNIVERSE}


def test_publication_staging_cannot_reinterpret_unknown_wad_type_as_discovery(tmp_path):
    from deployment.source_health import prepare_verified_sync, SourceHealthError
    _, repositories = _source_repo(tmp_path, "Unknown")
    output = tmp_path / "candidate"
    with pytest.raises(SourceHealthError):
        prepare_verified_sync(repositories, output)
    assert not output.exists()


def test_publication_staging_uses_same_verified_bytes_after_worktree_is_changed(tmp_path, monkeypatch):
    import deployment.source_health as health
    import yaml
    repo, repositories = _source_repo(tmp_path)
    original_acquire = health.acquire
    def mutate_after_verified(*args, **kwargs):
        value = original_acquire(*args, **kwargs)
        (repo / "_wadcoms/One.md").write_text("command: attacker-replacement\n")
        return value
    monkeypatch.setattr(health, "acquire", mutate_after_verified)
    output = tmp_path / "candidate"
    health.prepare_verified_sync(repositories, output)
    wad_paths = list((output / "data/entries").rglob("wadcoms__*.yaml"))
    assert len(wad_paths) == 1
    entry = yaml.safe_load(wad_paths[0].read_text())
    assert entry["commands"][0]["template"] == "original"


@pytest.mark.parametrize("name,content", [
    ("index.html", '<base href="/">'),
    ("index.html", '<script src="/app.js"></script>'),
    ("index.html", '<link rel="stylesheet" href="https://loldex.sh/theme.css">'),
    ("index.html", '<img src="&#47;asset.png">'),
    ("theme.css", "a{background:url('/asset.png')}"),
    ("app.js", "fetch('/catalog.json')"),
    ("app.js", r"fetch('\57catalog.json')"),
    ("theme.css", r"a{background:url('\2f asset.png')}"),
])
def test_statically_escaped_unversioned_resource_cannot_bypass_release_prefix(name, content):
    from deployment.url_closure import validate_url_closure
    with pytest.raises(ValueError):
        validate_url_closure({name: content.encode()})
