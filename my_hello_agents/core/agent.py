"""Agent基类"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING, AsyncGenerator
import asyncio
from .message import Message
from .llm import HelloAgentsLLM
from .config import Config
from .lifecycle import AgentEvent, AgentEventType, LifecycleHook, ExecutionContext

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

    @abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
        """Run the agent synchronously."""
        pass
