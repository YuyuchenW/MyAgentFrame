import asyncio

from my_hello_agents.core.lifecycle import (
    AgentEvent,
    AgentEventType,
    ExecutionContext,
)


async def print_event(event: AgentEvent) -> None:
    """A minimal lifecycle hook."""
    print(event)


async def main() -> None:
    agent_name = "demo_agent"
    context = ExecutionContext(input_text="Summarize this document")

    await print_event(
        AgentEvent.create(
            AgentEventType.AGENT_START,
            agent_name,
            input_text=context.input_text,
        )
    )

    context.increment_step()
    await print_event(
        AgentEvent.create(
            AgentEventType.STEP_START,
            agent_name,
            step=context.current_step,
        )
    )

    await print_event(
        AgentEvent.create(
            AgentEventType.LLM_CHUNK,
            agent_name,
            chunk="The document is about...",
        )
    )

    context.add_tokens(42)
    context.set_metadata("final_answer", "The document is about lifecycle hooks.")

    await print_event(
        AgentEvent.create(
            AgentEventType.AGENT_Finish,
            agent_name,
            total_tokens=context.total_tokens,
            final_answer=context.get_metadata("final_answer"),
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
