import json
import os
from typing import Dict, List, Optional
from openai import OpenAI
from qdrant_client import QdrantClient, models
from qdrant_client.http import models as rest
from qdrant_client.http.models import Distance, VectorParams
import tiktoken
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
print(f"Looking for .env file at: {env_path}")
print(f"Does .env file exist? {os.path.exists(env_path)}")
load_dotenv(env_path)

# Constants
COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'AparaviDocs')
OPENAI_MODEL = "text-embedding-3-small"
MAX_TOKENS = 8191  # OpenAI's embedding model token limit
BATCH_SIZE = 100
VECTOR_SIZE = 1536  # text-embedding-3-small dimension size

# Initialize OpenAI client
openaiClient = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def init_qdrant_client() -> QdrantClient:
    """Initialize Qdrant client and create collection if it doesn't exist"""
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    
    if not qdrant_url or not qdrant_api_key:
        raise ValueError("QDRANT_URL or QDRANT_API_KEY not found in environment variables")
    
    client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
    )
    
    # Delete existing collection if it exists
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection: {COLLECTION_NAME}")
    except Exception as e:
        print(f"Collection {COLLECTION_NAME} does not exist yet")
    
    # Create collection with correct vector size
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    print(f"Created collection {COLLECTION_NAME} with vector size {VECTOR_SIZE}")
    
    return client

def get_token_count(text: str) -> int:
    """Get the number of tokens in a text string"""
    encoding = tiktoken.encoding_for_model(OPENAI_MODEL)
    return len(encoding.encode(text))

def get_word_count(text: str) -> int:
    """Get the number of words in a text string"""
    return len(text.split())

def chunk_text(text: str, max_tokens: int = MAX_TOKENS) -> List[str]:
    """Split text into chunks that fit within token limit"""
    chunks = []
    current_chunk = []
    current_length = 0
    
    # Split into sentences (simple approach)
    sentences = text.split(". ")
    
    for sentence in sentences:
        sentence_tokens = get_token_count(sentence)
        
        if current_length + sentence_tokens > max_tokens:
            # Save current chunk and start new one
            chunks.append(". ".join(current_chunk) + ".")
            current_chunk = [sentence]
            current_length = sentence_tokens
        else:
            current_chunk.append(sentence)
            current_length += sentence_tokens
    
    # Add the last chunk if it exists
    if current_chunk:
        chunks.append(". ".join(current_chunk) + ".")
    
    return chunks

def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Get embeddings for a list of texts using OpenAI's API"""
    try:
        response = openaiClient.embeddings.create(
            model=OPENAI_MODEL,
            input=texts
        )
        return [data.embedding for data in response.data]
    except Exception as e:
        print(f"Error getting embeddings: {e}")
        return []

def process_pdf_content(pdf_data: Dict) -> List[Dict]:
    """Process a single PDF's content and prepare it for vectorization"""
    chunks = []
    
    # Extract metadata
    filename = os.path.basename(pdf_data["filepath"])
    total_sections = len(pdf_data["content"]["sections"])
    total_words = get_word_count(pdf_data["content"]["full_text"])
    
    # Extract basic metadata
    base_metadata = {
        "source_url": pdf_data["source_url"],
        "pdf_url": pdf_data["pdf_url"],
        "filename": filename,
        "total_sections": total_sections,
        "total_words": total_words,
        "doc_metadata": pdf_data["metadata"]["doc_metadata"],
        "processing_time": pdf_data["metadata"]["processing_time"]
    }
    
    # Process full text into chunks
    text_chunks = chunk_text(pdf_data["content"]["full_text"])
    
    # Create chunk entries with metadata
    for i, chunk in enumerate(text_chunks):
        chunk_words = get_word_count(chunk)
        chunks.append({
            "text": chunk,
            "metadata": {
                **base_metadata,
                "chunk_type": "full_text",
                "chunk_index": i,
                "total_chunks": len(text_chunks),
                "chunk_words": chunk_words,
                "chunk_tokens": get_token_count(chunk)
            }
        })
    
    # Also process each section separately if available
    for section_idx, section in enumerate(pdf_data["content"]["sections"]):
        if section["header"] and section["content"]:
            section_text = f"{section['header']}: {' '.join(section['content'])}"
            section_chunks = chunk_text(section_text)
            
            for i, chunk in enumerate(section_chunks):
                chunk_words = get_word_count(chunk)
                chunks.append({
                    "text": chunk,
                    "metadata": {
                        **base_metadata,
                        "chunk_type": "section",
                        "section_header": section["header"],
                        "section_index": section_idx,
                        "chunk_index": i,
                        "total_chunks": len(section_chunks),
                        "chunk_words": chunk_words,
                        "chunk_tokens": get_token_count(chunk)
                    }
                })
    
    return chunks

def main():
    # Initialize Qdrant client
    client = init_qdrant_client()
    
    # Load processed PDFs
    current_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_file = os.path.join(current_dir, "processed_pdfs.json")
    
    with open(pdf_file, 'r', encoding='utf-8') as f:
        pdf_data = json.load(f)
    
    # Process all PDFs
    all_chunks = []
    for filepath, pdf_info in tqdm(pdf_data["processed_pdfs"].items(), desc="Processing PDFs"):
        chunks = process_pdf_content(pdf_info)
        all_chunks.extend(chunks)
    
    print(f"Total chunks to process: {len(all_chunks)}")
    
    # Process chunks in batches
    for i in tqdm(range(0, len(all_chunks), BATCH_SIZE), desc="Vectorizing chunks"):
        batch = all_chunks[i:i + BATCH_SIZE]
        
        # Get embeddings for the batch
        texts = [chunk["text"] for chunk in batch]
        embeddings = get_embeddings(texts)
        
        if embeddings:
            # Prepare points for Qdrant
            points = [
                models.PointStruct(
                    id=i + idx,
                    vector=embedding,
                    payload={
                        "text": chunk["text"],
                        **chunk["metadata"]
                    }
                )
                for idx, (chunk, embedding) in enumerate(zip(batch, embeddings))
            ]
            
            # Upload to Qdrant
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )

if __name__ == "__main__":
    main()