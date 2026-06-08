# Sentiment Analysis for Code Review
This repository contains the replication package for the bachelor end project "Sentiment Analysis for Code Review."

## Repository structure

- `notebooks/`:`main.ipynb`, the end-to-end analysis: data collection, DEVA and LLM experiments, and results tables.
- `scripts/`: `ro_data_collection/`, the pipeline that mines GitHub and builds the Romanian gold standard dataset.
- `datasets/`: input datasets: Novielli et al.'s GitHub gold standards, the Coutinho replication set, and the Romanian gold standard (`ro-gold/`).
- `models/`: third-party tools used as baselines, currently the DEVA sentiment tool (`DEVA/DEVA_V1.jar`).
- `cache/`: `llm/`, cached LLM responses keyed by model/prompt/dataset so experiments rerun without re-querying the models.
- `input/`: preformatted inputs for external tools (e.g. `deva/` `.txt` files).
- `output/`: generated artifacts: DEVA outputs, combined prediction parquets, and the qualitative sample.
- `requirements.txt`: Python dependencies.

