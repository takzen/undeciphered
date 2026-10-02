# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.

## What this repo is

Reproducible, skeptical computational studies of undeciphered writing systems: khipu, Linear A, Proto-Elamite, the Indus script, Rongorongo and others.

Each study takes **one published claim**, replicates it from public data, tests it against null models, and reports what survives. The audience is researchers and the public, so correctness and fairness matter more than speed.

## Setup and commands

The environment is managed with **uv**. Never use `pip install` or a bare `python`.

```bash
uv sync                                   # create .venv from uv.lock
uv sync --group bert                      # + torch/transformers, only for the BERT studies
./scripts/fetch_okr.sh                    # Open Khipu Repository DB, pinned commit -> data/okr/
./scripts/fetch_lexicons.sh               # Quechua + Swahili word lists, pinned -> data/lexicons/
./scripts/fetch_clindaniel.sh             # colour-BERT code/checkpoint + OKR v2.0.0 (study 03)
uv run python studies/<script>/<NN-slug>/<entry>.py
uv run ruff check .                       # lint
```

To add a dependency, use `uv add <pkg>` (or `uv add --dev <pkg>`) and commit `pyproject.toml` together with `uv.lock`.

## Layout

```
scripts/                      data fetchers; every source pinned to a commit or version
data/                         downloaded data, git-ignored; never commit raw datasets
studies/<script>/NN-<slug>/
    README.md                 the write-up (template below)
    <entry>.py                the full analysis, runnable end to end, no notebooks required
    results/                  committed outputs: summary.json, CSVs, PNG figures
```

- Study numbers are global and sequential (`01`, `02`, …), even across scripts.
- After adding a study, update the **Studies** table in the root `README.md`.

## Study README template

Use these sections, in this order:

1. **Title + status line**: `**Status:** … · **Verdict:** …`
2. **The claim under test**: who, where (link), and exactly what is claimed, quoted where possible.
3. **Prior work: credit**: anyone who raised the same point first.
4. **Method**: enough detail to re-implement; state every assumption made where the original is unclear.
5. **Results**: tables and figures. **Every number must come from `results/`** produced by the committed code.
6. **Conclusion**: what is refuted, what is untested, what still stands, and what a stronger test would need.
7. **Reproduce**: the exact `uv run` commands.

## Rules for analyses

- **Pin everything.** Pin data sources to a commit or version, fix random seeds, and record the data version in `summary.json`.
- **Null before claim.** Never report a pattern without a null model that destroys the hypothesised signal while keeping the data's other statistics: shuffled objects, scrambled lexicons, wrong-language lexicons, metadata-only predictors.
- **Run the whole pipeline under the null.** Re-run the full search or calibration on null data, not just the final scoring step. Selection effects live in the search.
- **Hold out properly.** Split by collection, site or object, not by random row, whenever labels correlate with provenance.
- **Report robustness.** Repeat across seeds and reasonable parameter choices, and report the spread.
- **Negative and null results get the same write-up quality as positive ones.**
- **Never invent numbers, citations or quotes.** If a source is not accessible, say so in the README and describe what was reconstructed and from which public description.

## Tone

- Test claims, not people. Be neutral and precise, with no mockery.
- Credit prior critiques first, and link original papers and code.
- Say clearly what was **not** tested.

## Code style

- Python 3.11, plain scripts with `pandas`, `numpy` and `scikit-learn`. Vectorise heavy searches with numpy.
- Keep each study self-contained. Shared helpers go in a top-level package only once two studies need them.
- Comments explain *why*, not *what*. Docstrings at the top of each entry script state the claim, the test and how to run it.
- Run `uv run ruff check .` before committing.

## Git

- One study per branch or PR when possible. Keep commit messages descriptive, e.g. `Study 02: ALBA syllabary null test`.
- Commit regenerated `results/` together with the code that produced them.
- Never commit anything under `data/`, or `.venv/`.
- All repository text is in **English**.
