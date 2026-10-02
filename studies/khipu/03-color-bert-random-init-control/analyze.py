"""
Study 03, step 2 - does the colour-embedding analysis need a *trained* model?

Runs Clindaniel's cord-level pipeline (analysis.ipynb, cell 7) on embeddings from
  (a) the published trained checkpoint and
  (b) the same architecture with random weights,
and compares the quantities the paper interprets:
  - colours falling into distinct clusters (UMAP 100-d cosine + HDBSCAN min_cluster_size=250)
  - within-colour cosine similarity ("polysemy" histograms; monosemy threshold 0.5, peaks > 0.9)
  - between-colour cosine similarity of average colour embeddings ("foundational / extension sets")
It also checks whether the checkpoint reproduces the embeddings published with the paper.

Run:  uv run --group bert python studies/khipu/03-color-bert-random-init-control/analyze.py
      (after embed.py --model trained and embed.py --model random --seed 0)
"""
import json
from pathlib import Path

import hdbscan
import numpy as np
import pandas as pd
import pyarrow.ipc as ipc
import umap
from scipy.stats import spearmanr
from sklearn.metrics import normalized_mutual_info_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DER = ROOT / "data" / "derived" / "study03"
SRC = ROOT / "data" / "clindaniel" / "data"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
SEED = 7  # as in the notebook
MODELS = {"trained": "trained", "random": "random_seed0"}


def load(tag):
    return pd.read_parquet(DER / f"tokens_{tag}.parquet"), np.load(DER / f"emb_{tag}.npy")


def unit(x):
    x = np.asarray(x, dtype=np.float64)
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def upper(S):
    return S[np.triu_indices(len(S), 1)]


summary = {}
rng = np.random.default_rng(0)

# ---------------------------------------------------------------- 1. checkpoint vs published embeddings
tok_t, emb_t = load(MODELS["trained"])
tok_r, emb_r = load(MODELS["random"])
check = {}
for c in ["M3", "Y2", "R2", "L4"]:
    pub = ipc.open_stream(open(SRC / f"token_embeddings_{c}" / "data-00000-of-00001.arrow", "rb")).read_all().to_pandas()
    P, T = [], []
    for r in pub.itertuples():
        P.append(np.vstack(list(r.embeddings)))
        T.append(emb_t[tok_t[(tok_t.color == c) & (tok_t.cluster_id == r.cluster_id)].index])
    P, T = unit(np.vstack(P)), unit(np.vstack(T))
    check[c] = {"tokens": len(P), "median_cosine_published_vs_checkpoint": round(float(np.median((P * T).sum(1))), 3),
                "published_within_colour_median": round(float(np.median(upper(P @ P.T))), 3),
                "checkpoint_within_colour_median": round(float(np.median(upper(T @ T.T))), 3)}
summary["checkpoint_reproduces_published_embeddings"] = check

# ---------------------------------------------------------------- 2. cord-level clustering, both models
colours = tok_t.color.value_counts()
summary["n_colour_tokens"] = int(len(tok_t))
summary["colour_counts"] = colours.to_dict()
cluster_rows = []
for name, (tok, emb) in {"trained": (tok_t, emb_t), "random": (tok_r, emb_r)}.items():
    np.random.seed(SEED)
    X = emb + np.random.normal(0, 0.01, emb.shape)  # the notebook's jitter before UMAP
    red = umap.UMAP(n_neighbors=15, n_components=100, min_dist=0.0, metric="cosine", random_state=SEED).fit_transform(X)
    lab = hdbscan.HDBSCAN(min_cluster_size=250).fit_predict(red)
    d = pd.DataFrame({"color": tok.color.values, "label": lab})
    inc = d[d.label != -1]
    # a colour "owns" a cluster when it is the majority colour of that cluster
    majority = inc.groupby("label").color.agg(lambda s: s.value_counts().index[0])
    purity = float((inc.color == inc.label.map(majority)).mean())
    owners = sorted(set(majority))
    S = unit(emb)
    per_colour = {}
    for c in colours.index:
        idx = np.where(tok.color.values == c)[0]
        if len(idx) > 1500:
            idx = rng.choice(idx, 1500, replace=False)
        w = upper(S[idx] @ S[idx].T)
        per_colour[c] = {"median": float(np.median(w)), "share_ge_0.9": float((w >= 0.9).mean()),
                         "share_ge_0.5": float((w >= 0.5).mean())}
    means = unit(np.vstack([emb[tok.color.values == c].mean(0) for c in colours.index]))
    summary[name] = {
        "clusters": int(lab.max() + 1),
        "share_tokens_clustered": round(float((lab != -1).mean()), 3),
        "nmi_colour_vs_cluster_on_clustered": round(float(normalized_mutual_info_score(inc.color, inc.label)), 3),
        "cluster_purity_majority_colour": round(purity, 3),
        "colours_owning_at_least_one_cluster": owners,
        "within_colour_cosine_median_range": [round(min(v["median"] for v in per_colour.values()), 3),
                                              round(max(v["median"] for v in per_colour.values()), 3)],
        "colours_with_median_within_cosine_ge_0.5": int(sum(v["median"] >= 0.5 for v in per_colour.values())),
        "between_colour_cosine_range": [round(float(upper(means @ means.T).min()), 3),
                                        round(float(upper(means @ means.T).max()), 3)],
    }
    summary[name]["_between_matrix"] = (means @ means.T).tolist()
    summary[name]["_per_colour"] = per_colour
    for c, v in per_colour.items():
        cluster_rows.append({"model": name, "color": c, "count": int(colours[c]), **{k: round(x, 4) for k, x in v.items()}})
    print(name, {k: v for k, v in summary[name].items() if not k.startswith("_")})

# ---------------------------------------------------------------- 3. does structure survive without training?
Bt, Br = np.array(summary["trained"]["_between_matrix"]), np.array(summary["random"]["_between_matrix"])
summary["between_colour_matrix_spearman_trained_vs_random"] = round(float(spearmanr(upper(Bt), upper(Br))[0]), 3)
logf = np.log(colours.values.astype(float))
freq_pair = upper(np.add.outer(logf, logf))  # pairs of common colours vs rare colours
summary["between_colour_cosine_spearman_with_log_frequency"] = {
    "trained": round(float(spearmanr(upper(Bt), freq_pair)[0]), 3),
    "random": round(float(spearmanr(upper(Br), freq_pair)[0]), 3)}
pd.DataFrame(cluster_rows).to_csv(OUT / "within_colour_cosine.csv", index=False)
for m in ["trained", "random"]:
    pd.DataFrame(summary[m].pop("_between_matrix"), index=colours.index, columns=colours.index).round(4) \
      .to_csv(OUT / f"between_colour_cosine_{m}.csv")
    summary[m].pop("_per_colour")
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
print(json.dumps({k: v for k, v in summary.items() if k not in ("colour_counts",)}, indent=1, ensure_ascii=False))
