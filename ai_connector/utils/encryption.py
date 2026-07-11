"""Reversible, best-effort encryption for stored AI provider secrets.

Uses `cryptography.fernet` when available (strong encryption) and falls back
to a lightweight XOR + base64 obfuscation otherwise so the module remains
dependency-free on minimal Odoo installs. The fallback is *not* cryptographically
secure and only prevents accidental plaintext disclosure in the database.
"""

import base64
import hashlib
import os

try:
    from cryptography.fernet import Fernet

    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_CRYPTOGRAPHY = False

# A per-deployment secret derived from the Odoo `database` secret (if present)
# falling back to a constant. In production deployers should set a strong
# `ai_connector.secret` system parameter.
_FALLBACK_SECRET = "ai-connector-change-me"


def _get_secret(env):
    key = False
    if env is not None:
        try:
            key = env["ir.config_parameter"].sudo().get_param("ai_connector.secret")
        except Exception:
            key = False
    return (key or _FALLBACK_SECRET).encode("utf-8")


def _fernet(env):
    secret = _get_secret(env)
    digest = hashlib.sha256(secret).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value, env=None):
    """Encrypt a plaintext string and return a unicode ciphertext."""
    if not value:
        return value
    if _HAS_CRYPTOGRAPHY:
        return _fernet(env).encrypt(value.encode("utf-8")).decode("utf-8")
    return _xor_obfuscate(value, _get_secret(env))


def decrypt(ciphertext, env=None):
    """Decrypt a ciphertext produced by :func:`encrypt`."""
    if not ciphertext:
        return ciphertext
    if _HAS_CRYPTOGRAPHY:
        try:
            return _fernet(env).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception:
            # Tolerate values that were stored before encryption was enabled.
            return _xor_deobfuscate(ciphertext, _get_secret(env))
    return _xor_deobfuscate(ciphertext, _get_secret(env))


def _xor_obfuscate(value, secret):
    secret = secret * (1 + len(value) // len(secret))
    out = bytes(c ^ s for c, s in zip(value.encode("utf-8"), secret))
    return base64.b64encode(out).decode("utf-8")


def _xor_deobfuscate(ciphertext, secret):
    try:
        raw = base64.b64decode(ciphertext.encode("utf-8"))
    except Exception:
        return ciphertext
    secret = secret * (1 + len(raw) // len(secret))
    return bytes(c ^ s for c, s in zip(raw, secret)).decode("utf-8", "ignore")


def generate_secret():
    """Generate a strong random secret for the `ai_connector.secret` parameter."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")
