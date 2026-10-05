import re
from dataclasses import dataclass
from typing import Iterator

from app.config import get_settings


settings = get_settings()

DEFAULT_CHUNK_SIZE = 500  # tokens (roughly 2000 chars)
DEFAULT_CHUNK_OVERLAP = 50  # tokens
MIN_CHUNK_SIZE = 50  # tokens


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str
    token_count: int
    char_start: int
    char_end: int


def count_tokens(text: str) -> int:
    """Rough token count: ~4 chars per token for English."""
    return max(1, len(text) // 4)


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s]


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Split text into overlapping chunks at sentence boundaries.
    
    Args:
        text: Full document text
        chunk_size: Target token count per chunk
        chunk_overlap: Token overlap between consecutive chunks
        
    Returns:
        List of Chunk objects with content and metadata
    """
    if not text or not text.strip():
        return []

    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current_chunk_sentences: list[str] = []
    current_token_count = 0
    char_offset = 0
    chunk_index = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        
        # If single sentence exceeds chunk size, split it
        if sentence_tokens > chunk_size:
            # Flush current chunk first
            if current_chunk_sentences:
                chunk_content = " ".join(current_chunk_sentences)
                chunks.append(Chunk(
                    index=chunk_index,
                    content=chunk_content,
                    token_count=current_token_count,
                    char_start=char_offset - len(chunk_content),
                    char_end=char_offset,
                ))
                chunk_index += 1
                current_chunk_sentences = []
                current_token_count = 0

            # Split long sentence into sub-chunks
            sub_chunks = _split_long_sentence(sentence, chunk_size, chunk_overlap)
            for sub_chunk in sub_chunks:
                chunks.append(Chunk(
                    index=chunk_index,
                    content=sub_chunk,
                    token_count=count_tokens(sub_chunk),
                    char_start=char_offset,
                    char_end=char_offset + len(sub_chunk),
                ))
                chunk_index += 1
                char_offset += len(sentence) + 1  # +1 for space
            continue

        # Check if adding this sentence exceeds chunk size
        if current_token_count + sentence_tokens > chunk_size and current_chunk_sentences:
            # Finalize current chunk
            chunk_content = " ".join(current_chunk_sentences)
            chunks.append(Chunk(
                index=chunk_index,
                content=chunk_content,
                token_count=current_token_count,
                char_start=char_offset - len(chunk_content),
                char_end=char_offset,
            ))
            chunk_index += 1

            # Start new chunk with overlap
            overlap_sentences = _get_overlap_sentences(
                current_chunk_sentences, chunk_overlap
            )
            current_chunk_sentences = overlap_sentences + [sentence]
            current_token_count = sum(count_tokens(s) for s in current_chunk_sentences)
        else:
            current_chunk_sentences.append(sentence)
            current_token_count += sentence_tokens
        
        char_offset += len(sentence) + 1

    # Don't forget the last chunk
    if current_chunk_sentences:
        chunk_content = " ".join(current_chunk_sentences)
        chunks.append(Chunk(
            index=chunk_index,
            content=chunk_content,
            token_count=current_token_count,
            char_start=char_offset - len(chunk_content),
            char_end=char_offset,
        ))

    return chunks


def _split_long_sentence(sentence: str, chunk_size: int, overlap: int) -> list[str]:
    """Split a sentence that's longer than chunk_size into smaller pieces."""
    words = sentence.split()
    if not words:
        return []

    chunks = []
    current_words = []
    current_tokens = 0

    for word in words:
        word_tokens = count_tokens(word)
        if current_tokens + word_tokens > chunk_size and current_words:
            chunks.append(" ".join(current_words))
            # Keep overlap words
            overlap_words = current_words[-overlap:] if len(current_words) > overlap else current_words
            current_words = overlap_words + [word]
            current_tokens = sum(count_tokens(w) for w in current_words)
        else:
            current_words.append(word)
            current_tokens += word_tokens

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def _get_overlap_sentences(sentences: list[str], overlap_tokens: int) -> list[str]:
    """Get sentences from the end that fit within overlap token budget."""
    if not sentences:
        return []

    overlap = []
    token_count = 0
    for sentence in reversed(sentences):
        sentence_tokens = count_tokens(sentence)
        if token_count + sentence_tokens > overlap_tokens and overlap:
            break
        overlap.insert(0, sentence)
        token_count += sentence_tokens
    return overlap


def chunk_document(text: str) -> list[Chunk]:
    """Convenience function using settings."""
    return chunk_text(
        text,
        chunk_size=getattr(settings, 'CHUNK_SIZE', DEFAULT_CHUNK_SIZE),
        chunk_overlap=getattr(settings, 'CHUNK_OVERLAP', DEFAULT_CHUNK_OVERLAP),
    )