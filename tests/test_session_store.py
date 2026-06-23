import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from my_hello_agents.core.message import Message
from my_hello_agents.core.session_store import SessionStore


class SessionStoreTest(unittest.TestCase):
    def test_init_creates_session_directory(self):
        with TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "sessions"

            SessionStore(session_dir=str(session_dir))

            self.assertTrue(session_dir.exists())
            self.assertTrue(session_dir.is_dir())

    def test_generate_session_id_format(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)

            session_id = store._generate_session_id()

            self.assertRegex(
                session_id,
                r"^s-\d{8}-\d{6}-[0-9a-f]{8}$",
            )

    def test_save_and_load_session(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)
            history = [
                Message("hello", "user", metadata={"source": "test"}),
                {"role": "assistant", "content": "hi"},
            ]

            filepath = store.save(
                agent_config={"name": "demo_agent", "llm_model": "test-model"},
                history=history,
                tool_schema_hash="hash-v1",
                read_cache={"file.txt": {"lines": 10}},
                metadata={"total_tokens": 12},
                session_name="demo_session",
            )

            loaded = store.load(filepath)

            self.assertEqual(Path(filepath).name, "demo_session.json")
            self.assertEqual(loaded["agent_config"]["name"], "demo_agent")
            self.assertEqual(loaded["tool_schema_hash"], "hash-v1")
            self.assertEqual(loaded["read_cache"], {"file.txt": {"lines": 10}})
            self.assertEqual(loaded["metadata"], {"total_tokens": 12})
            self.assertEqual(loaded["history"][0]["role"], "user")
            self.assertEqual(loaded["history"][0]["content"], "hello")
            self.assertEqual(loaded["history"][0]["metadata"], {"source": "test"})
            self.assertEqual(loaded["history"][1], {"role": "assistant", "content": "hi"})

    def test_save_without_session_name_uses_generated_filename(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)

            filepath = store.save(
                agent_config={},
                history=[],
                tool_schema_hash="hash-v1",
                read_cache={},
                metadata={},
            )

            self.assertRegex(
                Path(filepath).name,
                r"^session-s-\d{8}-\d{6}-[0-9a-f]{8}\.json$",
            )

    def test_save_uses_metadata_created_at_when_provided(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)

            filepath = store.save(
                agent_config={},
                history=[],
                tool_schema_hash="hash-v1",
                read_cache={},
                metadata={"created_at": "2026-06-23T10:00:00"},
                session_name="created_at_session",
            )

            loaded = store.load(filepath)

            self.assertEqual(loaded["created_at"], "2026-06-23T10:00:00")
            self.assertEqual(loaded["metadata"]["created_at"], "2026-06-23T10:00:00")

    def test_save_leaves_no_temp_file_after_success(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)

            filepath = store.save(
                agent_config={},
                history=[],
                tool_schema_hash="hash-v1",
                read_cache={},
                metadata={},
                session_name="atomic_session",
            )

            self.assertTrue(Path(filepath).exists())
            self.assertFalse(Path(f"{filepath}.tmp").exists())

    def test_list_sessions_returns_metadata_sorted_by_saved_at_desc(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)

            older = Path(tmpdir) / "older.json"
            newer = Path(tmpdir) / "newer.json"
            older.write_text(
                json.dumps(
                    {
                        "session_id": "older-id",
                        "created_at": "2026-06-23T10:00:00",
                        "saved_at": "2026-06-23T10:01:00",
                        "metadata": {"name": "older"},
                    }
                ),
                encoding="utf-8",
            )
            newer.write_text(
                json.dumps(
                    {
                        "session_id": "newer-id",
                        "created_at": "2026-06-23T11:00:00",
                        "saved_at": "2026-06-23T11:01:00",
                        "metadata": {"name": "newer"},
                    }
                ),
                encoding="utf-8",
            )

            sessions = store.list_sessions()

            self.assertEqual([s["session_id"] for s in sessions], ["newer-id", "older-id"])
            self.assertEqual(sessions[0]["filename"], "newer.json")
            self.assertEqual(sessions[0]["metadata"], {"name": "newer"})

    def test_delete_existing_and_missing_session(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)
            filepath = Path(tmpdir) / "demo_session.json"
            filepath.write_text("{}", encoding="utf-8")

            self.assertTrue(store.delete("demo_session"))
            self.assertFalse(filepath.exists())
            self.assertFalse(store.delete("demo_session"))

    def test_check_config_consistency_when_same(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)
            config = {
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "max_steps": 5,
            }

            result = store.check_config_consistency(config, config.copy())

            self.assertEqual(result, {"consistent": True, "warnings": []})

    def test_check_config_consistency_when_changed(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)

            result = store.check_config_consistency(
                saved_config={
                    "llm_provider": "openai",
                    "llm_model": "gpt-4",
                    "max_steps": 5,
                },
                current_config={
                    "llm_provider": "anthropic",
                    "llm_model": "claude",
                    "max_steps": 10,
                },
            )

            self.assertFalse(result["consistent"])
            self.assertEqual(len(result["warnings"]), 3)

    def test_check_tool_schema_consistency_when_same(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)

            result = store.check_tool_schema_consistency("hash-v1", "hash-v1")

            self.assertEqual(result["changed"], False)
            self.assertEqual(result["saved_hash"], "hash-v1")
            self.assertEqual(result["current_hash"], "hash-v1")

    def test_check_tool_schema_consistency_when_changed(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(session_dir=tmpdir)

            result = store.check_tool_schema_consistency("hash-v1", "hash-v2")

            self.assertEqual(result["changed"], True)
            self.assertEqual(result["saved_hash"], "hash-v1")
            self.assertEqual(result["current_hash"], "hash-v2")


if __name__ == "__main__":
    unittest.main()
