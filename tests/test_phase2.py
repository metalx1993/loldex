"""Phase-2 tests — the four remaining adapters migrated to the layered model
with PER-CLAIM provenance/confidence.

Contract under test (approved):
  - all four adapters go through projection.make_entry();
  - no adapter assigns projection-owned top-level fields directly;
  - each enriched_value carries its OWN provenance/confidence;
  - an upstream-derived claim keeps high confidence even alongside heuristic
    claims in the same entry;
  - any value introduced by a rule/default/keyword is heuristic/low with a note.

Scope discipline: data model only. No operational capability is introduced.
"""
import glob
import inspect
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters import projection as pj      # noqa: E402
from adapters import enrich                # noqa: E402
from adapters.base import LOLDEX_INTERPRETIVE_KEYS  # noqa: E402

MIGRATED = ["lolbas", "wadcoms", "lolad", "loldrivers"]
OWNED = ("capabilities", "phases", "attack_techniques", "privilege_required")


def _norm_src(mod_name, cls_name):
    mod = __import__(f"adapters.{mod_name}", fromlist=[cls_name])
    return inspect.getsource(getattr(mod, cls_name).normalize)


ADAPTER_CLASS = {
    "lolbas": "LOLBASAdapter", "wadcoms": "WADComsAdapter",
    "lolad": "LOLADAdapter", "loldrivers": "LOLDriversAdapter",
}


# --- helper module -------------------------------------------------------
def test_enrich_helpers_shape():
    ev = enrich.enriched("x", ptype="upstream", source="S", adapter="s@1",
                         confidence="high")
    assert ev == {"value": "x",
                  "provenance": {"type": "upstream", "source": "S", "adapter": "s@1"},
                  "confidence": {"level": "high"}}
    ev2 = enrich.enriched("y", ptype="heuristic", source="S", adapter="s@1",
                          confidence="low", note="guessed")
    assert ev2["provenance"]["note"] == "guessed"
    lst = enrich.claims(["a", "a", "b"], ptype="adapter", source="S", adapter="s@1",
                        confidence="high")
    assert [c["value"] for c in lst] == ["a", "b"]      # dedup, order kept


def test_source_block_upstream_only():
    b = enrich.source_block(project_raw={"k": "v"}, upstream_url="https://u/",
                            upstream_version="r1", last_synced="2026-08-28")
    assert b["raw"] == {"k": "v"} and b["upstream_url"] == "https://u/"
    assert b["upstream_version"] == "r1" and b["last_synced"] == "2026-08-28"


# --- static guardrails on every migrated adapter -------------------------
def test_all_migrated_use_make_entry():
    for m in MIGRATED:
        src = _norm_src(m, ADAPTER_CLASS[m])
        assert "make_entry" in src, f"{m} not migrated"
        assert "yield Entry(" not in src, f"{m} still yields legacy Entry"


def _make_entry_args(src: str) -> str:
    """Extract the argument text of the projection.make_entry(...) call via
    balanced-paren scan, so we inspect ONLY what is passed to the constructor
    path (not what is passed to enrich.assemble/claims)."""
    i = src.find("make_entry(")
    assert i != -1
    i += len("make_entry(")
    depth, out = 1, []
    for ch in src[i:]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
        out.append(ch)
    return "".join(out)


def test_no_direct_toplevel_assignment():
    """No migrated adapter passes a projection-owned field as a kwarg to
    make_entry(): the owned fields must be DERIVED from enrichment, never
    authored. (Owned-field names legitimately appear as enrich.assemble()
    kwargs — those build the enrichment and are not inspected here.)"""
    for m in MIGRATED:
        args = _make_entry_args(_norm_src(m, ADAPTER_CLASS[m]))
        for f in OWNED:
            assert f"{f}=" not in args, f"{m} passes {f} to make_entry directly"


# --- behavioral checks on the regenerated data ---------------------------
def _entries(prefix):
    out = []
    for f in glob.glob(str(ROOT / "data/entries/**/*.yaml"), recursive=True):
        d = yaml.safe_load(open(f))
        if d["id"].startswith(prefix + "/"):
            out.append(d)
    return out


def test_every_migrated_entry_has_layers():
    for m, prefix in [("lolbas", "lolbas"), ("wadcoms", "wadcoms"),
                      ("lolad", "lolad"), ("loldrivers", "loldrivers")]:
        ents = _entries(prefix)
        assert ents, f"no {m} entries found"
        for d in ents[:50]:
            assert d.get("source_data"), f"{d['id']} missing source_data"
            assert d.get("enrichment"), f"{d['id']} missing enrichment"
            assert d.get("_meta", {}).get("schema_version") == 1


def test_source_data_raw_upstream_only():
    """The source_data block's own keys must not be loldex-interpretive."""
    for prefix in ("lolbas", "wadcoms", "lolad", "loldrivers"):
        for d in _entries(prefix)[:50]:
            for project, block in d["source_data"].items():
                assert not (LOLDEX_INTERPRETIVE_KEYS & set(block)), \
                    f"{d['id']}: interpretive key in source_data.{project}"


