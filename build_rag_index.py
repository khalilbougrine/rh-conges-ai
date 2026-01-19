from pathlib import Path
from conges.rag.build_index import build_faiss_index

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    info = build_faiss_index(root)
    print("✅ Index construit :", info)
