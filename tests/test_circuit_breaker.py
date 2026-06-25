import io
import unittest
from contextlib import redirect_stdout

from my_hello_agents.tools.circuit_breaker import CircuitBreaker
from my_hello_agents.tools.errors import ToolErrorCode
from my_hello_agents.tools.response import ToolResponse


def success_response() -> ToolResponse:
    return ToolResponse.success(text="ok")


def error_response() -> ToolResponse:
    return ToolResponse.error(
        code=ToolErrorCode.EXECUTION_ERROR,
        message="failed",
    )


class CircuitBreakerTest(unittest.TestCase):
    def test_initial_status_is_closed(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10)

        self.assertFalse(breaker.is_open("demo_tool"))
        self.assertEqual(
            breaker.get_status("demo_tool"),
            {"state": "closed", "failure_count": 0},
        )

    def test_failure_below_threshold_does_not_open(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10)

        breaker.record_result("demo_tool", error_response())

        self.assertFalse(breaker.is_open("demo_tool"))
        self.assertEqual(
            breaker.get_status("demo_tool"),
            {"state": "closed", "failure_count": 1},
        )

    def test_failures_at_threshold_open_circuit(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10)

        with redirect_stdout(io.StringIO()):
            breaker.record_result("demo_tool", error_response())
            breaker.record_result("demo_tool", error_response())

        self.assertTrue(breaker.is_open("demo_tool"))
        status = breaker.get_status("demo_tool")
        self.assertEqual(status["state"], "open")
        self.assertEqual(status["failure_count"], 2)
        self.assertIn("open_since", status)
        self.assertIn("recover_in_seconds", status)

    def test_success_resets_failure_count(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

        breaker.record_result("demo_tool", error_response())
        breaker.record_result("demo_tool", success_response())

        self.assertEqual(
            breaker.get_status("demo_tool"),
            {"state": "closed", "failure_count": 0},
        )

    def test_manual_open_and_close(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

        with redirect_stdout(io.StringIO()):
            breaker.open("demo_tool")

        self.assertTrue(breaker.is_open("demo_tool"))

        with redirect_stdout(io.StringIO()):
            breaker.close("demo_tool")

        self.assertFalse(breaker.is_open("demo_tool"))
        self.assertEqual(
            breaker.get_status("demo_tool"),
            {"state": "closed", "failure_count": 0},
        )

    def test_is_open_auto_recovers_after_timeout(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10)

        with redirect_stdout(io.StringIO()):
            breaker.record_result("demo_tool", error_response())

        breaker.open_timestamps["demo_tool"] -= 11

        with redirect_stdout(io.StringIO()):
            self.assertFalse(breaker.is_open("demo_tool"))

        self.assertEqual(
            breaker.get_status("demo_tool"),
            {"state": "closed", "failure_count": 0},
        )

    def test_disabled_breaker_never_opens_or_records(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10, enabled=False)

        breaker.record_result("demo_tool", error_response())
        breaker.open("demo_tool")

        self.assertFalse(breaker.is_open("demo_tool"))
        self.assertEqual(
            breaker.get_status("demo_tool"),
            {"state": "closed", "failure_count": 0},
        )

    def test_get_all_status_includes_known_tools(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10)

        breaker.record_result("failed_tool", error_response())
        breaker.record_result("healthy_tool", success_response())

        statuses = breaker.get_all_status()

        self.assertEqual(statuses["failed_tool"]["failure_count"], 1)
        self.assertEqual(statuses["healthy_tool"]["failure_count"], 0)


if __name__ == "__main__":
    unittest.main()
