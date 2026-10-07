"""VQ-207: Extractive answer engine — retrieval-only, no generation.

Answers are sentences lifted verbatim from the tenant's own document
chunks. There is no generation, no paraphrasing, and no external model
anywhere in this module. If the tenant's documents do not answer the
question, the engine says so (routing="no_answer") and never invents or
grabs a random excerpt (HeXta bug 2 must not come back).

Behaviour kept from HeXta's answer layer (referenced, not imported):

- answer / partial / no_answer confidence routing
- extractive answer-phrase selection from retrieved evidence
- a query<->evidence relevance floor below which retrieval is treated as
  off-topic and never presented as an answer
- follow-up suggestions sourced only from the tenant's own content
- corpus-vocabulary-gated typo correction whose confirmation is echoed in
  the response

Deliberately NOT ported (HeXta's optional generation layer): the client
SDKs, the on/off switch for that layer, and its grounding, routing,
breaker and analytics components.
"""

from __future__ import annotations

import difflib
import re
import uuid
from typing import List, Set, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.answer import (
    AnswerResponse,
    AnswerSource,
    SpellcheckInfo,
    SpellCorrection,
)
from app.services.search import hybrid_search, SearchTenantRequiredError

# --- Confidence / routing thresholds (answer / partial / no_answer) -----

ANSWER_CONFIDENCE = 90.0
PARTIAL_CONFIDENCE = 50.0
NO_ANSWER_RELEVANCE_FLOOR = 0.35

# --- Answer phrase selection --------------------------------------------

MAX_ANSWER_CHARS = 300
MIN_SENTENCE_CHARS = 25
HEADING_MAX_CHARS = 80
MAX_SOURCES = 5

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_SOFT_WRAP_RE = re.compile(r"\n(?=[a-z])")
_FOOTER_RE = re.compile(r"^(source:|category:|note:|see\s)", re.IGNORECASE)
_TERMINAL_PUNCT = set(".!?")
_ABBREVIATION_BOUNDARY_RE = re.compile(r"\b[A-Z]\.$")

_WH_OPENERS = {
    "what", "how", "why", "when", "where", "who", "whom", "which", "whose",
    "is", "are", "do", "does", "did", "can", "could", "will", "would",
    "should", "may", "might",
}

_QUESTION_STARTERS = {
    "what", "how", "why", "when", "where", "who", "whom", "which",
    "whose", "is", "are", "was", "were", "do", "does", "did", "can",
    "could", "will", "would", "should", "may", "might", "please", "tell",
}

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "so",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "up",
    "about", "into", "over", "after", "before", "between", "out",
    "it", "its", "this", "that", "these", "those", "they", "them",
    "you", "your", "me", "my", "we", "us", "our", "he", "she", "his",
    "her", "i", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "can", "could", "should", "may",
    "might", "shall", "not", "no", "yes", "as", "are", "was", "were",
    "is", "am", "any", "all", "each", "some", "such", "more", "most",
    "other", "than", "also", "only", "just", "per", "within", "during",
    "much", "many", "every", "must", "get", "gets", "want", "wants",
}

_TOKEN_RE = re.compile(r"[a-z0-9']+")

_FOLLOWUP_TEMPLATES = ("What is {t}?", "What are the rules for {t}?",
                       "How does {t} work?")


def _stem(word: str) -> str:
    """Naive English stemmer for cheap query<->chunk term matching.

    Handles the common plural / past / progressive forms only. Good
    enough for a relevance floor that must never *raise* confidence; a
    miss here only lowers relevance slightly.
    """
    w = word.lower().strip("'")
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ied") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    for suffix in ("s", "es", "ed", "ly"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: -len(suffix)]
    return w


def _content_terms(text: str) -> List[str]:
    """Lower-cased, stopped, question-starter-free words in ``text``."""
    out: List[str] = []
    seen: Set[str] = set()
    for tok in _TOKEN_RE.findall((text or "").lower()):
        if tok in _STOPWORDS or tok in _QUESTION_STARTERS or len(tok) < 2:
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _term_present(term: str, text: str) -> bool:
    """True when a stemmed form of ``term`` occurs in ``text``."""
    stem = _stem(term)
    if len(stem) <= 2:
        return f" {term} ".find(f" {stem} ") >= 0 or text.lower().startswith(term)
    tokens = {_stem(t) for t in _TOKEN_RE.findall(text.lower())}
    return stem in tokens


