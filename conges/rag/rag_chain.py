from pathlib import Path
from typing import List, Dict, Optional

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document


MODEL_EMBED = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OLLAMA_MODEL = "llama3.2:1b"

# Routing STRICT : 1 template_id => sources autorisées
TEMPLATE_STRICT_SOURCES = {
    # Refus pour période de pointe
    "REFUS_PEAK_PERIOD": ["periodes_pointe.md", "explications_decisions.md"],

    # Refus pour solde insuffisant
    "REFUS_SOLDE": ["politique_conges.md", "explications_decisions.md"],

    # Refus manager
    "REFUS_MANAGER": ["politique_conges.md", "explications_decisions.md"],

    # Tu pourras compléter au fur et à mesure
}



def load_vectorstore(project_root: Path) -> FAISS:
    embeddings = HuggingFaceEmbeddings(model_name=MODEL_EMBED)
    vs = FAISS.load_local(
        str(project_root / "rag_store" / "lc_faiss"),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    return vs


def format_context(docs: List[Document], max_chars: int = 6000) -> str:
    """
    Formate le contexte injecté au LLM.
    On limite la taille pour ne pas surcharger le modèle.
    """
    parts = []
    total = 0
    for i, d in enumerate(docs, start=1):
        src = d.metadata.get("source_file", "unknown")
        sec = d.metadata.get("section", "unknown")
        snippet = d.page_content.strip()
        block = f"[EXTRAIT {i}] Source={src} | Section={sec}\n{snippet}\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts).strip()


def build_allowed_sources(leave_type, tags, template_id):
    """
    Filtrage PRO :
    - si template_id est connu => filtrage STRICT (aucun mélange)
    - sinon => filtrage "soft" basé sur leave_type/tags (comme avant)
    """
    # 1) STRICT si template_id est reconnu
    if template_id and template_id in TEMPLATE_STRICT_SOURCES:
        return TEMPLATE_STRICT_SOURCES[template_id]

    # 2) Sinon soft (question générale ou template pas encore mappé)
    if not (leave_type or tags or template_id):
        return None

    tags = tags or []
    allowed = set()

    # Sources génériques
    allowed.add("explications_decisions.md")
    allowed.add("politique_conges.md")
    allowed.add("faq_rh.md")

    if leave_type == "SickLeave":
        allowed.add("conges_maladie.md")

    if leave_type == "ExceptionalLeave":
        allowed.add("conges_exceptionnels.md")

    if any("PEAK" in t or "POINTE" in t for t in tags):
        allowed.add("periodes_pointe.md")

    if any("CDD" in t or "CDI" in t for t in tags):
        allowed.add("regles_cdd_cdi.md")

    return sorted(list(allowed))



def retrieve_docs(vs: FAISS, question: str, top_k: int = 5, allowed_sources: Optional[List[str]] = None, prefer_keywords: Optional[List[str]] = None) -> List[Document]:
    docs = vs.similarity_search(question, k=top_k)

    if allowed_sources:
        docs = [d for d in docs if d.metadata.get("source_file") in allowed_sources] or docs

    # rerank simple par mots-clés (optionnel mais efficace)
    if prefer_keywords:
        def score_kw(d: Document) -> int:
            txt = (d.page_content or "").lower()
            return sum(1 for kw in prefer_keywords if kw.lower() in txt)

        docs = sorted(docs, key=score_kw, reverse=True)

    return docs



def answer_rh_question(
    project_root: Path,
    question: str,
    leave_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    template_id: Optional[str] = None,
    top_k: int = 5,
) -> Dict:
    """
    RAG complet : retrieval + Llama-3 + réponse + sources
    """
    vs = load_vectorstore(project_root)
    allowed_sources = build_allowed_sources(leave_type, tags, template_id)

    docs = retrieve_docs(vs, question, top_k=top_k, allowed_sources=allowed_sources)
    context = format_context(docs)

    prefer_keywords = None
    if tags and any("PEAK" in t or "POINTE" in t for t in tags):
        prefer_keywords = ["pointe", "forte activité", "période"]

    docs = retrieve_docs(vs, question, top_k=top_k, allowed_sources=allowed_sources, prefer_keywords=prefer_keywords)

    # Prompt RH sécurisé
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Tu es un assistant RH interne. "
         "Une décision a DÉJÀ été prise par le système (accepté/refusé). "
         "Ton rôle est d'EXPLIQUER cette décision, PAS de proposer d'autres motifs. "
         "Tu dois répondre UNIQUEMENT à partir des extraits fournis. "
         "Si les extraits ne contiennent pas l'explication, dis : "
         "'Information non trouvée dans les documents internes'. "
         "N'invente jamais de règle. "
         "Réponds en français, clair et professionnel. "
         "Termine toujours par une section 'Sources' listant les fichiers et sections utilisés."),
        ("user",
         "Contexte décision (à respecter) :\n"
         "- template_id = {template_id}\n"
         "- leave_type = {leave_type}\n"
         "- tags = {tags}\n\n"
         "Question employé:\n{question}\n\n"
         "Extraits de la base RH (seules sources autorisées):\n{context}\n\n"
         "Consignes:\n"
         "- Réponds en 6-10 lignes max.\n"
         "- N'ajoute pas d'autres raisons que celles cohérentes avec template_id/tags.\n"
         "- Si rien ne répond, dis 'Information non trouvée dans les documents internes'.\n"
         ),
    ])

    llm = ChatOllama(model=OLLAMA_MODEL, temperature=0)

    chain = prompt | llm

    resp = chain.invoke({
        "question": question,
        "context": context,
        "template_id": template_id,
        "leave_type": leave_type,
        "tags": tags
    })

    answer_text = resp.content if hasattr(resp, "content") else str(resp)

    sources = []
    for d in docs:
        sources.append({
            "source_file": d.metadata.get("source_file"),
            "section": d.metadata.get("section")
        })

    return {
        "answer": answer_text,
        "sources": sources,
        "allowed_sources": allowed_sources
    }
