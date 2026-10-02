"""
Study 03, step 1 - contextual colour embeddings from Clindaniel's khipu BERT, and from the same
architecture with random (untrained) weights.

Reproduces the embedding step of github.com/jonclindaniel/colorful-ai-khipukamayuq (analysis.ipynb,
MIT licence): every first-order cord group in OKR v2.0.0 becomes a sequence of KCCS colour codes,
the sequence is run through BERT, and each colour token is represented by the concatenation of the
last four hidden layers (3,072 dims). The SQL query below is copied from that notebook.

  --model trained   the published checkpoint (checkpoint-400)
  --model random    identical BertConfig, freshly initialised weights (seeded), no training

Run:  ./scripts/fetch_clindaniel.sh
      uv run --group bert python studies/khipu/03-color-bert-random-init-control/embed.py --model trained
      uv run --group bert python studies/khipu/03-color-bert-random-init-control/embed.py --model random --seed 0
"""
import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from transformers import BertConfig, BertForMaskedLM, BertTokenizerFast

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = ROOT / "data" / "clindaniel"
MODEL_PATH = SRC / "pretrained-bert"
OKR_V2 = ROOT / "data" / "okr-v2.0.0" / "khipu.db"
OUT = ROOT / "data" / "derived" / "study03"
MAX_LENGTH = 512

# ---- cord-group colour sequences: query copied from Clindaniel's analysis.ipynb (cell 3) ----
QUERY = """
SELECT okr_num, cord.khipu_id, cluster_id, cord_id, cord_ordinal, cluster_ordinal,
    (SELECT color_concat FROM
        (SELECT GROUP_CONCAT(REPLACE(TRIM(
              c1.color || c1.intensity
                || case when color.operator_1 <> '' then '' || color.operator_1 else '' END
                || case when color.color_cd_2 <> '' then '' || c2.color || c2.intensity else '' END
                || case when color.operator_2 <> '' then '' || color.operator_2 else '' END
                || case when color.color_cd_3 <> '' then '' || c3.color || c3.intensity else '' END
                || case when color.operator_3 <> '' then '' || color.operator_3 else '' END
                || case when color.color_cd_4 <> '' then '' || c4.color || c4.intensity else '' END
                || case when color.operator_4 <> '' then '' || color.operator_4 else '' END
                || case when color.color_cd_5 <> '' then '' || c5.color || c5.intensity else '' END
                || case when color.operator_5 <> '' then '' || color.operator_5 else '' END,
                '*:- '), ' ', ''), '/') AS color_concat, cord_id
          FROM ascher_cord_color AS color
          LEFT JOIN ascher_color_dc AS c1 ON REPLACE(TRIM(color.color_cd_1, '*:- '), ' ', '') = REPLACE(TRIM(c1.as_color_cd, '*:- '), ' ', '')
          LEFT JOIN ascher_color_dc AS c2 ON REPLACE(TRIM(color.color_cd_2, '*:- '), ' ', '') = REPLACE(TRIM(c2.as_color_cd, '*:- '), ' ', '')
          LEFT JOIN ascher_color_dc AS c3 ON REPLACE(TRIM(color.color_cd_3, '*:- '), ' ', '') = REPLACE(TRIM(c3.as_color_cd, '*:- '), ' ', '')
          LEFT JOIN ascher_color_dc AS c4 ON REPLACE(TRIM(color.color_cd_4, '*:- '), ' ', '') = REPLACE(TRIM(c4.as_color_cd, '*:- '), ' ', '')
          LEFT JOIN ascher_color_dc AS c5 ON REPLACE(TRIM(color.color_cd_5, '*:- '), ' ', '') = REPLACE(TRIM(c5.as_color_cd, '*:- '), ' ', '')
          GROUP BY cord_id ORDER BY color_range)
      WHERE cord_id = cord.cord_id) AS color
FROM cord JOIN khipu_main ON cord.khipu_id = khipu_main.khipu_id
WHERE (cord_level = 1 OR cord_level = -(1))
ORDER BY okr_num, cord_ordinal
"""


def cord_groups():
    df = pd.read_sql_query(QUERY, sqlite3.connect(OKR_V2))
    # same cleaning as the notebook
    no_cg = (df.CLUSTER_ID == 0) & (df.CLUSTER_ORDINAL == 0)
    df = df[(df.CLUSTER_ID != 0) | no_cg].copy()  # drop cords missing a cluster id but with an ordinal
    df["CLUSTER_ID"] = df.CLUSTER_ID.astype(object)
    df.loc[no_cg, "CLUSTER_ID"] = df.loc[no_cg, "OKR_NUM"]  # khipus without cord groups: one group per khipu
    df["CLUSTER_ID"] = df.CLUSTER_ID.astype(str)
    all_missing = df.groupby("KHIPU_ID").color.apply(lambda s: s.isna().all())
    df = df[~df.KHIPU_ID.isin(all_missing[all_missing].index)].rename(
        columns={"OKR_NUM": "okr_num", "CLUSTER_ID": "cluster_id"})
    cg_map = df[["okr_num", "cluster_id"]].drop_duplicates()
    df.loc[df.color.isna(), "color"] = "[UNK]"
    cg = df.groupby("cluster_id").color.apply(" ".join).reset_index()
    return cg.merge(cg_map, on="cluster_id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["trained", "random"], required=True)
    ap.add_argument("--seed", type=int, default=0, help="initialisation seed for --model random")
    args = ap.parse_args()
    torch.set_num_threads(4)

    tok = BertTokenizerFast.from_pretrained(MODEL_PATH)
    colour_ids = {k.capitalize(): v for k, v in tok.get_vocab().items() if len(k) == 2}  # as in the notebook
    id2colour = {v: k for k, v in colour_ids.items()}

    if args.model == "trained":
        model = BertForMaskedLM.from_pretrained(MODEL_PATH / "checkpoint-400")
        tag = "trained"
    else:
        torch.manual_seed(args.seed)
        model = BertForMaskedLM(BertConfig.from_pretrained(MODEL_PATH / "checkpoint-400"))
        tag = f"random_seed{args.seed}"
    model.eval()

    cg = cord_groups()
    rows, vecs = [], []
    with torch.no_grad():
        for r in cg.itertuples(index=False):
            ids = tok(r.color, truncation=True, max_length=MAX_LENGTH, return_tensors="pt")["input_ids"]
            hs = model(input_ids=ids, output_hidden_states=True).hidden_states
            cat = torch.cat([hs[i] for i in range(-1, -5, -1)], dim=-1).squeeze(0)  # (seq, 3072)
            for pos, t in enumerate(ids[0].tolist()):
                if t in id2colour:
                    rows.append((r.okr_num, r.cluster_id, id2colour[t], pos))
                    vecs.append(cat[pos].numpy())
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["okr_num", "cluster_id", "color", "pos"]).to_parquet(OUT / f"tokens_{tag}.parquet")
    np.save(OUT / f"emb_{tag}.npy", np.vstack(vecs).astype(np.float32))
    print(f"{tag}: {len(cg)} cord groups, {len(rows)} colour tokens -> {OUT}")


if __name__ == "__main__":
    main()
