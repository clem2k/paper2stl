"""Stage A — image pre-processing: grid removal, binarisation, vectorisation."""

from .grid_removal import remove_grid
from .binarize import extract_pencil
from .vectorize import vectorize_lines
from .regularize import regularize_silhouette

__all__ = ["remove_grid", "extract_pencil", "vectorize_lines", "regularize_silhouette"]
