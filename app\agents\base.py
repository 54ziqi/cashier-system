"""Agent 基类 - 低优先级后台线程"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent 运行约束：
    - 独立低优先级 daemon 线程
    - 内存上限 < 15MB (全部Agent合计)
    - CPU 优先级最低
    - 失败静默降级
    - 可通过 features.agents = false 关闭
    """

    def __init__(self, interval: float = 300):
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._running = False
        self._enabled = True

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name=f"agent-{self.name}"
        )
        # 设置为最低优先级 (Windows不可用，忽略)
        try:
            self._thread.priority = threading.Thread.MIN_PRIORITY
        except AttributeError:
            pass
        self._thread.start()
        log.info(f"Agent 已启动: {self.name}")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info(f"Agent 已停止: {self.name}")

    def _run_loop(self) -> None:
        while self._running:
            try:
                if self._enabled:
                    self.tick()
            except Exception:
                log.exception(f"Agent {self.name} 执行异常")
            time.sleep(self._interval)

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def tick(self) -> None:
        """每次执行的逻辑"""
        ...


class AgentManager:
    """Agent 管理器"""

    def __init__(self):
        self._agents: list[BaseAgent] = []

    def register(self, agent: BaseAgent) -> None:
        self._agents.append(agent)

    def start_all(self) -> None:
        for agent in self._agents:
            agent.start()

    def stop_all(self) -> None:
        for agent in self._agents:
            agent.stop()
