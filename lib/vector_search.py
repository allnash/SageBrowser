# lib/vector_search.py
"""
Vector search module for saved pages using sentence-transformers.
"""

import os
import re
import glob
import json
import hashlib
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime


class PageVectorSearch:
    """Utility class for vector search over saved markdown pages"""

    def __init__(self, saved_pages_dir="saved_pages",
                 model_name="all-MiniLM-L6-v2",
                 index_file="page_index.json"):
        """Initialize the vector search system"""
        self.saved_pages_dir = saved_pages_dir
        self.model_name = model_name
        self.index_file = os.path.join(saved_pages_dir, index_file)

        # Create directory if it doesn't exist
        if not os.path.exists(saved_pages_dir):
            os.makedirs(saved_pages_dir)

        # Load model lazily when needed
        self._model = None

        # Load existing index if available
        self.index = self._load_index()

    @property
    def model(self):
        """Lazy-load the embedding model when needed"""
        if self._model is None:
            try:
                # Import here to avoid requiring this dependency when not needed
                from sentence_transformers import SentenceTransformer
                print(f"Loading model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                print("Model loaded successfully")
            except ImportError as e:
                print(f"Error importing sentence_transformers: {e}")
                raise ImportError(
                    "The sentence-transformers package is required for vector search. "
                    "Please install it with: pip install sentence-transformers"
                )
            except Exception as e:
                print(f"Error loading model: {e}")
                raise RuntimeError(f"Failed to load model: {e}")
        return self._model

    def _load_index(self) -> Dict[str, Any]:
        """Load existing index or create a new one"""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading index: {e}")

        # Return empty index structure
        return {
            "files": {},
            "last_updated": datetime.now().isoformat(),
            "model": self.model_name
        }

    def _save_index(self):
        """Save the current index to disk"""
        self.index["last_updated"] = datetime.now().isoformat()

        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2)
                print(f"Index saved to {self.index_file}")
        except Exception as e:
            print(f"Error saving index: {e}")

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from markdown front matter"""
        metadata = {}

        try:
            # Extract front matter
            match = re.match(r'---\n(.*?)\n---\n', content, re.DOTALL)
            if match:
                front_matter = match.group(1)
                for line in front_matter.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip().strip('"\'')
        except Exception as e:
            print(f"Error extracting metadata: {e}")

        return metadata

    def _extract_chunks(self, content: str, chunk_size=1000,
                        overlap=200) -> List[str]:
        """Extract text chunks from markdown content"""
        chunks = []

        try:
            # Remove front matter
            content = re.sub(r'---\n.*?\n---\n', '', content, flags=re.DOTALL)

            # Split content into paragraphs
            paragraphs = re.split(r'\n\n+', content)

            current_chunk = ""

            for para in paragraphs:
                # Skip empty paragraphs
                if not para.strip():
                    continue

                if len(current_chunk) + len(para) < chunk_size:
                    # Add paragraph to current chunk
                    current_chunk += para + "\n\n"
                else:
                    # Save current chunk if not empty
                    if current_chunk:
                        chunks.append(current_chunk.strip())

                    # Start new chunk with overlap from previous chunk
                    if len(current_chunk) > overlap:
                        # Get last few characters for overlap
                        overlap_text = current_chunk[-overlap:]
                        # Find paragraph break if possible
                        paragraph_break = overlap_text.find("\n\n")
                        if paragraph_break != -1:
                            current_chunk = overlap_text[paragraph_break + 2:]
                        else:
                            current_chunk = ""
                    else:
                        current_chunk = ""

                    # Add current paragraph
                    current_chunk += para + "\n\n"

            # Add final chunk if not empty
            if current_chunk:
                chunks.append(current_chunk.strip())
        except Exception as e:
            print(f"Error extracting chunks: {e}")
            # Return at least one chunk with whatever content we have
            if not chunks and content:
                chunks = [content[:1000]]

        return chunks

    def index_file(self, file_path: str) -> Dict[str, Any]:
        """Index a single markdown file"""
        print(f"Indexing file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract metadata
            metadata = self._extract_metadata(content)

            # Extract content chunks
            chunks = self._extract_chunks(content)

            if not chunks:
                print(f"No chunks extracted from {file_path}")
                return {"error": "No content chunks extracted"}

            # Generate embeddings for chunks
            try:
                print(f"Generating embeddings for {len(chunks)} chunks")
                embeddings = self.model.encode(chunks)
                print(f"Embeddings generated successfully")
            except Exception as e:
                print(f"Error generating embeddings: {e}")
                return {"error": f"Failed to generate embeddings: {e}"}

            # Create page entry
            page_entry = {
                "metadata": metadata,
                "chunks": chunks,
                "embeddings": embeddings.tolist(),
                "indexed_at": datetime.now().isoformat(),
                "file_path": file_path
            }

            # Update index
            self.index["files"][os.path.basename(file_path)] = page_entry

            # Save updated index
            self._save_index()

            return page_entry
        except Exception as e:
            print(f"Error indexing file {file_path}: {e}")
            return {"error": str(e)}

    def index_all(self) -> int:
        """Index all markdown files in the directory"""
        try:
            md_files = glob.glob(os.path.join(self.saved_pages_dir, "*.md"))
            print(f"Found {len(md_files)} markdown files in {self.saved_pages_dir}")

            indexed_count = 0
            for file_path in md_files:
                filename = os.path.basename(file_path)

                # Check if file already indexed
                if filename in self.index["files"]:
                    # Check if file was modified
                    file_mtime = os.path.getmtime(file_path)
                    indexed_time = datetime.fromisoformat(
                        self.index["files"][filename]["indexed_at"]
                    ).timestamp()

                    if file_mtime < indexed_time:
                        # Skip if file wasn't modified
                        print(f"Skipping {filename} - already indexed")
                        continue

                # Index the file
                result = self.index_file(file_path)
                if "error" not in result:
                    indexed_count += 1

            return indexed_count
        except Exception as e:
            print(f"Error indexing files: {e}")
            return 0

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for pages matching the query"""
        results = []

        try:
            # Check if we have any files in index
            if not self.index["files"]:
                print("No files in index to search")
                return []

            # Encode query
            print(f"Encoding query: {query}")
            query_embedding = self.model.encode(query)
            print("Query encoded successfully")

            # Search through all indexed files
            for filename, page_data in self.index["files"].items():
                # For each chunk in the page
                for i, chunk_embedding in enumerate(page_data["embeddings"]):
                    # Skip if we somehow have mismatched lengths
                    if i >= len(page_data["chunks"]):
                        continue

                    # Convert to numpy array
                    chunk_np = np.array(chunk_embedding)

                    # Calculate similarity using a try-except to catch any errors
                    try:
                        similarity = np.dot(query_embedding, chunk_np) / (
                                np.linalg.norm(query_embedding) * np.linalg.norm(chunk_np)
                        )
                    except Exception as e:
                        print(f"Error calculating similarity: {e}")
                        continue

                    results.append({
                        "filename": filename,
                        "metadata": page_data["metadata"],
                        "chunk": page_data["chunks"][i],
                        "chunk_index": i,
                        "similarity": float(similarity),
                        "file_path": page_data["file_path"]
                    })

            # Sort by similarity (highest first)
            results.sort(key=lambda x: x["similarity"], reverse=True)

            # Return top k results
            return results[:top_k]
        except Exception as e:
            import traceback
            print(f"Error in search method: {e}")
            print(traceback.format_exc())
            return []


