from src.embeddings import MyEmbedder
import numpy as np

embedder = MyEmbedder()

vector = embedder.embed_query(
    "Trách nhiệm bảo vệ an ninh mạng là gì?"
)

print("Vector dimension:", len(vector))
print("Vector norm:", np.linalg.norm(vector))