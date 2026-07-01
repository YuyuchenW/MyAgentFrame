import json
import io
from typing import List
import unittest
from contextlib import redirect_stdout

from my_hello_agents.tools import (
    CustomFilter,
    FullAccessFilter,
    ReadOnlyFilter,
    Tool,
    ToolErrorCode,
    ToolParameter,
    ToolRegistry,
    ToolResponse,
    ToolStatus,
    CircuitBreaker,
    create_docx_tool_registry,
    tool_action,
)


class AddTool(Tool):
    def __init__(self):
        super().__init__("add", "Add two integers")

    def get_parameters(self):
        return [
            ToolParameter(
                name="left",
                type="integer",
                description="Left operand",
            ),
            ToolParameter(
                name="right",
                type="integer",
                description="Right operand",
            ),
        ]

    def run(self, parameters):
        result = parameters["left"] + parameters["right"]
        return ToolResponse.success(
            text=str(result),
            data={"result": result},
        )

class AlwaysFailTool(Tool):
    def __init__(self):
        super().__init__("always_fail", "Always fail")

    def get_parameters(self):
        return []

    def run(self, parameters):
        return ToolResponse.error(
            code=ToolErrorCode.EXECUTION_ERROR,
            message="boom",
        )


class RepeatTextTool(Tool):
    def __init__(self):
        super().__init__("repeat_text", "repeat text")

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="text", type="string", description="input string", required=True
            ),
            ToolParameter(
                name="times",
                type="integer",
                description="repeat times",
                required=False,
                default=2,
            ),
        ]

    def run(self, parameters):
        text = parameters.get("text")
        if not isinstance(text, str):
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_PARAM, message="input text is not allowed"
            )

        times: int = parameters.get("times", 2)
        if not isinstance(times, int)  or isinstance(times, bool):
                return ToolResponse.error(
                    code=ToolErrorCode.INVALID_PARAM,
                    message="bool types is not allowed",
                )
        result = text * times
        if times > 0 and times < 6:
            return ToolResponse.success(
                text=result, data={"result": result, "times": times}
            )
        return ToolResponse.error(
            code=ToolErrorCode.INVALID_PARAM,
            message=f" times : {times} is not in range(1,5)",
        )


class InvalidReturnTool(Tool):
    def __init__(self):
        super().__init__("invalid_return", "Return the wrong response type")

    def get_parameters(self):
        return []

    def run(self, parameters):
        return "not a ToolResponse"


class ExpandableTextTool(Tool):
    def __init__(self):
        super().__init__("text", "Text actions", expandable=True)

    def get_parameters(self):
        return []

    def run(self, parameters):
        return ToolResponse.error(
            code=ToolErrorCode.EXECUTION_ERROR,
            message="Use an expanded action",
        )

    @tool_action("text_upper", "Uppercase text")
    def upper(self, text: str) -> str:
        """Uppercase text.

        Args:
            text: Text to convert.
        """
        return text.upper()

    @tool_action("text_async", "Return text asynchronously")
    async def async_text(self, text: str) -> str:
        """Return text asynchronously.

        Args:
            text: Text to return.
        """
        return f"async:{text}"


class ToolResponseTest(unittest.TestCase):
    def test_response_round_trip(self):
        response = ToolResponse.partial(
            text="truncated",
            data={"items": [1, 2]},
            stats={"time_ms": 4},
            context={"tool_name": "demo"},
        )

        restored = ToolResponse.from_json(response.to_json())

        self.assertEqual(restored.status, ToolStatus.PARTIAL)
        self.assertEqual(restored.text, "truncated")
        self.assertEqual(restored.data, {"items": [1, 2]})
        self.assertEqual(restored.stats, {"time_ms": 4})
        self.assertEqual(restored.context, {"tool_name": "demo"})