def _relevance(question: str, text: str) -> float:
    """Fraction of query content terms present in ``text`` (0..1)."""
    terms = _content_terms(question)
    if not terms:
        return 0.0
    return sum(1 for t in terms if _term_present(t, text)) / len(terms)


def _merge_abbreviation_fragments(fragments: List[str]) -> List[str]:
    """Join a fragment ending in a single-capital-letter abbreviation with
    whatever the sentence splitter cut off after it ("Jordan A. Rivera.")."""
    merged: List[str] = []
    for fragment in fragments:
        if merged and _ABBREVIATION_BOUNDARY_RE.search(merged[-1].rstrip()):
            merged[-1] = f"{merged[-1]} {fragment}"
        else:
            merged.append(fragment)
    return merged


def _is_question(sentence: str) -> bool:
    s = sentence.strip()
    if not s:
        return False
    if s.endswith("?"):
        return True
    if s[-1] in _TERMINAL_PUNCT:
        return False
    first = s.split(" ", 1)[0].lower().rstrip("?")
    return first in _WH_OPENERS


def _is_heading(sentence: str) -> bool:
    s = sentence.strip()
    if not s:
        return False
    if s[-1] in _TERMINAL_PUNCT:
        return False
    return len(s) <= HEADING_MAX_CHARS


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars - 1]
    space = head.rfind(" ")
    if space > max_chars // 2:
        head = head[:space]
    return head + "…"


def _best_snippet(sentence: str, groups: List[str], max_chars: int,
                  wants_number: bool) -> str:
    """Highest-coverage fixed-width window of a run-on sentence.

    Falls back to a plain prefix truncation when nothing beats it (and
    never returns a term-free window, so an off-topic run-on still gets a
    clean prefix cut rather than a random middle slice).
    """
    if len(sentence) <= max_chars:
        return sentence
    words = sentence.split()
    if not words or not groups:
        return _truncate(sentence, max_chars)
    budget = max_chars - 2  # room for the leading/trailing ellipses
    best_key: Tuple = (False, -1, -1)
    best_snippet = _truncate(sentence, max_chars)
    for start in range(len(words)):
        width = 0
        for end in range(start, len(words)):
            width += len(words[end]) + (1 if width else 0)
            if width > budget:
                break
            window = " ".join(words[start:end + 1])
            has_number = bool(re.search(r"\d", window))
            matched = sum(1 for g in groups if _term_present(g, window))
            key = (has_number if wants_number else False, matched, len(window))
            if key > best_key:
                best_key = key
                best_snippet = window
    if best_key[1] <= 0:
        return _truncate(sentence, max_chars)
    prefix = "…" if not sentence.startswith(best_snippet) else ""
    index = sentence.find(best_snippet)
    suffix = "…" if index + len(best_snippet) < len(sentence) else ""
    full = f"{prefix}{best_snippet}{suffix}"
    return full or _truncate(sentence, max_chars)


def _extract_answer_phrase(
    chunk_text: str,
    query: str,
    max_chars: int = MAX_ANSWER_CHARS,
) -> str:
    """Extract a single verbatim answer sentence from ``chunk_text``.

    Rules (order matters, mirrors HeXta's extractive selection):
      1. Collapse soft line-wraps, strip a leading heading line.
      2. Split into sentences, dropping footers, questions, headings and
         fragments shorter than MIN_SENTENCE_CHARS.
      3. Without query terms, the first qualifying sentence wins.
      4. With query terms, every candidate is scored by query content-term
         coverage plus, when the query names a number, whether the
         sentence carries a figure; the best wins (max() is stable, so
         ties keep source order = deterministic).
      5. Over-length winners are cut to a term-dense window.
      6. If a leading short statement and nothing else qualifies, return
         it ("Yes."). Otherwise return "" (caller routes to no_answer).
    No synthesis — the phrase is always verbatim from the chunk.
    """
    if not chunk_text:
        return ""
    text = _SOFT_WRAP_RE.sub(" ", chunk_text)
    parts = text.split("\n", 1)
    if len(parts) == 2:
        first, rest = parts[0].strip(), parts[1].strip()
        if first and rest and first[-1] not in _TERMINAL_PUNCT and len(first) <= HEADING_MAX_CHARS:
            text = rest

    groups = _content_terms(query)
    wants_number = bool(re.search(r"\d", query or ""))

    scored: List[Tuple[str, bool]] = []
    fallback: List[str] = []
    for sentence in _merge_abbreviation_fragments(_SENTENCE_RE.split(text)):
        s = sentence.strip()
        if not s or _FOOTER_RE.match(s):
            continue
        if _is_question(s) or _is_heading(s):
            continue
        is_long = len(s) > max_chars
        if not is_long and len(s) < MIN_SENTENCE_CHARS:
            fallback.append(s)
            continue
        if not groups:
            return _truncate(s, max_chars) if is_long else s
        scored.append((s, is_long))

    if scored:
        def _score_key(p: Tuple[str, bool]) -> Tuple:
            s, is_long = p
            has_number = bool(re.search(r"\d", s)) if wants_number else False
            return (has_number, sum(1 for g in groups if _term_present(g, s)))
        best, best_is_long = max(scored, key=_score_key)
        return _best_snippet(best, groups, max_chars, wants_number) if best_is_long else best

    for s in fallback:
        if not _is_heading(s) and not _is_question(s):
            return s
    return ""


