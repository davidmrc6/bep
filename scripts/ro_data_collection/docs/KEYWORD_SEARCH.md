# Keyword Search

This script is the first collection step in the pipeline. Its job is simple: take a list of Romanian keywords, ask GitHub which repositories and code files match them, and turn that into a clean list of candidate repositories for later stages.

## What it needs

The script expects a GitHub token in your environment:

```bash
GH_TOKEN=your_token_here
```

Because `helpers.session` calls `load_dotenv()`, keeping that token in a local `.env` file also works.

## Basic usage

Run the full keyword list:

```bash
python repo_search.py
```

Run the small test list:

```bash
python repo_search.py --test
```

Use a custom keyword file or output folder:

```bash
python repo_search.py --words path/to/keywords.txt --output-dir path/to/output
```

If you want to slow the run down a bit more between queries:

```bash
python repo_search.py --delay 4
```

## Keyword file format

The keyword files live in `__dictionaries__/`.

- `keywords.txt` is the main list.
- `keywords_test.txt` is a smaller list for quick checks.

## How the search works

For each keyword or phrase, the script performs two separate GitHub searches:

1. `search/repositories`
   This finds repositories whose metadata matches the query. These results include things like description, language, stars, timestamps, topics, and owner info.
2. `search/code`
   This finds individual files matching the query, then maps those file hits back to their parent repositories.

That split is intentional. Repository search is good at finding projects that describe themselves clearly. Code search catches projects where the Romanian signal is inside the codebase rather than in the repo metadata.

After both searches finish, the script merges the results into one repository-level output file:

- `candidate_repositories.json`
