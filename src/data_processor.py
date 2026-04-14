import os
import re
from typing import List
from langchain_core.documents import Document

def split_paragraphs_with_overlap(text: str, max_chars: int = 1600, overlap_chars: int = 320) -> List[str]:
    """
    Split text by paragraphs (\n\n) if it exceeds max_chars.
    Appends an overlap of ~size overlap_chars from the end of the previous chunk to the start of the next chunk.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        if not p.strip():
            continue
            
        proposed_len = len(current_chunk) + len(p) + 2 # accounts for \n\n
        if proposed_len > max_chars and len(current_chunk) > 0:
            chunks.append(current_chunk.strip())
            
            # Tính toán overlap từ current_chunk
            overlap_text = current_chunk[-overlap_chars:] if len(current_chunk) > overlap_chars else current_chunk
            # Để tránh cắt ngang từ, tiến tới dấu cách tiếp theo
            space_idx = overlap_text.find(' ')
            if space_idx != -1 and space_idx < len(overlap_text) - 1:
                overlap_text = overlap_text[space_idx+1:]
                
            current_chunk = overlap_text + "\n\n" + p
        else:
            if current_chunk:
                current_chunk += "\n\n" + p
            else:
                current_chunk = p
                
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return chunks

def process_file(filepath: str, domain: str) -> List[Document]:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    match = re.search(r"===\s*(.*?)\s*===", content)
    global_metadata_text = ""
    sections_text = content
    if match:
        global_metadata_text = content[:match.start()].strip()
        sections_text = content[match.start():]
        
    file_meta = {"domain": domain, "source_file": os.path.basename(filepath)}
    for line in global_metadata_text.split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            file_meta[key.strip()] = val.strip()
            
    section_pattern = r"(===\s*.*?\s*===)"
    parts = re.split(section_pattern, sections_text)
    
    docs = []
    for i in range(1, len(parts), 2):
        sec_header = parts[i]
        sec_content = parts[i+1].strip() if i+1 < len(parts) else ""
        if not sec_content:
            continue
            
        sec_name = sec_header.replace("===", "").strip()
        
        if len(sec_content) > 1600:
            sub_chunks = split_paragraphs_with_overlap(sec_content, max_chars=1600, overlap_chars=320)
            for j, sc in enumerate(sub_chunks):
                meta = file_meta.copy()
                meta["section_name"] = sec_name
                meta["chunk_part"] = j + 1
                docs.append(Document(page_content=sc, metadata=meta))
        else:
            meta = file_meta.copy()
            meta["section_name"] = sec_name
            docs.append(Document(page_content=sec_content, metadata=meta))
            
    if not match and content.strip():
        if len(content) > 1600:
            sub_chunks = split_paragraphs_with_overlap(content, max_chars=1600, overlap_chars=320)
            for j, sc in enumerate(sub_chunks):
                meta = file_meta.copy()
                meta["chunk_part"] = j + 1
                docs.append(Document(page_content=sc, metadata=meta))
        else:
             docs.append(Document(page_content=content.strip(), metadata=file_meta))
             
    return docs

def load_and_process_all_docs(docs_dir: str = "data/docs") -> List[Document]:
    domain_mapping = {
        "access_control_sop.txt": "IT",
        "it_helpdesk_faq.txt": "IT",
        "sla_p1_2026.txt": "IT",
        "hr_leave_policy.txt": "HR",
        "policy_refund_v4.txt": "CS"
    }
    
    all_docs = []
    for filename, domain in domain_mapping.items():
        filepath = os.path.join(docs_dir, filename)
        if os.path.exists(filepath):
            docs = process_file(filepath, domain)
            all_docs.extend(docs)
            print(f"Processed {filename} -> {len(docs)} chunks")
        else:
            print(f"Warning: {filepath} not found")
            
    return all_docs

if __name__ == "__main__":
    docs = load_and_process_all_docs()
    print(f"Total chunks created: {len(docs)}")
    if docs:
        print("\nSample Chunk:")
        print("Metadata:", docs[0].metadata)
        print("Content limit(100):", docs[0].page_content[:100], "...")
