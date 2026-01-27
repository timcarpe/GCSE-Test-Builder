# Changelog

All notable changes to GCSE Test Builder will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.2] - 2026-01-27

### Fixed
- **Pinned Questions Not Appearing in PDF**: Fixed critical bug where pinned questions and parts were not reliably included in the final generated exam when using Keyword Mode.
  - Pinned parts are now guaranteed to be included in the selection, even if they exceed the mark budget.
  - The selection logic now finds the smallest option that contains ALL pinned labels (not just budget-optimal).
  - Pinned parts are now protected from pruning during mark target adjustment.
  - Added 7 new unit tests to verify pinned parts protection.
- **Keyword Panel Ignoring Year/Paper Filters**: Fixed issue where Keyword Mode preview results showed all matching questions regardless of the active Year and Paper filters.
  - Keyword search results are now filtered to respect the selected year(s) and paper(s).
  - Match counts update to reflect only questions matching the active filters.
  - Filter changes in Build tab automatically update Keyword Panel filters.

## [1.2.1] - 2026-01-26

### Changed
- **Rebranding**: Renamed application from "GCSE Toolkit" to "GCSE Test Builder" across all user-facing interfaces, documentation, and build outputs.
  - Updated package name in `pyproject.toml` to `gcse-test-builder`.
  - Updated application data paths (Documents, AppData) to use "GCSE Test Builder".
  - Updated build specs for macOS and Windows to produce "GCSE Test Builder" executables.
  - Updated PDF footer and ZIP export branding.
  - Internal package name remains `gcse_toolkit` for plugin compatibility.

### Added
- **About in Settings Menu**: Added "About" option to the gear icon settings menu.
- **License Link**: Made the license text in the About dialog a clickable hyperlink to the PolyForm Noncommercial License.

## [1.2.0] - 2026-01-26

### Added
- **Budget-Aware Selection**: Selector now favors questions that fit within the remaining mark budget per topic, improving results for short, topic-dense exams.
- **Strict Topic Representation**: Topics are now forced based on individual question parts (leaves), ensuring all requested topics are represented in final examination marks.
- **Seed-Based Selection Retry**: Implemented a deterministic retry loop (up to 5 attempts) to find valid question combinations that cover all requested topics.

### Fixed
- **Topic Coverage False Positives**: Fixed bug where questions were counted as covering a topic even if their selected parts carried different topics.
- **Force Topic Representation Failures**: Fixed issues where "Force topic representation" would fail to satisfy requested topics on small mark targets.

## [1.1.1] - 2026-01-26

### Changed
- **Version Bump**: Bumped version to v1.1.1 for macOS compilation.

## [1.1.0] - 2026-01-16

### Added
- **Greedy Fill Toggle**: New `allow_greedy_fill` configuration option in `SelectionConfig` to explicitly control backfilling behavior.
  - Automatically disabled in Keyword Mode by default to prevent "leaking" non-matching questions.
  - Preserved existing behavior in Topic Mode (enabled by default).
- **Keyword Backfill Toggle**: Added a GUI toggle in the Build Options area (visible only in Keyword Mode) to control whether keyword matches should be used to reach the mark target.
- **Selection Breakdown Warnings**: The console now provides a clear summary of how many marks came from pins vs keyword matches.

### Changed
- **Keyword Mode Logic Overhaul**: Structural reorganization of the selection algorithm to prioritize explicit user intent.
  - **Pins & Keyword Matches** are now processed FIRST and forced where appropriate.
  - **Topic Coverage** now runs after keyword matching, preventing generic topics from blocking specific matches.
  - **Topic Filter Bypass**: User-pinned or keyword-matched questions are now included even if they do not match the sidebar topic filter.
- **Non-Leaf Part Support**: Keyword matching and pinning now automatically expand parent parts (e.g., "1(a)") to include all their descendants.
- **Forced SKIP Mode**: Keyword Mode now internally forces `PartMode.SKIP` to ensure precisely matched parts are selected.

