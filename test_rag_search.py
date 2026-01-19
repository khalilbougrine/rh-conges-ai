import json
from pathlib import Path

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def cosine_normalize(v):
    v = np.array(v, dtype="float32")
    n = np.linalg.norm(v) + 1e-12
    return v / n


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    store = root / "rag_store"

    index = faiss.read_index(str(store / "index.faiss"))
    metadatas = json.loads((store / "metadata.json").read_text(encoding="utf-8"))

    model = SentenceTransformer(MODEL_NAME)

    query = "Pourquoi un congé peut être refusé en période de pointe ?"
    q_vec = model.encode([query], convert_to_numpy=True)[0]
    q_vec = cosine_normalize(q_vec).reshape(1, -1)

    top_k = 5
    scores, ids = index.search(q_vec, top_k)

    print("\nQUESTION:", query)
    print("\nTOP RESULTS:")
    for rank, (idx, score) in enumerate(zip(ids[0], scores[0]), start=1):
        meta = metadatas[int(idx)]
        print(f"\n#{rank} score={float(score):.4f}")
        print("source:", meta["source_file"], "| section:", meta["section"])
