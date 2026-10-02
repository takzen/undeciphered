"""
Study 03c - compare embedding models on the paper's quantities.

For every embedding tag (written by embed.py) compute:
  - cord-level clustering as in the notebook (UMAP 100-d cosine + HDBSCAN min 250): clusters, share clustered,
    purity, colours owning a cluster
  - median within-colour cosine and whether it passes the paper's 0.5 monosemy threshold
  - the between-colour cosine matrix, how much of it frequency explains (R^2), and how similar the
    matrices of different models are (Spearman)
  - how well the paper's foundational / extension / refinement sets are recovered as the 3 groups of the matrix

Run:  uv run --group bert python studies/khipu/03-color-bert-random-init-control/compare.py \\
          trained random_seed0 retrained_original_seed0 retrained_shuffled_seed0
"""
import itertools
import json
import sys
from pathlib import Path

import hdbscan
import numpy as np
import pandas as pd
import umap
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DER = ROOT / "data" / "derived" / "study03"
OUT = HERE / "results"
SEED = 7
REFINEMENT = {"Y2", "Y3", "R2", "R3", "R4", "G2", "H2", "H4", "L2", "L3", "L4", "N3", "N4", "M3", "M4"}


def unit(x):
    x = np.asarray(x, dtype=np.float64)
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def upper(S):
    return S[np.triu_indices(len(S), 1)]


tags = sys.argv[1:]
rng = np.random.default_rng(0)
res, mats = {}, {}
for tag in tags:
    tok = pd.read_parquet(DER / f"tokens_{tag}.parquet")
    emb = np.load(DER / f"emb_{tag}.npy")
    counts = tok.color.value_counts()
    order = counts.index
    S = unit(emb)
    within = {}
    for c in order:
        idx = np.where(tok.color.values == c)[0]
        if len(idx) > 1500:
            idx = rng.choice(idx, 1500, replace=False)
        within[c] = float(np.median(upper(S[idx] @ S[idx].T)))
    means = unit(np.vstack([emb[tok.color.values == c].mean(0) for c in order]))
    M = means @ means.T
    mats[tag] = pd.DataFrame(M, index=order, columns=order)
    logf = np.log(counts.values.astype(float))
    iu = np.triu_indices(len(order), 1)
    y = M[iu]
    X = np.column_stack([np.ones_like(y), logf[iu[0]] + logf[iu[1]], np.abs(logf[iu[0]] - logf[iu[1]])])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r2 = 1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    ri = [i for i, c in enumerate(order) if c in REFINEMENT]
    ci = [i for i, c in enumerate(order) if c not in REFINEMENT]

    np.random.seed(SEED)
    red = umap.UMAP(n_neighbors=15, n_components=100, min_dist=0.0, metric="cosine", random_state=SEED) \
        .fit_transform(emb + np.random.normal(0, 0.01, emb.shape))
    lab = hdbscan.HDBSCAN(min_cluster_size=250).fit_predict(red)
    d = pd.DataFrame({"color": tok.color.values, "label": lab})
    inc = d[d.label != -1]
    majority = inc.groupby("label").color.agg(lambda s: s.value_counts().index[0])

    res[tag] = {
        "clusters": int(lab.max() + 1),
        "share_tokens_clustered": round(float((lab != -1).mean()), 3),
        "cluster_purity": round(float((inc.color == inc.label.map(majority)).mean()), 3),
        "colours_owning_a_cluster": int(majority.nunique()),
        "within_colour_median_range": [round(min(within.values()), 3), round(max(within.values()), 3)],
        "colours_passing_0.5_monosemy_threshold": int(sum(v >= 0.5 for v in within.values())),
        "between_colour_cosine_range": [round(float(y.min()), 3), round(float(y.max()), 3)],
        "r2_between_colour_from_frequency": round(float(r2), 3),
        "mean_cosine_within_refinement_set": round(float(upper(M[np.ix_(ri, ri)]).mean()), 3),
        "mean_cosine_among_other_colours": round(float(upper(M[np.ix_(ci, ci)]).mean()), 3),
    }
    print(tag, res[tag], flush=True)

pairs = {}
for a, b in itertools.combinations(tags, 2):
    order = mats[a].index
    pairs[f"{a} vs {b}"] = round(float(spearmanr(upper(mats[a].loc[order, order].values),
                                                  upper(mats[b].loc[order, order].values))[0]), 3)
out = {"models": res, "between_colour_matrix_spearman": pairs}
(OUT / "model_comparison.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=1))
