"""工具子系统入口。

目前提供 python-docx 工具集，并暴露与 HelloAgentsLLM.invoke_with_tools 对接的
辅助函数：get_docx_tool_schemas / dispatch_tool_call / run_with_tools。
"""

import json
from typing import Any, Dict, List, Optional

from my_hello_agents.core.llm import HelloAgentsLLM
from my_hello_agents.core.llm_response import ToolCall
from my_hello_agents.tools.builtin.docx_tools import (
    DOCX_TOOLS,
    get_tool_schemas,
    run_tool,
)

__all__ = [
    "DOCX_TOOLS",
    "get_docx_tool_schemas",
    "dispatch_tool_call",
    "run_with_tools",
]


def get_docx_tool_schemas() -> List[Dict[str, Any]]:
    """返回 docx 工具集的 OpenAI function-calling schema 列表。"""
    return get_tool_schemas()


def dispatch_tool_call(tc: ToolCall) -> str:
    """执行单个 ToolCall，返回可直接作为 'tool' 消息 content 的字符串。"""
    try:
        args = json.loads(tc.arguments) if tc.arguments else {}
    except json.JSONDecodeError as e:
        return json.dumps({"ok": False, "error": f"参数 JSON 解析失败: {e}"}, ensure_ascii=False)
    result = run_tool(tc.name, args)
    return json.dumps(result, ensure_ascii=False)


def run_with_tools(
    llm: HelloAgentsLLM,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    max_steps: int = 100,
    verbose: bool = True,
) -> Optional[str]:
    """自动工具调用循环。

    流程：模型返回 tool_calls -> 逐个执行 -> 回填 tool 消息 -> 再问模型，
    直到模型不再调用工具或达到 max_steps 上限。
    """
    for step in range(max_steps):
        resp = llm.invoke_with_tools(messages, tools)

        if not resp.tool_calls:
            if verbose and resp.content:
                print("\n[模型回复]:", resp.content)
            return resp.content

        # 记录 assistant 消息（含 tool_calls）
        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": resp.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in resp.tool_calls
            ],
        }
        messages.append(assistant_msg)

        # 执行每个工具并回填 tool 消息
        for tc in resp.tool_calls:
            if verbose:
                print(f"\n[调用工具] {tc.name}  参数: {tc.arguments}")
            content = dispatch_tool_call(tc)
            if verbose:
                print(f"[工具结果] {content[:500]}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": content,
                }
            )

    return "达到最大工具调用步数，循环终止。"