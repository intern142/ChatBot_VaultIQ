import threading
from typing import List, Optional

from fastembed import TextEmbedding
from app.config import get_settings


settings = get_settings()

_MODEL: Optional[TextEmbedding] = None
_MODEL_LOCK = threading.Lock()
_EMBEDDING_DIM = 384


def get_embedding_model() -> TextEmbedding:
    """Get or create the FastEmbed model (thread-safe singleton)."""
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                _MODEL = TextEmbedding(
                    model_name="BAAI/bge-small-en-v1.5",
                    cache_dir=getattr(settings, 'FASTEMBED_CACHE_DIR', None),
                    threads=getattr(settings, 'FASTEMBED_THREADS', 4),
                )
    return _MODEL


def embed_texts(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.
    
    Args:
        texts: List of text strings to embed
        batch_size: Number of texts to process at once
        
    Returns:
        List of embedding vectors (each 384-dimensional)
    """
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = list(model.embed(batch))
        embeddings.extend([emb.tolist() for emb in batch_embeddings])

    return embeddings


def embed_text(text: str) -> List[float]:
    """Generate embedding for a single text."""
    return embed_texts([text])[0]


def get_embedding_dimension() -> int:
    """Return the embedding dimension (384 for bge-small-en-v1.5)."""
    return _EMBEDDING_DIM


def validate_embedding(embedding: List[float]) -> bool:
    """Validate embedding dimension and values."""
    if len(embedding) != _EMBEDDING_DIM:
        return False
    return all(isinstance(x, (int, float)) for x in embedding)