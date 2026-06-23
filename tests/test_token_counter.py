import unittest

from my_hello_agents.context.token_counter import TokenCounter
from my_hello_agents.core.message import Message


class TokenCounterTest(unittest.TestCase):
    def test_count_text_returns_integer(self):
        counter = TokenCounter(model="gpt-4")

        tokens = counter.count_text("hello world")

        self.assertIsInstance(tokens, int)
        self.assertGreater(tokens, 0)

    def test_count_message_adds_role_overhead(self):
        counter = TokenCounter(model="gpt-4")
        message = Message("hello world", "user")

        text_tokens = counter.count_text(message.content)
        message_tokens = counter.count_message(message)

        self.assertEqual(message_tokens, text_tokens + 4)

    def test_count_messages_sums_each_message(self):
        counter = TokenCounter(model="gpt-4")
        messages = [
            Message("hello", "user"),
            Message("hi there", "assistant"),
            Message("tool output", "tool"),
        ]

        expected = sum(counter.count_message(message) for message in messages)

        self.assertEqual(counter.count_messages(messages), expected)

    def test_count_message_uses_cache_for_same_role_and_content(self):
        counter = TokenCounter(model="gpt-4")
        first = Message("same content", "user")
        second = Message("same content", "user")

        first_tokens = counter.count_message(first)
        second_tokens = counter.count_message(second)

        self.assertEqual(first_tokens, second_tokens)
        self.assertEqual(counter.get_cache_size(), 1)
        self.assertEqual(
            counter.get_cache_stats(),
            {
                "cached_messages": 1,
                "total_cached_tokens": first_tokens,
            },
        )

    def test_cache_key_includes_role(self):
        counter = TokenCounter(model="gpt-4")

        counter.count_message(Message("same content", "user"))
        counter.count_message(Message("same content", "assistant"))

        self.assertEqual(counter.get_cache_size(), 2)

    def test_clear_cache(self):
        counter = TokenCounter(model="gpt-4")
        counter.count_message(Message("hello", "user"))

        counter.clear_cache()

        self.assertEqual(counter.get_cache_size(), 0)
        self.assertEqual(
            counter.get_cache_stats(),
            {"cached_messages": 0, "total_cached_tokens": 0},
        )

    def test_unknown_model_falls_back_to_general_encoding(self):
        counter = TokenCounter(model="unknown-model-name")

        self.assertIsInstance(counter.count_text("abcdefgh"), int)
        self.assertGreater(counter.count_text("abcdefgh asd"), 1)

    def test_fallback_character_estimate_when_encoding_is_none(self):
        counter = TokenCounter(model="gpt-4")
        counter._encoding = None

        self.assertEqual(counter.count_text("abcdefgh"), 2)
        self.assertEqual(counter.count_message(Message("abcdefgh", "user")), 6)


if __name__ == "__main__":
    unittest.main()
