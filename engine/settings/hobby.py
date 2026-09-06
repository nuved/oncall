import os

from .prod_without_db import *  # noqa: F403

# Encryption key and IV for fields stored with mirage (Slack tokens, webhook credentials).
# Set MIRAGE_SECRET_KEY and MIRAGE_CIPHER_IV in the environment (scripts/init-env.sh generates them);
# unset, they fall back to the historical derivation so existing hobby installs keep decrypting their
# data. Never change them on an installation that already has encrypted rows.
MIRAGE_SECRET_KEY = os.environ.get("MIRAGE_SECRET_KEY") or SECRET_KEY  # noqa: F405
MIRAGE_CIPHER_IV = os.environ.get("MIRAGE_CIPHER_IV") or "1234567890abcdef"

APPEND_SLASH = False
SECURE_SSL_REDIRECT = False
