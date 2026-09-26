"""Deterministic document processing: extraction, normalization, registry.

Design contract: no LLM/OCR logic ever lives in this package — later AI
layers consume the traceable extraction results it produces.
"""
