"""Calculator tool implemented with a restricted Python AST."""

import ast
import math
import operator
from typing import Any, Dict, List

from ..base import Tool, ToolParameter
from ..errors import ToolErrorCode
from ..registry import ToolRegistry
from ..response import ToolResponse


class CalculatorTool(Tool):
    """Evaluate basic arithmetic expressions safely."""

    BINARY_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    UNARY_OPERATORS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    
    FUNCTIONS = {
        'abs': abs,
        'round': round,
        'max': max,
        'min': min,
        'sum': sum,
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'exp': math.exp,
        'pi': math.pi,
        'e': math.e,
    }

    def __init__(
        self,
        max_expression_length: int = 200,
        max_exponent: int = 100,
        max_absolute_result: float = 1e100,
    ):
        super().__init__(
            name="calculator",
            description=(
                "Evaluate a basic arithmetic expression. Supports +, -, *, /, "
                "//, %, **, parentheses, and unary signs."
            ),
        )
        self.max_expression_length = max_expression_length
        self.max_exponent = max_exponent
        self.max_absolute_result = max_absolute_result

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="expression",
                type="string",
                description="Arithmetic expression, for example: (12 + 3) * 4",
                required=True,
            )
        ]

    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        expression = parameters.get("expression", "")
        if not isinstance(expression, str) or not expression.strip():
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_PARAM,
                message="expression must be a non-empty string",
            )

        expression = expression.strip()
        if len(expression) > self.max_expression_length:
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_PARAM,
                message=(
                    "expression is too long "
                    f"(maximum {self.max_expression_length} characters)"
                ),
            )

        try:
            tree = ast.parse(expression, mode="eval")
            result = self._evaluate(tree.body)
            self._validate_result(result)
        except (
            SyntaxError,
            TypeError,
            ValueError,
            ZeroDivisionError,
            OverflowError,
        ) as exc:
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_PARAM,
                message=f"Invalid arithmetic expression: {exc}",
                context={"expression": expression},
            )

        return ToolResponse.success(
            text=f"{expression} = {result}",
            data={
                "expression": expression,
                "result": result,
            },
        )

    def _evaluate(self, node: ast.AST) -> Any:
        """Recursively evaluate an allowed AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(
                node.value,
                (int, float),
            ):
                raise ValueError(
                    "only integer and floating-point constants are allowed"
                )
            return node.value

        if isinstance(node, ast.BinOp):
            operator_type = type(node.op)
            operation = self.BINARY_OPERATORS.get(operator_type)
            if operation is None:
                raise ValueError(
                    f"operator {operator_type.__name__} is not allowed"
                )

            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            if operator_type is ast.Pow and abs(right) > self.max_exponent:
                raise ValueError(
                    f"exponent must be between -{self.max_exponent} "
                    f"and {self.max_exponent}"
                )
            return operation(left, right)

        if isinstance(node, ast.UnaryOp):
            operation = self.UNARY_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError(
                    f"operator {type(node.op).__name__} is not allowed"
                )
            return operation(self._evaluate(node.operand))

        raise ValueError(
            f"expression element {type(node).__name__} is not allowed"
        )

    def _validate_result(self, result: Any) -> None:
        """Reject non-real, non-finite, or excessively large results."""
        if isinstance(result, complex) or not isinstance(result, (int, float)):
            raise ValueError("result must be a real number")
        if isinstance(result, float) and not math.isfinite(result):
            raise ValueError("result must be finite")
        if abs(result) > self.max_absolute_result:
            raise ValueError(
                f"absolute result exceeds {self.max_absolute_result:g}"
            )


def register_calculator_tool(registry: ToolRegistry) -> CalculatorTool:
    """Register the calculator in an existing registry."""
    tool = CalculatorTool()
    registry.register_tool(tool)
    return tool


def create_calculator_registry() -> ToolRegistry:
    """Create a registry containing the calculator."""
    registry = ToolRegistry()
    register_calculator_tool(registry)
    return registry
