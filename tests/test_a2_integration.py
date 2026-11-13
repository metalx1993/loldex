"""End-to-end A2 with the actual site copied into a disposable committed tree."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from deployment.package import package_commit, read_package
from deployment.server import ReleaseStore

ROOT = Path(__file__).resolve().parents[1]


def test_actual_site_committed_package_install_activate_and_retain(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    shutil.copytree(ROOT / "site", source / "site")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    def git(*args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", "-C", str(source), *args], env=env, stderr=subprocess.DEVNULL).decode().strip()
    git("init")
    git("add", "site")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Committed site fixture")
    commit = git("rev-parse", "HEAD")
    raw = package_commit(source, commit)
    manifest, files = read_package(raw)
    assert manifest["commit"] == commit
    assert files["catalog.json"] == (ROOT / "site/catalog.json").read_bytes()
    # Dirty and untracked working-tree bytes cannot enter the release.
    (source / "site/index.html").write_text("tampered working tree")
    assert package_commit(source, commit) == raw
    store = ReleaseStore(tmp_path / "public_html", tmp_path / "loldex-control")
    before = store.status()
    rid = store.install(raw)
    assert store.status() == before
    active = store.activate(rid, before)
    assert active["release_id"] == rid and active["commit"] == commit
    assert store.verify(rid) == manifest
    assert (store.releases / rid / "index.html").read_bytes() == files["index.html"]
    assert store.install(raw) == rid
    assert store.activate(rid, active) == active
    # Entire app data is internally coherent in this same release directory.
    graph = json.loads((store.releases / rid / "graph.json").read_bytes())
    catalog = json.loads((store.releases / rid / "catalog.json").read_bytes())
    assert graph["stats"]["entries"] == catalog["count"]


def test_host_probe_never_claims_http_or_cron_readiness(tmp_path):
    store = ReleaseStore(tmp_path / "public_html", tmp_path / "loldex-control")
    before = store.status()
    result = store.probe()
    assert result["posix_lock"] and result["same_filesystem"] and result["replace_and_fsync"]
    assert not result["http_verified"] and not result["cron_ready"]
    assert store.status() == before and not store.active.exists()
    assert not list(store.control.glob("probe-*"))