### Fixed
- **Selection Overshoot**: Fixed inverted scoring in the greedy selection algorithm that rewarded candidates for exceeding the remaining mark budget.
- **Distance-Aware Greedy Fill**: Updated selector to stop backfilling when adding more questions would increase the absolute error from the target.
- **Improved Pruning Accuracy**: Pruning logic now respects absolute error, preventing it from removing parts if the result would be further from the target than the initial overshoot (especially important for atomic questions).
- **Part-Level Topic Filtering**: Fixed bug in `controller.py` where requested topics were not passed to the selection engine, causing granular topic filtering to be ignored in `SKIP` mode.
- **Granular Metadata Reporting**: `build_metadata.json` now includes part-level metadata (marks, topic) for each selected question.
- **Strict Parity Warnings**: Implemented consolidated console warnings (`PARITY FAILURE` / `PARITY WARNING`) when topic leakage is detected in `SKIP` or `PRUNE` mode.
- **Pin/Keyword Internal Conflict**: Fixed bug where pinning a part of a question would accidentally block all other keyword matches from that same question.
- **Leaky Greedy Fill**: Fixed bug where questions not matching any keywords could still be included in Keyword Mode papers via the greedy fill mechanism.
- **Startup Crash in Keyword Mode**: Fixed application crash `QThread: Destroyed while thread '' is still running` when opening the app if the previous session ended in Keyword mode.
  - Disabled persistence of Keyword mode settings (`filter_mode`, `keywords`, `keyword_pins`) in `gui_settings.json`.
  - Application now always starts in "Topics" mode to ensure safe initialization.
  - Automatically resets any existing dangerous keyword settings on save.

## [1.0.0] - 2026-01-14

### Added
- **Feedback UI in Diagnostic Reports**: Interactive feedback mechanism for reporting detection issues
  - Category dropdown: Correct Skip, Missed Label, Wrong Bounds, False Positive, Other
  - Notes textarea for detailed descriptions
  - JSON export with agent action hints for automated processing
  - Auto-save to localStorage for persistence
- **1:1 Diagnostic Parity**: Part-level validation status now stored in both regions.json and diagnostics.json
  - `is_valid` and `validation_issues` fields added to regions.json (Schema v3)
  - All invalid parts have corresponding entries in detection_diagnostics.json
  - Enables querying part validity from extracted data

### Changed
- **Part-Level Filtering in Selection**: Invalid parts now excluded from selection options
  - Valid parts from questions with some invalid parts are still retained
  - Maximizes usable question content while excluding unreliable parts
  - Logged as debug message when parts are filtered
- **Diagnostic Report Filtering**: Non-actionable "Skipping malformed mark box" issues filtered from reports
  - Summary and issue counts reflect only actionable issues
- **Visual Context in Reports**: Images now displayed at real size in scrollable containers (max-height 600px)
  - Full debug composite shown as fallback when y_span unavailable
- **UI Improvements**: Updated beta warning text and increased font size to H2 (16pt) in Extract tab for better visibility.
- **About Dialog**: Updated copyright year to 2025-2026.

### Fixed
- **UI Locking**: Fixed "Show Exam Code Labels" toggle not being disabled during exam generation (Build tab).
- **Pagination Atomic Grouping**: Fixed issue where question headers or contexts could be separated from their first child part across page breaks.
- **Footer Overlap**: Fixed content overlapping the footer in generated PDFs by enforcing correct bottom margins.
- **Part Mode Selection**: Fixed pruning logic to correctly respect `PartMode.PRUNE` (tail-only removal) and `PartMode.SKIP` constraints.
- **Exam Selection Logs**: Added warning logs when selected questions exceed target marks or contain mismatched topics.

## [0.2.7] - 2026-01-06


### Added
- **Three-State Part Selection**: Replaced `allow_pruning`/`allow_skipping` with unified `PartMode` enum
  - `PartMode.ALL`: Full questions only (no partial selections)
  - `PartMode.PRUNE`: Remove parts from end only (contiguous prefix subsets)
  - `PartMode.SKIP`: Remove parts from anywhere (all combinations)
  - New `ThreeStateButtonGroup` widget in Build tab for mode selection
  - Backward-compatible settings migration from legacy boolean toggles
  - 9 unit tests for `PartMode` behavior validation
