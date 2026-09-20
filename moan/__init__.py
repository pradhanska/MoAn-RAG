"""Movie & Anime Q&A AI — retrieval-augmented chat over public film/TV/anime data."""

from .pipeline import Answer, ask

__version__ = "1.0.0"
__all__ = ["Answer", "ask", "__version__"]