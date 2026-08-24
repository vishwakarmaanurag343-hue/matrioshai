import hashlib
from typing import List
from app.memory.base_embedding import EmbeddingProvider

class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Lightweight deterministic local embedding provider for Phase 1.
    Prepares vector interfaces for ONNX runtime or sqlite-vec without external heavy dependencies.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed(self, text: str) -> List[float]:
        # Generate a deterministic float vector based on SHA256 of text
        text_bytes = text.strip().lower().encode("utf-8")
        hash_bytes = hashlib.sha256(text_bytes).digest()
        vector = []
        for i in range(self.dimension):
            byte_val = hash_bytes[i % len(hash_bytes)]
            val = (byte_val / 255.0) * 2.0 - 1.0  # Normalized to [-1.0, 1.0]
            vector.append(round(val, 4))
        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]
