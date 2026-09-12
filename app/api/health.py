from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request):
    lic = request.app.state.license
    ok = lic.status in ("valid", "grace")
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "degraded",
            "license": lic.status,
            "license_message": lic.message,
        },
    )
