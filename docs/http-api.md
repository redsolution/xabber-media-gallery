# HTTP API reference

[Project home](../README.md) · [Documentation](README.md) · [Installation](installation.md) · [Client protocol](client-protocol.md) · [HTTP API](http-api.md) · [Operations](operations.md)

---

Look up routes, authentication requirements, request fields, response formats, and errors.

Default prefix: `https://gallery.example.com/api/v1/`. All routes below are relative
to that prefix and retain their trailing slash. Send JSON for non-upload request
bodies and multipart form data for uploads. Authenticated requests use
`Authorization: Bearer <token>`; many views also accept Django admin session auth.

### On this page

- [Client endpoints](#client-endpoints)
- [Administration endpoints](#administration-endpoints)
- [Errors and limits](#errors-and-limits)
- [Source of truth](#source-of-truth)

---

## Client endpoints

| Method | Route | Authentication | Purpose |
| --- | --- | --- | --- |
| POST | `account/xmpp_code_request/` | None | Send a code through XMPP |
| POST | `account/xmpp_auth/` | None | Exchange a code for a token |
| GET | `files/slot/` | User | Quota/deduplication check; may create a file record |
| POST | `files/upload/` | User | Upload a file |
| GET | `files/` | User | List user's file records |
| DELETE | `files/` | User | Delete selected file records |
| GET | `files/stats/` | User | Usage breakdown and quota |
| GET, DELETE | `files/percent/<int:percent>/` | User | Select/remove files to reach a free-space target |
| GET, DELETE | `account/tokens/` | User | Token management; see ownership limitation below |
| DELETE | `account/` | Token or code | Delete a gallery account; see limitation below |
| POST | `opengraph/` | None | Fetch a URL's Open Graph metadata |

`User` means an authenticated gallery user. Requests targeting another JID may
also require a scoped token; a scope is configured administratively, not granted
by the ordinary authentication exchange.

### Authentication

- Code request: required `jid` (full JID accepted), optional `type` (`iq` or
  `message`, default `message`). Returns HTTP 201 with `request_id` and `api_jid`.
- Code exchange: required `jid` (**bare JID**) and integer `code`; optional `client`
  and `device`. Returns HTTP 201 with `token` and `expires`.
- Codes default to a 90-second lifetime. Tokens default to 24 hours; expiry cleanup
  must be scheduled. No token refresh operation exists.

See [the verification stanza and complete exchange](client-protocol.md).

### Slot and upload

`GET files/slot/` requires `name`, `size` (bytes), and `hash` (SHA-1 hex). HTTP 200
returns either `{ "quota": 104857600, "used": 0 }` for absent content or a full
file response for deduplicated content. The latter creates a new per-user file
record, public link, and quota usage. It does not reserve a future upload.

`POST files/upload/` accepts:

| Field | Required | Meaning |
| --- | --- | --- |
| `file` | Yes | Binary multipart file |
| `size` | No | Actual byte size; omitted/zero is derived from the saved file |
| `media_type` | No* | MIME type used for media processing |
| `context` | No | `file` (default), `avatar`, `voice`, `gif`, or `call` |
| `metadata` | No | JSON metadata stored with the user's file record |
| `create_thumbnails` | No | Default true; controls avatar variant generation |

*Supply an image MIME type for avatars. Ordinary image/video thumbnail work is
started whenever a relevant `media_type` is present; `create_thumbnails=false`
does not disable all thumbnail processing.*

Returns HTTP 201. File responses include `id`, `size`, `media_type`, `name`,
`slot_id`, `created_at`, `file`, `hash`, `used`, `quota`, and `context`. Optional
fields include `metadata`, `thumbnail`, and `thumbnails`. `slot_id` is the public
link title, not a presigned upload credential. Clients should use returned URLs
rather than reconstructing paths. Thumbnail URLs may precede completed generation.

### Listing and deletion

`GET files/` accepts `id`, `date_gte`, `date_lte`, `size_gte`, `size_lte`, `type`
(or `media_type`), and repeated `contexts` query parameters (default `file`).
`type=file` excludes image/video/voice/audio MIME categories. `order_by` is the
configured ordering parameter. Optional `jid` targets another account and requires
appropriate scope when different from the authenticated user.

Pagination uses `page` and `obj_per_page` (default 50):

```json
{"total_pages":1,"total_objects":1,"obj_per_page":50,"items":[{"id":42,"name":"hello.txt"}]}
```

The item above is abbreviated; listings include file metadata and URLs, but not
the upload response's top-level `used` and `quota` fields.

`DELETE files/` accepts a JSON body with `id` or `file` (returned public URL), or
selection filters including `contexts`, `media_type`, `date_gte`, and `date_lte`.
`contexts` must be an array. With ID/URL selection the implementation does not
apply context filtering. Prefer a single explicit `id` to avoid broad deletion.
Success is HTTP 204; no matching files produces HTTP 404.

`files/percent/<int:percent>/` selects oldest files until the requested free-space
target is reached, placing avatars last. GET previews the selection; DELETE
removes it. This route does not implement the ordinary list's full filter set.
Preview and confirm the selected records before destructive use.

### Statistics

`GET files/stats/` returns `images`, `avatars`, `videos`, `voices`, `audio`, `files`,
and `total` objects with `count` and `used`, plus a numeric `quota`. Optional filters
include dates, file ID, media type, and target JID. Do not use its `host` parameter
as a trusted tenant-isolation boundary; review authorization for your deployment.

### Sensitive/optional endpoints

- `account/tokens/`: DELETE takes `token_id`. The current queryset is not scoped
  to the caller. Restrict this route until token ownership checks are added.
- `account/`: deletes the gallery user and related data, not the XMPP account.
  The code-based deletion path does not perform the expiry check used by login.
  Disable or restrict this route until that behavior is reviewed.
- `opengraph/`: POST `{ "url": "https://example.com/" }` returns HTTP 201 with
  `ogp` HTML or an error. This unauthenticated server-side URL fetcher needs an
  outbound-network policy; disable it if unused.

## Administration endpoints

These require an authenticated Django staff user. Cross-user/domain operations
may additionally require the appropriate token scope. Use the Django admin at
`/admin/` for initial configuration; do not assume staff session authentication
satisfies token-scope checks on every API operation.

| Method | Route | Main parameters / result |
| --- | --- | --- |
| GET, PUT | `account/quota/` | Optional `jid`; PUT `value` in bytes; returns `quota`, `used` |
| GET, POST | `account/default_quota/` | `host`; POST `size` for domain default |
| GET | `account/list/` | Required `vhost`; account quota/usage listing |
| GET, POST | `whitelist/` | `host`, `users` array, `all_users` |
| GET, POST | `blacklist/` | `host`, `users` array, `all_users` |
| GET | `disk/space/` | `disk_total`, `disk_used`, `disk_free` for `/` |

Administrative token scopes can be `global`, a domain, or a comma-separated list
of domains/JIDs. The scope parser has implementation-specific behavior; validate
your exact scope and target combination rather than treating this as a general
OAuth scope system. `disk/space/` measures `/`, which may differ from the upload
volume. A zero quota value falls back to a domain/default quota, rather than
representing a zero-byte allowance.

## Errors and limits

Validation errors commonly return JSON like:

```json
{"status":403,"error":"Quota exceeded"}
```

**Check both HTTP status and body.** The custom quota, upload-size, and transfer-rate
exceptions currently use HTTP **400**, while their JSON `status` values may be 403,
413, or 429 respectively. A proxy can separately return HTTP 413 for its body limit.
Invalid tokens normally return HTTP 401, access denial 403, and missing/expired
verification codes 404. Do not assume every error uses the same JSON shape.

Defaults: 30 MiB per file, 100 MiB per user, 1 MiB quota oversize setting, and upload
counter settings `FILES_LIMIT=10`, `TIME_WINDOW=10`. These are implemented by the
custom upload handler/cache, not a complete global API rate limiter. Quota checks
use a strict less-than comparison, so a file exactly filling remaining quota may
be rejected. See [Operations](operations.md) for deployment constraints.

## Source of truth

- [URL routing](../gallery/api/urls.py)
- [Views and permission declarations](../gallery/api/views.py)
- [Request/response serializers](../gallery/api/serializers.py)
- [Upload response construction](../gallery/api/utils/responses.py)
- [Default settings](../gallery/generic_settings.py)

This reference describes current behavior; it does not imply every exposed route
has been audited for public multi-tenant deployment.

---

[Project home](../README.md) · [Documentation](README.md) · [Installation](installation.md) · [Client protocol](client-protocol.md) · [HTTP API](http-api.md) · [Operations](operations.md)
