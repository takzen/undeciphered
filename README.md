# undeciphered-scripts

**Reproducible, skeptical computational studies of the world's undeciphered writing systems.**

Every few months a headline says that *AI has cracked* the Inca khipu, the Indus script or Linear A. None of these systems has been deciphered. Machine learning finds regularities very easily. Most of them turn out to come from how the data were collected, from searching too many hypotheses, or from pattern-matching against a dictionary that will match anything.

This repository takes such claims one at a time. For each one it does three things:

1. **Replicates** the result from public data with code anyone can run.
2. **Tests it against a null**: would the same pipeline "find" the same thing in shuffled data, in a fake language, or in metadata that knows nothing about the script?
3. **Reports what survives**, positive or negative, with credit to everyone whose work it builds on.

The long-term aim is constructive: a set of clean, documented baselines and null tests that a real decipherment would have to beat.

## Studies

| # | Script | Claim tested | Verdict |
|---|---|---|---|
| [01](studies/khipu/01-khipu-ml-transcription-confound/) | Khipu (Inca) | ML clusters and an "Inka imperial style" classifier (F1 = 0.86) found from structure | **Not supported.** Clusters are transcription regimes; "imperial" = one museum's incomplete records |
| [02](studies/khipu/02-alba-syllabary-null-test/) | Khipu (Inca) | ALBA / KhipuReader: calibrating a knot→syllable mapping finds Quechua words that generalise to other khipus | **Not diagnostic.** Fake Quechua, random syllables, Swahili and shuffled khipus score the same |
| [03](studies/khipu/03-color-bert-random-init-control/) | Khipu (Inca) | A BERT model learns colour "semantic domains", polysemy and three colour sets (Clindaniel) | **Largely not supported.** Clusters and "polysemy" appear with random weights; the sets are frequency tiers; a model trained on shuffled colours reproduces the similarity structure (ρ = 0.85). Released checkpoint does not reproduce released embeddings |

## Roadmap: the scripts

| Script | What is unknown | Public data | Priority |
|---|---|---|---|
| **Khipu** (Andes) | non-numeric content | [Open Khipu Repository](https://github.com/khipulab/open-khipu-repository): 619 khipus, 110k knots | **now** |
| **Linear A** (Minoan Crete) | language | ~1,400 inscriptions; sign values partly known from Linear B | next |
| **Proto-Elamite** (Iran) | non-numeric signs | ~1,600 tablets | next |
| **Indus script** (Harappa) | script and language | ~4–5k very short inscriptions | later |
| **Rongorongo** (Easter Island) | script and language | ~25 objects, ~15k glyphs | later |
| **Cypro-Minoan**, **Cretan hieroglyphic**, **Byblos**, **Isthmian** | script and language | small corpora | later |

## Principles

- **Pin the data.** Every study fetches its dataset at a fixed commit or version.
- **Null before claim.** No pattern is reported without a baseline that destroys the hypothesised signal.
- **Hold out properly.** Split by collection or site, not by random fold, when the labels correlate with where objects ended up.
- **Credit and civility.** Studies test claims, not people. Prior critiques are cited first.
- **Negative results are results.**

## Layout

```
scripts/            data fetchers (pinned versions)
data/               downloaded data (git-ignored)
studies/<script>/NN-<slug>/
    README.md       claim, method, results, verdict
    *.py            the full analysis, runnable end to end
    results/        committed outputs (json, csv, figures)
```

## Run

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
./scripts/fetch_okr.sh && ./scripts/fetch_lexicons.sh
uv run python studies/khipu/01-khipu-ml-transcription-confound/replicate.py
uv run python studies/khipu/02-alba-syllabary-null-test/null_test.py --space Ca_syllables --draws 200
```

Study 03 needs the optional BERT dependencies: `uv sync --group bert`, then see its README.

Contributor and AI-agent conventions are in [AGENTS.md](AGENTS.md).

## Contributing

Issues and pull requests are welcome, especially:

- corrections to anything here;
- new claims to test;
- better null models;
- people who work with the physical objects and can say where the data mislead.

## License

Code: MIT. Data belongs to its sources: the Open Khipu Repository is MIT-licensed by the OKR team.
