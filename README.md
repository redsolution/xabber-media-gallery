# Xabber Media Gallery

**Self-hosted file and media storage for XMPP clients.**

Xabber Media Gallery stores chat attachments, images, videos, voice messages, and
avatars. Clients prove ownership of an XMPP account, receive an HTTP bearer token,
and use the gallery API to upload and manage files. Recipients download shared
files over HTTPS.

## Documentation

Choose a guide to open it directly on GitHub.

| Guide | What you’ll find | For |
| --- | --- | --- |
| **[Install the gallery →](docs/installation.md)** | Requirements, configuration, first launch, and production deployment | Server administrators |
| **[Connect an XMPP client →](docs/client-protocol.md)** | Discovery, verification stanzas, authentication, uploads, and sharing | Client developers |
| **[Explore the HTTP API →](docs/http-api.md)** | Endpoints, request fields, responses, pagination, and errors | API integrators |
| **[Operate your instance →](docs/operations.md)** | Quotas, expiration cleanup, backups, limitations, and troubleshooting | Operators |

**New here?** Start with [Installation](docs/installation.md), then follow
[Client integration](docs/client-protocol.md) to verify an upload end to end.

[Browse all documentation](docs/README.md) · [Contribute](CONTRIBUTING.md)

## How it works

```text
XMPP client ── request verification ──► Gallery HTTP API
     ▲                                      │
     └──── verification stanza over XMPP ───┘
     │
     └── exchange code → bearer token → upload → share HTTPS URL
                                                      │
Recipient ◄────────────────── download from web server ┘
```

- **XMPP account verification:** codes delivered as chat messages or HTTP-auth IQs.
- **HTTP file management:** uploads, listings, deletion, usage statistics, and quotas.
- **Media processing:** image/video thumbnails and multiple avatar sizes.
- **Storage reuse:** SHA-1 based deduplication with per-user file records and links.
- **Administration:** Django admin, domain/user access lists, and quota controls.

This is a Django REST service, with no bundled gallery web frontend. It implements
Xabber's custom media API, **not XEP-0363 HTTP File Upload**. Clients must implement
this API; support for XEP-0363 alone is insufficient.

## Get started

You need a Linux host, Python environment, Memcached, FFmpeg, ImageMagick, a
filesystem supporting symbolic links, and an XMPP account for delivering codes.
The [installation guide](docs/installation.md) covers settings, database setup,
local startup, and production deployment with Nginx and Gunicorn.

```sh
git clone https://github.com/redsolution/xabber-media-gallery.git
cd xabber-media-gallery
python3.10 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp examples/settings.py gallery/settings.py
# Configure the required GALLERY_* environment variables; see the guide.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

The application serves its API at `/api/v1/`. A web server separately serves public
file URLs from `MEDIA_ROOT/symlinks/`; `runserver` does not serve uploads by default.

## Connect an XMPP client

1. Configure or discover the gallery base URL, for example `https://gallery.example.com/api/`.
2. While connected to XMPP, request a verification code for your full JID.
3. Read the code from the XMPP stanza and exchange it using your bare JID.
4. Use `Authorization: Bearer <token>` for HTTP API requests.
5. Upload a file and send its returned HTTPS URL in an XMPP message.

The [client protocol guide](docs/client-protocol.md) includes discovery XML,
verification IQs, curl examples, and compatibility details.

## Deployment status

The dependency file targets Django 3.2 and Django REST Framework 3.12 or earlier,
and does not fully pin transitive dependencies. Treat this as a legacy stack:
validate your resolved environment and review the [operational limitations](docs/operations.md)
before exposing an instance to the Internet. The examples are deployment starting
points, not a claim of a hardened or supported production distribution.

## Project layout

| Path | Purpose |
| --- | --- |
| `gallery/generic_settings.py` | Upstream defaults |
| `gallery/settings.py` | Local settings; intentionally ignored by Git |
| `gallery/api/` | REST endpoints, models, authentication, media processing |
| `gallery/api/migrations/` | Database schema history |
| `examples/` | Settings, Nginx, and systemd deployment examples |
| `docs/` | Operator and client developer documentation |

## Community and license

Use [GitHub Issues](https://github.com/redsolution/xabber-media-gallery/issues) for
bugs and feature requests. Include reproducible steps and sanitized logs; never
post passwords, bearer tokens, verification codes, or private files.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

Licensed under the [GNU Affero General Public License v3.0](LICENSE).
