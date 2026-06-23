import unittest

from my_hello_agents.context.history import HistoryManager
from my_hello_agents.core.llm_response import LLMResponse
from my_hello_agents.core.message import Message


class FakeLLM:
    def __init__(self):
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return LLMResponse(
            content="The earlier conversation discussed greetings and project setup.",
            model="fake-summary-model",
        )


class HistoryManagerTest(unittest.TestCase):
    def test_history_without_llm_appends_rounds_and_serializes(self):
        history = HistoryManager(min_retain_rounds=2)

        history.append(Message("hello", "user"))
        history.append(Message("hi", "assistant"))
        history.append(Message("what can you do?", "user"))
        history.append(Message("I can help with code.", "assistant"))

        self.assertEqual(history.estimate_rounds(), 2)
        self.assertEqual(history.find_round_boundaries(), [0, 2])

        data = history.to_dict()
        self.assertEqual(data["rounds"], 2)
        self.assertEqual(len(data["history"]), 4)
        self.assertEqual(data["history"][0]["role"], "user")
        self.assertEqual(data["history"][1]["content"], "hi")

        restored = HistoryManager()
        restored.load_from_dict(data)

        self.assertEqual(restored.estimate_rounds(), 2)
        self.assertEqual(
            [message.to_text() for message in restored.get_history()],
            [
                "[user] hello",
                "[assistant] hi",
                "[user] what can you do?",
                "[assistant] I can help with code.",
            ],
        )

    def test_history_with_llm_summary_compresses_old_rounds(self):
        history = HistoryManager(min_retain_rounds=1)
        history.append(Message("hello", "user"))
        history.append(Message("hi", "assistant"))
        history.append(Message("what is this project?", "user"))
        history.append(Message("It is an agent framework.", "assistant"))
        history.append(Message("what should I learn next?", "user"))
        history.append(Message("Learn history management.", "assistant"))

        fake_llm = FakeLLM()
        summary_prompt = [
            {
                "role": "user",
                "content": "\n".join(message.to_text() for message in history.get_history()),
            }
        ]

        summary_response = fake_llm.invoke(summary_prompt)
        history.compress(summary_response.content)

        compressed = history.get_history()

        self.assertEqual(len(fake_llm.calls), 1)
        self.assertEqual(fake_llm.calls[0], summary_prompt)
        self.assertEqual(history.estimate_rounds(), 1)
        self.assertEqual(compressed[0].role, "summary")
        self.assertIn("Archived Session Summary", compressed[0].content)
        self.assertIn("earlier conversation", compressed[0].content)
        self.assertEqual(
            [message.to_text() for message in compressed[1:]],
            [
                "[user] what should I learn next?",
                "[assistant] Learn history management.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