# --- Confidence and routing --------------------------------------------

_RRF_K = 60  # must match app/services/search.py's k


def _base_confidence(score: float) -> float:
    """Normalize the top RRF score onto a 0-100 scale.

    A chunk ranked #1 in both the keyword and vector lists scores
    1/(K+1); every viable chunk appears in at least one list, so a
    single-list leader caps at weighted*100.
    """
    if score <= 0:
        return 0.0
    return min(score * (_RRF_K + 1) * 100.0, 100.0)


def _recalibrate_confidence(confidence: float, relevance: float) -> float:
    """Scale confidence down for weak query<->evidence relevance (never up)."""
    if relevance >= 0.70:
        return confidence
    if relevance >= 0.35:
        factor = 0.55 + (relevance - 0.35) / 0.35 * 0.45
        return confidence * factor
    factor = 0.35 + relevance / 0.35 * 0.20
    return confidence * factor


def _route_by_confidence(confidence: float) -> str:
    if confidence >= ANSWER_CONFIDENCE:
        return "answer"
    if confidence >= PARTIAL_CONFIDENCE:
        return "partial"
    return "no_answer"


# --- Tenancy-guarded spellcheck confirmation ----------------------------

_TOKEN_FOR_CORRECTION_MIN = 4
_RATIO_THRESHOLD = 0.80
_VOCAB_LIMIT = 20000


async def _tenant_vocabulary(db: AsyncSession, tenant_id: uuid.UUID) -> List[str]:
    """Distinct alphabetic tokens (len >= 4) across the tenant's chunks,
    most frequent first. This vocabulary is the only authority the
    spellchecker corrects *against*, so a corpus term is never rewritten
    into an unrelated word (HeXta false-positive class: "respa" -> "repay")."""
    sql = text("""
        SELECT word
        FROM (
            SELECT lower(unnest(regexp_split_to_array(content, '[^a-zA-Z0-9'']+'))) AS word
            FROM document_chunks
            WHERE tenant_id = :tenant_id
        ) t
        WHERE word ~ '^[a-z][a-z0-9'']+$' AND length(word) >= :min_len
        GROUP BY word
        ORDER BY count(*) DESC
        LIMIT :limit
    """)
    result = await db.execute(
        sql,
        {"tenant_id": tenant_id, "min_len": _TOKEN_FOR_CORRECTION_MIN, "limit": _VOCAB_LIMIT},
    )
    return [row["word"] for row in result.mappings()]


def _correct_query(query: str, vocabulary: List[str]) -> Tuple[str, List[SpellCorrection]]:
    """Corpus-gated single-token typo correction.

    A token is corrected only when ALL of these hold (each was a HeXta
    false positive):
      * purely alphabetic and long enough (numbers/amounts never touched)
      * NOT already a known word in the tenant's own corpus (a real term
        is never rewritten into a dictionary twin)
      * it has a strong fuzzy match (> 0.80) against a corpus token
    Returns the corrected query plus the list of applied corrections so
    the response can confirm what changed (spellcheck confirmation).
    """
    vocab_set = {w for w in vocabulary}
    corrections: List[SpellCorrection] = []
    tokens = _TOKEN_RE.findall(query.lower())
    if not tokens:
        return query, corrections
    corrected_tokens: List[str] = []
    for tok in tokens:
        if (not re.fullmatch(r"[a-z]+", tok) or len(tok) < _TOKEN_FOR_CORRECTION_MIN
                or tok in vocab_set):
            corrected_tokens.append(tok)
            continue
        close = difflib.get_close_matches(tok, vocabulary, n=3, cutoff=0.75)
        best = None
        best_ratio = 0.0
        for w in close:
            ratio = difflib.SequenceMatcher(None, tok, w).ratio()
            if ratio > best_ratio:
                best, best_ratio = w, ratio
        if best and best_ratio >= _RATIO_THRESHOLD and len(corrections) < 3:
            corrections.append(SpellCorrection(original_term=tok, corrected_term=best))
            corrected_tokens.append(best)
        else:
            corrected_tokens.append(tok)
    return " ".join(corrected_tokens), corrections


