# Extractor V2 Documentation

The Extractor V2 pipeline is responsible for converting PDF question papers into structured JSON data and image slices.

## Pipeline Overview

1.  **PDF Rendering**: Convert PDF pages to images.
2.  **Text Extraction**: Extract text and positions.
3.  **Component Detection**: Find numbers, parts, and marks.
4.  **Structure Building**: Build the `Part` hierarchy.
5.  **Bounds Calculation**: Calculate pixel bonding boxes.
6.  **Output Generation**: Save metadata and composite images.

## Module Breakdown

### `detection/`
*   `numerals.py`: Detects question numbers (1, 2, 3...).
*   `parts.py`: Detects sub-part labels ((a), (b), (i), (ii)...).
*   `marks.py`: Detects mark boxes ([2], [3]).

### `structuring/`
*   `tree_builder.py`: Assembles flat detections into a `Part` hierarchy.

### `slicing/`
*   `bounds_calculator.py`: Calculates vertical territory for each part.
*   `compositor.py`: Creates the single `composite.png` for a question.
*   `offset_calculator.py`: Handles vertical alignment between pages.
*   `writer.py`: Saves `regions.json`, `metadata.json`, and images.

### `utils/`
*   `pdf.py`: PDF rendering using PyMuPDF.
*   `text.py`: OCR and text processing.
*   `topic_model.py`: Topic classification logic.
*   `visualizer.py`: Debugging utilities for painting bounds.

## Key Features
*   **Composite Storage**: Stores one image per question instead of dozens of tiny slices.
*   **Precision**: Uses decimal-aware bounding boxes for seamless stitching.
*   **Invariants**: Enforces strict vertical ordering and mark aggregation.
