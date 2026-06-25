"""Tool registration, discovery, schema generation, and execution."""

import asyncio
import inspect
import json
import time
from typing import Any, Callable, Dict, List, Optional, get_args, get_origin

from .base import Tool
from .circuit_breaker import CircuitBreaker
from .errors import ToolErrorCode
from .response import ToolResponse


class ToolRegistry:
    """Registry for Tool objects and plain Python functions."""

    def __init__(self, circuit_breaker: Optional[CircuitBreaker] = None):
        self._tools: Dict[str, Tool] = {}
        self._functions: Dict[str, Dict[str, Any]] = {}
        self.read_metadata_cache: Dict[str, Dict[str, Any]] = {}
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def register_tool(self, tool: Tool, auto_expand: bool = True) -> None:
        """Register a Tool, optionally expanding its decorated actions."""
        if auto_expand and tool.expandable:
            expanded_tools = tool.get_expanded_tools()
            if expanded_tools:
                for sub_tool in expanded_tools:
                    self._tools[sub_tool.name] = sub_tool
                return

        self._tools[tool.name] = tool

    def register_function(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a function and infer its OpenAI schema when needed.

        The legacy call form ``register_function(name, description, func)`` is
        still accepted for compatibility.
        """
        if isinstance(func, str) and callable(description):
            func, name, description = description, func, name

        if not callable(func):
            raise TypeError("func must be callable")

        tool_name = name or func.__name__
        tool_description = description or self._function_description(func, tool_name)
        parameter_schema = parameters or self._infer_function_parameters(func)

        self._functions[tool_name] = {
            "description": tool_description,
            "func": func,
            "schema": {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": parameter_schema,
                },
            },
        }

    def register_schema_function(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        func: Callable,
    ) -> None:
        """Register a function with an existing OpenAI parameter schema."""
        self.register_function(
            func=func,
            name=name,
            description=description,
            parameters=parameters,
        )

    def unregister(self, name: str) -> bool:
        """Remove a registered tool or function."""
        if name in self._tools:
            del self._tools[name]
            return True
        if name in self._functions:
            del self._functions[name]
            return True
        return False

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_function(self, name: str) -> Optional[Callable]:
        info = self._functions.get(name)
        return info["func"] if info else None

    def get_all_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_all_functions(self) -> Dict[str, Callable]:
        return {
            name: info["func"]
            for name, info in self._functions.items()
        }

    def get_tool_names(self) -> List[str]:
        return list(self._tools) + [
            name for name in self._functions if name not in self._tools
        ]

    def get_openai_schemas(self, tool_filter: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Return OpenAI function-calling schemas for allowed tools."""
        allowed_names = self.get_tool_names()
        if tool_filter is not None:
            allowed_names = tool_filter.filter(allowed_names)
        allowed = set(allowed_names)

        schemas = [
            tool.to_openai_schema()
            for name, tool in self._tools.items()
            if name in allowed
        ]
        schemas.extend(
            info["schema"]
            for name, info in self._functions.items()
            if name in allowed and name not in self._tools
        )
        return schemas

    def execute_tool(self, name: str, input_data: Any) -> ToolResponse:
        """Execute a registered tool synchronously."""
        blocked = self._circuit_open_response(name)
        if blocked is not None:
            return blocked

        if name in self._tools:
            response = self._execute_tool_object(
                self._tools[name],
                self._parse_parameters(input_data),
            )
        elif name in self._functions:
            response = self._execute_function(
                name,
                self._functions[name]["func"],
                input_data,
            )
        else:
            response = ToolResponse.error(
                code=ToolErrorCode.NOT_FOUND,
                message=f"Tool '{name}' was not found",
                context={"tool_name": name},
            )

        self.circuit_breaker.record_result(name, response)
        return response

    async def aexecute_tool(self, name: str, input_data: Any) -> ToolResponse:
        """Execute a registered tool without blocking the event loop."""
        blocked = self._circuit_open_response(name)
        if blocked is not None:
            return blocked

        if name in self._tools:
            tool = self._tools[name]
            parameters = self._parse_parameters(input_data)
            if not tool.validate_parameters(parameters):
                response = self._invalid_parameters_response(tool, parameters)
            else:
                response = await tool.arun_with_timing(parameters)
        elif name in self._functions:
            response = await self._aexecute_function(
                name,
                self._functions[name]["func"],
                input_data,
            )
        else:
            response = ToolResponse.error(
                code=ToolErrorCode.NOT_FOUND,
                message=f"Tool '{name}' was not found",
                context={"tool_name": name},
            )

        self.circuit_breaker.record_result(name, response)
        return response

    def _execute_tool_object(
        self,
        tool: Tool,
        parameters: Dict[str, Any],
    ) -> ToolResponse:
        if not tool.validate_parameters(parameters):
            return self._invalid_parameters_response(tool, parameters)
        return tool.run_with_timing(parameters)

    def _invalid_parameters_response(
        self,
        tool: Tool,
        parameters: Dict[str, Any],
    ) -> ToolResponse:
        required = [item.name for item in tool.get_parameters() if item.required]
        missing = [name for name in required if name not in parameters]
        return ToolResponse.error(
            code=ToolErrorCode.INVALID_PARAM,
            message=f"Missing required parameters: {', '.join(missing)}",
            context={
                "tool_name": tool.name,
                "params_input": parameters,
                "missing": missing,
            },
        )

    def _execute_function(
        self,
        name: str,
        func: Callable,
        input_data: Any,
    ) -> ToolResponse:
        start_time = time.time()
        try:
            result = self._call_function(func, input_data)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._wrap_function_result(name, input_data, result, elapsed_ms)
        except Exception as exc:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return ToolResponse.error(
                code=ToolErrorCode.EXECUTION_ERROR,
                message=f"Function execution failed: {exc}",
                stats={"time_ms": elapsed_ms},
                context={"tool_name": name, "input": input_data},
            )

    async def _aexecute_function(
        self,
        name: str,
        func: Callable,
        input_data: Any,
    ) -> ToolResponse:
        start_time = time.time()
        try:
            if inspect.iscoroutinefunction(func):
                result = await self._acall_function(func, input_data)
            else:
                result = await asyncio.to_thread(self._call_function, func, input_data)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._wrap_function_result(name, input_data, result, elapsed_ms)
        except Exception as exc:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return ToolResponse.error(
                code=ToolErrorCode.EXECUTION_ERROR,
                message=f"Function execution failed: {exc}",
                stats={"time_ms": elapsed_ms},
                context={"tool_name": name, "input": input_data},
            )

    def _call_function(self, func: Callable, input_data: Any) -> Any:
        args, kwargs = self._function_arguments(func, input_data)
        return func(*args, **kwargs)

    async def _acall_function(self, func: Callable, input_data: Any) -> Any:
        args, kwargs = self._function_arguments(func, input_data)
        return await func(*args, **kwargs)

    def _function_arguments(
        self,
        func: Callable,
        input_data: Any,
    ) -> tuple[List[Any], Dict[str, Any]]:
        signature = inspect.signature(func)
        parameters = list(signature.parameters.values())
        parsed = self._parse_parameters(input_data)

        if not parameters:
            return [], {}

        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        accepted_names = {
            parameter.name
            for parameter in parameters
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }

        if accepts_kwargs or set(parsed).issubset(accepted_names):
            return [], parsed

        if len(parameters) == 1 and set(parsed) == {"input"}:
            return [parsed["input"]], {}

        return [], parsed

    def _wrap_function_result(
        self,
        name: str,
        input_data: Any,
        result: Any,
        elapsed_ms: int,
    ) -> ToolResponse:
        if isinstance(result, ToolResponse):
            response = result
            if response.stats is None:
                response.stats = {}
            if response.context is None:
                response.context = {}
            response.stats["time_ms"] = elapsed_ms
            response.context.update({"tool_name": name, "input": input_data})
            return response

        return ToolResponse.success(
            text=str(result),
            data={"output": result},
            stats={"time_ms": elapsed_ms},
            context={"tool_name": name, "input": input_data},
        )

    def _circuit_open_response(self, name: str) -> Optional[ToolResponse]:
        if not self.circuit_breaker.is_open(name):
            return None
        status = self.circuit_breaker.get_status(name)
        return ToolResponse.error(
            code=ToolErrorCode.CIRCUIT_OPEN,
            message=(
                f"Tool '{name}' is temporarily disabled after repeated failures. "
                f"Retry in {status['recover_in_seconds']} seconds."
            ),
            context={"tool_name": name, "circuit_status": status},
        )

    @staticmethod
    def _parse_parameters(input_data: Any) -> Dict[str, Any]:
        if isinstance(input_data, dict):
            return input_data
        if isinstance(input_data, str):
            try:
                parsed = json.loads(input_data)
            except json.JSONDecodeError:
                return {"input": input_data}
            return parsed if isinstance(parsed, dict) else {"input": parsed}
        return {"input": input_data}

    @staticmethod
    def _function_description(func: Callable, name: str) -> str:
        doc = inspect.getdoc(func)
        return doc.splitlines()[0].strip() if doc else f"Execute {name}"

    def _infer_function_parameters(self, func: Callable) -> Dict[str, Any]:
        signature = inspect.signature(func)
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for name, parameter in signature.parameters.items():
            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            annotation = (
                parameter.annotation
                if parameter.annotation is not inspect.Parameter.empty
                else str
            )
            properties[name] = {"type": self._json_type(annotation)}
            if parameter.default is inspect.Parameter.empty:
                required.append(name)
            else:
                properties[name]["description"] = f"Default: {parameter.default}"

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    @staticmethod
    def _json_type(annotation: Any) -> str:
        origin = get_origin(annotation)
        if origin in (list, List):
            return "array"
        if origin in (dict, Dict):
            return "object"
        if origin is not None and type(None) in get_args(annotation):
            non_none = [item for item in get_args(annotation) if item is not type(None)]
            return ToolRegistry._json_type(non_none[0]) if non_none else "string"
        return {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }.get(annotation, "string")
