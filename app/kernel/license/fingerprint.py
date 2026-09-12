"""硬件指纹：MAC + 主机名 + CPU → SHA256"""
import hashlib
import platform
import uuid


def get_fingerprint() -> str:
    raw = "|".join([
        f"{uuid.getnode():012x}",
        platform.node(),
        platform.machine(),
        platform.system(),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()
