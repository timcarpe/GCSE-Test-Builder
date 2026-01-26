"""Centralized threshold and magic number configuration.

This module contains all hardcoded thresholds, ratios, and magic numbers
used throughout the extraction and building process. Having these in one
place makes tuning easier and documents why each value was chosen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ImageProcessingThresholds:
    """Thresholds for image processing and trimming."""
    
    # Barcode detection (pixel heuristic in slicer)
    barcode_chunk_size: int = 4  # Lines to check at a time for barcodes
    barcode_detection_threshold: float = 0.4  # Dark ratio threshold for candidate barcode slices
    barcode_dark_threshold: int = 236  # Pixel value considered "dark" for barcode detection
    barcode_high_dark_ratio: float = 0.9  # Dark ratio for secondary barcode heuristic
    barcode_low_std_threshold: float = 6.0  # Std dev threshold for secondary barcode heuristic
    min_page_height_for_barcode: int = 40  # Minimum page height to scan for barcodes
    min_clip_band_height_px: int = 30  # Minimum barcode band height
    
    # Whitespace trimming
    trim_padding: int = 4  # Pixels of padding to keep after trim
    min_white_threshold: int = 240  # Pixel value considered "white"
    dynamic_trim_divisor: int = 150  # Divisor for dynamic padding
    
    # Footer detection
    footer_proximity_ratio: float = 0.15  # Distance from bottom to be considered footer
    footer_padding: int = 6  # Minimum padding above detected footer bands
    
    # Sidebar margins (auto-detection)
    sidebar_base_ratio: float = 0.045  # Default sidebar margin
    sidebar_max_ratio: float = 0.072  # Maximum sidebar when widened


@dataclass
class TextDetectionThresholds:
    """Thresholds for text-based detection and classification."""
    
    decorative_line_length: int = 20  # Chars needed for decorative line detection


@dataclass
class LayoutThresholds:
    """Thresholds for layout and cropping decisions."""
    
    # Part cropping
    min_part_height: int = 24  # Minimum height for a part cropping
    part_bottom_padding: int = 12  # Extra padding below parts
    
    min_crop_width_ratio: float = 0.6  # Min width ratio for intelligent cropping
    final_trim_thr: int = 245  # Threshold used in final trim
    final_trim_row_fraction: float = 0.995  # Row fraction for tail trimming
    final_trim_min_tail_px: int = 80  # Minimum tail pixels to trim
    final_trim_min_tail_ratio: float = 0.08  # Minimum tail ratio
    final_trim_width_guard_ratio: float = 0.4  # Width guard ratio
    final_trim_col_extend_px: int = 2  # Column extension when trimming


@dataclass
class SelectionThresholds:
    """Thresholds for question selection algorithm."""
    
    # Topic budgeting
    per_topic_overshoot: int = 3  # Marks allowed over per-topic budget
    per_topic_pool_size: int = 0  # Max questions per topic pool (0 = unlimited)
    per_topic_flexibility: float = 1.4  # 40% extra flexibility for per-topic budget
    per_topic_stop_multiplier: float = 1.6  # Stop adding to topic at 160% of budget
    
    # Question limits by budget size
    small_budget_threshold: int = 15  # Base budget below this is "small"
    max_questions_small_budget: int = 1  # Max questions per topic for small budgets
    max_questions_large_budget: int = 2  # Max questions per topic for larger budgets
    
    # Trim variants
    trim_variants_per_question: int = 5  # Increased from 2 for more partial question options
    
    # Selection scoring
    small_option_bias: float = -0.1  # Bias towards small options near budget
    jitter_scale: float = 25.0  # Phase 3: Diversity jitter (25 chosen after testing)
    diversity_weight: float = 0.7  # Phase 3: 70% random, 30% fitness
    near_mark_window: int = 2  # Window for near-budget marks
    
    # Phase 3: Adaptive small question bonus weights
    small_question_weight_low: float = 0.5  # Small exams (≤20 marks), single topic
    small_question_weight_medium: float = 0.3  # Medium exams (20-50 marks)
    small_question_weight_high: float = 0.1  # Large exams (≥50 marks) or many topics
    
    # Fill phase scoring
    underrepresented_threshold: float = 0.7  # Topic is underrepresented below 70% of fair share
    underrepresented_strong_bonus: int = -10  # Strong preference for underrepresented
    underrepresented_moderate_bonus: int = -5  # Moderate preference


@dataclass
class TextLayoutThresholds:
    """Thresholds for text layout and sidebar/footer logic."""

    sidebar_sample_band_ratio: float = 0.12  # Sidebar sampling band ratio
    sidebar_sample_band_min_px: int = 12  # Minimum sidebar sampling width
    sidebar_widen_grey_threshold: float = 0.55  # Grey threshold for widen
    sidebar_widen_dark_threshold: float = 0.015  # Dark threshold for widen
    sidebar_widen_alt_grey: float = 0.45  # Alternate grey threshold
    sidebar_widen_alt_dark: float = 0.02  # Alternate dark threshold
    sidebar_widen_alt_std: float = 12.0  # Std dev threshold for alternate widen
    clip_guard_ratio: float = 0.4  # Minimum width after sidebar shave
    min_clip_height_px: int = 20  # Minimum clip height after sanitization
    discard_threshold_ratio: float = 0.08  # Ratio for discard region trimming
    clip_min_keep_ratio: float = 0.3  # Minimum keep ratio for clipped regions
    margin_band_ratio: float = 0.18  # Margin band ratio for header/footer detection
    footer_limit_ratio: float = 0.22  # Footer distance ratio
    footer_min_distance_px: int = 70  # Minimum footer distance in pixels
    footer_min_distance_ratio: float = 1 / 40  # Footer min distance ratio
    footer_pad_divisor: int = 80  # Divisor for footer padding
    excerpt_max_chars: int = 800  # Max characters for text excerpt


@dataclass
class SectionDetectionThresholds:
    """Thresholds for section label detection and spacing."""

    letter_spacing_min_px: int = 8  # Minimum spacing between letters
    letter_spacing_divisor: int = 500  # Divisor for dynamic spacing
    section_alignment_tolerance_px: float = 12.0  # Alignment tolerance absolute
    section_alignment_ratio: float = 0.05  # Alignment tolerance ratio
    section_bucket_height_px: int = 10  # Bucket height for alignment


@dataclass
class MarkSchemeThresholds:
    """Thresholds for mark scheme processing."""

    trim_padding: int = 6  # Padding for mark scheme trim
    trim_threshold: int = 240  # Threshold for mark scheme trim


@dataclass
class LayoutRenderThresholds:
    """Thresholds for rendering layout and numbering."""

    leaf_padding_px: int = 10
    header_box_w: int = 70
    header_box_h: int = 64
    header_left_nudge: int = 0
    header_pad_px: int = 12
    header_min_height_px: int = 40
    header_top_padding_px: int = 6
    inter_slice_padding_base: int = 110
    top_padding_min: int = 28
    scale_epsilon: float = 0.02
    number_box_min_w: int = 42
    number_box_max_w: int = 88
    number_box_h: int = 64
    number_font_size: int = 36
    number_left_nudge: int = 10
    number_text_pad_x: int = 10
    number_text_pad_y: int = 0  # Reduced from 4 to align number at top of box
    fallback_box_w: int = 70
    fallback_box_h: int = 64
    fallback_box_x_ratio: float = 0.02
    fallback_box_y_ratio: float = 0.015


@dataclass
class RenderValidationThresholds:
    """Thresholds for rendering validation and labeling."""

    label_pad_x: int = 4
    label_pad_y: int = 2
    label_min_w: int = 20
    max_diff_warn: float = 12.0


# Global instances for easy import
IMAGE_THRESHOLDS = ImageProcessingThresholds()
TEXT_THRESHOLDS = TextDetectionThresholds()
LAYOUT_THRESHOLDS = LayoutThresholds()
SELECTION_THRESHOLDS = SelectionThresholds()
TEXT_LAYOUT_THRESHOLDS = TextLayoutThresholds()
SECTION_THRESHOLDS = SectionDetectionThresholds()
MARK_SCHEME_THRESHOLDS = MarkSchemeThresholds()
LAYOUT_RENDER_THRESHOLDS = LayoutRenderThresholds()
RENDER_VALIDATION_THRESHOLDS = RenderValidationThresholds()
