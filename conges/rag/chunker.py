import re
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Chunk:
    text: str
    metadata: Dict


def split_markdown_by_headers(md_text: str) -> List[Dict]:
    """
    Découpe un markdown en sections basées sur # / ## / ###.
    Retourne une liste de blocs {"title": "...", "content": "..."}.
    """
    lines = md_text.splitlines()
    blocks = []
    current_title = "INTRO"
    current_content = []

    header_re = re.compile(r"^(#{1,3})\s+(.*)$")

    for line in lines:
        m = header_re.match(line.strip())
        if m:
            # push previous block
            if current_content:
                blocks.append({"title": current_title, "content": "\n".join(current_content).strip()})
            current_title = m.group(2).strip()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        blocks.append({"title": current_title, "content": "\n".join(current_content).strip()})

    # filter empty
    return [b for b in blocks if b["content"].strip()]


def chunk_text_with_overlap(text: str, chunk_size: int = 2500, overlap: int = 300) -> List[str]:
    """
    Chunking simple par taille de caractères avec overlap.
    chunk_size ~ 1500-3000 recommandé, overlap 10-20%.
    """
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap)

    return chunks


def build_chunks_from_markdown(md_text: str, source_file: str) -> List[Chunk]:
    """
    Markdown-aware chunking:
    - split by headers
    - then chunk long sections with overlap
    """
    sections = split_markdown_by_headers(md_text)
    all_chunks: List[Chunk] = []

    for sec in sections:
        title = sec["title"]
        content = sec["content"]

        sub_chunks = chunk_text_with_overlap(content, chunk_size=2500, overlap=300)
        for i, c in enumerate(sub_chunks):
            all_chunks.append(
                Chunk(
                    text=c,
                    metadata={
                        "source_file": source_file,
                        "section": title,
                        "chunk_in_section": i
                    }
                )
            )

    return all_chunks
