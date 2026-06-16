"""Rhodia — orthographic pencil-sketch → STL reconstruction pipeline.

Public entry points are exposed lazily to keep optional heavy dependencies
(torch, easyocr, open3d) out of the import path unless they are actually used.
"""

__version__ = "0.1.0"

__all__ = ["Pipeline", "PipelineConfig", "get_device"]


def __getattr__(name):  # PEP 562 lazy re-export
    if name == "Pipeline":
        from .pipeline import Pipeline

        return Pipeline
    if name == "PipelineConfig":
        from .config import PipelineConfig

        return PipelineConfig
    if name == "get_device":
        from .device import get_device

        return get_device
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
