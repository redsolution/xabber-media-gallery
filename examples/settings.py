"""Copy to gallery/settings.py; provide secrets through the service environment."""
import os
from gallery.generic_settings import *  # noqa: F403,F401

SECRET_KEY = os.environ["GALLERY_SECRET_KEY"]
DEBUG = os.environ.get("GALLERY_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get(
    "GALLERY_ALLOWED_HOSTS", "localhost,127.0.0.1"
).split(",") if host.strip()]
XMPP_LOGIN = os.environ["GALLERY_XMPP_LOGIN"]
XMPP_PASS = os.environ["GALLERY_XMPP_PASSWORD"]
STATIC_LINK = os.environ.get("GALLERY_STATIC_LINK", "http://127.0.0.1:8080/media/")
MEDIA_ROOT = os.environ.get("GALLERY_MEDIA_ROOT", os.path.join(BASE_DIR, "uploaded"))
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Enable only behind a trusted proxy that overwrites this header.
if os.environ.get("GALLERY_BEHIND_HTTPS_PROXY", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
