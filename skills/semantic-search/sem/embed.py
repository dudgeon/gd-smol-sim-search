"""Model loading, tokenisation (for chunk budgets) and batched embedding."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import numpy as np

from .env import Paths, SemError, log, model_spec
from .progress import Progress

_WORD = re.compile(r"\w+", re.UNICODE)


class Embedder:
    key: str
    spec: dict
    dim: int
    revision: str
    device: str = "cpu"

    def count_tokens(self, texts: list[str]) -> list[int]:
        raise NotImplementedError

    def token_spans(self, text: str) -> list[tuple[int, int]]:
        """Character spans of each token in ``text`` (used to cut long text)."""
        raise NotImplementedError

    def encode(self, texts: list[str], kind: str = "document", progress: bool = False) -> np.ndarray:
        raise NotImplementedError

    @property
    def max_chunk_tokens(self) -> int:
        # leave room for special tokens
        return int(self.spec["max_seq_length"]) - 8


# --- hash backend (tests; no torch, no download) ------------------------------

_STOP = frozenset("""a an and are as at be but by for from has have how i in is it its of on or
that the this to was were what when where which who why will with you your do does""".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


class HashEmbedder(Embedder):
    def __init__(self, spec: dict):
        self.spec = spec
        self.key = spec["key"]
        self.dim = int(spec["dim"])
        self.revision = "builtin"
        self.device = "cpu"

    def count_tokens(self, texts):
        return [len(_WORD.findall(t)) for t in texts]

    def token_spans(self, text):
        return [m.span() for m in _WORD.finditer(text)]

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        words = [_stem(w) for w in (m.group(0).lower() for m in _WORD.finditer(text)) if w not in _STOP]
        feats = words + [a + "_" + b for a, b in zip(words, words[1:])]
        for f in feats:
            h = hashlib.blake2b(f.encode(), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            v[idx] += 1.0 if h[4] & 1 else -1.0
        v = np.sign(v) * np.log1p(np.abs(v))
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def encode(self, texts, kind="document", progress=False):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._vec(t) for t in texts]).astype(np.float32)


# --- sentence-transformers backend --------------------------------------------

def _is_oom(e: BaseException) -> bool:
    s = str(e).lower()
    return "out of memory" in s or "mps backend out of memory" in s


class STEmbedder(Embedder):
    def __init__(self, spec: dict, model_dir: Path, device: str):
        import logging
        import warnings

        warnings.filterwarnings("ignore", category=FutureWarning)
        warnings.filterwarnings("ignore", category=UserWarning)
        for name in ("transformers", "sentence_transformers", "huggingface_hub"):
            logging.getLogger(name).setLevel(logging.ERROR)
        try:
            from transformers.utils import logging as tlog
            tlog.set_verbosity_error()
            tlog.disable_progress_bar()
        except Exception:
            pass

        from sentence_transformers import SentenceTransformer

        self.spec = spec
        self.key = spec["key"]
        self.dim = int(spec["dim"])
        rev_file = model_dir / ".sem-revision"
        self.revision = rev_file.read_text().strip() if rev_file.exists() else "unknown"
        self.device = device
        self.model = SentenceTransformer(str(model_dir), device=device, local_files_only=True)
        self.model.max_seq_length = min(int(spec["max_seq_length"]), int(self.model.max_seq_length or 10**9))
        self.tokenizer = self.model.tokenizer
        dim_fn = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        got = dim_fn()
        if got and got != self.dim:
            raise SemError(f"model '{self.key}' has dim {got}, registry says {self.dim}")
        self.batch_size = int(os.environ.get("SEM_BATCH_SIZE") or (64 if device == "mps" else 32))

    @property
    def max_chunk_tokens(self) -> int:
        return int(self.model.max_seq_length) - 8

    def count_tokens(self, texts):
        if not texts:
            return []
        enc = self.tokenizer(list(texts), add_special_tokens=False, truncation=False)
        return [len(ids) for ids in enc["input_ids"]]

    def token_spans(self, text):
        enc = self.tokenizer(text, add_special_tokens=False, truncation=False, return_offsets_mapping=True)
        return [tuple(o) for o in enc["offset_mapping"]]

    def _encode_batch(self, batch: list[str], kind: str) -> np.ndarray:
        kw: dict = {}
        if kind == "query":
            if self.spec.get("query_prompt_name") and self.spec["query_prompt_name"] in (self.model.prompts or {}):
                kw["prompt_name"] = self.spec["query_prompt_name"]
            elif self.spec.get("query_prefix"):
                kw["prompt"] = self.spec["query_prefix"]
        elif self.spec.get("document_prefix"):
            kw["prompt"] = self.spec["document_prefix"]
        return self.model.encode(batch, batch_size=len(batch), normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False, **kw)

    def encode(self, texts, kind="document", progress=False):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        # sort by length so batches are similarly padded
        order = sorted(range(len(texts)), key=lambda i: -len(texts[i]))
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        bar = Progress(len(texts), "embedding") if progress else None
        i = 0
        while i < len(order):
            idx = order[i: i + self.batch_size]
            batch = [texts[j] for j in idx]
            try:
                vecs = self._encode_batch(batch, kind)
            except RuntimeError as e:
                if not _is_oom(e):
                    raise
                self._empty_cache()
                if self.batch_size > 1:
                    self.batch_size = max(1, self.batch_size // 2)
                    log(f"sem: out of memory on {self.device}; batch size -> {self.batch_size}")
                    continue
                if self.device != "cpu":
                    log("sem: out of memory at batch size 1; moving model to cpu")
                    self.model.to("cpu")
                    self.device = "cpu"
                    self.batch_size = 16
                    continue
                raise
            out[idx] = vecs
            i += len(idx)
            if bar:
                bar.update(len(idx))
        if bar:
            bar.close()
        return out

    def _empty_cache(self):
        try:
            import torch
            if self.device == "mps":
                torch.mps.empty_cache()
        except Exception:
            pass


def model_dir_for(paths: Paths, key: str) -> Path:
    base = paths.models_dir
    if base is None:
        raise SemError("sem runtime not found (SEM_RUNTIME unset). Run ./setup.sh from the repo.")
    d = base / key
    if not (d / "modules.json").exists() and not (d / "config.json").exists():
        raise SemError(f"model '{key}' is not installed. Run ./setup.sh --model {key} in your terminal.")
    return d


def installed_revision(paths: Paths, key: str) -> str | None:
    spec = model_spec(key)
    if spec.get("backend") == "hash":
        return "builtin"
    base = paths.models_dir
    if base is None:
        return None
    f = base / key / ".sem-revision"
    return f.read_text().strip() if f.exists() else None


def load_embedder(paths: Paths, key: str, device: str) -> Embedder:
    spec = model_spec(key)
    if spec.get("backend") == "hash":
        return HashEmbedder(spec)
    return STEmbedder(spec, model_dir_for(paths, key), device)
