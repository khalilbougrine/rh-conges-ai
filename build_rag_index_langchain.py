from pathlib import Path
from conges.rag.build_index_langchain import build_and_save_langchain_index

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    info = build_and_save_langchain_index(root)
    print("✅ LangChain index OK:", info)
