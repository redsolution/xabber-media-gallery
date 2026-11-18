# Installation and deployment

[Back to README](../README.md) · [Operations](operations.md)

## 1. Prepare the host

The commands below use Debian/Ubuntu package names. Install Python 3.10 with its
`venv` module using your distribution's packages or your usual Python manager.
The source targets Django 3.2; do not assume a current Python release or Django 4+
will work without changes. Django 3.2 is a legacy dependency; plan an upgrade before
relying on this service for a new public deployment.

```sh
sudo apt-get update
sudo apt-get install git memcached ffmpeg imagemagick nginx
sudo systemctl enable --now memcached
command -v convert identify ffmpeg
```

ImageMagick must expose both `convert` and `identify` on the service's PATH, with
WebP support for avatar thumbnails. Keep Memcached on loopback; never publish its
port. The service needs writable local storage and symbolic links.

Register a dedicated XMPP account, for example `gallery-bot@example.com/gallery`.
It must be able to connect using xmpppy's domain-based connection discovery,
authenticate, and deliver stanzas to your users. This repository does not include
an XMPP server or an external-component connection configuration.

## 2. Install the application

For production, use a dedicated unprivileged `gallery` OS account. The examples
assume its checkout is `/srv/xabber-media-gallery`, owned by that account.
For a local evaluation, use any writable checkout instead.

```sh
git clone https://github.com/redsolution/xabber-media-gallery.git
cd xabber-media-gallery
python3.10 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp examples/settings.py gallery/settings.py
```

`requirements.txt` fetches `jid_validation` from GitHub, so Git and network access
are needed. It uses version ranges and an unpinned Git dependency. Record the
resolved package versions and Git revision for reproducible deployments.

## 3. Configure settings

`manage.py`, WSGI, and ASGI load `gallery.settings`; that file is intentionally
absent from the checkout. The supplied example imports `gallery.generic_settings`
and overrides deployment-specific values. It reads these environment variables:

| Variable | Meaning |
| --- | --- |
| `GALLERY_SECRET_KEY` | Required unique Django secret; generate below |
| `GALLERY_XMPP_LOGIN` | Required service XMPP JID, optionally including a resource |
| `GALLERY_XMPP_PASSWORD` | Required password for that service account |
| `GALLERY_ALLOWED_HOSTS` | Comma-separated HTTP hostnames; default `localhost,127.0.0.1` |
| `GALLERY_DEBUG` | `true` for local debugging only; default `false` |
| `GALLERY_STATIC_LINK` | Public file URL prefix, including trailing slash |
| `GALLERY_MEDIA_ROOT` | Absolute writable upload directory |
| `GALLERY_BEHIND_HTTPS_PROXY` | `true` only with a trusted HTTPS proxy setting the header |

For a local shell:

```sh
export GALLERY_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export GALLERY_XMPP_LOGIN='gallery-bot@example.com/gallery'
read -rs -p 'XMPP service password: ' GALLERY_XMPP_PASSWORD
export GALLERY_XMPP_PASSWORD
export GALLERY_DEBUG=true
export GALLERY_ALLOWED_HOSTS='localhost,127.0.0.1'
export GALLERY_MEDIA_ROOT="$PWD/uploaded"
export GALLERY_STATIC_LINK='http://127.0.0.1:8080/media/'
mkdir -p "$GALLERY_MEDIA_ROOT/symlinks"
python manage.py migrate
python manage.py createsuperuser
python manage.py check
python manage.py runserver 127.0.0.1:8000
```

The `read` example uses Bash. Use your shell's equivalent secret prompt otherwise.
The superuser is for Django administration, separate from users' XMPP accounts.
Users and their quota records are created automatically when codes are requested.

Visit `http://127.0.0.1:8000/admin/`. An unauthenticated request to
`http://127.0.0.1:8000/api/v1/files/` should return HTTP 401.
The development server does not serve uploaded media. Use the Nginx mapping below
for complete upload/download verification, or serve **only** `uploaded/symlinks/`
with a local static server on port 8080 using a `/media/` URL mapping.

## 4. Configure production HTTP serving

Use an HTTPS hostname such as `gallery.example.com`. Set:

```text
GALLERY_ALLOWED_HOSTS=gallery.example.com
GALLERY_STATIC_LINK=https://gallery.example.com/media/
GALLERY_MEDIA_ROOT=/srv/xabber-media-gallery/uploaded
GALLERY_DEBUG=false
GALLERY_BEHIND_HTTPS_PROXY=true
```

Persist these and the required secrets in `/etc/xabber-media-gallery.env`, owned
by root with mode `0600`. Use systemd `EnvironmentFile` syntax (`KEY=value`, no
`export`); it is not a shell script. Keep the same secret across restarts.

```sh
.venv/bin/pip install gunicorn
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
```

Run management commands with the same settings environment as the service. Review
`check --deploy` output for your deployment, including HTTPS redirects and HSTS.

Adapt [the systemd unit](../examples/xabber-media-gallery.service), install it as
`/etc/systemd/system/xabber-media-gallery.service`, then run:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now xabber-media-gallery
```

Adapt [the Nginx server block](../examples/nginx.conf): replace the hostname,
certificate paths, checkout path, and media path. Provision TLS certificates using
your normal certificate tooling before enabling it. Validate with `sudo nginx -t`
and reload Nginx.

**The media alias must point at `uploaded/symlinks/`, not `uploaded/`.**
The application creates public links there, referencing private originals and
thumbnails elsewhere under `MEDIA_ROOT`. Nginx needs read/traverse permissions on
the target files and directories and must be allowed to follow these symlinks.
The application account needs write permission. Do not expose the checkout,
SQLite database, settings, or original/thumbnail directories as static roots.

The example uses a separate API hostname from browser clients. Cross-origin web
clients additionally need a deliberate CORS policy at your proxy or application:
allow trusted origins and the `Authorization` header, and support preflight for
POST/DELETE. The repository does not configure CORS. Native clients do not need it.

## 5. Connect and verify

Follow [the client protocol](client-protocol.md) to request an IQ code, authenticate,
upload a small text file, download its returned `file` URL, and delete that file by
ID. Also test an image and confirm its thumbnail eventually becomes accessible.
A successful code-request HTTP response alone does not prove XMPP delivery.

Schedule the expiration cleanup command described in [Operations](operations.md).
Back up the database and the entire media tree together before updates.

## Validation scope

The documentation setup was smoke-tested with Python 3.11, Django 3.2.25, and DRF
3.12.4 on macOS using a temporary SQLite database and local-memory cache. Settings
loading, existing migrations, code request/exchange, both slot response forms,
upload/symlink creation, listing, statistics, deletion, and cleanup were exercised.
XMPP delivery was mocked; this was not a live federation or production deployment
test. Python 3.10 remains the conservative version for the legacy Django target.
The Memcached service, Nginx/TLS, systemd, CORS, and media conversion must be verified
on your deployment host. See the known schema-check findings in [Operations](operations.md).