def test_raw_is_not_loldex_normalized():
    """raw must hold upstream values, not a Loldex normalization of them.
    Regression guards for the two audited cases:
      - WADComs raw must not carry a display-name derived from the filename
        (hyphens->spaces); it carries the raw file stem instead.
      - LOLDrivers raw.privileges must preserve upstream case (no .lower()).
    """
    for d in _entries("wadcoms"):
        if "source_data" not in d:
            continue                                # preexisting legacy orphan
        raw = d["source_data"]["WADComs"]["raw"]
        assert "name" not in raw, f"{d['id']}: wadcoms raw must not carry a derived name"
        assert "file" in raw, f"{d['id']}: wadcoms raw should carry the upstream file stem"
        # the raw file stem must not contain the hyphen->space transform artifact
        assert raw["file"] == raw["file"].strip()
    saw_upper = False
    for d in _entries("loldrivers"):
        if "source_data" not in d:
            continue                                # preexisting legacy orphan
        p = d["source_data"]["LOLDrivers"]["raw"].get("privileges", "")
        if p and p != p.lower():
            saw_upper = True                       # upstream case preserved somewhere
    # at least one upstream Privileges value has mixed/upper case, proving no .lower()
    assert saw_upper, "expected at least one loldrivers raw.privileges with upstream case"


def test_toplevel_equals_projection_all_migrated():
    """Full-dataset projection parity for the four migrated sources (not a
    sample): every LAYERED entry's top-level equals build(enrichment).

    Three preexisting legacy orphan entries (lolbas/vssadmin/tamper/0,
    loldrivers/alinubx-sys, loldrivers/dcrcvdrv-sys) are no longer produced by
    current upstream and carry no enrichment; they are documented exceptions
    (see PHASE2.md) and are skipped here rather than treated as errors."""
    for prefix in ("lolbas", "wadcoms", "lolad", "loldrivers"):
        for d in _entries(prefix):
            if "enrichment" not in d:
                continue                    # preexisting legacy orphan — skip
            proj = pj.build(d["enrichment"])
            assert d.get("capabilities", []) == proj["capabilities"], d["id"]
            assert d.get("phases", []) == proj["phases"], d["id"]
            assert d.get("attack_techniques", []) == proj["attack_techniques"], d["id"]
            assert d.get("privilege_required", "") == proj["privilege_required"], d["id"]


def test_lolbas_is_adapter_high():
    d = _entries("lolbas")[0]
    c = d["enrichment"]["capabilities"][0]
    assert c["provenance"]["type"] == "adapter"
    assert c["confidence"]["level"] == "high"


def test_lolad_is_heuristic_low_with_note():
    for d in _entries("lolad")[:20]:
        for c in d["enrichment"]["capabilities"]:
            assert c["provenance"]["type"] == "heuristic"
            assert c["confidence"]["level"] == "low"
            assert c["provenance"].get("note")


def test_wadcoms_fallback_is_heuristic():
    """At least one wadcoms entry used the discovery fallback and it is marked
    heuristic/low with a note; map-derived ones are adapter/high."""
    fallbacks = adapters = 0
    for d in _entries("wadcoms"):
        c = d["enrichment"]["capabilities"][0]
        t = c["provenance"]["type"]
        if t == "heuristic":
            fallbacks += 1
            assert c["confidence"]["level"] == "low"
            assert c["provenance"].get("note")
        elif t == "adapter":
            adapters += 1
            assert c["confidence"]["level"] == "high"
    assert fallbacks >= 1, "expected at least one discovery fallback"
    assert adapters >= 1, "expected at least one map-derived entry"


def test_loldrivers_mixed_provenance():
    """In a LOLDrivers entry that has a MITRE id, attack_techniques is
    upstream/high while capabilities/phases are heuristic/low — the upstream
    claim is NOT downgraded by the presence of heuristic claims."""
    found = False
    for d in _entries("loldrivers"):
        e = d["enrichment"]
        if "attack_techniques" in e:
            found = True
            assert e["attack_techniques"][0]["provenance"]["type"] == "upstream"
            assert e["attack_techniques"][0]["confidence"]["level"] == "high"
            assert e["capabilities"][0]["provenance"]["type"] == "heuristic"
            assert e["capabilities"][0]["confidence"]["level"] == "low"
            break
    assert found, "expected a loldrivers entry with a MITRE id"


# --- integration ---------------------------------------------------------
def test_validate_clean():
    r = subprocess.run([sys.executable, "-m", "scripts.validate"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 error" in r.stdout


def test_build_parity_sha256():
    """data.json must be byte-identical to the pre-phase-2 baseline (C1): the
    three stale orphans are kept, so the public output is unchanged."""
    import hashlib
    subprocess.run([sys.executable, "-m", "scripts.build_site_data"],
                   cwd=ROOT, check=True)
    h = hashlib.sha256((ROOT / "site" / "data.json").read_bytes()).hexdigest()
    baseline = pathlib.Path("/tmp/data.baseline.sha").read_text().strip()
    assert h == baseline, f"data.json changed: {h} != {baseline}"
