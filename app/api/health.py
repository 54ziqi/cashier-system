from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready():
    """
    就绪探针：返回服务本身是否可对外工作。
    License 详情仅通过 /api/v1/admin/... 授权接口查询，
    避免攻击者通过探针获取授权状态。
    """
    return {"status": "ready"}
