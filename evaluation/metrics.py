"""Quality metrics for compaction evaluation.

Three layers of quality measurement:
1. ROUGE-L (lexical overlap — fast, deterministic)
2. NLI entailment (does the compacted answer preserve baseline facts? — deterministic, semantic)
3. LLM-as-judge (structured rubric scoring via local Qwen — interpretable, non-deterministic)
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    """Approximate token count (roughly 1 token per 4 chars).

    Good enough for demo purposes. Production would use the model's tokenizer.
    """
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# 1. ROUGE-L (lexical)
# ---------------------------------------------------------------------------

def compute_rouge_l(reference: str, hypothesis: str) -> dict[str, float]:
    """Compute ROUGE-L between reference and hypothesis."""
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        scores = scorer.score(reference, hypothesis)
        return {
            "rouge_l_precision": round(scores["rougeL"].precision, 4),
            "rouge_l_recall": round(scores["rougeL"].recall, 4),
            "rouge_l_f1": round(scores["rougeL"].fmeasure, 4),
        }
    except Exception as e:
        print(f"ROUGE-L error: {e}")
        return {"rouge_l_precision": 0, "rouge_l_recall": 0, "rouge_l_f1": 0}


# ---------------------------------------------------------------------------
# 2. NLI entailment (semantic, deterministic)
# ---------------------------------------------------------------------------

_nli_model = None
_nli_tokenizer = None
NLI_MODEL_NAME = "cross-encoder/nli-MiniLM2-L6-H768"


def _get_nli_model():
    """Load the NLI cross-encoder model (lazy, cached)."""
    global _nli_model, _nli_tokenizer
    if _nli_model is None:
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            print(f"Loading NLI model: {NLI_MODEL_NAME}")
            _nli_tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL_NAME)
            _nli_model = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL_NAME)
            _nli_model.eval()
            print("  NLI model loaded.")
        except Exception as e:
            print(f"Failed to load NLI model: {e}")
    return _nli_model, _nli_tokenizer


def compute_nli(reference: str, hypothesis: str) -> dict[str, float]:
    """Check whether the hypothesis entails / contradicts / is neutral to the reference.

    We run NLI in both directions:
    - Forward: does the compacted answer entail the baseline facts?
    - Backward: does the baseline entail the compacted answer's claims?

    The key metric is 'nli_preservation': geometric mean of bidirectional entailment.
    High only if the compacted answer both follows from AND covers the baseline.

    Returns scores for entailment, contradiction, and neutral (0.0-1.0).
    """
    model, tokenizer = _get_nli_model()
    if model is None or tokenizer is None:
        return {"nli_entailment": 0, "nli_contradiction": 0, "nli_neutral": 0, "nli_preservation": 0}

    try:
        import torch

        ref_trunc = reference[:1500]
        hyp_trunc = hypothesis[:1500]

        # Forward: does hypothesis preserve reference's facts?
        fwd_features = tokenizer(ref_trunc, hyp_trunc, padding=True, truncation=True, return_tensors="pt")
        with torch.no_grad():
            fwd_probs = torch.softmax(model(**fwd_features).logits, dim=-1)[0]

        # Backward: does reference support hypothesis's claims?
        bwd_features = tokenizer(hyp_trunc, ref_trunc, padding=True, truncation=True, return_tensors="pt")
        with torch.no_grad():
            bwd_probs = torch.softmax(model(**bwd_features).logits, dim=-1)[0]

        # MiniLM label order: {0: contradiction, 1: entailment, 2: neutral}
        fwd_entail = float(fwd_probs[1])
        fwd_contra = float(fwd_probs[0])
        fwd_neutral = float(fwd_probs[2])
        bwd_entail = float(bwd_probs[1])

        # Preservation: geometric mean of bidirectional entailment
        preservation = (fwd_entail * bwd_entail) ** 0.5

        return {
            "nli_entailment": round(fwd_entail, 4),
            "nli_contradiction": round(fwd_contra, 4),
            "nli_neutral": round(fwd_neutral, 4),
            "nli_backward_entailment": round(bwd_entail, 4),
            "nli_preservation": round(preservation, 4),
        }
    except Exception as e:
        print(f"NLI error: {e}")
        return {"nli_entailment": 0, "nli_contradiction": 0, "nli_neutral": 0, "nli_preservation": 0}


# ---------------------------------------------------------------------------
# 3. LLM-as-judge (interpretable, non-deterministic)
# ---------------------------------------------------------------------------

_judge_client = None

# The judge model should ideally be different from the generator to avoid
# self-preference bias. Change this to a different Ollama model if available.
JUDGE_MODEL = "qwen2.5:7b-instruct"

JUDGE_RUBRIC = """You are an impartial quality judge. Compare the BASELINE answer to the TEST answer.

NOTE: You are NOT the model that generated these answers. Judge objectively.

Both answers were generated from the same question but with different amounts of context (the TEST answer may have had some context removed before the LLM saw it).

Score the TEST answer on these criteria (each 1-10):

