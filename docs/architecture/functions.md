# Function Catalog

> **Document Type:** CURRENT ARCHITECTURE  
> **Purpose:** Documents existing functions as-is for Phase 1 analysis  
> **See Also:** Proposed V2 changes are in `docs/TODO/d) Major Refactoring/30_builder_extractor_v2/`

## Overview

Comprehensive documentation of all public functions in the extractor and builder modules. Each function is documented with its signature, behavior, and verification status for V2 reuse decisions.

---

# CURRENT FUNCTIONS

## Extractor Module Functions

### pipeline.py

#### `ExtractionPipelineV2.__init__(config: ExtractorConfigV2 | None = None)`

**Purpose:** Initialize the extraction pipeline with optional configuration.

**Inputs:**
- `config` - Extractor configuration (defaults to `ExtractorConfigV2()`)

**Side Effects:**
- Sets up logging if not already configured
- Creates `QuestionExtractorV2`, `QuestionSlicer`, and `MarkSchemeSaver` instances

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Simple initialization, works well

---

#### `ExtractionPipelineV2.run_on_directory(path: Path) -> ExtractionReport`

**Purpose:** Process all PDF files in a directory, pairing question papers with mark schemes.

**Inputs:**
- `path` - Directory containing exam PDFs to process

**Outputs:**
- `ExtractionReport` with counts and missing markscheme info

**Side Effects:**
- Writes to filesystem (slice images, metadata JSONL)
- Cleans exam folders before re-extraction

**Dependencies:**
- `_scan_pdfs()` - Groups PDFs by exam code
- `_parse_exam_paper()` - Parses PDF metadata
- `_process_question_paper()` - Extracts questions
- `_process_mark_scheme()` - Associates mark schemes

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ⚠ MODIFY - Core orchestration is solid, but cleanup logic should be extracted

---

#### `ExtractionPipelineV2.run_on_pdf(path: Path) -> ExtractionResultV2`

**Purpose:** Process a single PDF file (question paper or mark scheme).

**Inputs:**
- `path` - Path to PDF file to process

**Outputs:**
- `ExtractionResultV2` containing extracted questions and metadata

**Side Effects:**
- Writes slice images and metadata to filesystem

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Simple wrapper around internal methods

---

### detection.py

#### `detect_question_starts(doc: fitz.Document, cfg: ExtractorConfigV2) -> List[QuestionStart]`

**Purpose:** Detect all question start markers in a PDF document.

**Inputs:**
- `doc` - PyMuPDF document to scan
- `cfg` - Extractor configuration

**Outputs:**
- List of `QuestionStart` objects with position and metadata

**Algorithm:**
1. Scan each page for patterns like question numbers (1, 2, 3...)
2. Filter left-margin content
3. Detect "Question N" patterns in text

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Battle-tested regex patterns work well

---

#### `filter_monotonic(starts: Iterable[QuestionStart]) -> List[QuestionStart]`

**Purpose:** Filter question starts to ensure monotonic question numbering.

**Inputs:**
- `starts` - Iterable of detected question starts

**Outputs:**
- Filtered list of question starts in sequential order

**Algorithm:**
- Removes duplicate question numbers
- Ensures sequential order (1, 2, 3...)
- Prefers non-pseudocode detections when duplicates exist

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Clean filtering logic

---

### slicer.py

#### `QuestionSlicer.process(bundle, paper, output_root, resources) -> Dict[str, object]`

**Lines:** 176-294

**Purpose:** Main entry point for processing a single question bundle into slices.

**Inputs:**
- `bundle` - `QuestionBundle` with question data and image
- `paper` - `ExamPaper` metadata
- `output_root` - Base path for output files
- `resources` - `ExamResources` from plugin

**Outputs:**
- Dictionary containing metadata record for the question

**Side Effects:**
- Writes PNG slices to filesystem
- Writes span ledger JSON
- Creates directory structure

**Algorithm:**
1. Classify topic using ML model or regex fallback
2. Mask page metadata (footers, barcodes)
3. Build span tree from detections
4. Apply consensus logic for unknown topics
5. Save root span and crop parts
6. Build metadata record

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [x] Complex - marked for refactoring

**Decision:** ✗ REWRITE - Too many responsibilities (294 lines). Should be split into:
- `_classify_topic()` - Topic classification
- `_process_metadata()` - Metadata masking
- `_build_structure()` - Span tree building
- `_save_outputs()` - File writing

---

#### `QuestionSlicer._build_spans(bundle: QuestionBundle) -> Dict[Tuple[str, ...], SpanNode]`

**Lines:** 561-667

**Purpose:** Build hierarchical node structure from question detections.

**Inputs:**
- `bundle` - Question bundle with detections and image

**Outputs:**
- Dictionary mapping node paths to `SpanNode` objects

