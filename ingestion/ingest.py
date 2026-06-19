"""Offline CLI — ingest DepEd PDFs into Qdrant with hybrid dense+sparse vectors.

Usage: uv run python -m ingestion.ingest [--force]
  --force  Recreate collection (deletes existing data)
"""

import argparse
import asyncio
import re
from pathlib import Path

from fastembed import SparseTextEmbedding
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import Distance, VectorParams, SparseVectorParams
from tqdm import tqdm

from ingestion.chunker import CHUNK_OVERLAP, CHUNK_SIZE
from src.config import settings
from src.core.embeddings import EMBEDDING_DIM, get_embeddings
from src.core.qdrant import COLLECTION_NAME, VECTOR_NAME

DOCUMENTS_DIR = Path("documents")


def subject_area_from_filename(name: str) -> str:
    """Extract subject area from DepEd PDF filename."""
    name = Path(name).stem
    # Remove trailing markers like -1, -Updated-as-of-...
    name = re.sub(r"-\d+$", "", name)
    name = re.sub(r"-Updated.*$", "", name)
    return name.replace("-", " ").strip()


async def create_collection(client: AsyncQdrantClient, force: bool = False) -> None:
    exists = await client.collection_exists(COLLECTION_NAME)
    if exists and force:
        await client.delete_collection(COLLECTION_NAME)
    if not exists or force:
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={VECTOR_NAME: VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()},
        )


async def ingest(force: bool = False) -> int:
    docs_dir = DOCUMENTS_DIR
    if not docs_dir.exists():
        print(f"ERROR: {docs_dir} not found")
        return 1

    pdfs = sorted(docs_dir.glob("*.pdf"))
    if not pdfs:
        print(f"ERROR: no PDFs in {docs_dir}")
        return 1

    print(f"Found {len(pdfs)} PDFs")

    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    embeddings = get_embeddings()
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    try:
        await create_collection(client, force)
        print(f"Collection '{COLLECTION_NAME}' ready")

        next_id = 0
        for pdf_path in tqdm(pdfs, desc="Ingesting PDFs"):
            subject = subject_area_from_filename(pdf_path.name)
            reader = SimpleDirectoryReader(input_files=[str(pdf_path)])
            docs = reader.load_data()

            for doc in docs:
                nodes = splitter.get_nodes_from_documents([doc])
                texts = [n.get_content() for n in nodes]

                if not texts:
                    continue

                dense_vectors = await embeddings.aembed_documents(texts)
                sparse_generator = sparse_model.embed(texts)
                sparse_vectors = [
                    (list(s.indices), list(s.values)) for s in sparse_generator
                ]

                points = []
                for i, (text, dense, (indices, values)) in enumerate(
                    zip(texts, dense_vectors, sparse_vectors)
                ):
                    page = doc.metadata.get("page_label", f"p{i}")
                    points.append(
                        models.PointStruct(
                            id=next_id,
                            vector={VECTOR_NAME: dense, "sparse": models.SparseVector(indices=indices, values=values)},
                            payload={
                                "text": text,
                                "source_document": pdf_path.name,
                                "page": str(page),
                                "subject_area": subject,
                                "track": None,
                                "cluster": None,
                            },
                        )
                    )
                    next_id += 1

                if points:
                    await client.upsert(
                        collection_name=COLLECTION_NAME,
                        points=points,
                        wait=True,
                    )

        count = await client.count(collection_name=COLLECTION_NAME)
        print(f"Done. {count.count} vectors in '{COLLECTION_NAME}'")
        return 0

    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SSHS PDFs into Qdrant")
    parser.add_argument("--force", action="store_true", help="Recreate collection")
    args = parser.parse_args()
    code = asyncio.run(ingest(force=args.force))
    exit(code)


if __name__ == "__main__":
    main()
