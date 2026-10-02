"""
Study 03, step 3 - are the "foundational / extension / refinement" colour sets just frequency tiers?

The paper groups colours by the cosine-similarity matrix of their average embeddings:
  foundational {A1, B2, B3, Z5}, extension {B4, G3, G4, H3, M2}, refinement = 15 rare colours
(analysis.ipynb, cell 37), and notes the sets "roughly correspond to usage percentages".
Here we ask how much of that matrix, and of the sets, frequency alone explains.

Run:  uv run --group bert python studies/khipu/03-color-bert-random-init-control/frequency_test.py
      (after analyze.py, which writes the between-colour matrices)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.metrics import adjusted_rand_score

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
summary = json.loads((OUT / "summary.json").read_text())
counts = pd.Series(summary["colour_counts"])

PAPER_SETS = {"foundational": {"A1", "B2", "B3", "Z5"},
              "extension": {"B4", "G3", "G4", "H3", "M2"},
              "refinement": {"Y2", "Y3", "R2", "R3", "R4", "G2", "H2", "H4", "L2", "L3", "L4", "N3", "N4", "M3", "M4"}}
paper = pd.Series({c: s for s, cs in PAPER_SETS.items() for c in cs})

# frequency tiers with the same sizes as the paper's sets (4 / 5 / 15)
order = counts.sort_values(ascending=False).index
freq_tier = pd.Series(["foundational"] * 4 + ["extension"] * 5 + ["refinement"] * 15, index=order)

res = {"paper_sets_vs_frequency_tiers": {
    "agreement": round(float((paper[order] == freq_tier[order]).mean()), 3),
    "adjusted_rand": round(float(adjusted_rand_score(paper[order], freq_tier[order])), 3),
    "disagreements": {c: {"paper": paper[c], "frequency_tier": freq_tier[c], "count": int(counts[c])}
                      for c in order if paper[c] != freq_tier[c]},
}}

logf = np.log(counts[order].values.astype(float))
iu = np.triu_indices(len(order), 1)
for model in ["trained", "random"]:
    M = pd.read_csv(OUT / f"between_colour_cosine_{model}.csv", index_col=0).loc[order, order].values
    y = M[iu]
    # pairwise frequency design: overall rarity of the pair and how different the two colours' frequencies are
    X = np.column_stack([np.ones_like(y), logf[iu[0]] + logf[iu[1]], np.abs(logf[iu[0]] - logf[iu[1]])])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r2 = 1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    # 3 groups recovered from the matrix itself (average linkage on 1 - cosine)
    D = 1 - M
    np.fill_diagonal(D, 0)
    groups = pd.Series(fcluster(linkage(squareform(D, checks=False), "average"), 3, "maxclust"), index=order)
    rare = [c for c in order if c in PAPER_SETS["refinement"]]
    ri = [list(order).index(c) for c in rare]
    common = [list(order).index(c) for c in order if c not in PAPER_SETS["refinement"]]
    res[model] = {
        "r2_cosine_from_frequency_only": round(float(r2), 3),
        "matrix_groups_vs_paper_sets_adjusted_rand": round(float(adjusted_rand_score(paper[order], groups)), 3),
        "matrix_groups_vs_frequency_tiers_adjusted_rand": round(float(adjusted_rand_score(freq_tier[order], groups)), 3),
        "mean_cosine_within_refinement_set": round(float(M[np.ix_(ri, ri)][np.triu_indices(len(ri), 1)].mean()), 3),
        "mean_cosine_within_non_refinement": round(float(M[np.ix_(common, common)][np.triu_indices(len(common), 1)].mean()), 3),
    }
(OUT / "frequency_summary.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=1))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

M = pd.read_csv(OUT / "between_colour_cosine_trained.csv", index_col=0).loc[order, order]
fig, ax = plt.subplots(1, 2, figsize=(14, 6.6), layout="constrained")
im = ax[0].imshow(M.values, cmap="viridis", vmin=0, vmax=1)
ax[0].set_xticks(range(len(order)), [f"{c}" for c in order], rotation=90, fontsize=8)
ax[0].set_yticks(range(len(order)), [f"{c} ({counts[c]})" for c in order], fontsize=8)
ax[0].set_title("Trained model: cosine of average colour embeddings\n(colours ordered by frequency)")
fig.colorbar(im, ax=ax[0], shrink=.8)
pair_rarity = -(logf[iu[0]] + logf[iu[1]])
same = np.array([paper[order[i]] == paper[order[j]] for i, j in zip(*iu, strict=True)])
for flag, lab, col in [(True, "same paper set", "#d62728"), (False, "different sets", "#9e9e9e")]:
    ax[1].scatter(pair_rarity[same == flag], M.values[iu][same == flag], s=14, alpha=.7, color=col, label=lab)
ax[1].set_xlabel("pair rarity  = −(log count₁ + log count₂)")
ax[1].set_ylabel("cosine similarity (trained model)")
ax[1].set_title(f"Frequency alone explains R² = {res['trained']['r2_cosine_from_frequency_only']:.2f} of the matrix")
ax[1].legend()
fig.savefig(OUT / "frequency_vs_similarity.png", dpi=150)
