"""首次启动生成 30 天试用 License"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .fingerprint import get_fingerprint


def generate_trial_license(priv_pem: bytes, out_path: Path, days: int = 30) -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "license_key": "TRIAL-" + hashlib.md5(get_fingerprint().encode()).hexdigest()[:12].upper(),
        "type": "trial",
        "merchant_id": "local",
        "module_flags": {"member": True, "report": True, "online_pay": False},
        "max_devices": 1,
        "max_cashiers": 3,
        "issued_at": now.isoformat(),
        "expire_at": (now + timedelta(days=days)).isoformat(),
        "hardware_fingerprint": get_fingerprint(),
    }

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    key = hashlib.sha256(get_fingerprint().encode()).digest()
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, payload_bytes, None)
    payload_enc = nonce + ct

    priv = serialization.load_pem_private_key(priv_pem, password=None)
    signature = priv.sign(
        payload_enc,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )

    envelope = {
        "payload": base64.b64encode(payload_enc).decode(),
        "signature": base64.b64encode(signature).decode(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
