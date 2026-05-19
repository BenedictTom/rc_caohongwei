"""调度器 worker：APScheduler 周期任务。

每 tick：
1) SQL 拉取 status=PENDING AND next_retry_at<=now，按 vendor 熔断状态过滤
2) 把选中的记录原子置为 IN_FLIGHT
3) 提交到并发池调度 dispatcher.dispatch
"""
import asyncio
from datetime import UTC, datetime
from functools import lru_cache

import httpx
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.db import session_scope
from app.delivery.breaker import get_breaker
from app.delivery.dispatcher import dispatch
from app.models.notification import Notification, NotificationStatus

log = structlog.get_logger("worker")


class DeliveryWorker:
    """对外只暴露 start/stop/run_once。便于测试时手动驱动一次 tick。"""

    def __init__(self) -> None:
        s = get_settings()
        self._scheduler = AsyncIOScheduler()
        self._semaphore = asyncio.Semaphore(s.worker_max_concurrency)
        self._http_client: httpx.AsyncClient | None = None
        self._tick_lock = asyncio.Lock()  # 同一时刻只跑一个 tick，避免重叠

    async def start(self) -> None:
        self._http_client = httpx.AsyncClient()
        s = get_settings()
        self._scheduler.add_job(
            self._safe_tick,
            trigger=IntervalTrigger(seconds=s.worker_interval_seconds),
            id="delivery_tick",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._scheduler.start()
        log.info("worker_started", interval=s.worker_interval_seconds)

    async def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        log.info("worker_stopped")

    @property
    def is_running(self) -> bool:
        return self._scheduler.running

    async def _safe_tick(self) -> None:
        if self._tick_lock.locked():
            return  # 上一轮还在跑就跳过
        async with self._tick_lock:
            try:
                await self.run_once()
            except Exception:  # 调度器周期任务不允许抛异常
                log.exception("tick_failed")

    async def run_once(self) -> int:
        """选一批 PENDING 单并派发。返回本轮派发条数。"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        s = get_settings()
        breaker = get_breaker()
        now = datetime.now(UTC)
        ids: list[str] = []

        with session_scope() as session:
            stmt = (
                select(Notification.id, Notification.provider)
                .where(Notification.status == NotificationStatus.PENDING)
                .where(Notification.next_retry_at <= now)
                .order_by(Notification.next_retry_at.asc())
                .limit(s.worker_batch_size)
            )
            rows = session.execute(stmt).all()
            for ntf_id, provider in rows:
                if not breaker.allow(provider, now=now):
                    continue
                # 抢占：CAS 把状态从 PENDING → IN_FLIGHT
                upd = (
                    update(Notification)
                    .where(Notification.id == ntf_id)
                    .where(Notification.status == NotificationStatus.PENDING)
                    .values(status=NotificationStatus.IN_FLIGHT)
                )
                result = session.execute(upd)
                if result.rowcount == 1:
                    ids.append(ntf_id)

        if not ids:
            return 0

        log.info("tick_dispatching", count=len(ids))
        await asyncio.gather(*(self._dispatch_one(i) for i in ids), return_exceptions=True)
        return len(ids)

    async def _dispatch_one(self, notification_id: str) -> None:
        async with self._semaphore:
            assert self._http_client is not None
            try:
                await dispatch(notification_id, http_client=self._http_client)
            except Exception:
                # dispatch 内已写状态机；这里只兜 dispatch 自身崩溃的极端情况：
                # 把卡在 IN_FLIGHT 的记录放回 PENDING，下个 tick 会重新派发
                log.exception("dispatch_uncaught", id=notification_id)
                with session_scope() as s:
                    s.execute(
                        update(Notification)
                        .where(Notification.id == notification_id)
                        .where(Notification.status == NotificationStatus.IN_FLIGHT)
                        .values(
                            status=NotificationStatus.PENDING,
                            next_retry_at=datetime.now(UTC),
                        )
                    )


@lru_cache(maxsize=1)
def get_worker() -> DeliveryWorker:
    return DeliveryWorker()
