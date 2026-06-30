from FlagEmbedding import BGEM3FlagModel

_embed_model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)


def embed(texts: list[str]) -> list[list[float]]:
    output = _embed_model.encode(
        texts,
        batch_size=12,
        max_length=512,
        return_dense=True,
    )
    return output["dense_vecs"].tolist()
