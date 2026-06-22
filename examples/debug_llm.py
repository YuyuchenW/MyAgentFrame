from dotenv import load_dotenv

from my_hello_agents.core.llm import HelloAgentsLLM

load_dotenv()

llm = HelloAgentsLLM()

messages = [
    {"role": "user", "content": "介绍一下你自己"}
]


def main():
    chunks = []

    for chunk in llm.think(messages):
        chunks.append(chunk)

    content = "".join(chunks)
    print()
    print("content:", content)
    print("stats:", llm.last_call_stats)


if __name__ == "__main__":
    main()
