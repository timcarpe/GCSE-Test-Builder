from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from gcse_toolkit.plugins.validation import (
    validate_manifest,
    verify_model,
    ManifestValidationError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicKeywordConfig:
    paper1: Dict[str, List[str]]
    paper2: Dict[str, List[str]]


class MissingResourcesError(RuntimeError):
    """Raised when the v2 resource bundle cannot be resolved."""


class UnsupportedCodeError(MissingResourcesError):
    """Raised when an exam code is not registered."""


@dataclass(frozen=True)
class ExamPlugin:
    code: str
    name: str
    subtopics_path: Path
    # TODO: hooks removed for security - see plugin_security_analysis.md
    options: Dict[str, Any]
    supported_years: List[str]  # Years of exams the plugin was trained on

    def load_topic_keywords(self) -> TopicKeywordConfig:
        from gcse_toolkit.common.topics import topic_patterns_from_subtopics

        patterns = topic_patterns_from_subtopics(self.code)
        if not patterns:
            raise MissingResourcesError(
                f"Exam {self.code} must embed topic patterns in topic_subtopics.json."
            )
        return TopicKeywordConfig(paper1=patterns, paper2=patterns)

    def load_evaluation_stats(self) -> Dict[str, Any]:
        """Load evaluation statistics if available."""
        # Assume report is in the same directory as subtopics
        report_path = self.subtopics_path.parent / "evaluation_report.json"
        
        if not report_path.exists():
            # Fallback to older name if needed or just return empty
            report_path = self.subtopics_path.parent / "evaluation_report_topics.json"
            
        if not report_path.exists():
            return {}
            
        try:
             # Handle possible encoding issues similar to other loaders
            try:
                text = report_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = report_path.read_text(encoding="utf-16")
            return json.loads(text)
        except (json.JSONDecodeError, IOError, OSError) as exc:
            logger.warning("Failed to load evaluation stats for %s: %s", self.code, exc)
            return {}

    def resolve_hook(self, name: str) -> Optional[Callable[..., Any]]:
        # TODO: Hooks disabled for security - see plugin_security_analysis.md
        _ = name  # unused
        return None


@dataclass(frozen=True)
class ExamResources:
    plugin: ExamPlugin
    topic_keywords: Any
    subtopics_path: Path
    # TODO: hooks removed for security
    options: Dict[str, Any]

    @property
    def code(self) -> str:
        return self.plugin.code

    def hook(self, name: str) -> Optional[Callable[..., Any]]:
        # TODO: Hooks disabled for security
        _ = name  # unused
        return None

    def option(self, name: str, default: Any = None) -> Any:
        return self.options.get(name, default)


def _get_user_plugins_dir() -> Path:
    """Get the user plugins directory (platform-specific).
    
    - macOS: ~/Documents/GCSE Test Builder/plugins/
    - Windows: %APPDATA%/GCSE Test Builder/plugins/
    """
    if sys.platform == "darwin":
        return Path.home() / "Documents" / "GCSE Test Builder" / "plugins"
    else:  # Windows
        return Path(os.environ.get("APPDATA", "")) / "GCSE Test Builder" / "plugins"

def _get_bundled_plugins_dir() -> Path:
    """Get the bundled plugins directory (in frozen app or source)."""
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "gcse_toolkit" / "plugins"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _load_manifest_generated_at(manifest_path: Path) -> Optional[str]:
    """Load the generated_at timestamp from a manifest.json file.
    
    Returns:
        ISO timestamp string, or None if not found/invalid.
    """
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return data.get("generated_at")
    except (json.JSONDecodeError, OSError):
        return None


def check_plugin_updates() -> List[Dict[str, Any]]:
    """Check for bundled plugins that are newer than installed versions.
    
    Compares the `generated_at` timestamp in manifests to determine
    which bundled plugins are newer than user-installed versions.
    
    Returns:
        List of dicts with keys: code, name, bundled_date, installed_date
        Only includes plugins where bundled version is newer.
    """
    if not getattr(sys, 'frozen', False):
        # Only relevant in frozen/compiled mode
        return []
    
    updates: List[Dict[str, Any]] = []
    user_plugins = _get_user_plugins_dir()
    bundled = _get_bundled_plugins_dir()
    
    if not bundled.exists() or not user_plugins.exists():
        return []
    
    for item in bundled.iterdir():
        if not item.is_dir():
            continue
        bundled_manifest = item / "manifest.json"
        if not bundled_manifest.exists():
            continue
        
        user_plugin = user_plugins / item.name
        user_manifest = user_plugin / "manifest.json"
        
        if not user_manifest.exists():
            # Plugin not installed yet - will be seeded normally
            continue
        
        bundled_date = _load_manifest_generated_at(bundled_manifest)
        installed_date = _load_manifest_generated_at(user_manifest)
        
        if not bundled_date:
            # Bundled plugin has no timestamp, can't compare
            continue
        
        # If installed has no date, or bundled is newer
        should_update = False
        if not installed_date:
            should_update = True
        elif bundled_date > installed_date:
            # ISO timestamps are lexicographically sortable
            should_update = True
        
        if should_update:
            # Load plugin name from manifest
            try:
                data = json.loads(bundled_manifest.read_text(encoding="utf-8"))
                name = data.get("name", item.name)
                code = data.get("code", item.name)
            except (json.JSONDecodeError, OSError):
                name = item.name
                code = item.name
            
            updates.append({
                "code": code,
                "name": name,
                "bundled_date": bundled_date,
                "installed_date": installed_date or "(unknown)",
            })
    
    return updates


def seed_plugins_from_bundle(force_update_codes: Optional[List[str]] = None) -> Path:
    """Copy bundled plugins to user directory with graceful error handling.
    
    Called on app startup. Copies plugins that don't already exist
    in the user directory. If force_update_codes is provided, those
    plugins will be overwritten even if they exist.
    
    Also ensures the models subfolder is copied if missing (for topic models).
    
    Args:
        force_update_codes: If provided, these plugin codes will be overwritten
                           even if they already exist in user directory.
    
    Returns:
        The user plugins directory path (may be bundled dir if user dir fails).
    """
    user_plugins = _get_user_plugins_dir()
    
    # Try to create user plugins directory
    try:
        user_plugins.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Cannot create user plugins directory: {e}")
        # Return bundled directory as read-only fallback
        return _get_bundled_plugins_dir()
    
    force_codes = set(force_update_codes or [])
    
    bundled = _get_bundled_plugins_dir()
    if not bundled.exists():
        return user_plugins
        
    for item in bundled.iterdir():
        if not item.is_dir() or not (item / "manifest.json").exists():
            continue
            
        dest = user_plugins / item.name
        should_force = item.name in force_codes
        
        try:
            if not dest.exists():
                # Full copy for new plugins
                shutil.copytree(item, dest)
            elif should_force:
                # Force update: remove old and copy new
                try:
                    shutil.rmtree(dest)
                except OSError as e:
                    logger.warning(f"Could not remove old plugin {item.name}: {e}")
                    continue
                shutil.copytree(item, dest)
                logger.info(f"Updated plugin: {item.name}")
            else:
                # Plugin exists - ensure models subfolder is present
                bundled_models = item / "models"
                dest_models = dest / "models"
                try:
                    if bundled_models.exists() and not dest_models.exists():
                        shutil.copytree(bundled_models, dest_models)
                    elif bundled_models.exists() and dest_models.exists():
                        # Copy individual model files that are missing
                        for model_file in bundled_models.iterdir():
                            dest_model = dest_models / model_file.name
                            if not dest_model.exists():
                                shutil.copy2(model_file, dest_model)
                except OSError as e:
                    logger.warning(f"Could not sync models for {item.name}: {e}")
        except OSError as e:
            logger.warning(f"Failed to seed plugin {item.name}: {e}")
            continue
    
    return user_plugins



def _get_resource_root() -> Path:
    """Get the appropriate plugins directory based on frozen state.
    
    Frozen mode: Use user plugins directory (seeded from bundle on first run)
    Dev mode: Use bundled plugins directly (no seeding needed)
    """
    if getattr(sys, 'frozen', False):
        # Frozen: use user plugins (which should be seeded on startup)
        return _get_user_plugins_dir()
    else:
        # Dev mode: use bundled plugins directly
        return _get_bundled_plugins_dir()


_RESOURCE_ROOT = _get_resource_root()


def _discover_plugins() -> tuple[Dict[str, ExamPlugin], Optional[str], Optional[str]]:
    """Discover and validate all plugins.
    
    Returns:
        Tuple of (registry, default_code, error_message).
        If error_message is not None, it indicates a non-fatal error that
        should be reported to the user but doesn't prevent operation.
    """
    global _RESOURCE_ROOT
    registry: Dict[str, ExamPlugin] = {}
    default_code: Optional[str] = None
    error_message: Optional[str] = None
    skipped_plugins: List[str] = []

    try:
        # In frozen mode, if user plugins dir doesn't exist, seed it from the bundle first
        if not _RESOURCE_ROOT.exists():
            if getattr(sys, 'frozen', False):
                # Fresh install - seed plugins from bundle before discovery
                try:
                    seed_plugins_from_bundle()
                    # Re-check after seeding
                    _RESOURCE_ROOT = _get_resource_root()
                except Exception as e:
                    logger.error(f"Failed to seed plugins: {e}")
                    # Fallback to bundled directory (read-only mode)
                    _RESOURCE_ROOT = _get_bundled_plugins_dir()
                    
                if not _RESOURCE_ROOT.exists():
                    error_message = f"No plugins directory found: {_RESOURCE_ROOT}"
                    return {}, None, error_message
            else:
                # Dev mode - this is a real error
                error_message = f"Resource directory missing: {_RESOURCE_ROOT}"
                return {}, None, error_message

        for entry in sorted(_RESOURCE_ROOT.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue
                
            # Validate manifest schema - per-plugin error handling
            try:
                validated = validate_manifest(manifest_path)
            except ManifestValidationError as exc:
                logger.warning(f"Skipping invalid plugin {entry.name}: {exc}")
                skipped_plugins.append(entry.name)
                continue  # Don't crash, skip this plugin
            except Exception as exc:
                logger.warning(f"Error loading plugin {entry.name}: {exc}")
                skipped_plugins.append(entry.name)
                continue

            code = validated.code
            name = validated.name
            subtopics_rel = validated.subtopics_path

            # Load options from raw manifest (validation doesn't cover options)
            try:
                raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                options = raw_manifest.get("options") or raw_manifest.get("overrides") or {}
                if not isinstance(options, dict):
                    options = {}
            except (json.JSONDecodeError, IOError, OSError) as exc:
                logger.debug("Could not load options from manifest %s: %s", manifest_path, exc)
                options = {}

            if code in registry:
                logger.warning(f"Duplicate exam code '{code}' - skipping {entry.name}")
                skipped_plugins.append(entry.name)
                continue

            subtopics_path = (entry / subtopics_rel).resolve()
            supported_years = validated.supported_years
            plugin = ExamPlugin(
                code=code,
                name=name,
                subtopics_path=subtopics_path,
                options=options,
                supported_years=supported_years,
            )
            registry[code] = plugin
            if validated.default:
                default_code = code

        if not registry:
            error_message = f"No valid plugins found in {_RESOURCE_ROOT}"
            if skipped_plugins:
                error_message += f"\nSkipped plugins with errors: {', '.join(skipped_plugins)}"
            return {}, None, error_message
            
        if skipped_plugins:
            error_message = f"Some plugins could not be loaded: {', '.join(skipped_plugins)}"
            
        if not default_code or default_code not in registry:
            default_code = sorted(registry.keys())[0]
            
    except Exception as e:
        logger.error(f"Plugin discovery failed: {e}")
        error_message = f"Plugin discovery failed: {e}"
        return {}, None, error_message
        
    return registry, default_code, error_message


# Lazy initialization - plugins are NOT discovered at import time
# This prevents CTD if the plugins directory is missing/corrupted
_PLUGINS: Dict[str, ExamPlugin] = {}
_DEFAULT_CODE: Optional[str] = None
_INIT_ERROR: Optional[str] = None
_INITIALIZED = False


def _ensure_initialized() -> None:
    """Ensure plugin registry is initialized.
    
    Called automatically by all public functions that access plugins.
    Stores any initialization error for later retrieval.
    """
    global _PLUGINS, _DEFAULT_CODE, _INIT_ERROR, _INITIALIZED
    if not _INITIALIZED:
        _PLUGINS, _DEFAULT_CODE, _INIT_ERROR = _discover_plugins()
        _INITIALIZED = True


def get_initialization_error() -> Optional[str]:
    """Return any error that occurred during plugin initialization.
    
    Returns None if initialization succeeded without errors.
    Returns error message string if there were issues.
    """
    _ensure_initialized()
    return _INIT_ERROR


def list_exam_plugins() -> Iterable[ExamPlugin]:
    _ensure_initialized()
    return _PLUGINS.values()


def supported_exam_codes() -> list[str]:
    _ensure_initialized()
    return sorted(_PLUGINS.keys())


def default_exam_code() -> str:
    _ensure_initialized()
    return _DEFAULT_CODE


def get_exam_plugin(code: Optional[str]) -> ExamPlugin:
    _ensure_initialized()
    if not code:
        code = _DEFAULT_CODE
    plugin = _PLUGINS.get(code)
    if not plugin:
        raise UnsupportedCodeError(f"Unsupported exam code: {code}")
    return plugin


def resolve_subtopics_path(code: Optional[str]) -> Path:
    plugin = get_exam_plugin(code)
    if not plugin.subtopics_path.exists():
        raise MissingResourcesError(f"Missing sub-topic mapping for exam {plugin.code}: {plugin.subtopics_path}")
    return plugin.subtopics_path


@lru_cache(maxsize=None)
def load_topic_keywords(code: Optional[str]) -> TopicKeywordConfig:
    plugin = get_exam_plugin(code)
    return plugin.load_topic_keywords()


@lru_cache(maxsize=None)
def load_exam_resources(code: Optional[str]) -> ExamResources:
    plugin = get_exam_plugin(code)
    topic_keywords = load_topic_keywords(code)
    # TODO: hooks removed for security
    return ExamResources(
        plugin=plugin,
        topic_keywords=topic_keywords,
        subtopics_path=plugin.subtopics_path,
        options=dict(plugin.options),
    )


@lru_cache(maxsize=None)
def load_exam_stats(code: Optional[str]) -> Dict[str, Any]:
    """Load evaluation stats for the given exam code."""
    plugin = get_exam_plugin(code)
    return plugin.load_evaluation_stats()
