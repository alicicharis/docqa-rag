import os

from dotenv import find_dotenv, load_dotenv

TOKENIZER = "cl100k_base"
CHUNK_TOKENS = 500
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_MAX_INPUTS = 2048
EMBED_MAX_TOKENS = 300_000
INDEX_DIR = ".docqa"
COLLECTION = "docs"
KNOWLEDGE_DIR = "knowledge"
TOP_K = 5
ANSWER_MODEL = "claude-sonnet-5-5"
ANSWER_MAX_TOKENS = 1024


class ConfigError(Exception):
    pass


def require_env(*names: str) -> None:
    load_dotenv(find_dotenv(usecwd=True))
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ConfigError(
            f"missing environment variables: {', '.join(missing)} "
            "(set them in the environment or a .env file)"
        )