class ToolBaseTest(unittest.IsolatedAsyncioTestCase):
    def test_tool_schema_and_timing(self):
        tool = AddTool()

        schema = tool.to_openai_schema()
        response = tool.run_with_timing({"left": 2, "right": 3})

        self.assertEqual(schema["function"]["name"], "add")
        self.assertEqual(
            schema["function"]["parameters"]["required"],
            ["left", "right"],
        )
        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data, {"result": 5})
        self.assertIn("time_ms", response.stats)
        self.assertEqual(response.context["tool_name"], "add")
        self.assertEqual(
            response.context["params_input"],
            {"left": 2, "right": 3},
        )

    def test_invalid_return_is_wrapped_as_error(self):
        response = InvalidReturnTool().run_with_timing({})

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.INTERNAL_ERROR,
        )

    async def test_default_async_execution(self):
        response = await AddTool().arun_with_timing({"left": 4, "right": 5})

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data, {"result": 9})

    def test_repeat_text_schema_and_default_value(self):
        tool = RepeatTextTool()

        schema = tool.to_openai_schema()
        response = tool.run_with_timing({"text": "ha"})

        self.assertEqual(schema["function"]["name"], "repeat_text")
        self.assertEqual(
            schema["function"]["parameters"]["required"],
            ["text"],
        )
        self.assertIn(
            "默认: 2",
            schema["function"]["parameters"]["properties"]["times"]["description"],
        )
        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.text, "haha")
        self.assertEqual(response.data, {"result": "haha", "times": 2})

    def test_repeat_text_explicit_times(self):
        response = RepeatTextTool().run_with_timing(
            {"text": "go", "times": 3}
        )

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data, {"result": "gogogo", "times": 3})

    def test_repeat_text_rejects_invalid_text_type(self):
        response = RepeatTextTool().run_with_timing({"text": 123})

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.INVALID_PARAM,
        )

    def test_repeat_text_rejects_invalid_times_type(self):
        response = RepeatTextTool().run_with_timing(
            {"text": "ha", "times": 1.5}
        )

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.INVALID_PARAM,
        )

    def test_repeat_text_rejects_bool_times(self):
        response = RepeatTextTool().run_with_timing(
            {"text": "ha", "times": True}
        )

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.INVALID_PARAM,
        )

    def test_repeat_text_rejects_times_out_of_range(self):
        response = RepeatTextTool().run_with_timing(
            {"text": "ha", "times": 6}
        )

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.INVALID_PARAM,
        )

    async def test_repeat_text_async_matches_sync(self):
        tool = RepeatTextTool()

        sync_response = tool.run_with_timing({"text": "ha", "times": 2})
        async_response = await tool.arun_with_timing(
            {"text": "ha", "times": 2}
        )

        self.assertEqual(sync_response.status, ToolStatus.SUCCESS)
        self.assertEqual(async_response.status, ToolStatus.SUCCESS)
        self.assertEqual(sync_response.data, async_response.data)

    async def test_expandable_actions_support_sync_and_async_methods(self):
        expanded = ExpandableTextTool().get_expanded_tools()
        registry = ToolRegistry()
        for tool in expanded:
            registry.register_tool(tool)

        sync_response = registry.execute_tool(
            "text_upper",
            {"text": "hello"},
        )
        async_response = await registry.aexecute_tool(
            "text_async",
            {"text": "hello"},
        )

        self.assertEqual(sync_response.data["output"], "HELLO")
        self.assertEqual(async_response.data["output"], "async:hello")


