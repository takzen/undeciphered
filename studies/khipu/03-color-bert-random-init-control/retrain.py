"""
Study 03c - retrain the colour BERT from scratch, on the original or on colour-shuffled sequences.

Reproduces the training recipe of Clindaniel's training.ipynb: BertForMaskedLM with the default
BertConfig (max_position_embeddings=512), MLM probability 0.15, 400 optimiser steps, batch size 1
with 4 gradient-accumulation steps, learning rate 5e-5 (Hugging Face Trainer defaults: AdamW,
linear decay, no warmup, gradient clipping at 1.0), on the published 512-token training chunks.

  --data original   the published training chunks (a second, independent training run)
  --data shuffled   colour tokens permuted across the whole corpus: every chunk keeps its length,
                    its special tokens and colour-combination operators in place, and every colour
                    keeps its frequency, but which colours co-occur in a cord group is destroyed

Run:  uv run --group bert python studies/khipu/03-color-bert-random-init-control/retrain.py --data shuffled --seed 0
"""
import argparse
import math
import random
import time
from pathlib import Path

import numpy as np
import pyarrow.ipc as ipc
import torch
from transformers import BertConfig, BertForMaskedLM, BertTokenizerFast, DataCollatorForLanguageModeling

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = ROOT / "data" / "clindaniel"
OUT = ROOT / "data" / "derived" / "study03" / "models"


def chunks(split):
    t = ipc.open_stream(open(SRC / "data" / split / "data-00000-of-00001.arrow", "rb")).read_all()
    return [list(map(int, x)) for x in t.column("input_ids").to_pylist()]


def shuffle_colours(seqs, colour_ids, rng):
    pos = [(i, j) for i, s in enumerate(seqs) for j, t in enumerate(s) if t in colour_ids]
    vals = [seqs[i][j] for i, j in pos]
    rng.shuffle(vals)
    out = [list(s) for s in seqs]
    for (i, j), v in zip(pos, vals, strict=True):
        out[i][j] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", choices=["original", "shuffled"], required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--steps", type=int, default=400)
    args = ap.parse_args()
    torch.set_num_threads(4)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    tok = BertTokenizerFast.from_pretrained(SRC / "pretrained-bert")
    colour_ids = {v for k, v in tok.get_vocab().items() if len(k) == 2}
    train, test = chunks("train"), chunks("test")
    if args.data == "shuffled":
        rng = random.Random(args.seed)
        train, test = shuffle_colours(train, colour_ids, rng), shuffle_colours(test, colour_ids, rng)

    model = BertForMaskedLM(BertConfig(max_position_embeddings=512))
    model.train()
    coll = DataCollatorForLanguageModeling(tok, mlm=True, mlm_probability=0.15)
    opt = torch.optim.AdamW(model.parameters(), lr=5e-5, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: max(0.0, 1 - s / args.steps))
    accum, step, order, t0 = 4, 0, [], time.time()
    while step < args.steps:
        for _ in range(accum):
            if not order:
                order = list(np.random.permutation(len(train)))
            b = coll([{"input_ids": train[order.pop()]}])
            loss = model(input_ids=b["input_ids"], labels=b["labels"]).loss / accum
            loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        opt.zero_grad()
        step += 1
        if step % 50 == 0 or step == 1:
            print(f"step {step}  loss {loss.item() * accum:.3f}  {time.time() - t0:.0f}s", flush=True)

    model.eval()
    torch.manual_seed(0)
    losses = []
    with torch.no_grad():
        for _ in range(5):
            for s in test:
                b = coll([{"input_ids": s}])
                losses.append(model(input_ids=b["input_ids"], labels=b["labels"]).loss.item())
    tag = f"retrained_{args.data}_seed{args.seed}"
    model.save_pretrained(OUT / tag)
    ev = float(np.mean(losses))
    (OUT / tag / "eval.txt").write_text(f"test MLM loss {ev:.4f} (perplexity {math.exp(ev):.2f}); steps {args.steps}\n")
    print(f"{tag}: test MLM loss {ev:.3f}, saved to {OUT / tag}")


if __name__ == "__main__":
    main()