**Algorithm:**
1. Create root node for main question
2. Build letter nodes from detections (a, b, c)
3. Build roman numeral nodes (i, ii, iii)
4. Adjust boundaries to prevent overlaps
5. Assign marks to appropriate nodes
6. Assign text snippets and flags

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [x] Complex - marked for refactoring

**Decision:** ⚠ MODIFY - Core algorithm is good but should extract bounds calculation into separate function

---

#### `QuestionSlicer._crop_parts(bundle, spans, base_dir, question_dir_name)`

**Purpose:** Generate slice images for each part of the question.

**Side Effects:**
- Writes PNG files for each part

**Verification Status:**
- [ ] Behavior verified
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ⚠ MODIFY - Extract bounds calculation logic for V2 composite format

---

#### `QuestionSlicer._fallback_regex_classify(sample_text, patterns, stats, model_probs) -> Optional[str]`

**Lines:** 73-174

**Purpose:** Infer topic using weighted pattern scoring when ML model is uncertain.

**Algorithm:**
1. Normalize text to match Miner V3 assumptions
2. Build pattern weights from stats
3. Score each topic based on pattern matches
4. Apply margin check and threshold
5. Use model probabilities to break ties

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Well-documented fallback logic

---

### detectors.py

#### `Detection` dataclass

**Fields:**
- `label: str` - Detected label (e.g., "a", "ii")
- `bbox: Tuple[float, float, float, float]` - Bounding box
- `kind: str` - Type of detection ("letter", "roman")

**Decision:** ✓ REUSE - Simple, clean data class

---

---

## Builder Module Functions

### controller.py

#### `run_builder(config: BuilderConfig) -> Path`

**Lines:** 33-199

**Purpose:** Execute the end-to-end workflow and return the summary path.

**Inputs:**
- `config` - Builder configuration with topics, marks, output settings

**Outputs:**
- Path to the generated summary JSON file

**Algorithm:**
1. Load questions from metadata
2. Apply year/paper filters
3. Apply topic or keyword filters
4. Run selection algorithm
5. Order by topic
6. Assign numbering and mark adjustments
7. Build layout plan
8. Generate PDF and/or ZIP output
9. Write summary and log files

**Side Effects:**
- Creates output directory
- Writes PDF/ZIP files
- Writes metadata files

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ⚠ MODIFY - Too many responsibilities. Should be split into:
- `_load_and_filter()` - Loading and filtering
- `_run_selection()` - Selection wrapper
- `_generate_outputs()` - Output generation

---

#### `_filter_by_topics(questions, config: BuilderConfig) -> List[QuestionRecord]`

**Lines:** 249-299

**Purpose:** Filter questions by matching topics.

**Algorithm:**
1. Normalize requested topics
2. Find direct topic hits
3. Include related topics as fallback
4. Combine primary and fallback results

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Clear filtering logic

---

#### `_filter_by_year_paper(questions, config) -> List[QuestionRecord]`

**Lines:** 503-524

**Purpose:** Filter questions by year and/or paper number.

**Verification Status:**
- [x] Behavior understood
- [x] Unit test written
- [x] Ready for v2 reuse

**Decision:** ✓ REUSE - Recently added, clean implementation

---

### loader.py

#### `load_questions(config: BuilderConfig) -> List[QuestionRecord]`

**Lines:** 30-40

**Purpose:** Load all question records discoverable beneath the metadata root.

**Inputs:**
- `config` - Builder configuration with metadata paths

**Outputs:**
- List of `QuestionRecord` objects

**Side Effects:**
- Reads from filesystem

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Clean entry point

---

#### `_question_from_payload(payload, metadata_root, exam_root, config) -> QuestionRecord`

**Lines:** 86-173

**Purpose:** Parse a single JSON payload into a `QuestionRecord`.

**Algorithm:**
1. Extract paths from payload
2. Determine exam code from multiple sources
3. Build part tree
4. Discover part images
5. Handle 15-pointer special case

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ⚠ MODIFY - Too complex. Exam code detection should be extracted.

---

#### `_validate_question_payload(payload, source, line)`

**Lines:** 277-307

**Purpose:** Validate question metadata before loading.

**Algorithm:**
- Check schema version
- Verify required fields
- Validate types

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Good validation logic

---

### selection.py

#### `select_questions(questions, config) -> SelectionResult`

**Lines:** 168-177

**Purpose:** Entry point for question selection.

**Inputs:**
- `questions` - Available questions to select from
- `config` - Selection configuration

**Outputs:**
- `SelectionResult` with selected questions and diagnostics

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Clean entry point

---

#### `_select_questions_budgeted(questions, config) -> SelectionResult`

**Lines:** 240-675

**Purpose:** Topic-first budgeted selection to approximate target marks.

