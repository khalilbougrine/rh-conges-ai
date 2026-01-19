from pathlib import Path
from conges.rag.rag_chain import answer_rh_question

if __name__ == "__main__":
    root = Path(__file__).resolve().parent

    question = "Pourquoi un congé peut être refusé en période de pointe ?"

    result = answer_rh_question(
        project_root=root,
        question=question,
        leave_type="AnnualLeave",
        tags=["TAG_IS_PEAK_PERIOD"],
        template_id="REFUS_PEAK_PERIOD",
        top_k=6
    )

    print("\n=== ANSWER ===\n")
    print(result["answer"])

    print("\n=== USED SOURCES ===")
    for s in result["sources"]:
        print("-", s)