- **Keyword Mode Backfilling**: Keyword search now supports backfilling from non-matched questions
  - Keyword-matched questions selected first (Phase 1)
  - Remaining marks filled from all available questions (Phase 2)
  - Backfill questions respect `PartMode` setting
  - Two-phase approach matches V1 behavior
- **Comprehensive Selection Test Suite**: 30 new tests for selection robustness
  - Determinism tests: Same seed = same result across all modes
  - Variability tests: Different seeds = varied results
  - Part mode behavior tests: Structural validation of ALL/PRUNE/SKIP
  - Keyword mode integration tests: Priority selection + backfill
  - Cross-parameter matrix tests: All mode × keyword combinations
- **Crashlogging for Compiled Builds**: Traceback crash reporting for PyInstaller distribution
  - `sys.excepthook` captures unhandled exceptions in frozen builds only
  - Crash logs saved to `~/Library/Application Support/GCSE Toolkit/crash_logs/` (macOS) or `%LOCALAPPDATA%\GCSE Toolkit\crash_logs\` (Windows)
  - 5-log rotation prevents accumulation
  - Qt dialog shows crash log location with full traceback in details
  - "Open Crash Logs" menu item in Settings (only visible when logs exist)
  - 6 unit tests for crashlog module
- **Storage Menu Enhancements**: New maintenance options in both Storage menus
  - "Clear Keyword Cache" - Removes cached keyword search data
  - "Reset GUI Settings..." - Deletes settings file with confirmation and restarts app
  - Available in both menu bar Storage menu and Settings gear popup
- **Graceful Settings Error Handling**: Detects malformed `gui_settings.json` on startup
  - Shows dialog prompting user to reset to defaults or exit
  - Prevents crashes from corrupted settings files

### Changed
- **Improved Seed Variability**: Selection algorithm now uses seed more extensively (like V1)
  - Added jitter to `_score_option` (0-30 random bonus) for varied question selection
  - Added jitter to `_pick_best_for_topic` (0-5 random bonus)
  - Shuffled topic processing order for more diverse coverage ordering
  - Randomized option selection from valid candidates (not just "best fit")
  - Different seeds now produce significantly different exam papers
  - Part combination variety: 5.1 unique combos per question (verified with 1000-seed test)

- **Topic Consensus (GAP-017)**: Implemented advanced topic consensus logic for multi-part questions
  - Ported V1 "majority voting" logic to V2 `classification.py`
  - Added hierarchical propagation: unknown parts inherit topics from children/parents/siblings
  - Ensures accurate root topic assignment even when root text is ambiguous
  - Integrated into `pipeline.py` with per-part classification support
  - 11 new unit tests covering propagation rules and voting logic
- **V2 Debug Visualization**: New debug overlay system for visual diagnosis of detection issues
  - `extractor_v2/utils/visualizer.py`: Color-coded bounding box visualization for detected elements
  - Red boxes: Question numerals
  - Blue boxes: Letter parts (a), (b), (c) with Y-positions
  - Green boxes: Roman parts (i), (ii), (iii) with Y-positions
  - Orange boxes: Mark boxes [N] with Y-positions  
  - Debug composite saved as `{question_id}_debug_composite.png` when `debug_overlay=True`
  - GUI integration: Debug Overlay toggle in Extract tab enables visualization
- **Enhanced Detection Logging**: Comprehensive diagnostics for part label detection
  - Logs all detected letters and romans with their Y-positions after each question extraction
  - Warns when romans detected without sufficient parent letters (potential missing label detection)
  - Structured logging with `extra={}` fields for machine-readable parsing
  - Example: `Q2: Detected 2 romans but only 1 letters - detection may have missed parent labels (e.g., missing '(b)' when '(i)' and '(ii)' exist)`
- **Question Validation at Extraction**: New `is_valid` metadata field for automatic quality control
  - Schema updated to v8 (from v7) to support validation flag
  - Questions automatically validated at extraction time for critical errors:
    - Missing bounds calculations
    - Zero leaf parts detected
    - Suspicious part structure (significantly more romans than letters)
  - Invalid questions excluded from builder selection automatically
  - Invalid questions hidden from topics panel to prevent broken content
  - Backward compatible: old extractions (schema v7) default to `is_valid=True`
  - Logger warns when questions marked invalid with detailed failure reasons
- **Enhanced Extraction Warning Logging**: All extraction warnings now include comprehensive debugging context
  - **Failed extraction warnings**: Include PDF name, exam code, and page number
  - **Mark box warnings**: Include question ID, PDF name, exam code, and logical page index
  - **Part validation errors**: Include both children's positions and parent label for clarity
  - **Structured logging**: All warnings include `extra={}` fields for machine-readable log parsing
  - Improved message clarity: data references now follow logical order and include complete context
-  **Phase 6.9: Improved Question Bounds Detection**: Enhanced bounds calculation and rendering for tighter, more professional PDFs
  - **Extractor**: Box bounds calculation using part label and mark box positions (replaces full-width spans)
    - Per-level per-page label normalization for consistent left boundaries
    - Per-page mark normalization with sanity check for consistent right boundaries
    - Graceful fallbacks to full-width when labels/marks unavailable
    - 9 new unit tests covering normalization and bounds calculation
  - **Renderer**: Smart horizontal positioning and vertical spacing
    - Root context parts centered on page
    - Child parts right-aligned to root boundary
    - 20px vertical spacing between context and child parts
    - Centering fallback when children exceed root width
  - **Result**: Eliminates excess left/right margins in generated PDFs while preserving all content
- **Slice Storage Optimization (Phase 1)**: New `ImageProvider` abstraction for slice image retrieval (`builder/image_provider.py`)
  - `ImageProvider` Protocol defining interface for image retrieval
  - `AtlasImageProvider`: Retrieves slices by cropping a single composite image using stored bounds
  - `FileImageProvider`: Backward-compatible provider for legacy physical slice files
  - `RegionBounds` dataclass for sub-part boundary definitions
  - Helper functions: `is_atlas_format()`, `load_regions()`
  - 31 unit tests covering both providers and legacy format compatibility
- **Slice Storage Optimization (Phase 2)**: Atlas output mode in slicer (feature-flagged)
  - `atlas_mode` flag on `QuestionSlicer` (env var: `GCSE_ATLAS_STORAGE=1`)
  - Outputs clean `_composite.png` (cropped from question numeral to mark box)
  - Outputs `_regions.json` with enhanced schema (adjusted coordinates, snippets)
  - Skips individual slice files and legacy `_raw.png` when enabled
  - 9 unit tests for atlas storage mode
- **Slice Storage Optimization (Phase 3)**: Provider integration
  - `provider` field added to `QuestionRecord` (optional)
  - Loader creates `AtlasImageProvider` when atlas format detected (env var: `GCSE_ATLAS_LOADING=1`)
  - Existing consumers (layout, reportlab, zip) work via in-memory images
- **Slice Storage Optimization (Phase 4)**: Viewport tooltip method
  - `show_region()` method on `ImageTooltip` for fast region display from cached QPixmap
  - `_pixmap_cache` in `KeywordPanel` stores composite QPixmaps per question
  - `eventFilter` updated to use provider bounds for region extraction
  - Extracts regions via `QPixmap.copy()` (no disk I/O when switching parts)
  - Falls back to legacy file-based display when atlas format not available

### Fixed
- **V2 Question ID Headers**: Fixed inconsistent header alignment and pagination issues
  - Headers now use fixed 10pt left margin instead of dynamically aligning to next content
  - Eliminates horizontal shifting of question IDs based on content width
  - Headers now stay with their questions across page breaks (look-ahead pagination logic)
  - Prevents orphaned headers at bottom of page when question starts on next page
- **Topics Panel Refresh**: Fixed issue where topic counts didn't reflect active year/paper filters on GUI load
  - Restored filter selections now immediately refresh topic panel with filtered counts
  - Switching between Topics/Keywords mode now preserves active filters
- **Mark Scheme Inclusion**: Fixed mark scheme files not being included in generated exam PDFs
  - Builder now correctly finds `*_ms.png` files (extractor output format) instead of obsolete `markscheme_page_*.png` pattern
- **Slice Cutoff at Page Bottom**: Fixed slices being cut off by bottom margin in generated PDFs
  - Context spacing (20px between context and child parts) now calculated during pagination, not post-pagination
  - Prevents content from being pushed past the page bottom margin
  - Added `context_child_spacing` config field to `LayoutConfig` for explicit control
- **Keyword Mode Mark Target**: Fixed over-selection bug where all keyword-matched questions were force-selected, ignoring the mark target
  - Keyword matches are now budget-constrained: selected only if they fit within remaining marks
  - Explicitly pinned questions (by ID) remain forced-included as expected
  - New test case `test_selector_keyword_repro.py` validates correct behavior
- **Roman Numeral Sorting**: Fixed part sorting bug in `_label_sort_key()` that incorrectly treated single-char roman numerals (i, v, x) as letters
  - Caused validation errors: "Children must be sorted by position: 6(e)(v) should be above 6(e)(ii)"
  - Parts now correctly sort as (i), (ii), (iii), (iv), (v) instead of (i), (v), (ii), (iii), (iv)
  - Fixes 13+ previously-failing questions across 0620 and 0478 exams

### Changed
- **Debug Overlay Toggle Removed**: Removed redundant Debug Overlay toggle from Extract tab
  - Debug overlay functionality is now tied to the "Run Diagnostics" setting
  - Simplifies UI by reducing duplicate controls

### Added (Testing)
- **Paginator Regression Tests**: New `tests/builder_v2/layout/test_paginator.py`
  - Tests context + child spacing behavior
  - Verifies page breaks occur correctly when content exceeds available space
- **Mark Scheme Regression Tests**: New `tests/builder_v2/output/test_markscheme.py`
  - Tests correct file pattern matching (`*_ms.png`)
  - Verifies mark scheme images are found and included in PDF


## [0.2.6] - 2025-12-11

### Added
- **Slice Quality Assurance**: New module for automated validation of extracted exam slices (`extractor/v2/slice_quality.py`)
  - `LabelPresenceValidator`: Verifies slices contain expected labels
  - `BoundaryContaminationChecker`: Detects adjacent question content in slices
  - `EdgeCutoffDetector`: Detects truncated text at image edges
  - `DuplicateFinder`: Identifies duplicate/near-duplicate slices using perceptual hashing
  - `SizeAnomalyDetector`: Flags unusually sized slices using z-score analysis
  - CLI entrypoint: `python -m gcse_toolkit.extractor.v2.slice_quality <slice_dir>`
  - Generates markdown quality reports with pass/fail status
  - 17 unit tests with synthetic image fixtures
  - Interactive HTML review tool for manual QA (`scripts/generate_quality_report.py`)

### Changed
- `SizeAnomalyDetector` z-score threshold raised from 2.5 to 4.0 (reduces false positives)
- `DuplicateFinder` disabled by default (100% false positive rate in testing)

### Fixed
- Label detection now validates alphabetical sequence, preventing detection of out-of-order labels like "(s)" after "(a)"
- Question detection now excludes footer zone (bottom 8% of page), preventing page numbers like "11" from being detected as question labels
- Root question slicing now uses markbox as definitive end boundary instead of page end, eliminating need for hacky footer masking
- Lettered and roman numeral part slicing now uses markbox to clamp bottom boundary, preventing footer content from peeking through
- Label alignment now uses left-margin consensus (x < 20% width) for baseline, preventing noise like "(g)" in content text from corrupting label detection

## [0.2.5] - 2025-12-10

### Added
- **Markscheme Migration**: Markscheme generation is now handled by the robust ReportLab PDF engine (replacing legacy pillow-based generation).
  - Supports scaling images to fit A4 page while preserving aspect ratio
  - Generates "editable" PDF objects (images) for better compatibility
- **Exam Code Toggle**: New configuration option `ENABLE_EXAM_CODE_LABELS` in code to toggle exam code headers on/off (Default: True).

### Changed
- **Visual Styling**: Improved vertical spacing for Question Papers.
  - **Strict Vertical Stacking**: Exam Code Headers are now treated as distinct layout elements with an 80px vertical gap before the question image starts. This prevents any overlap "pixel soup" issues.
  - **White Background**: Question numbers now have a crisp white background box for better legibility against any potential background artifacts.
  - **Clean Layout**: Removed legacy overlay logic in favor of a strictly sequential render order (Header -> Gap -> Question).

## [0.2.4] - 2025-12-10

### Added
- **Storage Management**: New storage submenu in settings dropdown + dedicated Storage menu in menu bar
  - Menu bar "Storage" menu shows live cache/PDF sizes with "Clear Cache..." and "Open Cache Folder" actions
  - Settings dropdown also includes storage submenu for quick access
  - Displays cache size, input PDFs size, and total storage usage
  - "Clear Cache..." option with confirmation dialog to free up disk space
  - "Open Cache Folder" option to browse extracted question data
  - Added storage utilities module (`gui_v2/utils/storage.py`)
  - Uninstall instructions added to README.md
- **Plugin Supported Years**: Plugin manifests now include `supported_years` field tracking which exam years were used for training
  - Plugin generator (`cli.py`) automatically extracts years from training PDF filenames (e.g., `m20` → 2020)
  - Extraction pipeline logs soft warning when processing PDFs outside plugin's supported year range
  - All 8 bundled plugins updated with `supported_years: ["2022", "2023", "2024", "2025"]`
- **Year Filtering**: Filter questions by exam year in the Build tab
  - Multi-select dropdown allows selecting one or more specific years or "All Years"
  - Topic counts and keyword previews refresh based on selected years
  - Red border highlights the filter when active
- **Paper Filtering**: Filter questions by paper number (1, 2, 3) in the Build tab
  - Multi-select dropdown positioned between Year filter and Reload button
  - Same behavior as year filter: red border when active, refreshes topic counts
  - Extraction now captures paper number in metadata (`paper_no` field, Schema v7)
- **Metadata Verification**: Unit tests for year discovery and schema version checking
- **Year Tracking**: Extraction pipeline now captures exam year in metadata (Schema v6)
- **Mark Target 0**: Enter 0 in Target Marks field to output ALL questions for a single selected topic
  - Confirmation dialog warns about processing time before generating
  - Only available with exactly one topic selected (no sub-topics)
- **First-Launch Tutorial**: 7-step spotlight overlay guides new users through the Extract → Build workflow
  - Appears on first launch with Skip/Next/Finish navigation
  - Steps: Source folder, Extract button, Nav toggle, Topic Mode, Keyword Mode, Settings panel, Generate button
  - Semi-transparent overlay with rounded spotlight cutout highlighting specific UI elements
  - Theme-aware callout tooltips with drop shadow (created fresh per step to prevent text artifacts)
  - Auto-switches between tabs and filter modes during demo
  - Returns to Extract tab when complete

### Changed
- **Metadata Schema**: Unified schema versioning with backward compatibility policy
  - Upgraded `METADATA_SCHEMA_VERSION` to 7 to support paper_no field
  - Plugin manifests: `manifest_schema_version` (integer, v3 adds board)
- **Extract Tab UI**: 
  - Refactored layout to a single centered column with 12.5% horizontal margins
  - Removed slice folder path input field and browse button (managed automatically)
  - Removed "Open slice cache" button
  - Updated Extract Exams button to align right within the center column
- **Build Tab UI**:
  - **Reorganized UI**: Split configuration controls into two 50% columns and moved primary actions to a sticky footer.
  - **Output Format**: Control constrained to 50% width of footer, with toggle right-aligned within that space.
  - Added Year Filter dropdown between Exam Code and Reload button
  - Converted Reload button to icon-only style to save space
- **Window Size**: Increased minimum window size to 1200x720 (from 960x640) to prevent UI element squashing
- **Header Branding**: Added logo icon inline to the left of "GCSE ToolKit" title
- **Settings**: Year selection is now saved per-exam code in persistent settings

### Fixed
- **Console**: Fixed resizing issue where console would snap or disappear. Added expanding size policy.
- **Circular Import**: Removed duplicate `_extract_year_from_series` function from `pipeline.py` to prevent import errors
- **UI Consistency**: Applied consistent checkbox styling to year filter dropdown
- **Page Breaks**: 
  - Fixed issue where parent question headers could be separated from their first child question across pages.
  - Logic updated to keep question root headers with their first child slice (lock_with_next=True).
- **Core**: Added `board` field to plugin manifests (Schema v3) and question metadata. Updated all bundled plugins to include `"board": "Cambridge"`.
- **Performance**: Storage menu calculations are now asynchronous (background thread) with caching, preventing UI freeze when opening Storage menu on large directories.
- **PDF Rendering**: Reduced question number font size (46→41) to prevent double-digit numbers overlapping question text.
- **Builder**: Year and paper filters now correctly filter questions during exam generation (previously only updated topic counts in UI).

## [0.2.3] - 2025-12-09

### Added
- Extraction: Final report dialog now shows counts (e.g., "Extracted 5 question papers, 3 mark schemes")
- Extraction: Warns when question papers are missing corresponding mark scheme files
- Branding: New application logo/icon (blue checkmark in brackets design)
- macOS: Added missing `logo.icns` file for proper dock icon rendering
- Icon generation script: `scripts/generate_icons.py` for future logo updates
- **Metadata Version Warning**: On startup, warns if extracted exams use outdated metadata schema and prompts re-extraction
  - "Extract Now" button navigates to Extract tab with pulsing highlight
  - Build action blocked if outdated metadata detected
- **Attention Getter Utility**: `utils/attention.py` module for reusable pulsing button animations
  - Smooth easing, pulses until clicked (or timed with `duration_ms`)
  - `pulse_button()` - yellow/gold (default), `pulse_button_danger()` - red, `pulse_button_success()` - green, `pulse_button_info()` - blue
- **Keyword Search**: Press Enter in keyword input field to trigger search (no need to click button)
- Dev: Added `pytest-qt` dependency for GUI widget testing
- Testing: Comprehensive UI test suite (`test_extract_tab_ui.py`) with 8 tests covering button labels and tooltips
- Testing: Button responsiveness test suite (`test_button_responsiveness.py`) with 7 tests for click handling
- **Builder Auto-Refresh**: Switching between Topics and Keywords tabs in the Build tab now automatically refreshes the data (reloads topics or previews keywords), eliminating the need for manual reload.

### Changed
- **Mac Checkbox Styling**: Replaced native Qt checkboxes with custom PNG icons (Light & Dark mode) to fix rendering inconsistencies on macOS.
- **UI Clarity**: Renamed folder selection buttons from "Browse..." to "Change folder" across Extract and Build tabs
  - Extract tab: PDF and Slice folder inputs now use "Change folder" button
  - Build tab: Output directory input now uses "Change folder" button
  - Updated tooltips to "Choose a different folder" for clarity
  - Improves distinction from "Open" button (which opens folder in file explorer)
- **Button Click Handling**: `SegmentedToggle` widget now uses `mouseReleaseEvent` for click consistency
  - Matches standard `QPushButton` behavior (clicks register on mouse release, not press)
  - Adds bounds checking to prevent accidental toggles from drag-off actions
  - Improves overall click reliability across the GUI
- Build tab: Renamed "Exam Code:" to "Choose Exam Code:" and moved exam name above dropdown for clearer UX
- Dark mode: Lightened background colors using VS Code Dark+ theme palette (`#1e1e1e` / `#252526`)
- Extraction pipeline refactored to two-phase scan-then-process approach for cleaner code
- **Keyword Search**: Loosened search logic for better user experience
  - All searches are now case-insensitive by default
  - Regex support removed from input field (replaced with default loose matching)
  - **Loose Matching**: "tracetable" now matches "Trace Table" (ignores spaces)
  - **Exact Matching**: Enclose terms in quotes (e.g., `"and"`) for whole-word exact matching (prevents "and" matching "nand")
