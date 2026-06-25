import time

from my_hello_agents.tools.circuit_breaker import CircuitBreaker
from my_hello_agents.tools.errors import ToolErrorCode
from my_hello_agents.tools.response import ToolResponse


def main() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    tool_name = "unstable_tool"

    print("Initial:", breaker.get_status(tool_name))

    breaker.record_result(
        tool_name,
        ToolResponse.error(
            code=ToolErrorCode.EXECUTION_ERROR,
            message="First failure",
        ),
    )
    print("After first failure:", breaker.get_status(tool_name))
    print("Is open:", breaker.is_open(tool_name))

    breaker.record_result(
        tool_name,
        ToolResponse.error(
            code=ToolErrorCode.EXECUTION_ERROR,
            message="Second failure",
        ),
    )
    print("After second failure:", breaker.get_status(tool_name))
    print("Is open:", breaker.is_open(tool_name))

    print("Waiting for recovery timeout...")
    time.sleep(1.1)
    print("Is open after timeout:", breaker.is_open(tool_name))
    print("After recovery:", breaker.get_status(tool_name))

    breaker.record_result(
        tool_name,
        ToolResponse.success(
            text="Tool recovered successfully",
            data={"ok": True},
        ),
    )
    print("After success:", breaker.get_status(tool_name))


if __name__ == "__main__":
    main()
