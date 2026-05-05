import unittest

from posture_watch.state import LlmRateLimiter, PostureStateMachine, WatchState


class PostureStateMachineTest(unittest.TestCase):
    def make_machine(self) -> PostureStateMachine:
        return PostureStateMachine(
            local_window_sec=90,
            local_score_trigger=70,
            llm_verify_score=75,
            bad_ratio_required=0.65,
            notify_cooldown_sec=900,
            recovery_sec=120,
            local_only_notify_score=84,
        )

    def test_continuous_bad_window_enters_verifying(self) -> None:
        machine = self.make_machine()
        snapshot = None
        for i in range(46):
            snapshot = machine.update(78, True, i * 2.0)
        assert snapshot is not None
        self.assertEqual(snapshot.state, WatchState.VERIFYING)
        self.assertGreaterEqual(snapshot.bad_ratio, 0.65)
        limiter = LlmRateLimiter(min_interval_sec=600, max_calls_per_hour=6)
        self.assertTrue(machine.should_verify_with_llm(snapshot, 92.0, limiter))

    def test_quality_bad_samples_do_not_trigger(self) -> None:
        machine = self.make_machine()
        snapshot = None
        for i in range(46):
            snapshot = machine.update(95, False, i * 2.0)
        assert snapshot is not None
        self.assertEqual(snapshot.state, WatchState.NORMAL)
        self.assertEqual(snapshot.valid_samples, 0)

    def test_cooldown_requires_recovery(self) -> None:
        machine = self.make_machine()
        machine.enter_cooldown(100.0)
        snapshot = machine.update(20, True, 500.0)
        self.assertEqual(snapshot.state, WatchState.COOLDOWN)
        snapshot = machine.update(20, True, 1121.0)
        self.assertEqual(snapshot.state, WatchState.NORMAL)


class LlmRateLimiterTest(unittest.TestCase):
    def test_limits_interval_and_hourly_count(self) -> None:
        limiter = LlmRateLimiter(min_interval_sec=10, max_calls_per_hour=2)
        self.assertTrue(limiter.allow(0))
        limiter.record(0)
        self.assertFalse(limiter.allow(5))
        self.assertTrue(limiter.allow(10))
        limiter.record(10)
        self.assertFalse(limiter.allow(20))
        self.assertTrue(limiter.allow(3611))


if __name__ == "__main__":
    unittest.main()

