from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import os


def build_llm() -> ChatOpenAI:
    """初始化大模型"""
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        temperature=0.7,
    )


def main() -> None:
    load_dotenv()

    llm = build_llm()

    # 对话历史
    messages = [
        SystemMessage(content="你是一个友好、专业的中文助手。")
    ]

    print("=== LangChain 多轮对话 Demo ===")
    print("输入 exit 或 quit 退出\n")

    while True:
        user_input = input("你：").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("已退出。")
            break

        if not user_input:
            continue

        messages.append(HumanMessage(content=user_input))

        try:
            response = llm.invoke(messages)
            assistant_text = response.content

            messages.append(AIMessage(content=assistant_text))
            print(f"助手：{assistant_text}\n")

        except Exception as e:
            print(f"调用模型失败：{e}\n")


if __name__ == "__main__":
    main()