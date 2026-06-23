from dotenv import load_dotenv

from my_hello_agents.core.llm import HelloAgentsLLM
from my_hello_agents.core.message import Message
from my_hello_agents.core.session_store import SessionStore


def main() -> None:
    load_dotenv()

    llm = HelloAgentsLLM()
    store = SessionStore(session_dir="memory/sessions")

    user_message = Message("用一句话解释 SessionStore 的作用", "user")
    messages = [
        {"role": user_message.role, "content": user_message.content},
    ]

    response = llm.invoke(messages)
    assistant_message = Message(
        response.content,
        "assistant",
        metadata={
            "model": response.model,
            "usage": response.usage,
            "latency_ms": response.latency_ms,
        },
    )

    filepath = store.save(
        agent_config={
            "name": "session_llm_demo",
            "llm_provider": "openai-compatible",
            "llm_model": llm.model,
            "max_steps": 1,
        },
        history=[user_message, assistant_message],
        tool_schema_hash="no-tools",
        read_cache={},
        metadata={
            "total_tokens": response.usage.get("total_tokens", 0),
            "latency_ms": response.latency_ms,
            "steps": 1,
        },
        session_name="llm_demo_session",
    )

    print("LLM response:", response.content)
    print("Saved session:", filepath)

    loaded = store.load(filepath)
    print("Loaded history:")
    for message in loaded["history"]:
        print(f"- {message['role']}: {message['content']}")


if __name__ == "__main__":
    main()
