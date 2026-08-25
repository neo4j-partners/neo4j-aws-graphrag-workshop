# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Stable embedding and index names shared by graph build and retrieval.

These are the values that have to agree between the module that writes the
graph and the modules that read it. A disagreement returns wrong results with
no error, so each one is defined here and nowhere else.
"""

EMBEDDING_MODEL_ID = "amazon.nova-2-multimodal-embeddings-v1:0"
EMBEDDING_PURPOSE = "GENERIC_INDEX"
EMBEDDING_DIMENSIONS = 1024
CHUNK_VECTOR_INDEX = "hotel_chunk_embeddings"
CHUNK_FULLTEXT_INDEX = "hotel_chunk_fulltext"

# Module 6's memory embeddings are a separate contract from the chunk
# embeddings above, on a different model, and the two are never mixed. The name
# lives here because three places need it and none of them may import from a
# module folder: Module 6 embeds with it, Setup checks Bedrock access to it
# before the workshop starts, and the facilitator prose quotes it.
MEMORY_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"

# Titan v2 will return more than one width on request, so the width is half of
# the same contract as the name: a memory index built at one width and queried
# with a vector of another fails at query time, not at write time. It is
# defined beside the model instead of beside each caller so that changing the
# model cannot leave a stale width behind in Setup or in Module 6.
MEMORY_EMBEDDING_DIMENSIONS = 1024
