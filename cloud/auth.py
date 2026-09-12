"""
云端鉴权

验证 POS 推送的日结数据签名。POS 用 License 内私钥签名，云端用公钥验签。
实际生产中公钥可来自证书目录、首次注册时交换、或 License 元数据。
演示版从本地 `cloud/data/license_pub.pem` 读取公钥。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature


def _load_public_key(pem_path: Path = Path("cloud/data/license_pub.pem")):
    """加载验签公钥；演示模式下若不存在返回 None（跳过验签）"""
    if not pem_path.exists():
        return None
    return serialization.load_pem_public_key(pem_path.read_bytes())


def verify_digest(payload: dict, signature_b64: str, pub_key=None) -> bool:
    """
    验证 POS 推送数据签名。
    若无私钥（演示模式）直接返回 True。
    """
    pub_key = pub_key or _load_public_key()
    if pub_key is None:
        # 演示模式：信任输入
        return True
    try:
        sig = base64.b64decode(signature_b64)
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        pub_key.verify(sig, data, padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, Exception):
        return False
