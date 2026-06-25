import unittest

from my_hello_agents.tools import (
    CalculatorTool,
    ToolErrorCode,
    ToolRegistry,
    ToolStatus,
    create_calculator_registry,
)


class CalculatorToolTest(unittest.IsolatedAsyncioTestCase):
    def test_basic_arithmetic(self):
        response = CalculatorTool().run(
            {"expression": "(12 + 3) * 4 - 5"}
        )

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data["result"], 55)
        self.assertEqual(response.text, "(12 + 3) * 4 - 5 = 55")

    def test_supported_operators(self):
        tool = CalculatorTool()

        self.assertEqual(tool.run({"expression": "7 / 2"}).data["result"], 3.5)
        self.assertEqual(tool.run({"expression": "7 // 2"}).data["result"], 3)
        self.assertEqual(tool.run({"expression": "7 % 2"}).data["result"], 1)
        self.assertEqual(tool.run({"expression": "-2 ** 3"}).data["result"], -8)

    def test_registry_execution_and_schema(self):
        registry = ToolRegistry()
        registry.register_tool(CalculatorTool())

        response = registry.execute_tool(
            "calculator",
            '{"expression": "2 ** 10"}',
        )
        schema = registry.get_openai_schemas()[0]

        self.assertEqual(response.data["result"], 1024)
        self.assertEqual(schema["function"]["name"], "calculator")
        self.assertEqual(
            schema["function"]["parameters"]["required"],
            ["expression"],
        )
        self.assertEqual(
            schema["function"]["parameters"]["properties"]["expression"]["type"],
            "string",
        )

    async def test_async_registry_execution(self):
        registry = create_calculator_registry()

        response = await registry.aexecute_tool(
            "calculator",
            {"expression": "100 // 9"},
        )

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data["result"], 11)
        self.assertIn("time_ms", response.stats)

    def test_missing_expression(self):
        registry = create_calculator_registry()

        response = registry.execute_tool("calculator", {})

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.INVALID_PARAM,
        )

    def test_division_by_zero_is_error(self):
        response = CalculatorTool().run({"expression": "10 / 0"})

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.INVALID_PARAM,
        )

    def test_python_code_is_rejected(self):
        response = CalculatorTool().run(
            {"expression": "__import__('os').getcwd()"}
        )

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertIn("not allowed", response.text)

    def test_large_exponent_is_rejected(self):
        response = CalculatorTool(max_exponent=10).run(
            {"expression": "2 ** 11"}
        )

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertIn("exponent", response.text)


if __name__ == "__main__":
    unittest.main()
