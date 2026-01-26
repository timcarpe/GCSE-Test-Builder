# Exam Plugin System

The GCSE Test Builder uses a plugin-based architecture for multi-exam support.

## Plugin Structure
Located in `src/gcse_toolkit/plugins/{code}/`:
*   **`manifest.json`**: Metadata (name, code, version, supported years).
*   **`topic_subtopics.json`**: Keyword patterns used by `extractor_v2` for classification.
*   **`models/`**: Serialized ML models for sub-topic prediction.

## Core Logic (`src/gcse_toolkit/plugins/`)
*   **`__init__.py`**:
    *   `seed_plugins_from_bundle()`: Copies bundled plugins to the user's documents directory on first run.
    *   `_discover_plugins()`: Dynamically loads and registers all valid plugins.
    *   `check_plugin_updates()`: Compares `generated_at` timestamps to suggest updates.
*   **`validation.py`**: Enforces strict schema validation for `manifest.json` to prevent application crashes from corrupted plugins.

## Creating a Plugin
Plugins are typically generated using the `scripts/Plugin Generation` tools. They require a syllabus structure (`topic_subtopics.json`) and a set of training data for the classification models.

## Security
For security, all execution hooks are disabled. Plugins are data-only and cannot execute arbitrary code.
