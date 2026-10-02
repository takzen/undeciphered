"""
Study 02 - Would the ALBA/KhipuReader syllabary search "find Quechua" in khipus even if there
were no Quechua to find?

Target: Sivan (2026), "Reading the Inca Spreadsheet" (preprint), ALBA Project / KhipuReader.
Published description of the calibration step: on one khipu (UR039, Huari), every valid mapping
from long-knot turn counts to Quechua syllables was tested exhaustively (46,512 candidates), each
scored against a 2,067-word Quechua dictionary. The best mapping, L3=ma L4=ka L5=ta L6=pa,
"produced 19 dictionary words", and was then reported to generalise to held-out khipus.

The ALBA code is not available to us, so this script rebuilds the *calibration logic* from that
description and asks one question: does the same search find as many "words" when
  (a) the dictionary is replaced by fake Quechua (same syllables, scrambled),
  (b) the dictionary is replaced by random syllable strings with Quechua statistics,
  (c) the dictionary is replaced by a real but wrong language (Swahili, also CV-syllabic),
      sampled to the same size and the same distribution of word lengths in syllables,
  (d) the khipu is replaced by a shuffled copy of itself?
If yes, "the best mapping produces N dictionary words" is not evidence for a linguistic channel.

Run:  ./scripts/fetch_okr.sh && ./scripts/fetch_lexicons.sh
      uv run python studies/khipu/02-alba-syllabary-null-test/null_test.py --space Ca_syllables --draws 200
      uv run python studies/khipu/02-alba-syllabary-null-test/null_test.py --space all_CV_syllables --draws 40
"""
import argparse
import itertools
import json
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(2026)
HELD_OUT_REF = 200_000  # reference mappings for held-out percentiles in the large space
UR039 = 1000374       # KHIPU_ID of UR039 (OKR KH0271)
ALBA = {3: "ma", 4: "ka", 5: "ta", 6: "pa"}

# ----------------------------------------------------------------------------------------
# Syllable inventory: Southern Quechua consonants x 3 vowels, plus bare vowels
# ----------------------------------------------------------------------------------------
CONS = ["p", "t", "ch", "k", "q", "s", "sh", "h", "m", "n", "ñ", "l", "ll", "r", "w", "y"]
VOW = ["a", "i", "u"]
SYL = [c + v for c in CONS for v in VOW] + VOW
SIDX = {s: i for i, s in enumerate(SYL)}
B = len(SYL)  # 51
SPACES = {
    # every C+a syllable: 16 candidates -> 43,680 injective 4-symbol maps (ALBA reports 46,512)
    "Ca_syllables": [SIDX[c + "a"] for c in CONS],
    # the full CV inventory: 51 candidates -> 5,997,600 maps
    "all_CV_syllables": list(range(B)),
}
_SYL_RE = re.compile("(" + "|".join(sorted(map(re.escape, SYL), key=len, reverse=True)) + ")")


def parse(word):
    """Split a word into inventory syllables, or None. Open-syllable parsing is unambiguous."""
    parts = _SYL_RE.findall(word)
    return parts if "".join(parts) == word and parts else None


def encode(sylls):
    return sum(SIDX[s] * B ** i for i, s in enumerate(sylls))


def normalise(w):
    # MINEDU mixes 3- and 5-vowel spellings; Swahili has 5 vowels. Map onto /a i u/.
    return w.lower().replace("e", "i").replace("o", "u")


# ----------------------------------------------------------------------------------------
# Lexicons
# ----------------------------------------------------------------------------------------
LEX = ROOT / "data" / "lexicons"
quechua_raw = {normalise(line.strip().rstrip(".").strip()) for line in open(LEX / "quechua_minedu_dict.quy", encoding="utf8")}
quechua_raw = {w for w in quechua_raw if re.fullmatch(r"[a-zñ]+", w)}
quechua = sorted(w for w in quechua_raw if parse(w) and len(parse(w)) >= 2)