- **Console**: Improved resize behavior
  - Increased splitter handle size for easier grabbing
  - Smoother resizing (opaque resize enabled)
  - Prevented console from snapping closed (collapsible disabled)

### Fixed
- Extraction: PDFs in subfolders now extracted correctly (was only scanning top-level directory)
- Build tab: Markscheme toggle and output format now grey out correctly during exam generation (was missing from UI lock)
- Production build: Eliminated hardcoded `workspace/` paths that caused `[Errno 30] Read-only file system: '/workspace'` error when running compiled apps
- Path resolution now correctly uses platform-specific directories in frozen builds:
  - macOS: `~/Library/Application Support/GCSE Toolkit/` and `~/Documents/GCSE Toolkit/`
  - Windows: `%LOCALAPPDATA%/GCSE Toolkit/` and `%APPDATA%/GCSE Toolkit/`
- Fixed fallback paths in `config.py`, `assemble_paper.py`, and `cli.py`
- Tooltips: Fixed flickering issue by converting `FluentTooltip` to a custom transparent-to-mouse-events widget

## [0.2.2] - 2025-12-08

### Added
- Build tab: Output format selector (PDF / ZIP / BOTH) - pill-shaped three-state button group
- Build tab: Mark scheme inclusion toggle - controls whether `markscheme.pdf` is generated
- ZIP export: `slices.zip` containing raw question slice images matching PDF content
- Smart directory opening: Opens exact output folder after generation
- **Test Suite Expansion**: 99 tests now pass (up from 56)
  - `test_plugin_discovery.py`: 24 tests for dynamic plugin discovery and validation
  - `test_builder_config_boundary.py`: 13 boundary/edge case tests
  - Selection edge cases: 6 new tests for empty lists and deviation calculations
  - `test_helpers.py`: 7 tests for `scan_exam_sources()` filename handling

