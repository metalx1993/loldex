# Security hardening delivery — 15 November 2026

This implements defence-in-depth recommendations from the independent audit.
It does not convert robustness findings into confirmed intrusions or change the
frozen CORE/D1 specification. Public knowledge APIs remain public and read-only.

## Delivered behaviour

- Contact accepts only bounded JSON/string or URL-encoded fields: body 16 KiB,
  name 120 bytes, email 254 bytes, message 8,000 bytes. Invalid UTF-8, unexpected
  fields, decoded duplicate keys, arrays, control/header injection and malformed
  body lengths are rejected before mail. Reply-To contains only the validated
  email. Recipients/subject/From are fixed; errors expose no filesystem details.
- Legacy PHP API validates bounded scalar parameters, decoded duplicates,
  methods and pagination; valid responses stay compatible. GET/HEAD/OPTIONS,
  generic error envelopes, no-store and Retry-After are explicit. V1 retains its
  release/manifest-bound semantics and shares the request-admission guard.
- Shared private quotas: API 120 admissions per client per 60 seconds and 3,000
  globally per 60 seconds; contact 3 per client per 900 seconds and 30 globally
  per hour. These are fixed windows, not sliding windows. Admission is persisted
  before a mail attempt; failed sends also consume admission. Honeypot requests
  cannot send mail. OPTIONS and rejected methods do not consume API admission.
- Client identity uses normalized REMOTE_ADDR with HMAC; forwarded headers cannot
  select an identity. The proxy must supply the actual peer address through its
  trusted server configuration. No raw client addresses are stored by this guard.
  API and contact share bounded state across retained immutable releases. At most
  1,024 active client buckets and 256 KiB state; new clients are refused when full.
  A stable lock, 250 ms contention deadline, private 0700/0600 permissions and
  atomic state replacement prevent lost updates; corrupt/unavailable state fails
  closed. These application quotas do not replace provider traffic filtering.
- All HTML uses a restrictive meta CSP and referrer policy. Contact JavaScript
  and CSS are external same-origin assets; no inline-script/style exception is
  needed. PHP JSON responses and both Apache configurations also supply defensive
  response headers, including frame restrictions. Meta CSP cannot enforce
  frame-ancestors and does not replace response headers: see the host gate below.
- A stable retained-release PHP bridge is supplied separately from immutable
  site payloads. Old API endpoints keep their old dataset/release identity but
  receive shared admission, strict queries and integrity checks. Old mail handlers
  are never executed: contact is redirected only to a verified guarded active
  release; rollback to an unguarded release fails503 instead of looping. New
  guarded endpoints are dispatched without duplicate admission. The root rewrite
  must intercept dynamic paths before release passthrough; MultiViews and PATH_INFO
  are disabled. This requires the host installation below; a GitHub push alone
  does not protect historical endpoints.
- All five deprecated adapter fetch methods now fail closed and direct callers
  to scripts.verified_refresh. Their normalize methods remain available. Shared
  implicit /tmp clones cannot be silently used as verified acquisition.
- Operational D2 YAML preflight counts repeated alias/merge occurrences before
  construction and rejects excessive nodes, depth, conservative expanded bytes
  or huge integers. No truncation or confidence/provenance reinterpretation.
  Frozen CORE canonical semantics are unchanged.
- Historical Cloudflare Worker: strict requests, generic failures, 16 MiB streamed
  catalogue cap, 10-second deadline, one concurrent loading promise and bounded
  same-origin A2 redirect handling. It remains inactive and is not a SiteGround
  deployment component. Future activation has a separate toolchain/staging gate.
- PHP test runtime has an exact npm graph/integrity lock and npm ci; CI Python
  dependencies have a separate exact hash lock. GitHub credentials are supplied
  through an ephemeral askpass helper, never persisted in a remote URL or passed
  in Git process arguments. Existing unchanged-base/non-force controls remain.

## Verification and independent corrections

Independent agents exercised malformed and duplicate requests, spoofed addresses,
IPv6 spellings, shared cross-release quotas, bad state, alias/merge amplification,
large integers and Worker upstream/error paths. Review found and fixed transient
state-file validation before locking, a valid A2 redirect regression and empty
CLI DOCUMENT_ROOT handling. PHP warnings are converted to generic endpoint errors.

Native SiteGround PHP 8.2.35 CLI verification passed with private disposable
fixtures: 20 concurrent same-client contact admissions gave exactly 3 success and
17 refusals; 40 concurrent admissions across 20 clients gave exactly 30 success
and 10 global refusals. Private file creation, persisted totals, lock deadline and
corrupt-state refusal passed. The fixture sent no mail and made no HTTP requests.
The permanent sibling rate-limits directory was prepared privately with mode0700.

Browser regression passed with CSP active, search/evidence/technique pages and
320px layouts. Unsafe references were tested on the entry page which actually
creates source anchors; a valid HTTPS reference remained usable. All 817 original
raw evidence documents retained identical canonical representations in a
read-only comparison. The original corpus and its data projections are unchanged; only generated OpenAPI and its build-manifest digest change to document 429/503 admission responses.

