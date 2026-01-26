# Function Index

Complete index of all public functions in GCSE Test Builder V2 with signatures and return types.

## Quick Navigation

- [Extraction Functions](#extraction-functions)
- [Building Functions](#building-functions)
- [Core Utilities](#core-utilities)
- [Selection Functions](#selection-functions)
- [Layout Functions](#layout-functions)

---

## Extraction Functions

### Extract Question Paper
**Module**: `extractor_v2/pipeline.py`  
**Tests**: `tests/v2/extractor_v2/test_pipeline.py`

```python
def extract_question_paper(
    pdf_path: Path,
    output_dir: Path,
    exam_code: str,
    *,
    config: Optional[ExtractionConfig] = None,
    markscheme_search_dirs: Optional[List[Path]] = None,
    diagnostics_collector: Optional[DiagnosticsCollector] = None,
) -> ExtractionResult:
    """Extract questions from a question paper PDF."""
```

### Detect Question Numerals
**Module**: `extractor_v2/detection/numerals.py`  
**Tests**: `tests/v2/extractor_v2/detection/test_numerals.py`

```python
def detect_question_numerals(
    doc: fitz.Document,
    header_ratio: float = 0.2,
    footer_ratio: float = 0.1
) -> list[QuestionNumeral]:
    """Find question number positions (1, 2, 3...)."""
```

### Detect Part Labels
**Module**: `extractor_v2/detection/parts.py`  
**Tests**: `tests/v2/extractor_v2/detection/test_parts.py`

```python
def detect_part_labels(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int,
    y_offset: int = 0,
    trim_offset: Tuple[int, int] = (0, 0),
) -> Tuple[List[PartLabel], List[PartLabel]]:
    """Detect (a), (b) letters and (i), (ii) roman numerals."""
```

### Detect Mark Boxes
**Module**: `extractor_v2/detection/marks.py`  
**Tests**: `tests/v2/extractor_v2/detection/test_marks.py`

```python
def detect_mark_boxes(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int,
    y_offset: int = 0,
    trim_offset: Tuple[int, int] = (0, 0),
) -> List[MarkBox]:
    """Detect [N] mark allocations in a page region."""
```

### Build Part Tree
**Module**: `extractor_v2/structuring/tree_builder.py`  
**Tests**: `tests/v2/extractor_v2/structuring/test_tree_builder.py`

```python
def build_part_tree(
    question_num: int,
    letters: list[PartLabel],
    romans: list[PartLabel],
    marks: list[MarkBox],
    composite_height: int,
    composite_width: int,
    exam_code: str,
    pdf_name: str,
    diagnostics_collector: Optional[DiagnosticsCollector] = None,
    text_extractor: Optional[Callable] = None,
) -> Part:
    """Build hierarchical Part tree from detections."""
```

### Calculate All Bounds
**Module**: `extractor_v2/slicing/bounds_calculator.py`  

```python
def calculate_all_bounds(
    parts: list[PartBounds],
    composite_height: int,
    composite_width: int,
    marks: list[MarkBox],
    config: SliceConfig,
    labels: list[PartLabel],
    numeral_bbox: Optional[tuple[int, int, int, int]] = None,
    exam_code: str = "unknown",
    pdf_name: str = "unknown",
    question_number: int = 0,
    diagnostics_collector: Optional[DiagnosticsCollector] = None,
) -> tuple[dict[str, SliceBounds], int]:
    """Determines vertical boundaries for every node."""
```

---

## Building Functions

### Build Exam
**Module**: `builder_v2/controller.py`  
**Tests**: `tests/v2/builder_v2/test_controller.py`

```python
def build_exam(config: BuilderConfig) -> BuildResult:
    """Build an exam from start to finish."""
```

### Load Questions
**Module**: `builder_v2/loading/loader.py`  
**Tests**: `tests/v2/builder_v2/loading/test_loader.py`

```python
def load_questions(
    cache_path: Path,
    exam_code: str,
    *,
    topics: Optional[List[str]] = None,
    years: Optional[List[int]] = None,
    papers: Optional[List[int]] = None,
) -> List[Question]:
    """Load all questions for an exam code."""
```

### Select Questions
**Module**: `builder_v2/selection/selector.py`  
**Tests**: `tests/v2/builder_v2/selection/test_selector.py`

```python
def select_questions(
    questions: List[Question],
    config: SelectionConfig,
) -> SelectionResult:
    """Select questions to meet mark target."""
```

### Compose Exam
**Module**: `builder_v2/layout/composer.py`  

```python
def compose_exam(
    result: SelectionResult,
    config: LayoutConfig,
    show_question_headers: bool = True,
) -> List[SliceAsset]:
    """Create assets for an entire exam selection."""
```

### Paginate
**Module**: `builder_v2/layout/paginator.py`  
**Tests**: `tests/v2/builder_v2/layout/test_paginator.py`

```python
def paginate(assets: list[SliceAsset], config: LayoutConfig) -> LayoutResult:
    """
    Arrange assets onto pages.
    
    Returns:
        LayoutResult with PagePlan for each page
        
    Algorithm:
        1. Place assets sequentially
        2. Check space availability
        3. Context slices stay with first child
        4. Start new page when full
    """
```

### Render to PDF
**Module**: `builder_v2/output/renderer.py`  
**Tests**: `tests/v2/builder_v2/output/test_renderer.py`

```python
def render_to_pdf(
    layout: LayoutResult,
    output_path: Path,
    *,
    dpi: int = 200,
    margin_left_px: int = 50
) -> None:
    """Render layout to PDF file."""
```

---

## Core Utilities

### Render PDF Pages
**Module**: `extractor_v2/utils/pdf.py`  
**Tests**: `tests/v2/extractor_v2/utils/test_pdf.py`

```python
def render_pdf_pages(
    pdf_path: Path,
    *,
    dpi: int = 200
) -> list[Image.Image]:
    """
    Render PDF pages to PIL images.
    
    Returns:
        List of Image objects at specified DPI
    """
```

### Extract Text from Page
**Module**: `extractor_v2/utils/text.py`  
**Tests**: Missing unit tests (covered by integration)

```python
def extract_text_spans(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int,
    y_offset: int = 0
) -> list[tuple[int, int, str]]:
    """
    Extract text spans with y-positions from a PDF page region.
    
    Returns:
        List of (y_top, y_bottom, text) tuples sorted by y_top
    """
```

### Crop Slice
**Module**: `builder_v2/images/cropper.py`  
**Tests**: `tests/v2/builder_v2/images/test_cropper.py`

```python
def crop_slice(
    composite: Image.Image,
    bounds: SliceBounds,
    *,
    add_mark_clearance: bool = False
) -> Image.Image:
    """
    Crop a slice from composite image.
    
    Args:
        composite: Full composite image
        bounds: Bounding box to crop
        add_mark_clearance: Add 10px padding below (for parts with marks)
        
    Returns:
        Cropped PIL Image
    """
```

---

## Selection Functions

### Generate Plan Options
**Module**: `builder_v2/selection/options.py`

```python
def generate_plan_options(question: Question) -> list[PlanOption]:
    """
    Generate all valid selection options for a question.
    
    Returns:
        List of PlanOption (full question + all part combinations)
    """
```

### Calculate Total Marks
**Module**: `core/models/part.py`

```python
@cached_property
def total_marks(self) -> int:
    """
    Calculate total marks from leaf parts.
    
    Returns:
        Sum of marks from all leaves
        
    Note:
        ALWAYS calculated, never stored
    """
```

---

## Keyword Functions

### Build Keyword Index
**Module**: `builder_v2/keyword/index.py`  
**Tests**: `tests/v2/builder_v2/keyword/test_keyword_index.py`

```python
def build_keyword_index(questions: list[Question]) -> KeywordIndex:
    """
    Build searchable keyword index from questions.
    
    Returns:
        KeywordIndex for fast searching
    """
```

### Search Keywords
**Module**: `builder_v2/keyword/index.py`

```python
def search(self, keywords: list[str]) -> SearchResult:
    """
    Search for questions matching keywords.
    
    Args:
        keywords: List of search terms
        
    Returns:
        SearchResult with matching questions and parts
    """
```

---

## Configuration Functions

### Validate Config
**Module**: `builder_v2/config.py`

```python
def __post_init__(self) -> None:
    """
    Validate configuration on construction.
    
    Raises:
        ValueError: If configuration invalid
    """
```

---

## Constants

### Page Dimensions
**Module**: `builder_v2/config.py`

```python
DEFAULT_PAGE_WIDTH_PX = 1654   # A4 width at 200 DPI
DEFAULT_PAGE_HEIGHT_PX = 2339  # A4 height at 200 DPI
DEFAULT_DPI = 200
```

### Spacing
**Module**: `builder_v2/layout/config.py`

```python
INTER_QUESTION_SPACING = 40  # px between questions
INTER_PART_SPACING = 20      # px between parts
```

### Bounds
**Module**: `builder_v2/images/cropper.py`

```python
MARK_BOX_CLEARANCE_PX = 10  # Padding below marks (layout only)
```

---

## See Also

- [Pipeline Documentation](pipelines.md) - How functions connect
- [Data Models](data-models.md) - Data structures
- [Testing Guide](testing.md) - Test examples