swahili_raw = set()
for line in open(LEX / "swahili_sw_TZ.dic", encoding="utf8", errors="ignore").read().splitlines()[1:]:
    w = line.split("/")[0].strip()
    if w and w.islower() and re.fullmatch(r"[a-z]+", w):
        swahili_raw.add(normalise(w))
swahili_pool = sorted(w for w in swahili_raw if parse(w) and len(parse(w)) >= 2)

q_lengths = np.array([len(parse(w)) for w in quechua])
q_sylfreq = pd.Series([s for w in quechua for s in parse(w)]).value_counts(normalize=True)


def lex_scrambled():
    out = set()
    for w in quechua:
        s = parse(w)
        RNG.shuffle(s)
        out.add("".join(s))
    return sorted(out)


def lex_unigram():
    out = set()
    while len(out) < len(quechua):
        n = RNG.choice(q_lengths)
        out.add("".join(RNG.choice(q_sylfreq.index, size=n, p=q_sylfreq.values)))
    return sorted(out)


swahili_by_len = pd.Series(swahili_pool).groupby(pd.Series([len(parse(w)) for w in swahili_pool]))
q_len_counts = pd.Series(q_lengths).value_counts()


def lex_swahili():
    """Swahili words drawn to match the Quechua lexicon's syllable-length distribution exactly"""
    out = []
    for n_syl, k in q_len_counts.items():
        out += list(RNG.choice(swahili_by_len.get_group(n_syl).values, size=k, replace=False))
    return sorted(out)


def lex_tables(words):
    """per-length sorted arrays of syllable codes"""
    by_len = {}
    for w in words:
        s = parse(w)
        by_len.setdefault(len(s), []).append(encode(s))
    return {L: np.unique(np.array(v, dtype=np.int64)) for L, v in by_len.items()}


# ----------------------------------------------------------------------------------------
# Khipu "string" cords: cords carrying two or more long knots (not valid decimal numbers)
# ----------------------------------------------------------------------------------------
conn = sqlite3.connect(ROOT / "data" / "okr" / "khipu.db")
k = pd.read_sql("""
    SELECT co.KHIPU_ID, k.CORD_ID, k.NUM_TURNS, k.KNOT_ORDINAL, kc.ORDINAL AS KC_ORD, co.CORD_ORDINAL
    FROM knot k JOIN knot_cluster kc ON k.CLUSTER_ID = kc.CLUSTER_ID
    JOIN cord co ON co.CORD_ID = k.CORD_ID
    WHERE k.TYPE_CODE = 'L'""", conn).sort_values(["KHIPU_ID", "CORD_ORDINAL", "KC_ORD", "KNOT_ORDINAL"])
seqs = k.groupby(["KHIPU_ID", "CORD_ID"], sort=False).NUM_TURNS.apply(
    lambda s: tuple(int(x) if x == x else -1 for x in s))
strings = seqs[seqs.map(len) >= 2]
in_alphabet = strings.map(lambda s: all(t in ALBA for t in s))
calib = list(strings.loc[UR039])                                            # 64 cords
held = [s for (kid, _), s in strings[in_alphabet].items() if kid != UR039 and len(s) <= 10]
assert all(all(t in ALBA for t in s) for s in calib)
TYPES = sorted(ALBA)                                                         # [3, 4, 5, 6]
TI = {t: i for i, t in enumerate(TYPES)}


def patterns(cords):
    c = pd.Series([tuple(TI[t] for t in s) for s in cords]).value_counts()
    return list(c.index), c.values