Full regression baseline: **962 passed in 722.76 seconds**. Subsequent targeted
**45 final targeted checks passed in 6.66 seconds**, covering the final retained-release
bridge, updated metadata, both API generations and dependency lock. Final collection
contains 969 tests; the late additions were exercised by those targeted checks. The read-only quality report passed for
3,336 entries and 3,345 generated files, with a stable 3,341-file input fingerprint
`6cdda8f7cab6613409ecf27c1ddaf655cdfb34ab5a8e9f5d90e0a8e9ae39e015`.
Publication receipt is kept outside the committed payload to avoid self-reference. No Strix scan, DDoS test or real contact-mail delivery is claimed.

## What is published to loldex.sh

Use the existing A2 publisher from the reviewed GitHub commit. It packages the
complete committed site/ into one immutable release, verifies it and changes the
active pointer. Do not overwrite installed immutable files or mix individual FTP
updates. In particular, contact.php and both APIs require request-guard.php, and
contact.html requires its new contact.css/contact.js; publish them together with
all existing data, evidence, manifest and static assets.

A local archive can also be built from the committed revision with:

```
python3 -m scripts.package_release --repo . --commit <REVIEWED_SHA> --out work/security-release.tar.gz
```

The archive belongs in a private inbox and follows the existing A2 install/verify/
activate procedure. The private rate state, key, SSH keys, work/, tests/, source
repositories and .git must never be placed in public_html. The new key is local
limiter state, unrelated to SSH. Do not copy or publish it.

The installed trusted private publisher can additionally receive the reviewed
update to deployment/package.py, which requires the guard, legacy API and contact
assets in production releases. It must stay outside public_html. Existing trusted
publisher code already packages every site/ blob; this update tightens validation.

## Host dynamic-endpoint installation gate

A complete SiteGround installation contains both the A2 site release and the
stable bridge. Merely publishing the release leaves pre-hardening retained PHP
endpoints outside the new admission checks. Install in this order:

1. Publish/verify the new complete A2 release with request-guard.php present.
2. Back up existing root .htaccess and loldex-router.php privately. Install the
   exact reviewed site/request-guard.php at private
   loldex-control/tools/security/request-guard.php (directories0700, file0600).
   Keep the existing shared loldex-control/rate-limits directory0700.
3. Install deployment/siteground/loldex-retained.php and loldex-router.php at the
   public_html root, with ordinary public script permissions0644. They expose no
   upload/admin capability; the retained bridge accepts only fixed PHP endpoints.
4. Install deployment/siteground/bootstrap.htaccess as public_html/.htaccess
   last, preserving its routing and ACME exception. Use a same-directory temporary
   file and atomic rename for each root update. No retained release is edited.
5. Verify a known old and the new versioned API still report their own release/
   dataset identities, and that legacy pretty/query routes, HEAD and OPTIONS work.
   Verify a POST with an invalid body to an old contact path reaches only the
   hardened active endpoint; do not send an actual message. Confirm denied/admitted
   calls use shared private state and that rollback to an old unguarded contact
   fails503 rather than looping. Do not exhaust real production quotas as a test.

The direct interpreter tests prove bridge dispatch and prior/current API behaviour;
they do not certify provider rewrite execution. Confirm Apache normalization,
extensionless requests, PATH_INFO, encoded paths and non-public helper access on
the real server after installation. Verify trusted proxy handling leaves the
actual visitor in REMOTE_ADDR; do not trust arbitrary forwarded headers.

## Host response-header gate (separate from GitHub upload)

The audit observed SiteGround Nginx serving static HTML without the Apache
headers. Uploading .htaccess alone cannot demonstrate this gate is complete.
After the new immutable release exists:

1. Preserve the current root routing configuration privately. The reviewed
   deployment/siteground/bootstrap.htaccess is the root public_html/.htaccess;
   site/.htaccess belongs inside the release. Never swap their roles.
2. Have SiteGround apply equivalent headers in Nginx, or disable NGINX Direct
   Delivery for loldex.sh in Site Tools → Speed → Caching → NGINX Direct Delivery
   so Apache rules apply. Preserve unrelated domains/settings.
3. Check real HTTPS GET/HEAD responses for root redirect, release index.html,
   contact.html, API JSON and 4xx responses. Expect nosniff, DENY, referrer policy,
   permissions restrictions and CSP with frame-ancestors 'none'. Check HSTS on
   HTTPS; it has no includeSubDomains or preload commitment. Confirm every
   page/script/style still loads and existing 307/no-store routing is preserved.
4. Confirm web PHP can use the private shared rate directory and that responses
   do not come from a cache bypassing admission. Use a safe invalid request or
   empty-body contact rejection, without sending an actual message or triggering
   production quotas. Do not claim mail delivery from this check.

Official provider reference:
https://www.siteground.com/kb/cross-origin-resource-sharing-cors/
https://www.siteground.com/tutorials/supercacher/nginx-direct-delivery/

If Nginx configuration cannot be changed yet, meta CSP/referrer and PHP headers
still ship, but the full static response-header gate remains pending. No new
Cloudflare service, hostname, paid scanner or cronjob is enabled by this delivery.
The already configured cron schedules and pending scheduled-cycle acceptance
remain described in docs/cron-activation.md.
