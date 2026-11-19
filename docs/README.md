# Documentation

[Project home](../README.md) · [Contributing](../CONTRIBUTING.md)

Everything you need to install Xabber Media Gallery, connect an XMPP client, and
operate your own instance.

## Find your guide

| | Guide | Start here when you want to… |
| --- | --- | --- |
| **01** | **[Installation and deployment](installation.md)** | Set up dependencies, configure the gallery, and put it behind HTTPS. |
| **02** | **[XMPP client protocol](client-protocol.md)** | Discover the gallery, verify an account, upload media, and share a file. |
| **03** | **[HTTP API reference](http-api.md)** | Find a route, request field, response format, or error code. |
| **04** | **[Operations and troubleshooting](operations.md)** | Adjust quotas, schedule cleanup, back up storage, or diagnose a problem. |

## Suggested reading paths

**Deploying a server**  
[Install and configure](installation.md) → [Verify with a client](client-protocol.md) → [Operate and maintain](operations.md)

**Building an XMPP client**  
[Understand the connection flow](client-protocol.md) → [Look up API details](http-api.md)

**Maintaining an existing instance**  
[Check operations and troubleshooting](operations.md) → [Review deployment configuration](installation.md#4-configure-production-http-serving)

## Deployment examples

| Example | Purpose |
| --- | --- |
| [Django settings](../examples/settings.py) | Environment-based configuration with local secrets kept out of Git. |
| [Nginx configuration](../examples/nginx.conf) | HTTPS reverse proxy and the public media directory mapping. |
| [systemd service](../examples/xabber-media-gallery.service) | Run Gunicorn under a dedicated service account. |

## Before deploying publicly

Review the [implementation limitations](operations.md#public-deployment-limitations)
and [validation scope](installation.md#validation-scope). The guides distinguish
current behavior from deployment steps that still need verification on your host.

---

[Project home](../README.md) · [Report an issue](https://github.com/redsolution/xabber-media-gallery/issues) · [Contribute](../CONTRIBUTING.md)
