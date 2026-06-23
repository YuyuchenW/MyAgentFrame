import json
import time
import unittest

from my_hello_agents.core.streaming import (
    StreamBuffer,
    StreamEvent,
    StreamEventType,
    stream_to_json,
    stream_to_sse,
)


async def make_event_stream():
    yield StreamEvent(
        type=StreamEventType.AGENT_START,
        timestamp=1.0,
        agent_name="demo_agent",
        data={"input_text": "hello"},
    )
    yield StreamEvent(
        type=StreamEventType.LLM_CHUNK,
        timestamp=2.0,
        agent_name="demo_agent",
        data={"chunk": "hi"},
    )
    yield StreamEvent(
        type=StreamEventType.AGENT_FINISH,
        timestamp=3.0,
        agent_name="demo_agent",
        data={"final_answer": "done"},
    )


async def collect_async(async_iterable):
    return [item async for item in async_iterable]


class StreamEventTest(unittest.IsolatedAsyncioTestCase):
    def test_create_event(self):
        before = time.time()

        event = StreamEvent.create(
            StreamEventType.TOOL_CALL_START,
            "demo_agent",
            tool_name="search",
            tool_args={"query": "hello"},
        )

        after = time.time()
        self.assertEqual(event.type, StreamEventType.TOOL_CALL_START)
        self.assertEqual(event.agent_name, "demo_agent")
        self.assertGreaterEqual(event.timestamp, before)
        self.assertLessEqual(event.timestamp, after)
        self.assertEqual(
            event.data,
            {"tool_name": "search", "tool_args": {"query": "hello"}},
        )

    def test_to_dict(self):
        event = StreamEvent(
            type=StreamEventType.LLM_CHUNK,
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

    def test_to_sse(self):
        event = StreamEvent(
            type=StreamEventType.LLM_CHUNK,
            timestamp=123.45,
            agent_name="demo_agent",
            data={"chunk": "hello"},
        )

        sse = event.to_sse()
        self.assertTrue(sse.startswith("event: llm_chunk\n"))
        self.assertTrue(sse.endswith("\n\n"))

        data_line = sse.splitlines()[1]
        self.assertTrue(data_line.startswith("data: "))
        payload = json.loads(data_line.removeprefix("data: "))

        self.assertEqual(payload["type"], "llm_chunk")
        self.assertEqual(payload["timestamp"], 123.45)
        self.assertEqual(payload["agent_name"], "demo_agent")
        self.assertEqual(payload["data"], {"chunk": "hello"})

    async def test_stream_to_sse_returns_all_events(self):
        items = await collect_async(stream_to_sse(make_event_stream()))

        self.assertEqual(len(items), 3)
        self.assertIn("event: agent_start", items[0])
        self.assertIn("event: llm_chunk", items[1])
        self.assertIn("event: agent_finish", items[2])

    async def test_stream_to_sse_can_filter_event_types(self):
        items = await collect_async(
            stream_to_sse(
                make_event_stream(),
                include_types=[StreamEventType.LLM_CHUNK],
            )
        )

        self.assertEqual(len(items), 1)
        self.assertIn("event: llm_chunk", items[0])
        self.assertNotIn("event: agent_start", items[0])

    async def test_stream_to_json_returns_json_lines(self):
        items = await collect_async(
            stream_to_json(
                make_event_stream(),
                include_types=[StreamEventType.LLM_CHUNK],
            )
        )

        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].endswith("\n"))

        payload = json.loads(items[0])
        self.assertEqual(payload["type"], "llm_chunk")
        self.assertEqual(payload["agent_name"], "demo_agent")
        self.assertEqual(payload["data"], {"chunk": "hi"})


class StreamBufferTest(unittest.TestCase):
    def test_add_and_get_all_returns_copy(self):
        buffer = StreamBuffer(max_buffer_size=10)
        event = StreamEvent.create(StreamEventType.AGENT_START, "demo_agent")

        buffer.add(event)
        events = buffer.get_all()
        events.clear()

        self.assertEqual(buffer.get_all(), [event])

    def test_buffer_drops_oldest_event_when_full(self):
        buffer = StreamBuffer(max_buffer_size=2)
        first = StreamEvent.create(StreamEventType.AGENT_START, "demo_agent")
        second = StreamEvent.create(StreamEventType.LLM_CHUNK, "demo_agent")
        third = StreamEvent.create(StreamEventType.AGENT_FINISH, "demo_agent")

        buffer.add(first)
        buffer.add(second)
        buffer.add(third)

        self.assertEqual(buffer.get_all(), [second, third])

    def test_filter_by_type(self):
        buffer = StreamBuffer(max_buffer_size=10)
        agent_start = StreamEvent.create(StreamEventType.AGENT_START, "demo_agent")
        llm_chunk = StreamEvent.create(StreamEventType.LLM_CHUNK, "demo_agent")
        agent_finish = StreamEvent.create(StreamEventType.AGENT_FINISH, "demo_agent")

        buffer.add(agent_start)
        buffer.add(llm_chunk)
        buffer.add(agent_finish)

        self.assertEqual(
            buffer.filter_by_type(StreamEventType.LLM_CHUNK),
            [llm_chunk],
        )

    def test_clear(self):
        buffer = StreamBuffer(max_buffer_size=10)
        buffer.add(StreamEvent.create(StreamEventType.AGENT_START, "demo_agent"))

        buffer.clear()

        self.assertEqual(buffer.get_all(), [])


if __name__ == "__main__":
    unittest.main()
