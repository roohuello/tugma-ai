"""Offline CLI — ingest DepEd PDFs into Qdrant with hybrid dense+sparse vectors.

Usage: uv run python -m ingestion.ingest [--force]
  --force  Recreate collection (deletes existing data)
"""

import argparse
import asyncio
import hashlib
import re
from pathlib import Path

from fastembed import SparseTextEmbedding
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import Distance, VectorParams, SparseVectorParams
from tqdm import tqdm

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
from src.config import settings
from src.core.embeddings import EMBEDDING_DIM, get_embeddings
from src.core.qdrant import COLLECTION_NAME, VECTOR_NAME

DOCUMENTS_DIR = Path("documents")


def subject_area_from_filename(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r"-\d+$", "", name)
    name = re.sub(r"-Updated.*$", "", name)
    return name.replace("-", " ").strip()


def make_doc_id(source_doc: str, page: str, chunk_idx: int) -> int:
    digest = hashlib.md5(f"{source_doc}:{page}:{chunk_idx}".encode()).hexdigest()
    return int(digest[:16], 16) % (2**63)


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

    await client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="subject_area",
        field_schema=models.KeywordIndexParams(type="keyword"),
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

    client = AsyncQdrantClient(url=settings.qdrant_url, timeout=120)
    embed_model = get_embeddings()
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    try:
        await create_collection(client, force)
        print(f"Collection '{COLLECTION_NAME}' ready")

        for pdf_path in tqdm(pdfs, desc="Ingesting PDFs"):
            subject = subject_area_from_filename(pdf_path.name)
            reader = SimpleDirectoryReader(input_files=[str(pdf_path)])
            docs = reader.load_data()

            for doc in docs:
                nodes = splitter.get_nodes_from_documents([doc])
                raw_texts = [n.get_content() for n in nodes]
                texts = [t.strip() for t in raw_texts if t and str(t).strip()]
                if not texts:
                    continue

                dense_vectors = embed_model.get_text_embedding_batch(texts)
                sparse_generator = sparse_model.embed(texts)
                sparse_vectors = [
                    (list(s.indices), list(s.values)) for s in sparse_generator
                ]

                page = doc.metadata.get("page_label", "p0")

                points = []
                for i, (text, dense, (indices, values)) in enumerate(
                    zip(texts, dense_vectors, sparse_vectors)
                ):
                    points.append(
                        models.PointStruct(
                            id=make_doc_id(pdf_path.name, str(page), i),
                            vector={
                                VECTOR_NAME: dense,
                                "sparse": models.SparseVector(indices=indices, values=values),
                            },
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
