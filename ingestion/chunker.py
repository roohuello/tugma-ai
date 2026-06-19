"""Document chunking pipeline — LlamaIndex SentenceSplitter."""

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


def get_pipeline() -> IngestionPipeline:
    return IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP),
        ]
    )
