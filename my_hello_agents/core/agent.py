"""Agent基类"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING, AsyncGenerator
import asyncio
from .message import Message
from .llm import HelloAgentsLLM
from .config import Config
from .lifecycle import AgentEvent, AgentEventType, LifecycleHook, ExecutionContext
from ..context.history import HistoryManager
from .llm_response import LLMResponse

if TYPE_CHECKING:
    from ..tools.registry import ToolRegistry
    from ..tools.tool_filter import ToolFilter


class Agent(ABC):
    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: str = "",
        config: Optional[Config] = None,
        tool_registry: Optional["ToolRegistry"] = None,
        history_manager: Optional["HistoryManager"] = None,
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.config = config or Config()
        self.tool_registry = tool_registry

        self.on_start: LifecycleHook = None
        self.on_step: LifecycleHook = None
        self.on_finish: LifecycleHook = None
        self.on_error: LifecycleHook = None

        self.history_manager = (
            history_manager
            if history_manager is not None
            else HistoryManager(
                min_retain_rounds=self.config.min_retain_rounds,
                compression_threshold=self.config.compression_threshold,
            )
        )

    @abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
        """Run the agent synchronously."""
        pass

    def _build_messages(self, history: List[Message]) -> List[Dict[str, str]]:
        result_message: List[Dict[str, str]] = []
        if self.system_prompt:
            result_message.append({"role": "system", "content": self.system_prompt})
        for msg in history:
            result_message.append(
                {
                    "role": "system" if msg.role == "summary" else msg.role,
                    "content": msg.content,
                }
            )
        return result_message

    def _prepare_messages(self, input_text: str) -> List[Dict[str, str]]:
        user_msg = Message(content=input_text, role="user")
        self.history_manager.append(user_msg)
        return self._build_messages(self.history_manager.get_history())

    def _invoke_llm(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> str:
        llm_resp: LLMResponse = self.llm.invoke(
            messages=messages, **kwargs
        )
        llm_msg = Message(content=llm_resp.content, role="assistant")
        self.history_manager.append(llm_msg)
        return llm_resp.content
