from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum


class WatchState(str, Enum):
    NORMAL = "NORMAL"
    WATCHING = "WATCHING"
    VERIFYING = "VERIFYING"
    COOLDOWN = "COOLDOWN"


@dataclass(frozen=True)
class StateSample:
    timestamp: float
    score: float
    quality_ok: bool


@dataclass(frozen=True)
class StateSnapshot:
    state: WatchState
    bad_ratio: float
    valid_samples: int
    window_span_sec: float
    latest_score: float
    max_score: float
    avg_score: float
    cooldown_remaining_sec: float = 0.0


class LlmRateLimiter:
    def __init__(self, min_interval_sec: int, max_calls_per_hour: int) -> None:
        self.min_interval_sec = min_interval_sec
        self.max_calls_per_hour = max_calls_per_hour
        self.calls: deque[float] = deque()

    def allow(self, now: float) -> bool:
        while self.calls and now - self.calls[0] > 3600:
            self.calls.popleft()
        if len(self.calls) >= self.max_calls_per_hour:
            return False
        if self.calls and now - self.calls[-1] < self.min_interval_sec:
            return False
        return True

    def record(self, now: float) -> None:
        self.calls.append(now)


class PostureStateMachine:
    def __init__(
        self,
        *,
        local_window_sec: int,
        local_score_trigger: float,
        llm_verify_score: float,
        bad_ratio_required: float,
        notify_cooldown_sec: int,
        recovery_sec: int,
        local_only_notify_score: float,
    ) -> None:
        self.local_window_sec = local_window_sec
        self.local_score_trigger = local_score_trigger
        self.llm_verify_score = llm_verify_score
        self.bad_ratio_required = bad_ratio_required
        self.notify_cooldown_sec = notify_cooldown_sec
        self.recovery_sec = recovery_sec
        self.local_only_notify_score = local_only_notify_score
        self.samples: deque[StateSample] = deque()
        self.state = WatchState.NORMAL
        self.cooldown_until = 0.0
        self.normal_since: float | None = None

    def update(self, score: float, quality_ok: bool, now: float) -> StateSnapshot:
        self.samples.append(StateSample(now, score, quality_ok))
        while self.samples and now - self.samples[0].timestamp > self.local_window_sec:
            self.samples.popleft()

        snapshot = self._snapshot(now)
        if self.state == WatchState.COOLDOWN:
            if snapshot.latest_score < 40 and quality_ok:
                if self.normal_since is None:
                    self.normal_since = now
                recovered = now - self.normal_since >= self.recovery_sec
                if now >= self.cooldown_until and recovered:
                    self.state = WatchState.NORMAL
                    self.normal_since = None
            else:
                self.normal_since = None
            if now < self.cooldown_until:
                return self._snapshot(now)
            return self._snapshot(now)

        if self._window_is_bad(snapshot):
            self.state = (
                WatchState.VERIFYING
                if snapshot.max_score >= self.llm_verify_score
                else WatchState.WATCHING
            )
        else:
            self.state = WatchState.NORMAL
        return self._snapshot(now)

    def should_verify_with_llm(self, snapshot: StateSnapshot, now: float, limiter: LlmRateLimiter) -> bool:
        return (
            snapshot.state == WatchState.VERIFYING
            and self._window_is_bad(snapshot)
            and snapshot.latest_score >= self.llm_verify_score
            and limiter.allow(now)
        )

    def should_notify_without_llm(self, snapshot: StateSnapshot) -> bool:
        return (
            snapshot.state == WatchState.VERIFYING
            and self._window_is_bad(snapshot)
            and snapshot.latest_score >= self.local_only_notify_score
            and snapshot.max_score >= self.local_only_notify_score
        )

    def enter_cooldown(self, now: float) -> None:
        self.state = WatchState.COOLDOWN
        self.cooldown_until = now + self.notify_cooldown_sec
        self.normal_since = None

    def _snapshot(self, now: float) -> StateSnapshot:
        valid = [s for s in self.samples if s.quality_ok]
        scores = [s.score for s in valid]
        bad = [s for s in valid if s.score >= self.local_score_trigger]
        span = valid[-1].timestamp - valid[0].timestamp if len(valid) >= 2 else 0.0
        cooldown_remaining = max(0.0, self.cooldown_until - now)
        return StateSnapshot(
            state=self.state,
            bad_ratio=(len(bad) / len(valid)) if valid else 0.0,
            valid_samples=len(valid),
            window_span_sec=span,
            latest_score=scores[-1] if scores else 0.0,
            max_score=max(scores) if scores else 0.0,
            avg_score=(sum(scores) / len(scores)) if scores else 0.0,
            cooldown_remaining_sec=cooldown_remaining,
        )

    def _window_is_bad(self, snapshot: StateSnapshot) -> bool:
        min_span = min(60.0, self.local_window_sec * 0.66)
        return (
            snapshot.valid_samples >= 5
            and snapshot.window_span_sec >= min_span
            and snapshot.bad_ratio >= self.bad_ratio_required
            and snapshot.avg_score >= self.local_score_trigger - 5
        )