def search_saved_pages(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Convenience function to search saved pages"""
    try:
        # Initialize the searcher
        searcher = PageVectorSearch()

        # Make sure all pages are indexed
        indexed_count = searcher.index_all()
        print(f"Indexed {indexed_count} new pages")

        # Check if we have any files in the index
        if not searcher.index["files"]:
            print("No files in index")
            return []

        # Return search results
        return searcher.search(query, top_k)
    except Exception as e:
        # Log the error and return empty results
        import traceback
        print(f"Error in search_saved_pages: {e}")
        print(traceback.format_exc())
        return []


def save_page_as_markdown(url: str, title: str, content: str,
                          description: str = "", reading_time: int = 0) -> str:
    """Save a page as markdown for vector search"""
    try:
        # Create save directory if it doesn't exist
        save_dir = "saved_pages"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # Create hash of URL for unique filename
        url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{save_dir}/{url_hash}_{timestamp}.md"

        # Create a clean domain name for metadata
        domain = url.split("//")[-1].split("/")[0]

        # Process the content for markdown conversion
        def clean_content(text):
            """Clean and structure the content for markdown"""
            # Replace multiple newlines with double newline for markdown paragraphs
            text = re.sub(r'\n{3,}', '\n\n', text)

            # Try to identify and format headings
            lines = text.split('\n')
            formatted_lines = []

            for line in lines:
                line = line.strip()
                if not line:
                    formatted_lines.append('')
                    continue

                # Check if line looks like a heading
                if len(line) < 80 and not line[-1] in '.,:;?!' and line.istitle():
                    # Make it a markdown heading
                    formatted_lines.append(f'## {line}')
                else:
                    formatted_lines.append(line)

            return '\n'.join(formatted_lines)

        # Create compressed markdown with metadata
        markdown_content = f"""---
title: "{title}"
url: {url}
domain: {domain}
date_saved: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
reading_time: {reading_time} minutes
description: "{description}"
---

# {title}

*Source: [{domain}]({url})*

{clean_content(content)}
"""

        # Save the markdown file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"Page saved as markdown: {filename}")
        return filename
    except Exception as e:
        print(f"Error saving page as markdown: {e}")
        return ""