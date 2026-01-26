# Builder V2 Documentation

The Builder V2 pipeline customizes exams by selecting and arranging questions.

## Pipeline Overview

1.  **Loading**: Reconstruct `Question` objects from cache.
2.  **Filtering**: Apply Year, Paper, Topic, and Keyword criteria.
3.  **Selection**: Knapsack-based question selection to hit mark targets.
4.  **Layout**: Crop slices and arrange them onto A4 pages.
5.  **Rendering**: Generate final PDF or ZIP outputs.

## Module Breakdown

### `loading/`
*   `loader.py`: Orchestrates loading from the filesystem.
*   `parser.py`: Low-level JSON parsing for metadata.
*   `reconstructor.py`: Builds the `Part` tree from flat JSON data.

### `selection/`
*   `selector.py`: The core selection algorithm.
*   `pruning.py`: Logic for removing parts of a question.
*   `part_mode.py`: Special logic for granular part-level selection.

### `layout/`
*   `composer.py`: Prepares image assets with context headers.
*   `paginator.py`: Arranges assets onto pages respecting margins.
*   `config.py`: Layout-specific settings (DPI, margins).

### `images/`
*   `provider.py`: High-level interface for getting images for questions.
*   `cropper.py`: Low-level PIL cropping and padding logic.

### `output/`
*   `renderer.py`: PDF generation using ReportLab.
*   `zip_writer.py`: Packages individual slices into a ZIP archive.
*   `markscheme.py`: Logic for generating the companion answer key.

### `keyword/`
*   `index.py`: Full-text search index for questions.
*   `models.py`: Keyword-specific data structures.