def score(maps, cords, tables):
    """for every mapping: (#cords whose reading is a word, #distinct readings that are words)"""
    pats, counts = patterns(cords)
    hits = np.zeros(len(maps), dtype=np.int32)
    words = np.zeros(len(maps), dtype=np.int32)
    for p, n in zip(pats, counts, strict=True):
        tab = tables.get(len(p))
        if tab is None:
            continue
        code = np.zeros(len(maps), dtype=np.int64)
        for pos, sym in enumerate(p):
            code += maps[:, sym].astype(np.int64) * (B ** pos)
        i = np.searchsorted(tab, code)
        ok = (i < len(tab)) & (tab[np.minimum(i, len(tab) - 1)] == code)
        hits += ok * n
        words += ok
    return hits, words


def shuffled(cords):
    flat = [t for s in cords for t in s]
    RNG.shuffle(flat)
    out, i = [], 0
    for s in cords:
        out.append(tuple(flat[i:i + len(s)]))
        i += len(s)
    return out


def calibrate(maps, cords, tables):
    hits, words = score(maps, cords, tables)
    best = np.lexsort((-words, -hits))[0]
    return best, int(hits[best]), int(words[best])


def held_out_percentile(ref, mapping, tables):
    """share of reference mappings that `mapping` beats on held-out khipus (ties count half)"""
    h, _ = score(ref, held, tables)
    hb = int(score(mapping[None, :], held, tables)[0][0])
    return float((h < hb).mean() + 0.5 * (h == hb).mean()), hb


# ----------------------------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------------------------
summary = {
    "okr_commit": (ROOT / "data" / "okr" / "COMMIT").read_text().strip(),
    "quechua_lexicon_size": len(quechua),
    "quechua_raw_single_word_entries": len(quechua_raw),
    "swahili_pool_size": len(swahili_pool),
    "calibration_khipu": "UR039 (OKR KH0271)",
    "calibration_string_cords": len(calib),
    "calibration_distinct_patterns": len(patterns(calib)[0]),
    "held_out_string_cords_L3_to_L6": len(held),
    "held_out_khipus": int(strings[in_alphabet].drop(UR039, level=0).index.get_level_values(0).nunique()),
    "spaces": {},
}
ap = argparse.ArgumentParser()
ap.add_argument("--space", choices=list(SPACES), default="Ca_syllables")
ap.add_argument("--draws", type=int, default=200, help="null draws per null model")
args = ap.parse_args()

