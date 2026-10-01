"""
Study 01 - Do the Khipu-ML clusters and the "Inka, Late Horizon" classifier measure khipus,
or the way khipus were transcribed?

Target: Contreras (2026), "Structural Pattern Mining in Inka Khipus", arXiv:2607.00185
        code: github.com/mcontrerasmalpar-pixel/Khipu-ML (notebooks/01_pipeline_khipu.ipynb)

Steps
  1. Rebuild the paper's 27 per-khipu features exactly as in the published notebook.
  2. Re-run UMAP + HDBSCAN with the published hyperparameters.
  3. Describe every khipu by *transcription completeness only* (how much of the record is
     blank / coded "unknown") - variables that say nothing about the object itself.
  4. Ask how well completeness alone predicts the clusters and the provenance labels.

Run:  ./scripts/fetch_okr.sh && python studies/khipu/01-khipu-ml-transcription-confound/replicate.py
"""
import json
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import entropy
from sklearn.metrics import f1_score, silhouette_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DB = ROOT / "data" / "okr" / "khipu.db"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)

conn = sqlite3.connect(DB)
khipu_main = pd.read_sql("SELECT KHIPU_ID, PROVENANCE, REGION, MUSEUM_NAME FROM khipu_main", conn)
cord = pd.read_sql("SELECT KHIPU_ID, CORD_ID, CORD_LEVEL, CORD_LENGTH, TWIST, ATTACHMENT_TYPE, FIBER FROM cord", conn)
knot = pd.read_sql("SELECT CORD_ID, TYPE_CODE, DIRECTION, NUM_TURNS FROM knot", conn)
colors = pd.read_sql("SELECT KHIPU_ID, CORD_ID, COLOR_CD_1, COLOR_CD_2 FROM ascher_cord_color", conn)

# --------------------------------------------------------------------------------------
# 1. The paper's 27 features (copied from the published notebook, cells 14-17)
# --------------------------------------------------------------------------------------
cord_feats = cord.groupby("KHIPU_ID").agg(
    n_cords=("CORD_ID", "count"),
    mean_length=("CORD_LENGTH", "mean"),
    std_length=("CORD_LENGTH", "std"),
    max_cord_level=("CORD_LEVEL", "max"),
    n_subsidiary=("CORD_LEVEL", lambda x: (x > 1).sum()),
    ratio_subsidiary=("CORD_LEVEL", lambda x: (x > 1).mean()),
    twist_S=("TWIST", lambda x: (x == "S").sum()),
    twist_Z=("TWIST", lambda x: (x == "Z").sum()),
).reset_index()
cord_feats["ratio_SZ"] = cord_feats.twist_S / (cord_feats.twist_S + cord_feats.twist_Z + 1e-9)
cord_feats["std_length"] = cord_feats.std_length.fillna(0)

knots_k = knot.merge(cord[["CORD_ID", "KHIPU_ID"]], on="CORD_ID", how="left")
knot_types = (
    pd.concat([knots_k[["KHIPU_ID"]], pd.get_dummies(knots_k.TYPE_CODE, prefix="knot")], axis=1)
    .groupby("KHIPU_ID").sum().reset_index()
)
knot_general = knots_k.groupby("KHIPU_ID").agg(
    n_knots=("TYPE_CODE", "count"),
    mean_turns=("NUM_TURNS", "mean"),
    knot_dir_S=("DIRECTION", lambda x: (x == "S").sum()),
    knot_dir_Z=("DIRECTION", lambda x: (x == "Z").sum()),
).reset_index()
knot_general["ratio_knot_SZ"] = knot_general.knot_dir_S / (knot_general.knot_dir_S + knot_general.knot_dir_Z + 1e-9)
knot_feats = knot_general.merge(knot_types, on="KHIPU_ID", how="left")


def color_entropy(s):
    c = s.dropna().value_counts(normalize=True)
    return entropy(c) if len(c) > 1 else 0.0


color_feats = colors.groupby("KHIPU_ID").agg(
    n_unique_colors=("COLOR_CD_1", "nunique"),
    color_entropy=("COLOR_CD_1", color_entropy),
    has_multicolor=("COLOR_CD_2", lambda x: int(x.notna().any())),
).reset_index()

fm = (khipu_main.merge(cord_feats, on="KHIPU_ID", how="left")
      .merge(knot_feats, on="KHIPU_ID", how="left")
      .merge(color_feats, on="KHIPU_ID", how="left"))
META = ["KHIPU_ID", "PROVENANCE", "REGION", "MUSEUM_NAME"]
FEATURES = [c for c in fm.columns if c not in META]
fm[FEATURES] = fm[FEATURES].fillna(0).astype(float)  # the paper imputes missing with 0
assert len(FEATURES) == 27, len(FEATURES)

# --------------------------------------------------------------------------------------
# 2. UMAP + HDBSCAN with the published hyperparameters
# --------------------------------------------------------------------------------------
from umap import UMAP  # noqa: E402  (slow import)
import hdbscan  # noqa: E402

