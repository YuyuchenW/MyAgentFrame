from my_hello_agents.tools import CalculatorTool


def main() -> None:
    tool = CalculatorTool()

    print("Tool:", tool)
    print("Parameters:", tool.get_parameters())
    print("OpenAI schema:", tool.to_openai_schema())
    print("Current response:", tool.run({"expression": "1 + 2"}).to_dict())


if __name__ == "__main__":
    main()