real_tables = lex_tables(quechua)
rows = []
for space, cand in [(args.space, SPACES[args.space])]:
    maps = np.array(list(itertools.permutations(cand, len(TYPES))), dtype=np.int16)
    # held-out percentiles: all mappings in the small space, a fixed random sample in the large one
    ref = maps if len(maps) <= HELD_OUT_REF else maps[np.random.default_rng(0).choice(len(maps), HELD_OUT_REF, replace=False)]
    alba_row = np.array([SIDX[ALBA[t]] for t in TYPES])
    alba_i = int(np.where((maps == alba_row).all(1))[0][0])

    # real data, real dictionary
    hits, words = score(maps, calib, real_tables)
    best, bh, bw = calibrate(maps, calib, real_tables)
    pct, held_hits = held_out_percentile(ref, maps[best], real_tables)
    alba_pct, alba_held = held_out_percentile(ref, maps[alba_i], real_tables)
    real = {
        "n_mappings": len(maps), "held_out_reference_mappings": len(ref),
        "best_mapping": {f"L{t}": SYL[maps[best, TI[t]]] for t in TYPES},
        "best_cord_hits": bh, "best_distinct_words": bw,
        "best_held_out_hits": held_hits, "best_held_out_percentile": round(pct, 4),
        "alba_mapping_cord_hits": int(hits[alba_i]), "alba_mapping_distinct_words": int(words[alba_i]),
        "alba_mapping_rank": int((hits > hits[alba_i]).sum() + 1),
        "alba_held_out_hits": alba_held, "alba_held_out_percentile": round(alba_pct, 4),
        "alba_words_found": sorted({"".join(ALBA[t] for t in s) for s in calib}
                                   & set(quechua)),
    }
    # null models: the whole calibration pipeline re-run with no Quechua signal in it
    nulls = {"scrambled_quechua": [], "random_syllable_lexicon": [], "swahili": [], "shuffled_khipu": []}
    for d in range(args.draws):
        for name, make in [("scrambled_quechua", lex_scrambled), ("random_syllable_lexicon", lex_unigram),
                           ("swahili", lex_swahili)]:
            t = lex_tables(make())
            b, h, w = calibrate(maps, calib, t)
            p, _ = held_out_percentile(ref, maps[b], t)
            nulls[name].append((h, w, p))
            rows.append({"space": space, "null": name, "draw": d, "best_cord_hits": h, "best_distinct_words": w,
                         "held_out_percentile": p})
        sc = shuffled(calib)
        b, h, w = calibrate(maps, sc, real_tables)
        nulls["shuffled_khipu"].append((h, w, None))
        rows.append({"space": space, "null": "shuffled_khipu", "draw": d, "best_cord_hits": h,
                     "best_distinct_words": w, "held_out_percentile": None})
    res = {}
    for name, v in nulls.items():
        h = np.array([x[0] for x in v])
        w = np.array([x[1] for x in v])
        r = {"draws": len(v),
             "best_cord_hits_mean": round(float(h.mean()), 2), "best_cord_hits_range": [int(h.min()), int(h.max())],
             "p_value_cord_hits_ge_real": round(float(((h >= bh).sum() + 1) / (len(h) + 1)), 4),
             "best_distinct_words_mean": round(float(w.mean()), 2),
             "p_value_distinct_words_ge_real": round(float(((w >= bw).sum() + 1) / (len(w) + 1)), 4)}
        if v[0][2] is not None:
            p = np.array([x[2] for x in v])
            r["held_out_percentile_median"] = round(float(np.median(p)), 4)
            r["share_with_held_out_percentile_ge_0.95"] = round(float((p >= 0.95).mean()), 3)
        res[name] = r
    summary["spaces"][space] = {"real_quechua": real, "nulls": res}
    print(space, json.dumps(summary["spaces"][space], indent=1, ensure_ascii=False))

summary["null_draws_per_model"] = args.draws
pd.DataFrame(rows).to_csv(OUT / f"null_draws_{args.space}.csv", index=False)
(OUT / f"summary_{args.space}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

df = pd.DataFrame(rows)
sp = args.space
real = summary["spaces"][sp]["real_quechua"]
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
labels = {"scrambled_quechua": "fake Quechua (syllables scrambled)", "random_syllable_lexicon": "random syllable strings",
          "swahili": "Swahili dictionary", "shuffled_khipu": "shuffled khipu + real Quechua"}
for name, lab in labels.items():
    v = df[(df.space == sp) & (df.null == name)].best_cord_hits
    ax[0].hist(v, bins=range(0, 66, 2), alpha=.55, label=lab)
ax[0].axvline(real["best_cord_hits"], color="k", lw=2, label=f"real UR039 + real Quechua ({real['best_cord_hits']})")
ax[0].set_xlabel("UR039 string cords read as dictionary words by the best mapping (of 64)")
ax[0].set_ylabel("null draws")
ax[0].set_title("Calibration: how many 'words' does the best mapping find?")
ax[0].legend(fontsize=8)
for name in ["scrambled_quechua", "random_syllable_lexicon", "swahili"]:
    v = df[(df.space == sp) & (df.null == name)].held_out_percentile.astype(float)
    ax[1].hist(v, bins=np.linspace(0, 1, 21), alpha=.55, label=labels[name])
ax[1].axvline(real["best_held_out_percentile"], color="k", lw=2, label="real Quechua")
ax[1].set_xlabel("held-out percentile of the calibrated mapping (other khipus)")
ax[1].set_title("'Generalisation' to held-out khipus")
ax[1].legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / f"null_distributions_{sp}.png", dpi=150)