X = StandardScaler().fit_transform(fm[FEATURES])


def cluster(seed):
    emb = UMAP(n_components=2, n_neighbors=15, min_dist=0.1, metric="euclidean", random_state=seed).fit_transform(X)
    lab = hdbscan.HDBSCAN(min_cluster_size=10, min_samples=5, metric="euclidean").fit_predict(emb)
    return emb, lab


emb, labels = cluster(42)
fm["cluster"] = labels
assigned = labels != -1
silhouette = float(silhouette_score(emb[assigned], labels[assigned]))
sizes = fm.cluster.value_counts().sort_index()
# name clusters by size so the output does not depend on HDBSCAN's arbitrary ids
order = sizes[sizes.index != -1].sort_values().index.tolist()
small_id = order[0]  # the paper's 17-khipu "imperial" cluster

# --------------------------------------------------------------------------------------
# 3. Transcription-completeness descriptors (nothing about the object itself)
# --------------------------------------------------------------------------------------
g = cord.groupby("KHIPU_ID")
blank = lambda s: s.isna() | (s.astype(str).str.strip() == "")  # noqa: E731
comp = pd.DataFrame({
    "cords_recorded": g.CORD_ID.count(),
    "twist_blank": g.TWIST.apply(lambda s: blank(s).mean()),
    "twist_coded_U": g.TWIST.apply(lambda s: (s == "U").mean()),
    "length_missing": g.CORD_LENGTH.apply(lambda s: (s.isna() | (s == 0)).mean()),
})
kg = knots_k.groupby("KHIPU_ID")
comp["knots_recorded"] = kg.size()
comp["knot_dir_coded_U"] = kg.DIRECTION.apply(lambda s: (s == "U").mean())
comp["knot_turns_missing"] = kg.NUM_TURNS.apply(lambda s: (s.isna() | (s == 0)).mean())
comp["color_records_per_cord"] = colors.groupby("KHIPU_ID").size() / g.CORD_ID.count()
fm = fm.merge(comp.reset_index(), on="KHIPU_ID", how="left")
fm[["cords_recorded", "knots_recorded"]] = fm[["cords_recorded", "knots_recorded"]].fillna(0)
# a khipu with no cords/knots in the database has *everything* missing
for c in ["twist_blank", "length_missing", "knot_dir_coded_U", "knot_turns_missing"]:
    fm[c] = fm[c].fillna(1.0)
fm[["twist_coded_U", "color_records_per_cord"]] = fm[["twist_coded_U", "color_records_per_cord"]].fillna(0)
fm["has_knots"] = (fm.knots_recorded > 0).astype(int)
fm["has_cords"] = (fm.cords_recorded > 0).astype(int)
COMPLETENESS = ["has_cords", "has_knots", "twist_blank", "twist_coded_U", "length_missing",
                "knot_dir_coded_U", "knot_turns_missing"]

profile = fm.groupby("cluster")[COMPLETENESS + ["ratio_SZ", "twist_S", "twist_Z", "n_knots"]].mean().round(3)
profile.insert(0, "n_khipus", fm.cluster.value_counts().sort_index())
profile.to_csv(OUT / "cluster_profile.csv")

cv = StratifiedKFold(5, shuffle=True, random_state=0)
d = fm[assigned]
tree_acc = float(cross_val_score(DecisionTreeClassifier(max_depth=3, random_state=0),
                                 d[COMPLETENESS], d.cluster, cv=cv).mean())
majority = float(d.cluster.value_counts(normalize=True).max())

# robustness: does the association survive other UMAP seeds?
robust = []
for seed in range(10):
    _, lab = cluster(seed)
    m = lab != -1
    if len(set(lab[m])) < 2:
        continue
    acc = cross_val_score(DecisionTreeClassifier(max_depth=3, random_state=0),
                          fm.loc[m, COMPLETENESS], lab[m], cv=cv).mean()
    base = pd.Series(lab[m]).value_counts(normalize=True).max()
    robust.append({"seed": seed, "n_clusters": int(len(set(lab[m]))), "noise": int((~m).sum()),
                   "tree_accuracy_completeness_only": round(float(acc), 3), "majority_baseline": round(float(base), 3)})
pd.DataFrame(robust).to_csv(OUT / "seed_robustness.csv", index=False)

small = fm[fm.cluster == small_id]
small_summary = {
    "n_khipus": int(len(small)),
    "museums": small.MUSEUM_NAME.replace("", "(blank)").value_counts().to_dict(),
    "khipus_with_zero_cords_in_db": int((small.cords_recorded == 0).sum()),
    "khipus_with_zero_knots_in_db": int((small.knots_recorded == 0).sum()),
    "cords_with_S_twist_recorded": int(small.twist_S.sum()),
    "cords_with_Z_twist_recorded": int(small.twist_Z.sum()),
}