1. **Factual Preservation** — Does the TEST answer contain the same key facts as the BASELINE? (10 = all facts present, 1 = most facts missing)
2. **Accuracy** — Are there any factual errors in the TEST answer that aren't in the BASELINE? (10 = no errors, 1 = major errors introduced)
3. **Completeness** — How much of the BASELINE's detail does the TEST answer cover? (10 = equally detailed, 1 = bare minimum)
4. **Coherence** — Is the TEST answer well-structured and readable? (10 = clear and logical, 1 = disjointed)

Respond with ONLY a JSON object, no other text:
{"factual_preservation": <int>, "accuracy": <int>, "completeness": <int>, "coherence": <int>, "overall": <int>, "explanation": "<one sentence>"}"""


def _get_judge_client():
    global _judge_client
    if _judge_client is None:
        from openai import OpenAI
        _judge_client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    return _judge_client


def compute_llm_judge(
    reference: str,
    hypothesis: str,
    model: str = "",
) -> dict[str, float]:
    """Use the local LLM as a judge to score answer quality on a structured rubric.

    Uses JUDGE_MODEL by default. Ideally this should be a different model than
    the one that generated the answers to avoid self-preference bias.

    Returns scores (0-1) for: factual_preservation, accuracy, completeness,
    coherence, and an overall score. Also returns the judge's explanation.
    """
    judge_model = model or JUDGE_MODEL
    try:
        client = _get_judge_client()

        user_msg = (
            f"BASELINE ANSWER:\n{reference[:2000]}\n\n"
            f"TEST ANSWER:\n{hypothesis[:2000]}"
        )

        response = client.chat.completions.create(
            model=judge_model,
            messages=[
                {"role": "system", "content": JUDGE_RUBRIC},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=300,
        )

        raw = response.choices[0].message.content or ""

        # Parse JSON from response
        import json
        import re

        # Extract JSON from the response (handle markdown code blocks)
        json_match = re.search(r'\{[^}]+\}', raw, re.DOTALL)
        if json_match:
            scores = json.loads(json_match.group())
        else:
            print(f"LLM judge returned unparseable response: {raw[:200]}")
            return _default_judge_scores()

        return {
            "judge_factual": scores.get("factual_preservation", 5) / 10,
            "judge_accuracy": scores.get("accuracy", 5) / 10,
            "judge_completeness": scores.get("completeness", 5) / 10,
            "judge_coherence": scores.get("coherence", 5) / 10,
            "judge_overall": scores.get("overall", 5) / 10,
            "judge_explanation": scores.get("explanation", ""),
        }
    except Exception as e:
        print(f"LLM judge error: {e}")
        return _default_judge_scores()


def _default_judge_scores() -> dict:
    return {
        "judge_factual": 0.5,
        "judge_accuracy": 0.5,
        "judge_completeness": 0.5,
        "judge_coherence": 0.5,
        "judge_overall": 0.5,
        "judge_explanation": "Judge unavailable",
    }


# ---------------------------------------------------------------------------
# Combined quality computation
# ---------------------------------------------------------------------------

def compute_quality(
    baseline_answer: str,
    test_answer: str,
    use_nli: bool = True,
    use_judge: bool = True,
) -> dict[str, float]:
    """Compute all quality metrics between baseline and test answers.

    Returns a dict with:
    - rouge_l_* (lexical overlap)
    - nli_* (factual preservation via NLI entailment)
    - judge_* (LLM rubric scores)
    - composite_score (weighted combination of all metrics)
    """
    if not baseline_answer or not test_answer:
        return {}

    metrics = {}

    # Layer 1: ROUGE-L (always)
    metrics.update(compute_rouge_l(baseline_answer, test_answer))

    # Layer 2: NLI entailment (deterministic, semantic)
    if use_nli:
        metrics.update(compute_nli(baseline_answer, test_answer))

    # Layer 3: LLM-as-judge (interpretable rubric)
    if use_judge:
        metrics.update(compute_llm_judge(baseline_answer, test_answer))

    # Composite score: weighted combination
    # NLI is downweighted because cross-encoder NLI models are unreliable on
    # multi-paragraph text (they're trained on sentence pairs). ROUGE-L and the
    # judge are more trustworthy for this task.
    rouge_f1 = metrics.get("rouge_l_f1", 0)
    nli_pres = metrics.get("nli_preservation", rouge_f1)
    judge_overall = metrics.get("judge_overall", 0.5)

    composite = (
        0.15 * nli_pres +
        0.45 * judge_overall +
        0.40 * rouge_f1
    )
    metrics["composite_score"] = round(composite, 4)

    return metrics


def compute_quality_fast(baseline_answer: str, test_answer: str) -> dict[str, float]:
    """Quick quality check — ROUGE-L only (for threshold sweeps where speed matters)."""
    if not baseline_answer or not test_answer:
        return {}
    metrics = compute_rouge_l(baseline_answer, test_answer)
    metrics["composite_score"] = metrics.get("rouge_l_f1", 0)
    return metrics
