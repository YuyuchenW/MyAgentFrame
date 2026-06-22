import unittest
from datetime import datetime

from pydantic import ValidationError

from my_hello_agents.core.message import Message


class MessageTest(unittest.TestCase):
    def test_create_message_with_defaults(self):
        message = Message("hello", "user")

        self.assertEqual(message.content, "hello")
        self.assertEqual(message.role, "user")
        self.assertIsInstance(message.timestamp, datetime)
        self.assertIsNone(message.metadata)

    def test_create_message_with_metadata_and_timestamp(self):
        timestamp = datetime(2026, 6, 20, 10, 30, 0)
        message = Message(
            "tool result",
            "tool",
            timestamp=timestamp,
            metadata={"tool_call_id": "call_123"},
        )

        self.assertEqual(message.timestamp, timestamp)
        self.assertEqual(message.metadata, {"tool_call_id": "call_123"})

    def test_to_dict_and_from_dict_round_trip(self):
        original = Message(
            "hi",
            "assistant",
            timestamp=datetime(2026, 6, 20, 10, 30, 0),
            metadata={"model": "test-model"},
        )

        restored = Message.from_dict(original.to_dict())

        self.assertEqual(restored.content, original.content)
        self.assertEqual(restored.role, original.role)
        self.assertEqual(restored.timestamp, original.timestamp)
        self.assertEqual(restored.metadata, original.metadata)

    def test_text_format(self):
        message = Message("hello", "system")

        self.assertEqual(message.to_text(), "[system] hello")
        self.assertEqual(str(message), "[system] hello")

    def test_invalid_role_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            Message("hello", "invalid")


if __name__ == "__main__":
    unittest.main()
