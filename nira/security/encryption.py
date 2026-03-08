from __future__ import annotations

import base64
import os
from hashlib import sha256
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("ascii"))


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
    )
    return kdf.derive(passphrase.encode("utf-8"))


class EncryptionManager:
    def __init__(self, key_env: str = "NIRA_ENCRYPTION_KEY", passphrase_env: str = "NIRA_PASSPHRASE") -> None:
        self.key_env = key_env
        self.passphrase_env = passphrase_env
        self.storage_dir = Path.home() / ".nira_agent" / "security"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._key = self._resolve_key()
        self._aes = AESGCM(self._key)

    def encrypt_text(self, text: str) -> str:
        nonce = os.urandom(12)
        cipher = self._aes.encrypt(nonce, text.encode("utf-8"), None)
        return f"{_b64e(nonce)}:{_b64e(cipher)}"

    def decrypt_text(self, payload: str) -> str:
        nonce_b64, data_b64 = payload.split(":", 1)
        plain = self._aes.decrypt(_b64d(nonce_b64), _b64d(data_b64), None)
        return plain.decode("utf-8")

    def _resolve_key(self) -> bytes:
        env_key = os.getenv(self.key_env)
        if env_key:
            try:
                decoded = _b64d(env_key)
                if len(decoded) == 32:
                    return decoded
            except Exception:
                pass
            return sha256(env_key.encode("utf-8")).digest()

        passphrase = os.getenv(self.passphrase_env)
        salt_path = self.storage_dir / "salt.bin"
        if passphrase:
            salt = salt_path.read_bytes() if salt_path.exists() else os.urandom(16)
            if not salt_path.exists():
                salt_path.write_bytes(salt)
            return derive_key(passphrase, salt)

        key_path = self.storage_dir / "key.bin"
        if key_path.exists():
            data = key_path.read_bytes()
            if len(data) == 32:
                return data
        key = os.urandom(32)
        key_path.write_bytes(key)
        return key

