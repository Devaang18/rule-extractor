import re
from .config import MAX_TOKENS_PER_CHUNK, OVERLAP_TOKENS
import tiktoken

tokenizer = tiktoken.get_encoding("cl100k_base")

def chunk_text(text, return_sections=False):
    """
    Split text into chunks based on numbered rules or headings.
    If no numbered rules found, fallback to fixed token chunking.
    If return_sections is True, also return a list of section headings (one per chunk).
    """
    pattern = re.compile(r"(^|\n)(\d+(\.\d+)*[a-z]?)\s+", re.MULTILINE)
    splits = list(pattern.finditer(text))
    
    chunks = []
    sections = []
    if len(splits) < 2:
        # fallback fixed size chunking
        tokens = tokenizer.encode(text)
        start = 0
        while start < len(tokens):
            end = min(start + MAX_TOKENS_PER_CHUNK, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text_str = tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text_str)
            sections.append("General")
            start = end - OVERLAP_TOKENS
    else:
        # chunk by rule headings
        for i in range(len(splits)):
            start_pos = splits[i].start()
            end_pos = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            chunk_text_str = text[start_pos:end_pos].strip()
            # Optionally check token length and merge if too small
            chunk_tokens = tokenizer.encode(chunk_text_str)
            if len(chunk_tokens) > MAX_TOKENS_PER_CHUNK:
                # fallback to fixed chunking inside this chunk if needed
                sub_chunks = chunk_text_fixed(chunk_text_str)
                chunks.extend(sub_chunks)
                # Use the heading for all subchunks
                heading = chunk_text_str.split('\n', 1)[0].strip()
                sections.extend([heading] * len(sub_chunks))
            else:
                chunks.append(chunk_text_str)
                heading = chunk_text_str.split('\n', 1)[0].strip()
                sections.append(heading)
    if return_sections:
        return chunks, sections
    else:
        return chunks

def chunk_text_fixed(text):
    tokens = tokenizer.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + MAX_TOKENS_PER_CHUNK, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_str = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text_str)
        start = end - OVERLAP_TOKENS
    return chunks