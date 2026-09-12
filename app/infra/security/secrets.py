"""自动生成与加载密钥"""
from __future__ import annotations
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _write_secure(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_or_create_secret(path: Path, nbytes: int = 48) -> bytes:
    if path.exists():
        return path.read_bytes()
    data = secrets.token_bytes(nbytes)
    _write_secure(path, data)
    return data


def load_or_create_rsa_keypair(priv_path: Path, pub_path: Path) -> tuple[bytes, bytes]:
    if priv_path.exists() and pub_path.exists():
        return priv_path.read_bytes(), pub_path.read_bytes()

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _write_secure(priv_path, priv_pem)
    _write_secure(pub_path, pub_pem)
    return priv_pem, pub_pem