# --------------------------------------------------------------------------------------
# 4. The "Inka, Late Horizon" label and the provenance classifier
# --------------------------------------------------------------------------------------
lh = fm.REGION.eq('"Inka, Late Horizon"')
dallas = fm.MUSEUM_NAME.eq("Dallas Museum of Art")
label_vs_museum = pd.crosstab(lh.rename("Late Horizon label"), dallas.rename("Dallas Museum of Art"))
label_vs_museum.to_csv(OUT / "late_horizon_vs_dallas.csv")

sup = fm[fm.REGION.fillna("").str.strip() != ""].copy()  # the 135 labelled khipus
counts = sup.REGION.value_counts()
sup["label"] = sup.REGION.map(lambda r: r if counts[r] >= 10 else "Other")
le = LabelEncoder()
y = le.fit_transform(sup.label)
lh_idx = list(le.classes_).index('"Inka, Late Horizon"')
cvs = StratifiedKFold(5, shuffle=True, random_state=42)

from xgboost import XGBClassifier  # noqa: E402


def xgb():
    return XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.8,
                         colsample_bytree=0.8, eval_metric="mlogloss", random_state=42)


def evaluate(cols):
    pred = cross_val_predict(xgb(), sup[cols].values, y, cv=cvs)
    return {"f1_weighted": round(float(f1_score(y, pred, average="weighted")), 3),
            "f1_late_horizon": round(float(f1_score(y == lh_idx, pred == lh_idx)), 3)}


clf = {
    "paper_27_structural_features": evaluate(FEATURES),
    "completeness_only_7_features": evaluate(COMPLETENESS),
    "single_feature_has_knots": evaluate(["has_knots"]),
}
dallas_in_sup = sup.MUSEUM_NAME.eq("Dallas Museum of Art")
clf["late_horizon_khipus_with_zero_knots_in_db"] = int((sup[sup.label == '"Inka, Late Horizon"'].knots_recorded == 0).sum())
clf["late_horizon_label_equals_dallas"] = bool((sup.label.eq('"Inka, Late Horizon"') == dallas_in_sup).all())

# --------------------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------------------
summary = {
    "okr_commit": (ROOT / "data" / "okr" / "COMMIT").read_text().strip(),
    "n_khipus": int(len(fm)),
    "n_features": len(FEATURES),
    "clusters_seed42": {str(k): int(v) for k, v in sizes.items()},
    "silhouette_seed42": round(silhouette, 3),
    "cluster_from_completeness_only": {"decision_tree_depth3_cv_accuracy": round(tree_acc, 3),
                                       "majority_class_baseline": round(majority, 3)},
    "smallest_cluster_the_imperial_one": small_summary,
    "late_horizon_vs_dallas": {"late_horizon_khipus": int(lh.sum()), "dallas_khipus": int(dallas.sum()),
                               "overlap": int((lh & dallas).sum())},
    "provenance_classifier_5fold": clf,
    "seed_robustness": robust,
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
fm[["KHIPU_ID", "REGION", "MUSEUM_NAME", "cluster"] + COMPLETENESS].to_csv(OUT / "khipu_clusters_completeness.csv", index=False)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

regime = np.select(
    [fm.has_knots.eq(0), fm.twist_coded_U.gt(0.5), fm.twist_blank.gt(0.5)],
    ["no knots in database", "twist mostly coded 'U'", "twist mostly blank"],
    "twist recorded (S/Z)")
fig, ax = plt.subplots(1, 2, figsize=(13, 5.5))
for c in sorted(fm.cluster.unique()):
    m = fm.cluster.eq(c).values
    ax[0].scatter(emb[m, 0], emb[m, 1], s=12, alpha=.8, label=f"cluster {c} (n={m.sum()})" if c != -1 else f"noise (n={m.sum()})")
ax[0].set_title("Khipu-ML replication: UMAP + HDBSCAN clusters")
ax[0].legend(fontsize=8)
for r, col in [("twist recorded (S/Z)", "#9e9e9e"), ("twist mostly coded 'U'", "#7b3fa0"),
               ("twist mostly blank", "#e08a00"), ("no knots in database", "#d62728")]:
    m = regime == r
    ax[1].scatter(emb[m, 0], emb[m, 1], s=12, alpha=.8, color=col, label=f"{r} (n={m.sum()})")
ax[1].scatter(emb[dallas.values, 0], emb[dallas.values, 1], s=70, facecolors="none", edgecolors="k", label="Dallas Museum of Art")
ax[1].set_title("Same embedding, coloured by how the khipu was transcribed")
ax[1].legend(fontsize=8)
for a in ax:
    a.set_xticks([]); a.set_yticks([])
fig.tight_layout()
fig.savefig(OUT / "umap_clusters_vs_transcription.png", dpi=150)

print(json.dumps(summary, indent=2, ensure_ascii=False))
print(profile.to_string())
