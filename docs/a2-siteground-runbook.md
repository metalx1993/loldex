# A2 — SiteGround operator runbook

Current decision: **DO NOT ENABLE CRON.** Local protocol tests do not certify a
live SiteGround deployment. This runbook prepares a concrete next operation;
commands below use placeholders; actual isolated host evidence is recorded at
the end. Root production migration is a separate operation.

## Access and setup

SiteGround exposes shell keys in **Site Tools → Devs → SSH Keys Manager**. Import
an existing public key or create a dedicated pair through your approved process.
Keep private keys/passphrases out of chat, Git, site files and release artifacts.
Read username/hostname/port under SSH Credentials and verify the host fingerprint
through a trusted channel. SiteGround documents port 18765; use account settings
as authority rather than assuming the path/username/port.

Official instructions:
https://www.siteground.com/tutorials/ssh/enable-ssh
https://www.siteground.com/kb/access-site-ssh-connection/

Confirm Python >=3.9, PHP enabled and the real public_html path on this account.
Install deployment/ plus scripts/deploy_release.py and scripts/__init__.py in a
private tools directory outside public_html. These host-side modules use standard
Python libraries; source-health preparation additionally needs the project's
existing PyYAML. Do not upload .git, private keys or control state into webroot.

Example layout (replace with the actual canonical account paths):

```
/home/customer/www/loldex.sh/
    public_html/releases/<release_id>/   immutable complete site versions
    loldex-control/active.json            sole private publication authority
    loldex-control/.publish.lock          stable lock inode
    loldex-control/tools/                 private publisher code
```

## Local package

Choose a reviewed committed SHA. The packager intentionally ignores dirty files;
uncommitted fixes therefore must be committed before a production package.

```sh
python3 -m scripts.package_release --repo . --commit <FULL_COMMIT_SHA> --out work/release.tar.gz
```

Record the printed release ID and package hash via a trusted channel. Transfer
into a private destination inbox using authenticated SSH/SFTP with pinned host
identity. A truncated upload may exist there; it cannot authorize activation.
No FTP-to-public_html synchronization step is part of A2.

## Destination probe, install, verify

Run from the private tools directory on the destination, substituting real paths:

```sh
python3 -m scripts.deploy_release --public-root <PUBLIC_REAL_PATH> --control-root <PRIVATE_CONTROL_REAL_PATH> probe
python3 -m scripts.deploy_release --public-root <PUBLIC_REAL_PATH> --control-root <PRIVATE_CONTROL_REAL_PATH> install <PRIVATE_ARCHIVE_PATH>
python3 -m scripts.deploy_release --public-root <PUBLIC_REAL_PATH> --control-root <PRIVATE_CONTROL_REAL_PATH> verify <EXPECTED_RELEASE_ID>
python3 -m scripts.deploy_release --public-root <PUBLIC_REAL_PATH> --control-root <PRIVATE_CONTROL_REAL_PATH> status > expected-token.json
```

Check that installed ID equals the approved local ID. The probe explicitly reports
http_verified=false and cron_ready=false: it checks filesystem primitives only.
A second install of the exact same intact release is safe; an altered existing
release is rejected. Never manually edit installed immutable files.

## Initial bootstrap and production check

Before the first migration, back up the existing root .htaccess and entry files.
Plan the legacy-cache transition explicitly. Stage deployment/siteground/
loldex-router.php at root and use bootstrap.htaccess as the reviewed root routing
configuration; do not replace the per-release site/.htaccess with that bootstrap.
Control directory must match the router's private sibling location. Verify ACME
renewal, PHP execution, no-store redirects, existing hosting caches and release
file access on a non-public staging domain first. Bootstrap installation itself
is a separately controlled initial host change, not a claim of atomic FTP upload.

After approval, on the server:

```sh
python3 -m scripts.deploy_release --public-root <PUBLIC_REAL_PATH> --control-root <PRIVATE_CONTROL_REAL_PATH> activate <EXPECTED_RELEASE_ID> --expected-token expected-token.json
```

Keep the returned token. Verify root307/no-store to that exact version, relative
assets/JSON, API queries, public content and the previous release's URLs. Contact
checks inspect307 without submitting/following a real message. No expected-token
refresh may be hidden inside a retry after conflict.

To roll back, read status into a NEW expected-token file, explicitly choose the
previous approved release and call rollback with that token. A rollback increments
generation; it never restores an old token. Preserve releases; no automatic GC.

Simulate truncated private archive upload and injected pre-switch failure: active
must stay unchanged. Exercise stale concurrent publisher refusal and rollback on
this host. If a post-rename durability error occurs, inspect actual status before
acting: the new release may already be authoritative.

## Scheduling gate

Only after the above remote evidence AND real verified source/retention workflow
are reviewed can the cron proposal be enabled. Current sync.yml is intentionally
manual and legacy; this A2 work does not alter that fact. The operator will receive
an explicit go/no-go decision based on observed results, not merely test counts.

### Verified host update — 13 November 2026

SSH is now configured and private filesystem/concurrency/rollback tests passed
on the actual destination. Isolated HTTPS switching and rollback also passed.
SiteGround bypasses `.htaccess` for an existing static file: moving legacy root
files aside is mandatory, not optional. Use `deployment.bootstrap.bootstrap`
with the exact reviewed inventory, an exclusive private backup destination and
an already verified/activated release. Keep the backup for explicit root restore.
Never leave root `index.html`, `data.json` or other old static assets alongside
this router. A release's own files stay under `/releases/<id>/`.

### Root migration performed

The 12 reviewed legacy root files were moved to the private
`loldex-control/legacy-backup-20261113` directory with their SHA-256 inventory.
Initial active release: `r-ab429b0b7a4b1d72d47c2e8c55c9ea58992335674e0fe31acf288fe61a9fc3c3`,
commit `140ecb96cfc2593d568b25e6c5c471ab12ad15e8`, generation 1.
The old root homepage remained in SiteGround dynamic cache until an explicitly
user-authorized purge in Site Tools. The UI confirmed success; subsequent plain
root HTTPS requests return 307/no-store to the expected immutable release.
Root index/data/API requests also route to that same release. A hosting rule
returns 403 for `build-manifest.json`; it is verified over SSH and is not a
runtime dependency. The 20 other public static files matched package bytes.

### Optional credential-free host publication job (not scheduled)

Install trusted `deployment` modules into a private tools directory. Create a
private bare Git cache outside public_html. From the trusted tools directory:

```sh
python3 -m deployment.pull --repo <PRIVATE_BARE_CACHE> \
  --public-root <CANONICAL_PUBLIC_ROOT> --control-root <PRIVATE_CONTROL_ROOT>
```

The publisher fetches only the fixed public LOLDEX GitHub main via HTTPS,
packages verified committed site objects, rechecks main before installation,
then activates under the token captured before acquisition. It never executes
fetched code, never refreshes a failed CAS silently, and needs no GitHub token or
SSH private key on a GitHub runner. This host job publishes already committed
site data; the separate verified GitHub workflow refreshes upstream sources.
Both must be tested manually before scheduling them. Installing this module
does not install a cron entry.
