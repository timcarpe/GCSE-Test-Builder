"""
Module: extractor_v2.slicing

Purpose:
    Slicing subpackage for creating composite images and calculating
    slice bounds. Outputs CompositeOnly format with regions.json.

Key Modules:
    - compositor: Create composite images from page segments
    - bounds_calculator: Calculate slice bounds with padding
    - writer: Atomic file writing with schema validation

Dependencies:
    - PIL: Image manipulation
    - gcse_toolkit.core.models: SliceBounds dataclass
    - gcse_toolkit.core.schemas: regions.schema.json validation

Used By:
    - extractor_v2.pipeline: Uses slicing for output generation
"""
