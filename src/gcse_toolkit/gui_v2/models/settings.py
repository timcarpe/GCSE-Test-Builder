"""
Settings persistence model for GUI v2.
Adapted from v1 SettingsStore.

This module handles all persistent GUI state with robust error handling.
Any malformed data should result in graceful fallback to defaults, never CTD.
"""
import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from gcse_toolkit.common import canonical_sub_topic_label, resolve_topic_label

logger = logging.getLogger(__name__)

@dataclass
class ExamSettings:
    topics: List[str]
    target_marks: int
    tolerance: int
    seed: int
    output_dir: Optional[str]
    sub_topics: Dict[str, List[str]] = field(default_factory=dict)
    filter_mode: str = "Topics"
    keywords: List[str] = field(default_factory=list)
    keyword_pins: List[str] = field(default_factory=list)
    # Part selection mode: 0=All, 1=Prune, 2=Skip
    part_mode: int = 2  # Default to Skip (most permissive)
    force_topic_representation: bool = True
    # Export options
    output_format: str = "pdf"           # "pdf", "zip", or "both"
    include_markschemes: bool = True
    selected_year: Optional[str] = None  # e.g., "2023" or None for "All Years"
    selected_papers: Optional[List[int]] = None  # e.g., [1, 2] or None for "All Papers"
    show_labels: bool = True
    allow_keyword_backfill: bool = True
    schema_version: int = 2

from PySide6.QtCore import QObject, Signal

