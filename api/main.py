from transformers import AutoTokenizer, AutoModelForCausalLM
from sentence_transformers import SentenceTransformer
import torch
import faiss
import numpy as np

MODEL_ID = "ytu-ce-cosmos/Turkish-Gemma-9b-v0.1"

# Modeller
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)
embedding_model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")

# -----------------------------
# Overlapping chunk fonksiyonu
# -----------------------------
def make_chunks(text, window=200, overlap=50):
    """Verilen metni kelime bazlı window + overlap ile böler."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + window
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += window - overlap  # overlap kadar geri kay
    return chunks

# -----------------------------
# Veri yükleme + chunking
# -----------------------------
with open("content/DYSKilavuz.txt", "r", encoding="utf-8") as f:
    full_text = f.read()

# Örn: 200 kelimelik parçalar, 50 kelime overlap
texts = make_chunks(full_text, window=200, overlap=50)

# -----------------------------
# FAISS index
# -----------------------------
embeddings = embedding_model.encode(texts, convert_to_numpy=True).astype("float32")
dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(embeddings)

# -----------------------------
# Arama
# -----------------------------
def search(query: str, top_k: int = 10):
    if index.ntotal == 0:
        return []
    q_emb = embedding_model.encode([query], convert_to_numpy=True).astype("float32")
    k = min(top_k, index.ntotal)
    D, I = index.search(q_emb, k)
    results = []
    for idx in I[0]:
        if 0 <= idx < len(texts):
            results.append({"content": texts[idx]})
    print(results)
    return results

# -----------------------------
# LLM cevap
# -----------------------------
def generate_answer(rag_context, user_query: str):
    message = f"""
Sen bir yapay zekâ finans asistanısın.
Aşağıdaki içerikler sana bağlam olarak verilmiştir: {rag_context}

Soru: {user_query}
Cevap:
"""
    inputs = tokenizer(message, return_tensors="pt").to("cuda")

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            temperature=0.7,
        )

    decoded = tokenizer.decode(output[0], skip_special_tokens=True)
    print(decoded[len(message):].strip())
    return decoded[len(message):].strip()
