# Sentiment Analysis for Code Review
This repository contains the replication package for the bachelor end project "Can Open-Source LLMs Match SE-Specific Sentiment Tools? An English
and Romanian Evaluation."

Note that this repository is available on both https://gitlab.tue.nl  and https://github.com.

## Repository structure

- `notebooks/`:`main.ipynb`, the end-to-end analysis: data collection, DEVA and LLM experiments, and results tables.
- `scripts/`: `ro_data_collection/`, the pipeline that mines GitHub and builds the Romanian gold standard dataset.
- `datasets/`: input datasets: Novielli et al.'s GitHub gold standards, the Coutinho replication set, and the Romanian gold standard (`ro-gold/`).
- `cache/`: `llm/`, cached LLM responses keyed by model/prompt/dataset so experiments rerun without re-querying the models.
- `input/`: preformatted inputs for external tools (e.g. `deva/` `.txt` files).
- `output/`: generated artifacts: DEVA outputs, combined prediction parquets, and the qualitative sample.
- `requirements.txt`: Python dependencies.

## Reproducing results
The analysis runs on Python 3.11+. Install the dependencies and run the notebook top to bottom:

```bash
pip install -r requirements.txt
jupyter notebook notebooks/main.ipynb
```

All LLM responses are cached under `cache/llm/`, so the notebook reproduces every table and figure without a GPU or a running Ollama server. 
The classification step reads cached entries directly and only queries a model for inputs not already in the cache. DEVA's outputs are committed under `output/deva/`.

## Regenerating from scratch

- **LLM predictions**: install [Ollama](https://ollama.com), pull the three models (`gemma3:12b`, `phi4:14b`, `llama3.1:8b`), delete the relevant files in `cache/llm/`, and rerun the classification cells.
- **DEVA baseline**: the DEVA tool is not included here (its `DEVA_V1.jar` is ~240 MB). You may download it [here](https://figshare.com/s/277026f0686f7685b79e), then run it on the `input/deva/*.txt` files to regenerate `output/deva/`.
- **Romanian dataset collection**: the pipeline in `scripts/ro_data_collection/` needs a GitHub API token. Create `scripts/ro_data_collection/.env` with a `GH_TOKEN=<token>` entry, then run `pipeline.py`. The final dataset is already provided in `datasets/ro-gold/`, so this step is only needed to rebuild it. The pipeline is not Romanian-specific: it mines and filters comments for any language supported by [lingua](https://github.com/pemistahl/lingua-py). To target a different language, replace the keyword lists in `__dictionaries__/` (`keywords_repo.txt`, `keywords_code.txt`) with terms for that language and change the `Language.ROMANIAN` target in `_lang_filter.py` to the desired language.