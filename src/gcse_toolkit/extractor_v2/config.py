"""
Module: extractor_v2.config

Purpose:
    Configuration dataclasses for the V2 extraction pipeline. Provides
    immutable settings for DPI, margins, and slice calculation parameters.

Key Classes:
    - ExtractionConfig: Main configuration for extraction
    - SliceConfig: Settings for slice bounds calculation

Dependencies:
    - dataclasses: For frozen dataclass support

Used By:
    - extractor_v2.pipeline: Uses ExtractionConfig for pipeline settings
    - extractor_v2.slicing.bounds_calculator: Uses SliceConfig for padding
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SliceConfig:
    """
    Configuration for slice bounds calculation.
    
    These settings control how slice boundaries are calculated.
    All values set to 0 to ensure bounds are exact label-to-label
    coordinates with no magic number adjustments.
    
    Attributes:
        padding_px: Pixels of padding around each slice. Set to 0.
        min_height_px: Minimum height for any slice. Defaults to 20.
        mark_box_clearance_px: Pixels to leave around mark boxes. Set to 0.
        overlap_tolerance_px: Tolerance when checking sibling overlap. Set to 0.
    """
    padding_px: int = 0  # No padding - exact label coordinates
    min_height_px: int = 20
    mark_box_clearance_px: int = 0  # No adjustment for mark boxes
    overlap_tolerance_px: int = 0  # No overlap tolerance


@dataclass(frozen=True)
class ExtractionConfig:
    """
    Configuration for question extraction pipeline.
    
    Attributes:
        dpi: Resolution for PDF rendering (default 200)
        header_ratio: Fraction of page to exclude as header (default 0.08)
        footer_ratio: Fraction of page to exclude as footer (default 0.08)
        extract_markschemes: Whether to extract markscheme PDFs (default True)
        slice_config: Configuration for slicing (default SliceConfig())
        debug_overlay: Enable debug visualization of detections (default False)
    """
    dpi: int = 200
    header_ratio: float = 0.08
    footer_ratio: float = 0.08
    slice_config: SliceConfig = field(default_factory=SliceConfig)
    debug_overlay: bool = False
    extract_markschemes: bool = True
    run_diagnostics: bool = False  # Enable detection diagnostics output

