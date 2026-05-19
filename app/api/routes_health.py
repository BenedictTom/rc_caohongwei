from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.schemas import HealthResponse
from app.core.db import session_scope
from app.delivery.worker import get_worker

router = APIRouter(tags=["meta"])


@router.get("/healthz", response_model=HealthResponse)
def healthz(response: Response) -> HealthResponse:
    failed: list[str] = []

    db_ok = "ok"
    try:
        with session_scope() as s:
            s.execute(text("SELECT 1"))
    except Exception:
        db_ok = "down"
        failed.append("db")

    sched_ok = "ok" if get_worker().is_running else "down"
    if sched_ok == "down":
        failed.append("scheduler")

    if failed:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unhealthy", db=db_ok, scheduler=sched_ok, failed=failed)
    return HealthResponse(status="ok", db=db_ok, scheduler=sched_ok)
