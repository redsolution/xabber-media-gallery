# Operations and troubleshooting

[Back to README](../README.md) · [Installation](installation.md)

## Configuration defaults

Override these in your ignored `gallery/settings.py` as needed:

| Setting | Default | Meaning |
| --- | --- | --- |
| `VERIFICATION_CODE_LIFETIME` | 90 seconds | Login code lifetime |
| `TOKEN_LIFETIME` | 86400 seconds | Stored token expiration |
| `MAX_FILE_SIZE` | 31457280 bytes | 30 MiB file limit |
| `DEFAULT_QUOTA_SIZE` | 104857600 bytes | 100 MiB fallback user quota |
| `DEFAULT_QUOTA_OVERSIZE` | 1048576 bytes | Upload-handler quota margin |
| `FILES_LIMIT` / `TIME_WINDOW` | 10 / 10 seconds | Cached transfer counter settings |
| `DEFAULT_THUMB_SIZE` | 256 | Square standard thumbnail size |
| `MAX_AVATAR_SIZE` | 1536 | Avatar size setting |
| `THUMBS_SIZE_LIST` | 32–768 | Configured avatar variant sizes |

If overriding `DEFAULT_THUMB_SIZE`, also update `DEFAULT_THUMB_SIZE_TUPLE` because
it is derived while importing the defaults. Keep reverse-proxy upload limits above
`MAX_FILE_SIZE` to account for multipart overhead. Check disk space on the actual
`MEDIA_ROOT` volume, not only the API's root-filesystem disk report.

## Expiration cleanup

Despite its name, `delete_expired_codes` removes both expired verification codes
and expired tokens:

```sh
/srv/xabber-media-gallery/.venv/bin/python /srv/xabber-media-gallery/manage.py delete_expired_codes
```

Run it regularly (for example, once per minute) using a timer or scheduler as the
application user, with the same environment file and working directory as the
service. A systemd timer invoking a separate oneshot service with `User=gallery`,
`WorkingDirectory`, and `EnvironmentFile` matching the main unit is one option.
Monitor execution and logs: the command catches exceptions and prints them, so an
exit status alone does not prove cleanup succeeded.

The login endpoint checks verification-code expiry directly. The bearer-token
authentication class does **not** check the stored `expires` timestamp on each
request; token expiration currently depends on deletion by this cleanup command.
Clients should still honor the returned expiry. Strict immediate server-side
expiration requires an authentication change, not just a shorter timer interval.

## Storage and backups

- Back up the database and all of `MEDIA_ROOT` consistently. With the default SQLite
  database, stop writes or use a SQLite-aware backup rather than copying a live DB blindly.
- Preserve symlinks as links. They contain absolute targets, so restoring to a new
  filesystem path requires repairing links or preserving the original absolute path.
- Keep originals, thumbnails, and symlinks together. Do not remove an original
  just because one user's link is deleted: content can be shared by multiple records.
- Back up deployment settings/secrets separately in appropriate secret storage.
- Before an upgrade, save the current Git revision and resolved dependency versions,
  take a backup, review migrations, and test the upgrade on a restored copy.

Thumbnails and orphan cleanup run in in-process threads. They are not durable jobs:
worker restarts may interrupt them. There is no bundled reconciliation or thumbnail
rebuild command. Monitor missing thumbnails and errors rather than assuming returned
URLs prove processing completed.

## Schema and framework checks

On the current source, `makemigrations --check --dry-run` reports pending model
changes for `MediaFile.context`, `Token.key`, and `Token.scope`. These predate the
documentation setup; the supplied migrations can still be applied to an empty
database. Review and commit the intended schema migration as a separate code
change before adopting a strict migration-clean CI gate. Do not silently generate
and apply unreviewed migrations to an existing production database.

Django also warns that `django_jsonfield_backport` is redundant on Django 3.2.
The example explicitly retains `AutoField` primary keys to match existing schema.

## Public deployment limitations

These are current implementation constraints relevant to operators, not guarantees
of a completed security audit:

- **Legacy dependencies:** the requirements target Django 3.2/DRF 3.12 or earlier,
  use upper bounds rather than a lockfile, and fetch an unpinned Git dependency.
  Upgrade/review the stack and record resolved versions before a public launch.
- **Public downloads:** the Nginx media path has no account authorization. Anyone
  holding a file URL can access it. Treat URLs as shareable links; there are no
  expiring download signatures or built-in end-to-end encryption.
- **Token ownership:** token listing/deletion views use an unfiltered token queryset.
  Restrict `/api/v1/account/tokens/` until owner filtering is implemented.
- **Account deletion:** its code-based path does not check code expiry. Restrict
  `/api/v1/account/` until authentication and deletion semantics are reviewed.
- **Outbound URL fetching:** `/api/v1/opengraph/` is unauthenticated and fetches
  supplied URLs server-side. Disable it if unnecessary, or enforce an outbound
  policy preventing access to internal services and sensitive network endpoints.
- **Tenant authorization:** review administrative scopes and host-wide statistics
  before offering shared hosting. A staff flag or domain parameter alone should
  not be treated as proof of tenant isolation.
- **Admission:** accounts are permitted by default unless access-list rules reject
  them. A whitelist row with no users does not implement a global deny-by-default
  policy, nor does a whitelist for one domain exclude every other domain.
- **Request abuse:** the upload cache counter does not rate-limit login requests,
  code delivery threads, or all API endpoints. Add appropriate proxy rate limits.

Keep Memcached private, use a unique Django secret with `DEBUG=False`, and expose
only the intended media directory. Serve user media from a dedicated origin,
without application session cookies. The Nginx example forces downloads and disables
MIME sniffing. Restrict administration to trusted operators using your existing
network/access policy. These deployment controls do not replace fixes to application
authorization or the legacy dependency stack.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `No module named gallery.settings` | Copy `examples/settings.py` to `gallery/settings.py` |
| Missing `GALLERY_*` / `KeyError` | Supply the required environment to both service and management commands |
| HTTP 400 / invalid host | Match `GALLERY_ALLOWED_HOSTS` to the actual HTTP hostname |
| Code request succeeds, no XMPP stanza | Service credentials, DNS/connectivity, server routing policy, connected full JID; inspect worker logs |
| Login returns 404 | Use bare JID, correct code, and exchange within the code lifetime |
| Requests fail with invalid token | Header must be `Bearer`, correct gallery instance, token exists and user active |
| Memcached connection errors | Service running on `127.0.0.1:11211`, matching Django cache configuration |
| Upload succeeds, file URL is 404 | `STATIC_LINK`, Nginx alias, symlink existence/target, read/traverse permissions |
| Thumbnail URL is 404 | Allow processing time; inspect `convert`, `identify`, `ffmpeg`, codec/policy errors and worker restarts |
| Upload returns HTTP 413 | Nginx body limit including multipart overhead |
| Upload returns HTTP 400 | Inspect JSON `error` and `status` for quota, size, transfer limit, or validation errors |
| Browser client fails, native client works | CORS policy and preflight support at the gallery origin |

Before reporting a problem, record the Git revision, resolved package versions,
HTTP status/body, and sanitized relevant logs. Never publish credentials, tokens,
verification codes, user content, or private account identifiers.
