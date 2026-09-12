"""
云端鉴权

验证 POS 推送的日结数据签名。POS 用 License 内私钥签名，云端用公钥验签。
实际生产中公钥可来自证书目录、首次注册时交换、或 License 元数据。
演示版从本地 `cloud/data/license_pub.pem` 读取公钥。
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PUBKEY_PATH = Path(os.environ.get("CLOUD_PUBKEY_PATH", "cloud/data/license_pub.pem"))


def _load_public_key(pem_path: Path = None):
    """加载验签公钥; 优先 env CLOUD_PUBKEY_PATH, 否则默认路径"""
    if pem_path is None:
        pem_path = Path(
            os.environ.get("CLOUD_PUBKEY_PATH", "cloud/data/license_pub.pem")
        )
    if not pem_path.exists():
        return None
    return serialization.load_pem_public_key(pem_path.read_bytes())


def ensure_pubkey_on_startup(pem_path: Path = PUBKEY_PATH) -> None:
    """
    启动时校验公钥文件存在性。
    若缺失，直接 SystemExit 并给出友好命令行提示。
    当环境变量 CLOUD_SKIP_PUBKEY_CHECK=1 时跳过（用于测试环境）。
    """
    if os.environ.get("CLOUD_SKIP_PUBKEY_CHECK") == "1":
        return
    if not isinstance(pem_path, Path):
        pem_path = Path(pem_path)
    if pem_path.exists():
        return
    gen_cmd = (
        'python -c "from cryptography.hazmat.primitives.asymmetric import rsa; '
        "from cryptography.hazmat.primitives import serialization; "
        "priv=rsa.generate_private_key(public_exponent=65537,key_size=2048); "
        f"open('{pem_path}','wb').write(priv.public_key().public_bytes("
        'serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))"'
    )
    raise SystemExit(
        f"Missing {pem_path} — generate via:\n"
        f"  mkdir -p {pem_path.parent}\n"
        f"  {gen_cmd}\n"
        f"Or place a valid RSA public PEM at {pem_path}."
    )


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
