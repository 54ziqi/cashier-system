"""完全离线 License 验签（RSA-PSS + AES-GCM）"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .fingerprint import get_fingerprint


LicenseStatus = Literal["valid", "expired", "invalid", "missing", "grace"]


@dataclass
class LicenseResult:
    status: LicenseStatus
    payload: dict | None = None
    message: str = ""


class LicenseVerifier:
    def __init__(self, public_key_pem: bytes, grace_days: int = 7):
        self.public_key = serialization.load_pem_public_key(public_key_pem)
        self.grace_days = grace_days

    def verify(self, license_path: Path) -> LicenseResult:
        if not license_path.exists():
            return LicenseResult("missing", None, "License 文件不存在")

        try:
            envelope = json.loads(license_path.read_bytes())
        except Exception as e:
            return LicenseResult("invalid", None, f"License 解析失败: {e}")

        payload_enc_b64 = envelope.get("payload", "")
        signature_b64 = envelope.get("signature", "")
        if not payload_enc_b64 or not signature_b64:
            return LicenseResult("invalid", None, "License 格式错误")

        import base64
        try:
            payload_enc = base64.b64decode(payload_enc_b64)
            signature = base64.b64decode(signature_b64)
        except Exception as e:
            return LicenseResult("invalid", None, f"Base64 解码失败: {e}")

        try:
            self.public_key.verify(
                signature, payload_enc,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                            salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
        except Exception:
            return LicenseResult("invalid", None, "签名验证失败")

        try:
            nonce, ct = payload_enc[:12], payload_enc[12:]
            key = self._derive_aes_key()
            payload_bytes = AESGCM(key).decrypt(nonce, ct, None)
            payload = json.loads(payload_bytes)
        except Exception as e:
            return LicenseResult("invalid", None, f"解密失败: {e}")

        fp = payload.get("hardware_fingerprint")
        if fp and fp != get_fingerprint():
            return LicenseResult("invalid", payload, "硬件指纹不匹配")

        expire_at = payload.get("expire_at")
        if expire_at:
            try:
                expire_ts = self._parse_iso(expire_at)
                now = time.time()
                if now > expire_ts + self.grace_days * 86400:
                    return LicenseResult("expired", payload, "授权已过期")
                if now > expire_ts:
                    return LicenseResult("grace", payload, "已进入宽限期")
            except Exception:
                pass

        return LicenseResult("valid", payload, "授权有效")

    def _derive_aes_key(self) -> bytes:
        import hashlib
        return hashlib.sha256(get_fingerprint().encode()).digest()

    @staticmethod
    def _parse_iso(iso: str) -> float:
        from datetime import datetime
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
