from pathlib import Path
from tempfile import TemporaryDirectory

from my_hello_agents.core.message import Message
from my_hello_agents.core.session_store import SessionStore


def main() -> None:
    with TemporaryDirectory() as tmpdir:
        store = SessionStore()

        filepath = store.save(
            agent_config={
                "name": "demo_agent",
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "max_steps": 5,
            },
            history=[
                Message("Summarize this document", "user"),
                {
                    "role": "assistant",
                    "content": "The document is about session persistence.",
                },
            ],
            tool_schema_hash="tool-hash-v1",
            read_cache={"doc.txt": {"size": 128}},
            metadata={"total_tokens": 42, "steps": 1},
            session_name="demo_session",
        )

        print("Saved file:", filepath)
        print("File exists:", Path(filepath).exists())

        loaded = store.load(filepath)
        print("Session id:", loaded["session_id"])
        print("History:", loaded["history"])
        print("Metadata:", loaded["metadata"])

        print("Sessions:", store.list_sessions())

        config_check = store.check_config_consistency(
            saved_config=loaded["agent_config"],
            current_config={
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "max_steps": 5,
            },
        )
        print("Config consistency:", config_check)

        tool_check = store.check_tool_schema_consistency(
            saved_hash=loaded["tool_schema_hash"],
            current_hash="tool-hash-v2",
        )
        print("Tool schema consistency:", tool_check)

        # print("Deleted:", store.delete("demo_session"))
        # print("File exists after delete:", Path(filepath).exists())


if __name__ == "__main__":
    main()
