# GUI V2 Architecture

The GUI V2 is a modern desktop interface built with **PySide6**. It follows a strictly decoupled architecture.

## Directory Structure

*   **`widgets/`**: Reusable UI components. Includes specialized modules like `extraction_overlay.py`, `builder_overlay.py`, `topic_selector.py`, and `console_widget.py`.
*   **`services/`**: logic for interacting with the backend.
    *   `keyword_service.py`: Manages asynchronous keyword search and indexing.
*   **`models/`**:
    *   `settings.py`: Persistent application configuration using `QSettings`.
*   **`styles/`**:
    *   `theme.py`: Defines color palettes and iconography.
    *   `icons/`: SVG/PNG assets.
*   **`utils/`**:
    *   `icons.py`: Centralized icon loading.
    *   `paths.py`: GUI-specific path resolution.
    *   `popup_queue.py`: Thread-safe notification system.
    *   `crashlog.py`: Error reporting and logging utilities.

## Key Components

### `MainWindow` (`main_window.py`)
Matches the PySide6 `QMainWindow`. It orchestrates the primary tabs (Extraction, Build, Options) and manages the status bar and global overlays.

### `app.py`
The application entry point. Handles high-DPI scaling, CSS application, and initial resource seeding.

## Design Patterns
*   **Worker Threads**: Heavy operations (extraction/building) are run via `QThread` or `QRunnable` to maintain 60fps UI responsiveness.
*   **Dynamic Styling**: UI colors are dynamically updated based on the `theme.py` definitions.
