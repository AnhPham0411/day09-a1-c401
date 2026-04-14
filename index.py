
import chromadb

client = chromadb.PersistentClient(path='chroma_db')

# Lấy collection cũ
old = client.get_collection('rag_lab')
data = old.get(include=['documents', 'embeddings', 'metadatas'])

# Tạo collection mới đúng tên
new = client.get_or_create_collection('day09_docs', metadata={'hnsw:space': 'cosine'})

# Copy toàn bộ data
new.add(
    ids=data['ids'],
    documents=data['documents'],
    embeddings=data['embeddings'],
    metadatas=data['metadatas']
)

print(f"Done! Copied {len(data['ids'])} chunks -> day09_docs")
print('Collections:', [c.name for c in client.list_collections()])
