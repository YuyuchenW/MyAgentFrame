import asyncio
import time
import unittest

from my_hello_agents.core.lifecycle import (
    AgentEvent,
    AgentEventType,
    ExecutionContext,
)


class AgentEventTest(unittest.TestCase):
    def test_create_event(self):
        before = time.time()

        event = AgentEvent.create(
            AgentEventType.TOOL_START,
            "demo_agent",
            tool_name="search",
            tool_args={"query": "hello"},
        )

        after = time.time()
        self.assertEqual(event.type, AgentEventType.TOOL_START)
        self.assertEqual(event.agent_name, "demo_agent")
        self.assertGreaterEqual(event.timestamp, before)
        self.assertLessEqual(event.timestamp, after)
        self.assertEqual(
            event.data,
            {"tool_name": "search", "tool_args": {"query": "hello"}},
        )

    def test_to_dict(self):
        event = AgentEvent(
            type=AgentEventType.LLM_CHUNK,
            timestamp=123.45,
            agent_name="demo_agent",
            data={"chunk": "hello"},
        )

        self.assertEqual(
            event.to_dict(),
            {
                "type": "llm_chunk",
                "timestamp": 123.45,
                "agent_name": "demo_agent",
                "data": {"chunk": "hello"},
            },
        )

    def test_string_format(self):
        event = AgentEvent(
            type=AgentEventType.AGENT_START,
            timestamp=123.456,
            agent_name="demo_agent",
            data={"input": "hello"},
        )

        self.assertEqual(
            str(event),
            "[agent_start] demo_agent @ 123.46: {'input': 'hello'}",
        )

    def test_async_hook_can_receive_event(self):
        received = []
        event = AgentEvent.create(AgentEventType.AGENT_START, "demo_agent")

        async def hook(received_event: AgentEvent):
            received.append(received_event)

        asyncio.run(hook(event))

        self.assertEqual(received, [event])


class ExecutionContextTest(unittest.TestCase):
    def test_context_defaults(self):
        context = ExecutionContext(input_text="hello")

        self.assertEqual(context.input_text, "hello")
        self.assertEqual(context.current_step, 0)
        self.assertEqual(context.total_tokens, 0)
        self.assertEqual(context.metadata, {})

    def test_step_and_token_counters(self):
        context = ExecutionContext(input_text="hello")

        context.increment_step()
        context.increment_step()
        context.add_tokens(10)
        context.add_tokens(5)

        self.assertEqual(context.current_step, 2)
        self.assertEqual(context.total_tokens, 15)

    def test_metadata_helpers(self):
        context = ExecutionContext(input_text="hello")

        context.set_metadata("trace_id", "trace_123")

        self.assertEqual(context.get_metadata("trace_id"), "trace_123")
        self.assertEqual(context.get_metadata("missing", "default"), "default")


if __name__ == "__main__":
    unittest.main()
