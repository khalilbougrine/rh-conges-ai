import json
from pathlib import Path
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from .chunker import build_chunks_from_markdown

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def build_and_save_langchain_index(project_root: Path):
    knowledge_dir = project_root / "rg_knowledge"
    store_dir = project_root / "rag_store"
    store_dir.mkdir(exist_ok=True)

    md_files = sorted(knowledge_dir.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"Aucun fichier .md trouvé dans {knowledge_dir}")

    texts: List[str] = []
    metadatas: List[dict] = []

    for fp in md_files:
        md_text = fp.read_text(encoding="utf-8", errors="ignore")
        chunks = build_chunks_from_markdown(md_text, source_file=fp.name)
        for c in chunks:
            texts.append(c.text)
            metadatas.append(c.metadata)

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

    vs = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)
    vs.save_local(str(store_dir / "lc_faiss"))

    (store_dir / "lc_metadata.json").write_text(
        json.dumps(metadatas, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return {
        "nb_files": len(md_files),
        "nb_chunks": len(texts),
        "store_path": str(store_dir / "lc_faiss"),
        "embedding_model": EMBEDDING_MODEL_NAME
    }
