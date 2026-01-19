import json
from pathlib import Path
from typing import List, Dict

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from .chunker import build_chunks_from_markdown, Chunk


EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _cosine_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
    return vectors / norms


def build_faiss_index(project_root: Path) -> Dict:
    """
    Construit l'index FAISS à partir de rg_knowledge/*.md
    Sauvegarde dans rag_store/
    """
    knowledge_dir = project_root / "rg_knowledge"
    store_dir = project_root / "rag_store"
    store_dir.mkdir(exist_ok=True)

    md_files = sorted(knowledge_dir.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"Aucun fichier .md trouvé dans {knowledge_dir}")

    # 1) Lire + chunker
    chunks: List[Chunk] = []
    for fp in md_files:
        md_text = fp.read_text(encoding="utf-8", errors="ignore")
        chunks.extend(build_chunks_from_markdown(md_text, source_file=fp.name))

    texts = [c.text for c in chunks]
    metadatas = [c.metadata for c in chunks]

    # 2) Embeddings
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    vectors = model.encode(texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True)

    # Cosine similarity via IndexFlatIP: on normalise les vecteurs
    vectors = _cosine_normalize(vectors).astype("float32")

    # 3) FAISS index
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    # 4) Sauvegarde
    faiss_path = store_dir / "index.faiss"
    meta_path = store_dir / "metadata.json"

    faiss.write_index(index, str(faiss_path))
    meta_path.write_text(json.dumps(metadatas, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "nb_files": len(md_files),
        "nb_chunks": len(chunks),
        "faiss_path": str(faiss_path),
        "meta_path": str(meta_path),
        "embedding_model": EMBEDDING_MODEL_NAME
    }