### Changed
- Export controls positioned above output directory for better workflow
- ZIP export uses LayoutPlan to ensure identical content to PDF output
- Plugin discovery uses lazy initialization pattern with `_ensure_initialized()`
- Replaced bare `except Exception` with specific exception types in plugin loader
- Syllabus parser tests now use generic assertions (not hardcoded topic numbers)

### Fixed
- ZIP export now includes only selected question slices (respects pruning/skipping)
- Directory opening fallback handles both `questions.pdf` and `slices.zip` detection
- Plugin loader logs warnings for JSON decode and IO errors instead of silently failing

## [0.2.1] - 2025-12-07

### Added
- Settings gear icon in main window header with dropdown menu
- Bundled plugins for 0450 (Business Studies) and 0478 (Computer Science)

### Changed
- Extract tab: removed slice browser, controls now use full width
- Extract tab: debug toggle now floats left with proper spacing
- Build tab: dice button now matches input field height (40x40, larger icon)
- Build tab: shortened "Mark Tolerance" label to prevent cutoff
- Header layout: segmented toggle floats right next to settings gear
- Exam selection dialog: checkboxes now use consistent orange theme

### Fixed
- Removed `hooks` field from `ExamDefinition` dataclass to fix runtime error
- Topic classification now runs consensus BEFORE creating folders, fixing folder/metadata mismatch
- Consensus logic uses >50% threshold (ties stay Unknown) for multi-topic questions
- Model-Based Tie Breaking: Updated `slicer.py` to use model confidence scores to resolve regex classification ties (e.g. Programming vs Databases) when margins are close.
- Evaluation Logic Parity: Synced `scripts/GCSE Plugin Generator/classifier.py` with production `slicer.py` logic (weighted scoring, thresholds) to ensure consistent metrics between training and runtime.

## [0.2.0] - 2025-12-07

### Added
- Plugin security: manifest validation and model signature verification
- Removed hook system for security (hooks disabled with TODO)
- `validation.py` module for runtime plugin validation

### Changed
- Plugins no longer support `hooks` field in manifest
- Plugin loader now validates manifest schema on load

### Fixed
- Extraction pipeline now cleans up stale question folders before re-extraction, preventing metadata/folder mismatch

## [0.1.0] - 2025-11-01

### Added
- Initial release
- GUI v2 with Extract, Build, and Settings tabs
- Plugin system for exam code configuration
- Question extraction from PDF exam papers
- Exam paper generation with topic selection
