import asyncio

from my_hello_agents.core.streaming import (
    StreamBuffer,
    StreamEvent,
    StreamEventType,
    stream_to_json,
    stream_to_sse,
)


async def demo_event_stream():
    yield StreamEvent.create(
        StreamEventType.AGENT_START,
        "demo_agent",
        input_text="Write a summary",
    )
    yield StreamEvent.create(
        StreamEventType.LLM_CHUNK,
        "demo_agent",
        chunk="The",
    )
    yield StreamEvent.create(
        StreamEventType.LLM_CHUNK,
        "demo_agent",
        chunk=" document is about streaming events.",
    )
    yield StreamEvent.create(
        StreamEventType.AGENT_FINISH,
        "demo_agent",
        final_answer="The document is about streaming events.",
    )


async def main() -> None:
    buffer = StreamBuffer(max_buffer_size=3)

    print("Buffer demo:")
    for event_type in [
        StreamEventType.AGENT_START,
        StreamEventType.STEP_START,
        StreamEventType.LLM_CHUNK,
        StreamEventType.AGENT_FINISH,
    ]:
        buffer.add(StreamEvent.create(event_type, "demo_agent"))

    for event in buffer.get_all():
        print(event.to_dict())

    print("\nSSE demo:")
    async for sse in stream_to_sse(demo_event_stream()):
        print(sse, end="")

    print("JSON Lines demo:")
    async for line in stream_to_json(
        demo_event_stream(),
        include_types=[StreamEventType.LLM_CHUNK],
    ):
        print(line, end="")


if __name__ == "__main__":
    asyncio.run(main())
