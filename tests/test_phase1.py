"""Phase-1 tests — layered data model, projection, per-source hashing,
Entry invariants, and no-regression integration.

Scope: this validates the DATA MODEL and the PROJECTION only. No exploit
execution, persistence, credential-access, or any operational capability is
introduced or tested here.
"""
import copy
import datetime as dt
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.base import Entry, EnrichedValue, LOLDEX_INTERPRETIVE_KEYS  # noqa: E402
from adapters import projection as pj  # noqa: E402


# =========================================================================
# helpers
# =========================================================================
def ev(value, ptype="adapter", level="high", **prov):
    p = {"type": ptype}
    p.update(prov)
    return {"value": value, "provenance": p, "confidence": {"level": level}}


def enr(caps=(), phases=(), attack=(), priv=None):
    e = {}
    if caps:
        e["capabilities"] = [ev(c) for c in caps]
    if phases:
        e["phases"] = [ev(p) for p in phases]
    if attack:
        e["attack_techniques"] = [ev(a) for a in attack]
    if priv:
        e["privilege_required"] = ev(priv)
    return e


def _entry(enrichment, source_data=None):
    # Ensure a VALID top-level baseline (phases + privilege + a capability) so
    # that layer-specific corruption is what a test triggers, not a pre-existing
    # empty top-level. Only fills keys the test didn't specify.
    enrichment = dict(enrichment)
    enrichment.setdefault("capabilities", [ev("shell")])
    enrichment.setdefault("phases", [ev("execution")])
    enrichment.setdefault("privilege_required", ev("user"))
    return pj.make_entry(
        source_data=source_data or {
            "GTFOBins": {"raw": {"binary": "tar"}, "upstream_url": "https://x/"}
        },
        enrichment=enrichment,
        on=dt.date(2026, 8, 28),
        id="gtfobins/tar/x",
        type="binary",
        platform="linux",
        name="tar",
        sources=[{"project": "GTFOBins", "upstream_url": "https://x/",
                  "license": "GPL-3.0"}],
    )


# =========================================================================
# build(): PURE + idempotent
# =========================================================================
def test_build_empty_enrichment():
    assert pj.build({}) == {
        "capabilities": [], "phases": [], "attack_techniques": [],
        "privilege_required": "",
    }


def test_build_single_enriched_value():
    assert pj.build(enr(caps=["file-write"]))["capabilities"] == ["file-write"]


def test_build_privilege_single():
    assert pj.build(enr(priv="suid"))["privilege_required"] == "suid"


def test_build_dedup():
    e = {"capabilities": [ev("file-read"), ev("file-read"), ev("file-write")]}
    assert pj.build(e)["capabilities"] == ["file-read", "file-write"]


def test_build_deterministic_order():
    e = {"phases": [ev("execution"), ev("persistence"), ev("collection")]}
    assert pj.build(e)["phases"] == ["execution", "persistence", "collection"]


def test_build_pure():
    e = enr(caps=["file-write"], phases=["persistence"], priv="suid")
    snapshot = copy.deepcopy(e)
    a, b = pj.build(e), pj.build(e)
    assert a == b
    assert e == snapshot


# =========================================================================
# apply(): MUTATIVE, assigns the FULL projection
# =========================================================================
def test_apply_updates_on_enrichment_change():
    e = _entry(enr(caps=["file-write"]))
    e.enrichment["capabilities"] = [ev("file-read")]
    pj.apply(e, on=dt.date(2026, 8, 28))
    assert e.capabilities == ["file-read"]


def test_apply_clears_removed_field():
    e = _entry(enr(caps=["file-write"], phases=["persistence"]))
    assert e.capabilities == ["file-write"]
    del e.enrichment["capabilities"]
    pj.apply(e, on=dt.date(2026, 8, 28))
    assert e.capabilities == []


def test_apply_equals_build():
    e = _entry(enr(caps=["file-write"], phases=["persistence"], priv="suid"))
    proj = pj.build(e.enrichment)
    assert e.capabilities == proj["capabilities"]
    assert e.phases == proj["phases"]
    assert e.privilege_required == proj["privilege_required"]


