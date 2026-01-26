"""
Module: extractor_v2.structuring

Purpose:
    Structuring subpackage for building question part trees from
    detection results. Converts flat detections into hierarchical
    immutable Part objects.

Key Modules:
    - tree_builder: Build Part tree from detections
    - validator: Validate tree structure and invariants

Dependencies:
    - gcse_toolkit.core.models: Part, Marks, PartKind dataclasses

Used By:
    - extractor_v2.pipeline: Uses tree builder for question structuring
"""