**Algorithm:**
1. Calculate per-topic budget
2. Generate plan options for each question
3. Select from each topic pool
4. Fill remaining budget
5. Trim if over target
6. Apply in-question pruning if needed

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [x] Complex - marked for refactoring

**Decision:** ✗ REWRITE - 435 lines, too complex. Core algorithm should be extracted and simplified:
- Separate option generation
- Separate topic-first selection
- Separate fill and trim phases
- Validate mark invariants at each step

---

#### `_generate_plan_options(question, ...) -> List[PlanOption]`

**Lines:** 713-900+

**Purpose:** Generate every feasible leaf-bundle for a question.

**Verification Status:**
- [ ] Behavior fully understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ⚠ MODIFY - Complex function with many parameters. Needs simplification.

---

### layout.py

#### `build_layout(selection: SelectionResult, config: BuilderConfig) -> LayoutPlan`

**Lines:** 65-86

**Purpose:** Convert the selection into a concrete layout plan.

**Algorithm:**
1. Compose question assets for each selected item
2. Paginate slices
3. Build question-to-page map

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Clean orchestration

---

#### `_compose_question_assets(option: PlanOption, config: BuilderConfig) -> Tuple[List[SliceAsset], List[str]]`

**Lines:** 89-206

**Purpose:** Return ordered slice assets for a question bundle.

**Algorithm:**
1. Load and scale base image
2. Emit question header asset
3. Build parent map for navigation
4. Emit letter context images
5. Emit roman leaf images

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ⚠ MODIFY - Should use ImageProvider abstraction instead of direct file I/O

---

#### `_paginate_slices(slices, config, warnings) -> List[PagePlan]`

**Lines:** 412-502

**Purpose:** Bin-pack slices onto pages.

**Algorithm:**
1. Calculate block extents (locked groups)
2. Fit blocks onto pages
3. Respect lock-with-next constraints
4. Add padding between slices

**Verification Status:**
- [x] Behavior understood
- [ ] Unit test written
- [ ] Ready for v2 reuse

**Decision:** ✓ REUSE - Solid pagination algorithm

---

---

## Core Data Structures

### types.py (Builder)

#### `QuestionRecord`

**Fields:**
- `question_id: str` - Unique identifier
- `main_topic: str` - Primary topic classification
- `total_marks: Optional[int]` - Total marks (often unreliable)
- `question_image: Path` - Path to question image
- `parts: List[PartNode]` - Part tree
- `exam_code: Optional[str]` - Exam code
- `year: Optional[int]` - Year of paper
- `paper_no: Optional[int]` - Paper number

**Decision:** ⚠ MODIFY - Add methods for mark calculation, make immutable in V2

---

#### `PartNode`

**Fields:**
- `label: str` - Part label (e.g., "Q1(a)(ii)")
- `marks: Optional[int]` - Mark value for this part
- `mark_source: str` - "explicit", "aggregate", or "inferred"
- `children: List[PartNode]` - Child parts
- `topic: str` - Topic for this part
- `sub_topics: List[str]` - Sub-topics

**Decision:** ⚠ MODIFY - Use `Marks` class for mark values, make immutable in V2

---

### models.py (Extractor)

#### `ExamPaper`

**Fields:**
- `path: Path` - Path to PDF file
- `variant: int` - Paper variant
- `paper: int` - Paper number
- `series: str` - Series code (e.g., "s21")
- `kind: str` - "qp" or "ms"
- `exam_code: str` - Exam code

**Decision:** ✓ REUSE - Clean data class

---

#### `SpanNode`

**Fields:**
- `path: Tuple[str, ...]` - Node path
- `kind: str` - "question", "letter", "roman"
- `top: int` - Top pixel position
- `bottom: int` - Bottom pixel position
- `marks: List[int]` - Detected marks
- `mark_bottom: Optional[int]` - Mark box bottom position

**Decision:** ⚠ MODIFY - Evolve into `SliceBounds` for V2

---

---

## Verification Summary

| Status | Count | Description |
|--------|-------|-------------|
| ✓ REUSE | 12 | Can be moved to V2 with minimal changes |
| ⚠ MODIFY | 10 | Core logic good, needs cleanup |
| ✗ REWRITE | 3 | Too tangled, build fresh |

### High-Priority Rewrites

1. **`QuestionSlicer.process()`** - Split into focused functions
2. **`_select_questions_budgeted()`** - Decompose into phases
3. **`_compose_question_assets()`** - Abstract image loading

### Required Unit Tests (Phase 1 Gaps)

1. `detect_question_starts()` - No tests
2. `_build_spans()` - No tests
3. `_question_from_payload()` - Partial tests
4. `_paginate_slices()` - Has tests, need edge cases
5. `_generate_plan_options()` - Partial tests
