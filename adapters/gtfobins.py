"""GTFOBins adapter.

Maps GTFOBins (_gtfobins/*.md YAML frontmatter) into canonical entries.

GTFOBins models two axes we map onto the schema:
  - `functions`  -> capability   (shell, file-read, download, ...)
  - `contexts`   -> privilege     (sudo, suid, capabilities, unprivileged)

One canonical entry is emitted per (binary, function, context) so that a query
like `--priv sudo` filters correctly. This is a first-pass mapping; refine the
tables below as the taxonomy evolves.

Licence note: GTFOBins content is redistributed under its own licence — verify
LICENSE in the upstream repo before publishing derived data.
"""

from __future__ import annotations
import pathlib
import subprocess
from typing import Iterable

import yaml

from .base import Adapter, Entry

GTFOBINS_REPO = "https://github.com/GTFOBins/GTFOBins.github.io.git"

# GTFOBins function name -> our capability
FUNCTION_CAP = {
    "shell": "shell",
    "command": "command-execution",
    "reverse-shell": "reverse-shell",
    "non-interactive-reverse-shell": "reverse-shell",
    "bind-shell": "bind-shell",
    "non-interactive-bind-shell": "bind-shell",
    "file-read": "file-read",
    "file-write": "file-write",
    "download": "file-download",
    "upload": "file-upload",
    "library-load": "library-load",
    # some binaries list the vector as a function (older style)
    "sudo": "privilege-escalation",
    "suid": "privilege-escalation",
    "capabilities": "privilege-escalation",
    "limited-suid": "privilege-escalation",
}

# GTFOBins context -> our privilege
CONTEXT_PRIV = {
    "sudo": "sudo",
    "suid": "suid",
    "limited-suid": "suid",
    "capabilities": "capability",
    "unprivileged": "user",
}

# capability -> default kill-chain phase(s)
CAP_PHASE = {
    "shell": ["execution"],
    "command-execution": ["execution"],
    "reverse-shell": ["execution", "command-and-control"],
    "bind-shell": ["execution", "command-and-control"],
    "file-read": ["collection"],
    "file-write": ["persistence"],
    "file-download": ["command-and-control"],
    "file-upload": ["exfiltration"],
    "library-load": ["execution", "persistence"],
    "privilege-escalation": ["privilege-escalation"],
}


class GTFOBinsAdapter(Adapter):
    source_name = "GTFOBins"
    platform = "linux"
    upstream_url = "https://gtfobins.github.io"
    license = "MIT (verify upstream LICENSE)"

    def __init__(self, clone_dir: pathlib.Path | None = None):
        self.clone_dir = clone_dir or pathlib.Path("/tmp/gtfobins_src")

    def fetch(self):
        if not (self.clone_dir / "_gtfobins").exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", GTFOBINS_REPO, str(self.clone_dir)],
                check=True, capture_output=True,
            )
        rev = subprocess.run(
            ["git", "-C", str(self.clone_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        files = sorted((self.clone_dir / "_gtfobins").glob("*"))
        return {"rev": rev, "files": files}

    @staticmethod
    def _frontmatter(path: pathlib.Path) -> dict | None:
        text = path.read_text(encoding="utf-8", errors="replace")
        # frontmatter is the YAML between the first pair of --- fences (or whole file)
        parts = text.split("---")
        chunk = parts[1] if len(parts) >= 3 and parts[0].strip() == "" else text
        try:
            data = yaml.safe_load(chunk)
        except yaml.YAMLError:
            return None
        return data if isinstance(data, dict) else None

    def normalize(self, raw) -> Iterable[Entry]:
        src = self.source_stub(upstream_version=raw["rev"])
        for path in raw["files"]:
            name = path.name
            data = self._frontmatter(path)
            if not data or "functions" not in data:
                continue
            for func_name, code_entries in (data["functions"] or {}).items():
                cap = FUNCTION_CAP.get(func_name)
                if cap is None:
                    continue
                # context -> list of {code, comment}
                per_ctx: dict[str, list[dict]] = {}
                for ce in (code_entries or []):
                    base_code = (ce.get("code") or "").strip()
                    comment = (ce.get("comment") or "").strip() or None
                    ctxs = ce.get("contexts") or {"unprivileged": None}
                    for ctx_name, ctx_val in ctxs.items():
                        code = base_code
                        if isinstance(ctx_val, dict) and ctx_val.get("code"):
                            code = ctx_val["code"].strip()
                        if not code:
                            continue
                        per_ctx.setdefault(ctx_name, []).append(
                            {"template": code, "comment": comment}
                        )
                for ctx_name, cmds in per_ctx.items():
                    priv = CONTEXT_PRIV.get(ctx_name, "user")
                    phases = list(CAP_PHASE.get(cap, ["execution"]))
                    if priv in ("sudo", "suid", "capability") and "privilege-escalation" not in phases:
                        phases.append("privilege-escalation")
                    yield Entry(
                        id=f"gtfobins/{name}/{func_name}/{ctx_name}",
                        type="binary",
                        platform="linux",
                        name=name,
                        phases=phases,
                        capabilities=[cap],
                        privilege_required=priv,
                        commands=[{k: v for k, v in c.items() if v} for c in cmds],
                        sources=[src],
                        references=[f"{self.upstream_url}/gtfobins/{name}/"],
                        tags=["linux", "unix", "gtfobins"],
                    )