def test_projection_full_contract_after_removal():
    e = _entry(enr(
        caps=["file-write", "file-read"],
        phases=["persistence", "collection"],
        priv="suid",
    ))
    e.enrichment["attack_techniques"] = [ev("T1059"), ev("T1547")]
    pj.apply(e, on=dt.date(2026, 8, 28))

    del e.enrichment["capabilities"]
    del e.enrichment["privilege_required"]
    pj.apply(e, on=dt.date(2026, 8, 28))

    proj = pj.build(e.enrichment)
    assert e.capabilities       == proj["capabilities"]       == []
    assert e.phases             == proj["phases"]             == ["persistence", "collection"]
    assert e.attack_techniques  == proj["attack_techniques"]  == ["T1059", "T1547"]
    assert e.privilege_required == proj["privilege_required"] == ""


# =========================================================================
# per-source hashing
# =========================================================================
def test_hash_ignores_last_synced():
    a = {"raw": {"binary": "tar"}, "upstream_url": "u", "last_synced": "2026-08-01"}
    b = {"raw": {"binary": "tar"}, "upstream_url": "u", "last_synced": "2026-08-28"}
    assert pj.source_hash(a) == pj.source_hash(b)


def test_hash_changes_on_raw():
    a = {"raw": {"binary": "tar"}, "upstream_url": "u"}
    b = {"raw": {"binary": "curl"}, "upstream_url": "u"}
    assert pj.source_hash(a) != pj.source_hash(b)


def test_hash_changes_on_version():
    a = {"raw": {"binary": "tar"}, "upstream_url": "u", "upstream_version": "aaa"}
    b = {"raw": {"binary": "tar"}, "upstream_url": "u", "upstream_version": "bbb"}
    assert pj.source_hash(a) != pj.source_hash(b)


def test_compute_source_hashes_two_sources():
    sd = {
        "GTFOBins": {"raw": {"binary": "tar", "function": "file-write"},
                     "upstream_url": "https://gtfobins/"},
        "LOLBAS":   {"raw": {"binary": "certutil.exe", "category": "Download"},
                     "upstream_url": "https://lolbas/"},
    }
    h0 = pj.compute_source_hashes(sd)
    assert set(h0) == {"GTFOBins", "LOLBAS"}
    assert h0["GTFOBins"] != h0["LOLBAS"]

    sd2 = copy.deepcopy(sd)
    sd2["LOLBAS"]["raw"]["category"] = "Execute"
    h1 = pj.compute_source_hashes(sd2)
    assert h1["GTFOBins"] == h0["GTFOBins"]
    assert h1["LOLBAS"]   != h0["LOLBAS"]

    sd3 = copy.deepcopy(sd)
    sd3["GTFOBins"]["raw"]["function"] = "file-read"
    h2 = pj.compute_source_hashes(sd3)
    assert h2["LOLBAS"]   == h0["LOLBAS"]
    assert h2["GTFOBins"] != h0["GTFOBins"]


# =========================================================================
# Entry invariants
# =========================================================================
def test_source_data_structure():
    e = _entry(enr(caps=["file-write"]))
    e.source_data["GTFOBins"].pop("raw")
    with pytest.raises(AssertionError, match="raw"):
        e.validate()

    e = _entry(enr(caps=["file-write"]))
    e.source_data["GTFOBins"]["raw"] = "not-a-dict"
    with pytest.raises(AssertionError, match="raw"):
        e.validate()

    e = _entry(enr(caps=["file-write"]))
    e.source_data["GTFOBins"].pop("upstream_url")
    with pytest.raises(AssertionError, match="upstream_url"):
        e.validate()

    e = _entry(enr(caps=["file-write"]))
    e.source_data["GTFOBins"]["upstream_url"] = ""
    with pytest.raises(AssertionError, match="upstream_url"):
        e.validate()

    _entry(enr(caps=["file-write"])).validate()


def test_source_data_rejects_interpretive_keys():
    for bad in ("relationships", "capabilities", "phases", "enrichment",
                "attack_techniques", "privilege_required"):
        e = _entry(enr(caps=["file-write"]))
        e.source_data["GTFOBins"][bad] = "leak"
        with pytest.raises(AssertionError, match="interpretive|belong"):
            e.validate()


def test_source_data_raw_is_opaque():
    """raw is the source's OWN payload: it is NOT validated against loldex
    vocab. A key literally named like a loldex-interpretive field, living
    INSIDE raw, must be accepted — the validator inspects the block's own
    keys, never recurses into raw."""
    for key in ("capabilities", "phases", "attack_techniques",
                "privilege_required", "relationships", "enrichment"):
        e = _entry(enr(caps=["file-write"]))
        e.source_data["GTFOBins"]["raw"][key] = "upstream calls it this"
        e.validate()   # must NOT raise — raw is opaque
        # and the value survives round-trip (not stripped/reinterpreted)
        assert e.source_data["GTFOBins"]["raw"][key] == "upstream calls it this"


