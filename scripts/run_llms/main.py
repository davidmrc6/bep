"""
Standalone script to run LLMs
Follows the same steps as the main notebook. Used to make it easier
to run in the background on a server.
"""
import json
import re
import ollama
from pathlib import Path
from tqdm import tqdm

tqdm.pandas()

# cache config
ROOT_DIR = Path.cwd()
CACHE_DIR = ROOT_DIR / "cache" / "llm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# llm config
MODELS = ["gemma3:12b", "phi4:14b", "llama3.1:8b"]

MAX_CONSECUTIVE_ERRORS = 3

SYSTEM_PROMPT = (
    "A chat between a curious user and an artificial intelligence assistant. "
    "The assistant gives helpful, detailed, and polite answers to the user's questions."
)

PROMPT_0 ="""
Please perform Sentiment Classification task. Given the sentence from GitHub pull request code review comments, assign a sentiment label from ['negative', 'neutral', 'positive']. Return label only without any other text.
"""

PROMPT_1 ="""
Please categorize the sentiment expressed in the following sentence from GitHub pull request code review comments as either (1) positive, (2) neutral, or (3) negative.
"""

PROMPT_2 ="""
I will give you a sentence from GitHub pull request code review comments. You need to reply with the sentiment expressed in the following sentence, either (1) positive, (2) neutral, or (3) negative.
"""

PROMPTS = {0: PROMPT_0, 1: PROMPT_1, 2: PROMPT_2}

LABEL_PATTERN = re.compile(r'(?:Label|Sentiment):\s*(\w+)')

# datasets
# TODO


# cache helpers
def cache_path(model: str, prompt_id: int, dataset: str) -> Path:
    safe_name = model.replace(":", "_").replace("/", "_")
    return CACHE_DIR / f"{safe_name}_prompt_{prompt_id}_{dataset}.json"

def load_cache(model: str, prompt_id: int, dataset: str) -> dict:
    path = cache_path(model, prompt_id, dataset)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return {e["text"]: (e.get("raw_message", ""), e["label"]) for e in entries}
    return {}

def save_cache(model: str, prompt_id: int, dataset: str, results: dict):
    entries = [
        {"text": text, "raw_message": raw, "label": label}
        for text, (raw, label) in results.items()
    ]
    with open(cache_path(model, prompt_id, dataset), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)


# label extraction
def extract_label(response: str) -> str:
    """Extract sentiment label from LLM response through the
    same processing step used in work by Zhang et al.

    For each line, first tries the regex pattern, then falls back to
    token-level substring matching. Defaults to 'neutral' if no
    sentiment keyword is found.

    This approach might not be optimal, but it is consistent
    with prior work.
    """
    for line in response.strip().lower().splitlines():
        line = line.strip()

        # regex match
        match = LABEL_PATTERN.search(line)
        if match:
            result = match.group(1).strip()
            if result in ('positive', 'negative', 'neutral'):
                return result

        # fallback: token-level substring check
        for token in line.split():
            if 'positive' in token:
                return 'positive'
            elif 'negative' in token:
                return 'negative'
            elif 'neutral' in token:
                return 'neutral'

    return 'neutral'


# run llms
def classify(text: str, model: str, task_prompt: str) -> tuple[str, str]:
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": task_prompt.strip()},
            {"role": "assistant", "content": "Sure!"},
            {"role": "user",      "content": f"Sentence: {text}\nLabel:"},
        ],
        options={"temperature": 0, "think": False},
    )
    raw = resp.message.content
    return raw, extract_label(raw)

def classify_with_cache(texts, model: str, prompt_id: int, dataset: str, task_prompt: str) -> list[str]:
    cached = load_cache(model, prompt_id, dataset)
    results = dict(cached)  # copy
    labels = []
    consecutive_errors = 0

    for text in tqdm(texts, desc=f"{model} (prompt {prompt_id})"):
        if text in results:
            labels.append(results[text][1])
            consecutive_errors = 0
            continue

        try:
            raw, label = classify(text, model, task_prompt)
            results[text] = (raw, label)
            labels.append(label)
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            print(f"\n  Error on {model}: {e}")
            results[text] = ('', 'error')
            labels.append("error")

            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"  {MAX_CONSECUTIVE_ERRORS} consecutive errors: skipping {model}")
                labels.extend(["error"] * (len(texts) - len(labels)))
                break

        # save periodically (every 25 items)
        if len(labels) % 25 == 0:
            save_cache(model, prompt_id, dataset, results)

    save_cache(model, prompt_id, dataset, results)
    return labels

def run_classification(df, model: str, prompt_id: int, dataset: str, task_prompt: str):
    col = f"{model.replace(':', '_').replace('/', '_')}_prompt_{prompt_id}"
    df[col] = classify_with_cache(df["text"].tolist(), model, prompt_id, dataset, task_prompt)


# TODO

if __name__ == "__main__":
    ...