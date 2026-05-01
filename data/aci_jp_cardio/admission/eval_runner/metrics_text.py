"""
Lexical and semantic similarity metrics:
- ROUGE-L  (Japanese MeCab tokenization via fugashi/unidic-lite)
- BERTScore F1 (Japanese model: cl-tohoku/bert-base-japanese-v3)

Both metrics are loaded lazily — eval_cardio.py can run with --skip-bertscore
if the model download is not yet cached.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# === MeCab tokenizer (singleton) ===
_TAGGER = None


def _get_tagger():
    global _TAGGER
    if _TAGGER is None:
        try:
            import fugashi
            _TAGGER = fugashi.Tagger()
        except Exception as e:
            logger.warning(f"fugashi unavailable: {e}; falling back to char-tokenize")
            _TAGGER = "char"
    return _TAGGER


def tokenize_ja(text: str) -> str:
    """Whitespace-joined token string for ROUGE input."""
    tagger = _get_tagger()
    if tagger == "char":
        return " ".join(list(text or ""))
    tokens = [w.surface for w in tagger(text or "")]
    return " ".join(tokens)


# === ROUGE ===
_ROUGE_SCORER = None


def _get_rouge():
    global _ROUGE_SCORER
    if _ROUGE_SCORER is None:
        from rouge_score import rouge_scorer
        _ROUGE_SCORER = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
    return _ROUGE_SCORER


def compute_rouge_l(generated: str, reference: str) -> float:
    """ROUGE-L F-measure on MeCab-tokenized text. Returns 0.0 if empty."""
    if not generated or not reference:
        return 0.0
    scorer = _get_rouge()
    g_tok = tokenize_ja(generated)
    r_tok = tokenize_ja(reference)
    score = scorer.score(r_tok, g_tok)
    return round(score["rougeL"].fmeasure, 4)


# === BERTScore ===
_BERTSCORE_MODEL = "cl-tohoku/bert-base-japanese-v3"


def compute_bertscore(generated: str, reference: str) -> Optional[float]:
    """BERTScore F1 with Japanese BERT. Returns None on failure."""
    if not generated or not reference:
        return 0.0
    try:
        from bert_score import score
        # cands, refs are lists; use single pair
        P, R, F = score(
            cands=[generated],
            refs=[reference],
            model_type=_BERTSCORE_MODEL,
            num_layers=9,  # default for bert-base
            verbose=False,
            device="cuda" if _has_cuda() else "cpu",
            batch_size=1,
        )
        return round(F.item(), 4)
    except Exception as e:
        logger.warning(f"BERTScore failed: {e}")
        return None


def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def compute_text_metrics(generated: str, reference: str, skip_bertscore: bool = False) -> Dict:
    out = {"rouge_l": compute_rouge_l(generated, reference)}
    if not skip_bertscore:
        bs = compute_bertscore(generated, reference)
        if bs is not None:
            out["bertscore_f1"] = bs
    return out
