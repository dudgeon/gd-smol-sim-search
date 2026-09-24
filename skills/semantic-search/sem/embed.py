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


# --- hash backend (tests; no model files) ---------------------------------------

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


# --- ONNX Runtime backend -------------------------------------------------------------

class OnnxEmbedder(Embedder):
    """BERT-style encoder (bge-small) in ONNX Runtime on CPU, tokenised with `tokenizers`.

    Matches sentence-transformers' output for the same model: CLS pooling + L2 normalisation.
    """

    def __init__(self, spec: dict, model_dir: Path):
        # onnxruntime 1.30's macOS wheel ships Microsoft 1DS telemetry that initialises at
        # import and later POSTs to mobile.events.data.microsoft.com from native code,
        # past the Python socket guard, writing ~/Library/Caches/python3/ (observed on
        # macOS 26). Only this env var, set before the import, prevents it;
        # disable_telemetry_events() after import is too late for the init event.
        os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")
        import onnxruntime as ort
        from tokenizers import Tokenizer

        ort.disable_telemetry_events()  # belt and braces for later per-session events

        self.spec = spec
        self.key = spec["key"]
        self.dim = int(spec["dim"])
        self.device = "cpu"
        rev_file = model_dir / ".sem-revision"
        self.revision = rev_file.read_text().strip() if rev_file.exists() else "unknown"
        self.max_len = int(spec["max_seq_length"])

        tok_path = str(model_dir / "tokenizer.json")
        self.counter = Tokenizer.from_file(tok_path)  # no truncation/padding: exact token counts
        self.counter.no_truncation()
        self.counter.no_padding()
        self.tok = Tokenizer.from_file(tok_path)
        self.tok.enable_truncation(self.max_len)
        pad_id = self.tok.token_to_id("[PAD]") or 0
        self.tok.enable_padding(pad_id=pad_id, pad_token="[PAD]")

        so = ort.SessionOptions()
        so.log_severity_level = 3
        threads = os.environ.get("SEM_THREADS")
        if threads:
            so.intra_op_num_threads = int(threads)
        self.sess = ort.InferenceSession(str(model_dir / "model.onnx"), sess_options=so,
                                         providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.sess.get_inputs()}
        self.batch_size = int(os.environ.get("SEM_BATCH_SIZE") or 32)

    def count_tokens(self, texts):
        if not texts:
            return []
        return [len(e.ids) for e in self.counter.encode_batch(list(texts), add_special_tokens=False)]

    def token_spans(self, text):
        return list(self.counter.encode(text, add_special_tokens=False).offsets)

    def _run(self, batch: list[str]) -> np.ndarray:
        enc = self.tok.encode_batch(batch)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        feeds = {"input_ids": ids,
                 "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64)}
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)
        hidden = self.sess.run(None, feeds)[0]
        cls = hidden[:, 0].astype(np.float32)
        norms = np.linalg.norm(cls, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return cls / norms

    def encode(self, texts, kind="document", progress=False):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        prefix = self.spec.get("query_prefix", "") if kind == "query" else self.spec.get("document_prefix", "")
        texts = [prefix + t for t in texts] if prefix else list(texts)
        # sort by length so each batch pads to a similar length
        order = sorted(range(len(texts)), key=lambda i: -len(texts[i]))
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        bar = Progress(len(texts), "embedding") if progress else None
        for s in range(0, len(order), self.batch_size):
            idx = order[s: s + self.batch_size]
            out[idx] = self._run([texts[j] for j in idx])
            if bar:
                bar.update(len(idx))
        if bar:
            bar.close()
        return out


def model_dir_for(paths: Paths, key: str) -> Path:
    base = paths.models_dir
    if base is None:
        raise SemError("sem runtime not found (SEM_RUNTIME unset). Run ./setup.sh from the repo.")
    d = base / key
    if not (d / "model.onnx").exists() or not (d / "tokenizer.json").exists():
        raise SemError(f"model '{key}' is not installed in {base}. Re-run ./setup.sh in your terminal.")
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


def load_embedder(paths: Paths, key: str) -> Embedder:
    spec = model_spec(key)
    if spec.get("backend") == "hash":
        return HashEmbedder(spec)
    return OnnxEmbedder(spec, model_dir_for(paths, key))
