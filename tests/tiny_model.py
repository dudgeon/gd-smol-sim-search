"""Build a tiny random-weight BERT sentence-transformer for offline tests.

The weights are random, so it says nothing about retrieval quality; it
exercises the real torch / sentence-transformers / tokenizer code path
(model loading, token-budget chunking, batching, device handling) without a
download. Golden-quality tests use the real model when it is installed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def build_tiny_model(dest: Path, corpus_dir: Path) -> Path:
    import torch
    from sentence_transformers import SentenceTransformer
    try:
        from sentence_transformers.sentence_transformer import modules as models
    except ImportError:  # older sentence-transformers
        from sentence_transformers import models
    from transformers import BertConfig, BertModel, BertTokenizerFast

    dest.mkdir(parents=True, exist_ok=True)
    words = set()
    for f in corpus_dir.rglob("*"):
        if f.is_file() and f.suffix != ".pdf":
            words.update(w.lower() for w in re.findall(r"\w+", f.read_text(errors="ignore")))
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"] + sorted(words) + list("abcdefghijklmnopqrstuvwxyz0123456789")
    tok_dir = dest / "_tok"
    tok_dir.mkdir(exist_ok=True)
    (tok_dir / "vocab.txt").write_text("\n".join(dict.fromkeys(vocab)) + "\n")
    tok = BertTokenizerFast(vocab_file=str(tok_dir / "vocab.txt"), do_lower_case=True)

    torch.manual_seed(0)
    cfg = BertConfig(vocab_size=len(tok), hidden_size=32, num_hidden_layers=2, num_attention_heads=2,
                     intermediate_size=64, max_position_embeddings=256)
    hf_dir = dest / "_hf"
    BertModel(cfg).save_pretrained(hf_dir)
    tok.save_pretrained(hf_dir)

    word = models.Transformer(str(hf_dir), max_seq_length=128)
    pool = models.Pooling(word.get_embedding_dimension(), pooling_mode="mean")
    st = SentenceTransformer(modules=[word, pool, models.Normalize()], device="cpu")
    out = dest / "tiny-bert"
    st.save(str(out))
    (out / ".sem-revision").write_text("tiny-local\n")
    return out


def tiny_registry(path: Path) -> Path:
    reg = {
        "schema": 1,
        "default": "tiny-bert",
        "models": {
            "tiny-bert": {"repo_id": "local/tiny-bert", "revision": "tiny-local", "license": "n/a",
                          "dim": 32, "max_seq_length": 128, "default_chunk_tokens": 60,
                          "query_prefix": "query: ", "query_prompt_name": None, "document_prefix": "",
                          "dupe_threshold": 0.95},
            "hash-test": {"backend": "hash", "hidden": True, "license": "n/a", "dim": 2048,
                          "max_seq_length": 4096, "default_chunk_tokens": 120, "query_prefix": "",
                          "query_prompt_name": None, "document_prefix": "", "dupe_threshold": 0.9},
        },
    }
    path.write_text(json.dumps(reg, indent=2))
    return path
