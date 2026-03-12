from pathlib import Path

def load_queries(path: Path) -> list[str]:
    """
    Loads all words and phrases from words.txt, and remove duplicates
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    queries = []
    seen = set()

    for line in lines:
        q = " ".join(line.strip().split())
        if not q:
            continue
        if q.lower() in seen:
            continue
        seen.add(q.lower())
        queries.append(q)

    return queries