class ToolRegistryTest(unittest.IsolatedAsyncioTestCase):
    def test_register_execute_and_list_tool(self):
        registry = ToolRegistry()
        tool = AddTool()

        registry.register_tool(tool)
        response = registry.execute_tool(
            "add",
            json.dumps({"left": 10, "right": 7}),
        )

        self.assertIs(registry.get_tool("add"), tool)
        self.assertEqual(registry.get_tool_names(), ["add"])
        self.assertEqual(response.data, {"result": 17})

    def test_missing_parameters_return_invalid_param(self):
        registry = ToolRegistry()
        registry.register_tool(AddTool())

        response = registry.execute_tool("add", {"left": 1})

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.INVALID_PARAM,
        )
        self.assertEqual(response.context["missing"], ["right"])

    def test_register_function_and_generate_schema(self):
        registry = ToolRegistry()

        def multiply(left: int, right: int = 2) -> int:
            """Multiply two integers."""
            return left * right

        registry.register_function(multiply)
        response = registry.execute_tool(
            "multiply",
            {"left": 3, "right": 4},
        )
        schema = registry.get_openai_schemas()[0]

        self.assertEqual(response.data["output"], 12)
        self.assertEqual(schema["function"]["name"], "multiply")
        self.assertEqual(
            schema["function"]["parameters"]["properties"]["left"]["type"],
            "integer",
        )
        self.assertEqual(
            schema["function"]["parameters"]["required"],
            ["left"],
        )

    async def test_async_function_execution(self):
        registry = ToolRegistry()

        async def greet(name: str) -> str:
            return f"hello {name}"

        registry.register_function(greet)
        response = await registry.aexecute_tool("greet", {"name": "Ada"})

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data["output"], "hello Ada")

    def test_schema_filtering(self):
        registry = ToolRegistry()
        registry.register_tool(AddTool())
        registry.register_function(lambda input: input, name="Read")
        registry.register_function(lambda input: input, name="Bash")

        read_only_names = {
            schema["function"]["name"]
            for schema in registry.get_openai_schemas(ReadOnlyFilter())
        }
        full_access_names = {
            schema["function"]["name"]
            for schema in registry.get_openai_schemas(FullAccessFilter())
        }
        custom_names = {
            schema["function"]["name"]
            for schema in registry.get_openai_schemas(
                CustomFilter(allowed=["add"], mode="whitelist")
            )
        }

        self.assertEqual(read_only_names, {"Read"})
        self.assertEqual(full_access_names, {"add", "Read"})
        self.assertEqual(custom_names, {"add"})

    def test_docx_tools_use_unified_registry(self):
        registry = create_docx_tool_registry()

        self.assertEqual(len(registry.get_tool_names()), 17)
        self.assertEqual(len(registry.get_openai_schemas()), 17)
        self.assertIn("docx_create", registry.get_tool_names())
        self.assertTrue(callable(registry.get_function("docx_create")))

    def test_string_input_func(self):
        registry = ToolRegistry()

        def echo(input: str) -> str:
            return f"echo:{input}"

        registry.register_function(echo)
        response = registry.execute_tool("echo", "hello")

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data["output"], "echo:hello")

    def test_string_input_falls_back_to_single_positional_arg(self):
        registry = ToolRegistry()

        def echo(text: str) -> str:
            return f"echo:{text}"

        registry.register_function(echo)
        response = registry.execute_tool("echo", "hello")

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data["output"], "echo:hello")

    def test_invalid_json_string_is_treated_as_input(self):
        registry = ToolRegistry()

        def echo(input: str) -> str:
            return f"echo:{input}"

        registry.register_function(echo)
        response = registry.execute_tool("echo", "{not-json")

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data["output"], "echo:{not-json")

    def test_non_object_json_is_wrapped_as_input(self):
        registry = ToolRegistry()

        def double(input: int) -> int:
            return input * 2

        registry.register_function(double)
        response = registry.execute_tool("double", "21")

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data["output"], 42)

    def test_function_exception_returns_execution_error(self):
        registry = ToolRegistry()

        def explode() -> str:
            raise RuntimeError("boom")

        registry.register_function(explode)
        response = registry.execute_tool("explode", {})

        self.assertEqual(response.status, ToolStatus.ERROR)
        self.assertEqual(
            response.error_info["code"],
            ToolErrorCode.EXECUTION_ERROR,
        )
        self.assertEqual(response.context["tool_name"], "explode")

    async def test_async_function_uses_same_string_argument_parsing(self):
        registry = ToolRegistry()

        async def echo(text: str) -> str:
            return f"async:{text}"

        registry.register_function(echo)
        response = await registry.aexecute_tool("echo", "hello")

        self.assertEqual(response.status, ToolStatus.SUCCESS)
        self.assertEqual(response.data["output"], "async:hello")

    def test_registry_blocks_open_circuit_before_tool_execution(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10)
        registry = ToolRegistry(circuit_breaker=breaker)
        registry.register_tool(AlwaysFailTool())

        with redirect_stdout(io.StringIO()):
            first = registry.execute_tool("always_fail", {})
        second = registry.execute_tool("always_fail", {})

        self.assertEqual(first.error_info["code"], ToolErrorCode.EXECUTION_ERROR)
        self.assertEqual(second.error_info["code"], ToolErrorCode.CIRCUIT_OPEN)

class ToolFilterTest(unittest.TestCase):
    def test_tool_filter(self):
        read_filter = ReadOnlyFilter(additional_allowed=["Custom"])
        self.assertTrue(read_filter.is_allowed("Read"))
        self.assertTrue(read_filter.is_allowed("Custom"))
        self.assertFalse(read_filter.is_allowed("Bash"))

        full_access_filter = FullAccessFilter(additional_denied=["Delete"])
        self.assertFalse(full_access_filter.is_allowed("Bash"))
        self.assertFalse(full_access_filter.is_allowed("Delete"))
        self.assertTrue(full_access_filter.is_allowed("Read"))

        custom_filter = CustomFilter(denied=["Delete"], mode="blacklist")
        self.assertEqual(
            custom_filter.filter(["Read", "Delete", "Write"]),
            ["Read", "Write"],
        )

        with self.assertRaises(ValueError):
            CustomFilter(mode="unknown")


if __name__ == "__main__":
    unittest.main()