class SettingsStore(QObject):
    """Lightweight JSON-backed store for persisting GUI preferences."""
    
    metadataRootChanged = Signal(str)
    CURRENT_VERSION = 4  # v4: Add global show_footer setting

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.data: Dict[str, object] = {}
        self._load_error: Optional[str] = None
        
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                self._migrate()
            except json.JSONDecodeError as e:
                self._load_error = f"Settings file is corrupted:\n{e}"
                self.data = {}
            except Exception as e:
                self._load_error = f"Failed to read settings:\n{e}"
                self.data = {}
        
        # Ensure version is set for new files
        if "version" not in self.data:
            self.data["version"] = self.CURRENT_VERSION
    
    def check_load_error(self) -> bool:
        """
        Check if there was an error loading settings and prompt user to reset.
        
        Returns True if app should continue, False if app should exit.
        Call this after QApplication is created.
        """
        if not self._load_error:
            return True
        
        from PySide6.QtWidgets import QMessageBox
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Settings Error")
        msg.setText("Your GUI settings file could not be loaded.")
        msg.setInformativeText(
            f"{self._load_error}\n\n"
            "Would you like to reset settings to defaults and continue?"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            # Reset was already done by setting self.data = {}
            self._save()  # Write empty settings
            self._load_error = None
            return True
        else:
            return False

    def _migrate(self) -> None:
        """Handle settings compatibility based on app version.
        
        If the settings were created by a different major.minor version,
        clear exam-specific settings to prevent crashes from schema changes.
        """
        stored_version = self.data.get("app_version", "0.0.0")
        current_version = self._get_app_version()
        
        # Compare major.minor (first two parts)
        stored_parts = stored_version.split(".")[:2]
        current_parts = current_version.split(".")[:2]
        
        if stored_parts != current_parts:
            # Major or minor version changed - clear exam settings to prevent crashes
            if "exams" in self.data:
                del self.data["exams"]
        
        # Always update to current app version
        self.data["app_version"] = current_version
        self._save()
    
    def _get_app_version(self) -> str:
        """Get current app version string."""
        try:
            from gcse_toolkit import __version__
            return __version__
        except ImportError:
            return "0.0.0"

    def get_metadata_root(self) -> Optional[str]:
        return self._get_dict().get("metadata_root")  # type: ignore[return-value]

    def set_metadata_root(self, value: str) -> None:
        state = self._get_dict()
        state["metadata_root"] = value
        self._save()
        self.metadataRootChanged.emit(value)

    def get_pdf_input_path(self) -> Optional[str]:
        return self._get_dict().get("pdf_input_path")  # type: ignore[return-value]

    def set_pdf_input_path(self, value: str) -> None:
        state = self._get_dict()
        state["pdf_input_path"] = value
        self._save()

    def get_exam_settings(self, exam_code: str) -> Optional[ExamSettings]:
        """Get exam settings with robust error handling.
        
        Returns None if settings don't exist or are malformed.
        Never raises exceptions - all errors result in None return.
        """
        try:
            exams = self._get_dict().setdefault("exams", {})  # type: ignore[assignment]
            raw = exams.get(exam_code)
            if not isinstance(raw, dict):
                return None
                
            # Parse sub-topics with defensive handling
            sub_topics_payload = raw.get("sub_topics")
            sub_topics: Dict[str, List[str]] = {}
            if isinstance(sub_topics_payload, dict):
                for topic, values in sub_topics_payload.items():
                    try:
                        canonical_topic = resolve_topic_label(str(topic), exam_code) if topic else None
                        if not canonical_topic:
                            continue
                        items = values if isinstance(values, list) else [values]
                        mapped: List[str] = []
                        seen: set[str] = set()
                        for item in items:
                            label = canonical_sub_topic_label(canonical_topic, item, exam_code)
                            if label and label not in seen:
                                mapped.append(label)
                                seen.add(label)
                        if mapped:
                            sub_topics[canonical_topic] = mapped
                    except Exception as e:
                        logger.debug(f"Skipping malformed sub-topic {topic}: {e}")
                        continue
                        
            # Parse topics with defensive handling
            topic_list = []
            topics_raw = raw.get("topics", [])
            if isinstance(topics_raw, list):
                for topic in topics_raw:
                    try:
                        canonical_topic = resolve_topic_label(str(topic), exam_code) if topic else None
                        if canonical_topic:
                            topic_list.append(canonical_topic)
                    except Exception:
                        continue
                    
            filter_mode = str(raw.get("filter_mode") or "Topics")
            
            # Parse keywords with defensive handling
            keywords_payload = raw.get("keywords") or []
            keyword_list = []
            if isinstance(keywords_payload, list):
                keyword_list = [str(entry).strip() for entry in keywords_payload if isinstance(entry, str) and entry.strip()]
            
            pinned_payload = raw.get("keyword_pins") or []
            pin_list = []
            if isinstance(pinned_payload, list):
                pin_list = [str(entry).strip() for entry in pinned_payload if isinstance(entry, str) and entry.strip()]
            
            # Migrate from old allow_pruning/allow_skipping to part_mode
            part_mode = raw.get("part_mode")
            if part_mode is None:
                # Backward compatibility: convert old settings
                allow_pruning = raw.get("allow_pruning", True)
                allow_skipping = raw.get("allow_skipping", True)
                if not allow_pruning:
                    part_mode = 0  # ALL
                elif not allow_skipping:
                    part_mode = 1  # PRUNE
                else:
                    part_mode = 2  # SKIP
            
            # Safe integer/bool conversions with defaults
            return ExamSettings(
                topics=topic_list,
                target_marks=self._safe_int(raw.get("target_marks"), 40),
                tolerance=self._safe_int(raw.get("tolerance"), 2),
                seed=self._safe_int(raw.get("seed"), random.randint(1, 99999)),
                output_dir=raw.get("output_dir") if isinstance(raw.get("output_dir"), str) else None,
                sub_topics=sub_topics,
                filter_mode=filter_mode,
                keywords=keyword_list,
                keyword_pins=pin_list,
                part_mode=self._safe_int(part_mode, 2),
                force_topic_representation=bool(raw.get("force_topic_representation", True)),
                output_format=str(raw.get("output_format", "pdf")),
                include_markschemes=bool(raw.get("include_markschemes", True)),
                selected_year=raw.get("selected_year") if isinstance(raw.get("selected_year"), str) else None,
                selected_papers=raw.get("selected_papers") if isinstance(raw.get("selected_papers"), list) else None,
                show_labels=bool(raw.get("show_labels", True)),
                allow_keyword_backfill=bool(raw.get("allow_keyword_backfill", True)),
                schema_version=self._safe_int(raw.get("schema_version"), 2),
            )
        except Exception as e:
            logger.warning(f"Failed to load exam settings for {exam_code}: {e}")
            return None
    
    def _safe_int(self, value: Any, default: int) -> int:
        """Safely convert a value to int, returning default on failure."""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def set_exam_settings(self, exam_code: str, settings: ExamSettings) -> None:
        exams: Dict[str, Dict[str, object]] = self._get_dict().setdefault("exams", {})  # type: ignore[assignment]
        exams[exam_code] = {
            "topics": settings.topics,
            "target_marks": settings.target_marks,
            "tolerance": settings.tolerance,
            "seed": settings.seed,
            "output_dir": settings.output_dir,
            "sub_topics": settings.sub_topics,
            "filter_mode": "Topics",  # Force Topics to prevent startup crash
            "keywords": [],  # Do not save keywords
            "keyword_pins": [],  # Do not save pins
            "part_mode": settings.part_mode,
            "force_topic_representation": settings.force_topic_representation,
            "output_format": settings.output_format,
            "include_markschemes": settings.include_markschemes,
            "selected_year": settings.selected_year,
            "selected_papers": settings.selected_papers,
            "show_labels": settings.show_labels,
            "allow_keyword_backfill": settings.allow_keyword_backfill,
            "schema_version": settings.schema_version,
        }
        self._save()

    def get_main_tab(self) -> Optional[int]:
        # v1 uses string names, v2 uses index (0 or 1)
        # We'll map string to int if present, or return int
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        val = ui.get("main_tab_v2") # Use separate key for v2 to avoid conflict if types differ
        return val if isinstance(val, int) else 0

    def set_main_tab(self, tab_index: int) -> None:
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        ui["main_tab_v2"] = tab_index
        self._save()

    def get_filter_tab(self) -> Optional[str]:
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        val = ui.get("filter_tab")
        return val if isinstance(val, str) else None

    def set_filter_tab(self, tab: str) -> None:
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        # Force Topics if Keywords is selected to prevent startup crash
        if tab == "Keywords":
            tab = "Topics"
        ui["filter_tab"] = tab
        self._save()

    def get_selected_exam_code(self) -> Optional[str]:
        """Get the last selected exam code for the build tab."""
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        val = ui.get("selected_exam_code")
        return val if isinstance(val, str) else None

    def set_selected_exam_code(self, exam_code: str) -> None:
        """Save the selected exam code for the build tab."""
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        ui["selected_exam_code"] = exam_code
        self._save()

    def get_extractor_options(self) -> Dict[str, object]:
        raw = self._get_dict().get("extractor_options", {})
        if isinstance(raw, dict):
            return dict(raw)
        return {}

    def set_extractor_options(self, options: Dict[str, object]) -> None:
        state = self._get_dict()
        state["extractor_options"] = options
        self._save()
        
    def get_debug_overlay(self) -> bool:
        # v1 stores this in extractor_options I think? 
        # "Current flags: --debug-marks"
        # Let's check get_extractor_options
        opts = self.get_extractor_options()
        return bool(opts.get("--debug-marks", False))

    def set_debug_overlay(self, enabled: bool) -> None:
        opts = self.get_extractor_options()
        opts["--debug-marks"] = enabled
        self.set_extractor_options(opts)

    def get_window_geometry(self) -> Optional[str]:
        """Get saved window geometry with hex validation.
        
        Returns None if geometry is missing or invalid hex.
        """
        geo = self._get_dict().get("window_geometry")
        if not isinstance(geo, str):
            return None
        # Validate hex string format
        try:
            bytes.fromhex(geo)
            return geo
        except (ValueError, TypeError):
            logger.warning("Invalid geometry string in settings, ignoring")
            return None

    def set_window_geometry(self, geometry: str) -> None:
        state = self._get_dict()
        state["window_geometry"] = geometry
        self._save()

    def get_splitter_state(self) -> Optional[str]:
        """Get saved splitter state with hex validation.
        
        Returns None if state is missing or invalid hex.
        """
        state = self._get_dict().get("splitter_state")
        if not isinstance(state, str):
            return None
        try:
            bytes.fromhex(state)
            return state
        except (ValueError, TypeError):
            logger.warning("Invalid splitter state in settings, ignoring")
            return None

    def set_splitter_state(self, state: str) -> None:
        data = self._get_dict()
        data["splitter_state"] = state
        self._save()

    def get_dark_mode(self) -> bool:
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        return bool(ui.get("dark_mode", True))

    def set_dark_mode(self, enabled: bool) -> None:
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        ui["dark_mode"] = enabled
        self._save()

    def has_seen_tutorial(self) -> bool:
        """Check if user has completed or skipped the first-launch tutorial."""
        return bool(self._get_dict().get("tutorial_seen", False))

    def set_tutorial_seen(self, seen: bool = True) -> None:
        """Mark the tutorial as seen."""
        self._get_dict()["tutorial_seen"] = seen
        self._save()

    def get_run_diagnostics(self) -> bool:
        """Get whether to run extraction diagnostics (default: False)."""
        opts = self.get_extractor_options()
        return bool(opts.get("run_diagnostics", False))

    def set_run_diagnostics(self, enabled: bool) -> None:
        """Set whether to run extraction diagnostics."""
        opts = self.get_extractor_options()
        opts["run_diagnostics"] = enabled
        self.set_extractor_options(opts)

    def get_show_footer(self) -> bool:
        """Get whether to show footer in generated PDFs (default: True)."""
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        return bool(ui.get("show_footer", True))

    def set_show_footer(self, enabled: bool) -> None:
        """Set whether to show footer in generated PDFs."""
        ui = self._get_dict().setdefault("ui", {})  # type: ignore[assignment]
        ui["show_footer"] = enabled
        self._save()

    def _get_dict(self) -> Dict[str, object]:
        if not isinstance(self.data, dict):
            self.data = {}
        return self.data  # type: ignore[return-value]

    def _save(self) -> None:
        """Safely write settings with atomic replacement.
        
        Uses a temp file to prevent corruption if write is interrupted.
        """
        temp_path = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temp file first
            temp_path = self.path.with_suffix('.tmp')
            temp_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            
            # Atomic rename (overwrites existing)
            temp_path.replace(self.path)
        except OSError as e:
            logger.warning(f"Failed to save settings: {e}")
            # Clean up temp file if it exists
            if temp_path:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except OSError:
                    pass
        except Exception as e:
            logger.warning(f"Unexpected error saving settings: {e}")
            if temp_path:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except OSError:
                    pass
