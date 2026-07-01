import unittest

from my_hello_agents.core.agent import Agent
from my_hello_agents.core.config import Config
from my_hello_agents.core.llm_response import LLMResponse
from my_hello_agents.core.message import Message
from my_hello_agents.context.history import HistoryManager


class StubAgent(Agent):
    def run(self, input_text: str, **kwargs) -> str:
        return input_text


class FalsyHistoryManager(HistoryManager):
    def __bool__(self):
        return False


class RecordingLLM:
    def __init__(self):
        self.calls = []

    def invoke(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(content="PONG", model="fake")


class FailingLLM:
    def invoke(self, messages, **kwargs):
        raise RuntimeError("LLM unavailable")


class AgentMessageBuildingTest(unittest.TestCase):
    def test_build_messages_adds_system_prompt_and_converts_summary(self):
        agent = StubAgent("stub", object(), system_prompt="Be helpful.")
        summary = Message("Earlier discussion", "summary")
        history = [summary, Message("Hello", "user")]

        messages = agent._build_messages(history)

        self.assertEqual(
            messages,
            [
                {"role": "system", "content": "Be helpful."},
                {"role": "system", "content": "Earlier discussion"},
                {"role": "user", "content": "Hello"},
            ],
        )
        self.assertEqual(summary.role, "summary")
        self.assertEqual(len(history), 2)

    def test_build_messages_omits_empty_system_prompt(self):
        agent = StubAgent("stub", object())

        messages = agent._build_messages([Message("Hello", "user")])

        self.assertEqual(messages, [{"role": "user", "content": "Hello"}])

    def test_constructor_preserves_injected_falsy_history_manager(self):
        history_manager = FalsyHistoryManager()

        agent = StubAgent("stub", object(), history_manager=history_manager)

        self.assertIs(agent.history_manager, history_manager)

    def test_constructor_configures_default_history_manager(self):
        config = Config(min_retain_rounds=3, compression_threshold=0.6)

        agent = StubAgent("stub", object(), config=config)

        self.assertIsInstance(agent.history_manager, HistoryManager)
        self.assertEqual(agent.history_manager.min_retain_rounds, 3)
        self.assertEqual(agent.history_manager.compression_threshold, 0.6)

    def test_prepare_messages_accumulates_user_history(self):
        agent = StubAgent("stub", object(), system_prompt="Be helpful.")

        first = agent._prepare_messages("first")
        second = agent._prepare_messages("second")

        self.assertEqual(
            first,
            [
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "first"},
            ],
        )
        self.assertEqual(
            second,
            [
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "first"},
                {"role": "user", "content": "second"},
            ],
        )
        self.assertEqual(
            [message.role for message in agent.history_manager.get_history()],
            ["user", "user"],
        )

    def test_invoke_llm_forwards_arguments_and_records_assistant(self):
        llm = RecordingLLM()
        agent = StubAgent("stub", llm)
        messages = [{"role": "user", "content": "ping"}]

        result = agent._invoke_llm(messages, temperature=0.2)

        self.assertEqual(result, "PONG")
        self.assertEqual(llm.calls, [(messages, {"temperature": 0.2})])
        self.assertEqual(
            [message.to_text() for message in agent.history_manager.get_history()],
            ["[assistant] PONG"],
        )

    def test_invoke_llm_does_not_record_assistant_on_error(self):
        agent = StubAgent("stub", FailingLLM())

        with self.assertRaisesRegex(RuntimeError, "LLM unavailable"):
            agent._invoke_llm([{"role": "user", "content": "ping"}])

        self.assertEqual(agent.history_manager.get_history(), [])


if __name__ == "__main__":
    unittest.main()