# --- Follow-up suggestions ----------------------------------------------

_FOLLOWUP_MAX = 3


def _suggest_followups(question: str, results) -> List[str]:
    """Up to three follow-up questions built from the tenant's own
    retrieved content.

    The template is a fixed, static question shape; the *subject* is a
    content term that appears in the tenant's retrieved chunks and not in
    the user's question. Everything above and beyond that static suffix
    comes from the tenant's content — nothing generic is invented.
    """
    picked: List[str] = []
    seen: Set[str] = set()
    if not results:
        return picked
    counts: dict = {}
    for r in results:
        for t in _content_terms(r.content):
            counts[t] = counts.get(t, 0) + 1
    question_terms = set(_content_terms(question))
    for t, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if t in question_terms or t in seen:
            continue
        if len(t) < 4:
            continue
        seen.add(t)
        template = _FOLLOWUP_TEMPLATES[len(picked) % len(_FOLLOWUP_TEMPLATES)]
        picked.append(template.format(t=t))
        if len(picked) >= _FOLLOWUP_MAX:
            break
    return picked


# --- Public entry point --------------------------------------------------

async def answer_question(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    question: str,
    top_k: int = 10,
    hybrid_weight: float = 0.5,
) -> AnswerResponse:
    """Answer ``question`` strictly from the tenant's own documents.

    Tenant is mandatory (defence in depth, VQ-205): without one the
    engine refuses to run before any database call.
    """
    if not tenant_id:
        raise SearchTenantRequiredError("Search requires tenant context")

    question = question.strip()

    vocabulary = await _tenant_vocabulary(db, tenant_id)
    search_query, corrections = _correct_query(question, vocabulary)
    applied = len(corrections) > 0

    response = await hybrid_search(
        db=db,
        tenant_id=tenant_id,
        query=search_query,
        top_k=top_k,
        hybrid_weight=hybrid_weight,
    )
    results = response.results

    spellcheck = SpellcheckInfo(
        applied=applied,
        original=question,
        corrected=search_query,
        corrections=corrections,
    )

    if not results:
        return AnswerResponse(
            question=question,
            routing="no_answer",
            confidence=0.0,
            spellcheck=spellcheck,
        )

    excerpts = [r.content for r in results if r.content]
    top_excerpt = excerpts[0] if excerpts else ""
    answer_phrase = _extract_answer_phrase(top_excerpt, question)
    if not answer_phrase:
        for r in results[1:]:
            if r.content:
                answer_phrase = _extract_answer_phrase(r.content, question)
                if answer_phrase:
                    break

    phrase_used = answer_phrase or top_excerpt
    relevance = max(
        _relevance(question, phrase_used),
        _relevance(question, top_excerpt),
    )
    if relevance < NO_ANSWER_RELEVANCE_FLOOR:
        return AnswerResponse(
            question=question,
            routing="no_answer",
            confidence=round(_base_confidence(results[0].score), 1),
            spellcheck=spellcheck,
        )

    confidence = _recalibrate_confidence(_base_confidence(results[0].score), relevance)
    confidence = round(confidence, 1)
    routing = _route_by_confidence(confidence)

    if routing == "no_answer":
        return AnswerResponse(
            question=question,
            routing="no_answer",
            confidence=confidence,
            spellcheck=spellcheck,
        )

    sources = [
        AnswerSource(
            document_id=r.document_id,
            chunk_index=r.chunk_index,
            original_filename=r.original_filename,
            score=r.score,
            excerpt=r.content,
        )
        for r in results[:MAX_SOURCES]
    ]
    followups = _suggest_followups(question, results)

    source_document_id = None
    source_chunk_index = None
    for r in results:
        if _extract_answer_phrase(r.content, question):
            source_document_id = r.document_id
            source_chunk_index = r.chunk_index
            break

    return AnswerResponse(
        question=question,
        answer_phrase=answer_phrase,
        routing=routing,
        confidence=confidence,
        sources=sources,
        followups=followups,
        spellcheck=spellcheck,
        source_document_id=source_document_id,
        source_chunk_index=source_chunk_index,
    )