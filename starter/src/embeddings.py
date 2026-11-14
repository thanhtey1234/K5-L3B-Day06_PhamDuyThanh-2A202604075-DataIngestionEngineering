
from sentence_transformers import SentenceTransformer
import numpy as np


class MyEmbedder:
    """Vietnamese embedding model adapter."""

    def __init__(
        self,
        model_name: str = "AITeamVN/Vietnamese_Embedding"
    ) -> None:

        self.model_name = model_name

        # Bắt đầu bằng CPU để tránh thiếu VRAM.
        self.device = "cpu"

        # Load model
        self.model = SentenceTransformer(
            model_name,
            device=self.device
        )

        # Giới hạn độ dài sequence
        self.model.max_seq_length = 2048

        # Lấy số chiều embedding từ model
        self.dimensions = (
            self.model.get_sentence_embedding_dimension()
        )

        print("Model:", self.model_name)
        print("Dimensions:", self.dimensions)

    def embed_documents(
        self,
        texts: list[str]
    ) -> list[list[float]]:

        if not texts:
            return []

        vectors = self.model.encode(
            texts,
            batch_size=2,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        return vectors.astype(np.float32).tolist()

    def embed_query(
        self,
        question: str
    ) -> list[float]:

        vector = self.model.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True
        )[0]

        return vector.astype(np.float32).tolist()
