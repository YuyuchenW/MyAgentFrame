import asyncio

from my_hello_agents.tools import (
    CalculatorTool,
    ToolRegistry,
    create_calculator_registry,
)


async def main() -> None:
    # 1. A Tool can be executed directly.
    tool = CalculatorTool()
    direct_response = tool.run_with_timing(
        {"expression": "(12 + 3) * 4"}
    )
    print("Direct response:", direct_response.to_dict())

    # 2. The normal framework path is Tool -> ToolRegistry -> ToolResponse.
    registry = ToolRegistry()
    registry.register_tool(tool)

    response = registry.execute_tool(
        "calculator",
        {"expression": "2 ** 8 + 10 / 2"},
    )
    print("Registry response:", response.to_dict())

    # 3. The registry provides schemas that can be sent to an LLM.
    print("OpenAI schema:", registry.get_openai_schemas()[0])

    # 4. The same tool can be executed through the asynchronous registry API.
    async_response = await registry.aexecute_tool(
        "calculator",
        {"expression": "100 // 9"},
    )
    print("Async response:", async_response.to_dict())

    # 5. Convenience factory when only the calculator is needed.
    calculator_registry = create_calculator_registry()
    print("Registered tools:", calculator_registry.get_tool_names())


if __name__ == "__main__":
    asyncio.run(main())