def test_projection_overwrites_manual_toplevel():
    """The top-level fields are NOT a source of truth: apply() overwrites any
    hand-set top-level with the projection of enrichment."""
    e = _entry(enr(caps=["file-write"], phases=["execution"], priv="suid"))
    e.capabilities = ["THIS-MUST-NOT-SURVIVE"]
    e.phases = ["fake-phase"]
    e.privilege_required = "root"
    pj.apply(e, on=dt.date(2026, 8, 28))
    assert e.capabilities == ["file-write"]
    assert e.phases == ["execution"]
    assert e.privilege_required == "suid"


def test_meta_contract_is_exactly_four_keys():
    """_meta active contract in phase 1: exactly schema_version, generated_by,
    projected_at, source_hashes. No `model`, no `_meta.last_synced`."""
    e = _entry(enr(caps=["file-write"]))
    assert set(e.meta) == {"schema_version", "generated_by",
                           "projected_at", "source_hashes"}
    assert e.meta["generated_by"] == pj.GENERATED_BY
    assert "model" not in e.meta
    assert "last_synced" not in e.meta          # sync time is per-source only
    assert "last_enriched" not in e.meta        # reserved, not populated


def test_meta_serializes_as_underscore():
    d = _entry(enr(caps=["file-write"])).to_dict()
    assert "_meta" in d and "meta" not in d


def test_enrichment_wellformed():
    e = _entry({"capabilities": [{"value": "file-write",
                                  "provenance": {"type": "banana"},
                                  "confidence": {"level": "high"}}]})
    with pytest.raises(AssertionError, match="provenance.type"):
        e.validate()
    e = _entry({"capabilities": [{"value": "file-write",
                                  "provenance": {"type": "adapter"},
                                  "confidence": {"level": "banana"}}]})
    with pytest.raises(AssertionError, match="confidence.level"):
        e.validate()


def test_toplevel_equals_projection():
    e = _entry(enr(caps=["file-write"],
                   phases=["persistence", "privilege-escalation"], priv="suid"))
    proj = pj.build(e.enrichment)
    assert e.capabilities == proj["capabilities"]
    assert e.phases == proj["phases"]
    assert e.privilege_required == proj["privilege_required"]


# =========================================================================
# pilot adapter — static guardrail + behavioral check on a real entry
# =========================================================================
def test_pilot_goes_through_projection_static():
    import inspect
    from adapters import gtfobins
    src = inspect.getsource(gtfobins.GTFOBinsAdapter.normalize)
    assert "make_entry" in src
    assert "capabilities=[cap]" not in src


def _run_pilot_one_entry(tmp_path):
    from adapters.gtfobins import GTFOBinsAdapter
    clone = tmp_path / "gtfobins_src"
    (clone / "_gtfobins").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=clone, check=True)
    (clone / "_gtfobins" / "tar.md").write_text(
        "---\nfunctions:\n  file-write:\n  - code: tar cf x\n    contexts:\n"
        "      suid:\n---\n")
    subprocess.run(["git", "add", "-A"], cwd=clone, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "x"], cwd=clone, check=True)
    adapter = GTFOBinsAdapter(clone_dir=clone)
    entries = list(adapter.normalize(adapter.fetch()))
    assert entries, "pilot produced no entries"
    return entries[0]


def test_pilot_entry_toplevel_equals_projection(tmp_path):
    e = _run_pilot_one_entry(tmp_path)
    proj = pj.build(e.enrichment)
    assert e.capabilities       == proj["capabilities"]
    assert e.phases             == proj["phases"]
    assert e.attack_techniques  == proj["attack_techniques"]
    assert e.privilege_required == proj["privilege_required"]
    assert e.source_data["GTFOBins"]["raw"]["function"] == "file-write"
    assert e.enrichment.get("capabilities")
    e.validate()


# =========================================================================
# integration — no regression
# =========================================================================
def test_legacy_entries_still_validate():
    r = subprocess.run([sys.executable, "-m", "scripts.validate"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_build_parity():
    before = (ROOT / "site" / "data.json").read_bytes()
    subprocess.run([sys.executable, "-m", "scripts.build_site_data"],
                   cwd=ROOT, check=True)
    after = (ROOT / "site" / "data.json").read_bytes()
    assert after == before
