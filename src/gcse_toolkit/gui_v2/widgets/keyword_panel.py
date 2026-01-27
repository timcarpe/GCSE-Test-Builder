"""
Keyword search panel for the Build tab.
Allows users to search for questions by keyword patterns.
"""

import logging
from pathlib import Path
from typing import List, Set, Dict, Optional, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QScrollArea, QFrame, QTextEdit, QCheckBox, QProgressBar,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, Slot, QSize, QThread
from PySide6.QtGui import QTextCharFormat, QFont, QColor

from gcse_toolkit.gui_v2.styles.theme import Colors, Fonts, Styles, get_colors, get_styles
from gcse_toolkit.gui_v2.widgets.console_widget import ConsoleWidget
from gcse_toolkit.builder_v2.keyword.models import KeywordSearchResult
from gcse_toolkit.core.models import Question
from gcse_toolkit.gui_v2.models.settings import SettingsStore
from gcse_toolkit.gui_v2.utils.icons import MaterialIcons
from gcse_toolkit.gui_v2.utils.tooltips import apply_tooltip
# V2 keyword service and helpers
from gcse_toolkit.gui_v2.services import KeywordSearchService
from gcse_toolkit.gui_v2.utils.question_helpers import find_part_by_label
import re
from .image_tooltip import ImageTooltip
from .toggle_switch import ToggleSwitch

logger = logging.getLogger(__name__)

class KeywordPanel(QWidget):
    """
    Keyword search panel with dynamic keyword rows, preview, and matched questions display.
    """
    
    preview_started = Signal()
    preview_completed = Signal()
    stateChanged = Signal()
    
    def __init__(self, console: Optional[ConsoleWidget] = None, parent=None):
        super().__init__(parent)
        
        self.console = console  # Reference to console for logging
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(12)
        
        # Get current theme colors
        C = get_colors()
        
        # Info Label
        self.info_label = QLabel(
            "Search plain text keywords. Pin questions to force them into generated exam. Remaining questions to meet mark target are pulled from the preview window matches."
        )
        self.info_label.setWordWrap(True)
        self.layout.addWidget(self.info_label)
        
        # Keyword Rows Container
        self.rows_container = QFrame()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        self.rows_container.setStyleSheet("background-color: transparent;")
        self.layout.addWidget(self.rows_container)
        
        # Common style override for keyword buttons to fit 32px height
        # We override hover/pressed states to prevent the "lift" effect from shifting text
        btn_style_override = """
            QPushButton { font-size: 12px; padding: 4px 16px; margin: 0px; }
            QPushButton:hover { margin: 0px; padding: 4px 16px; }
            QPushButton:pressed { margin: 0px; padding: 4px 16px; }
        """
        
        # Add Keyword Button
        self.add_btn = QPushButton("Keyword")
        self.add_btn.setIcon(MaterialIcons.plus(color=Colors.TEXT_PRIMARY))
        self.add_btn.setIconSize(QSize(16, 16))
        self.add_btn.setStyleSheet(Styles.BUTTON_SECONDARY + btn_style_override)
        self.add_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.add_btn.setFixedHeight(32)
        self.add_btn.clicked.connect(self._add_keyword_row)
        self.layout.addWidget(self.add_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Preview Button & Status
        preview_frame = QFrame()
        preview_frame.setStyleSheet("background-color: transparent;")
        preview_layout = QHBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)
        
        self.preview_btn = QPushButton("Preview Keywords")
        self.preview_btn.setIcon(MaterialIcons.magnify())
        self.preview_btn.setIconSize(QSize(16, 16))
        # Add transparent border to match secondary button sizing
        preview_override = btn_style_override + "QPushButton { border: 1px solid transparent; }"
        self.preview_btn.setStyleSheet(Styles.BUTTON_PRIMARY + preview_override)
        self.preview_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.preview_btn.setFixedHeight(32)
        self.preview_btn.clicked.connect(self._on_preview_clicked)
        preview_layout.addWidget(self.preview_btn)
        
        self.clear_btn = QPushButton("Clear Results")
        self.clear_btn.setIcon(MaterialIcons.close())
        self.clear_btn.setIconSize(QSize(16, 16))
        self.clear_btn.setStyleSheet(Styles.BUTTON_SECONDARY + btn_style_override)
        self.clear_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.clear_btn.setFixedHeight(32)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        preview_layout.addWidget(self.clear_btn)
        
        self.preview_status = QLabel("")
        self.preview_status.setStyleSheet(f"color: {C.TEXT_SECONDARY};")
        preview_layout.addWidget(self.preview_status)
        
        preview_layout.addStretch()
        
        # Backfill Toggle (Moved to BuildTab)
        # self.backfill_label = QLabel("Backfill")
        # self.backfill_toggle = ToggleSwitch()
        
        self.layout.addWidget(preview_frame)
        
        # Matched Questions Label
        self.matches_label = QLabel("Matched questions (updates after preview):")
        self.matches_label.setStyleSheet(f"font-weight: {Fonts.WEIGHT_MEDIUM}; background-color: transparent;")
        self.layout.addWidget(self.matches_label)
        
        # Matched Questions View
        self.matches_scroll = QScrollArea()
        self.matches_scroll.setWidgetResizable(True)
        self.matches_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.matches_scroll.setStyleSheet("background-color: transparent;")
        
        self.matches_container = QWidget()
        self.matches_container.setStyleSheet("background-color: transparent;")
        self.matches_layout = QVBoxLayout(self.matches_container)
        self.matches_layout.setContentsMargins(0, 0, 0, 0)
        self.matches_layout.setSpacing(8)
        
        self.matches_scroll.setWidget(self.matches_container)
        self.layout.addWidget(self.matches_scroll, stretch=1)
        
        # State
        self.keyword_rows: List[Dict] = []
        self.current_exam: Optional[str] = None
        self.metadata_root: Optional[Path] = None
        self.keyword_service: Optional[KeywordSearchService] = None
        
        # Year and paper filters (set by BuildTab)
        self.year_filter: Optional[List[int]] = None  # None = all years
        self.paper_filter: Optional[List[int]] = None  # None = all papers
        
        # Results storage  
        self.preview_results: Dict[str, Set[str]] = {}  # keyword -> question IDs
        self.preview_label_results: Dict[str, Dict[str, Set[str]]] = {}  # keyword -> qid -> labels
        self.result_aggregate_labels: Dict[str, Set[str]] = {}  # qid -> set of matched labels
        self.result_questions: Dict[str, Question] = {}  # qid -> V2 Question
        self.pin_vars: Dict[str, QCheckBox] = {}  # "qid::label" -> checkbox
        self.preview_running = False
        self.search_worker = None  # Track search worker thread for cleanup
        self.pin_worker = None  # Track pin loading worker thread for cleanup

        
        # Add initial row
        self._add_keyword_row()
        
        # Tooltip
        self.tooltip = ImageTooltip(self)
        
        # Cache composite pixmaps by question ID
        self._pixmap_cache: Dict[str, 'QPixmap'] = {}

        # Apply initial theme
        self.update_theme()
        
        # Connect destroyed signal to ensure cleanup when widget is destroyed
        self.destroyed.connect(self.cleanup)

    def cleanup(self) -> None:
        """Clean up resources before widget destruction."""
        # Wait for any running search worker to finish
        if self.search_worker is not None and self.search_worker.isRunning():
            self.search_worker.wait(1000)  # Wait up to 1 second
            self.search_worker = None
        # Wait for any running pin worker to finish
        if self.pin_worker is not None and self.pin_worker.isRunning():
            self.pin_worker.wait(1000)
            self.pin_worker = None

    def update_theme(self):
        """Update styles when theme changes."""
        C = get_colors()
        S = get_styles()
        
        # Update Info Label
        self.info_label.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-size: {Fonts.SMALL}; background-color: transparent;")
        
        # Update Buttons
        btn_style_override = """
            QPushButton { font-size: 12px; padding: 4px 16px; margin: 0px; }
            QPushButton:hover { margin: 0px; padding: 4px 16px; }
            QPushButton:pressed { margin: 0px; padding: 4px 16px; }
        """
        self.add_btn.setStyleSheet(S.BUTTON_SECONDARY + btn_style_override)
        self.add_btn.setIcon(MaterialIcons.plus(color=C.TEXT_PRIMARY))
        
        preview_override = btn_style_override + "QPushButton { border: 1px solid transparent; }"
        self.preview_btn.setStyleSheet(S.BUTTON_PRIMARY + preview_override)
        
        self.clear_btn.setStyleSheet(S.BUTTON_SECONDARY + btn_style_override)
        
        self.preview_status.setStyleSheet(f"color: {C.TEXT_SECONDARY};")
        self.matches_label.setStyleSheet(f"font-weight: {Fonts.WEIGHT_MEDIUM}; background-color: transparent;")
        
        # Update Rows
        for row in self.keyword_rows:
            row["entry"].setStyleSheet(S.INPUT_FIELD)
            row["count_label"].setStyleSheet(f"color: {C.SUCCESS}; font-weight: {Fonts.WEIGHT_BOLD};")
            row["matches_text"].setStyleSheet(f"color: {C.TEXT_SECONDARY};")
            
            # Update Remove Button - use object name for higher specificity
            row["remove_btn"].setObjectName("removeKeywordBtn")
            row["remove_btn"].setStyleSheet(f"""
                QPushButton#removeKeywordBtn {{
                    background-color: transparent;
                    color: {C.ERROR};
                    border: 1px solid {C.ERROR};
                    border-radius: 14px;
                    font-weight: bold;
                    font-size: 16px;
                    padding-bottom: 2px;
                }}
                QPushButton#removeKeywordBtn:hover {{
                    background-color: {C.HOVER};
                }}
                QPushButton#removeKeywordBtn:pressed {{
                    background-color: {C.HOVER};
                }}
                QPushButton#removeKeywordBtn:disabled {{
                    color: {C.TEXT_PRIMARY};
                    border-color: {C.TEXT_PRIMARY};
                }}
            """)
            
        # Refresh matches view to update its styles
        self._refresh_matches_view()
    
    def set_exam_context(self, exam_code: str, metadata_root: Path, force_refresh: bool = False):
        """Set the exam context for keyword searches."""
        self.current_exam = exam_code
        self.metadata_root = metadata_root
        
        # Initialize service if needed
        if self.keyword_service is None:
            self.keyword_service = KeywordSearchService(metadata_root)
            logger.debug(f"Initialized KeywordSearchService for {metadata_root}")
        elif force_refresh:
            # Clear cache on force refresh
            self.keyword_service.clear_cache(exam_code)
            logger.debug(f"Cleared cache for {exam_code}")
    
    def set_filters(
        self, 
        years: Optional[List[int]] = None, 
        papers: Optional[List[int]] = None
    ) -> None:
        """
        Set year and paper filters for keyword search results.
        
        When filters are set, preview results will only show questions
        matching the specified years and/or papers.
        
        Args:
            years: List of years to include, or None for all years
            papers: List of paper numbers to include, or None for all papers
        """
        self.year_filter = years
        self.paper_filter = papers
        logger.debug(f"Keyword panel filters set: years={years}, papers={papers}")
    
    def _add_keyword_row(self, value: str = "", count: int = 0, progress: int = 0):
        """Add a new keyword row."""
        # Get current theme colors
        C = get_colors()
        
        row_data = {
            "id": f"row_{len(self.keyword_rows)}",
            "value": value,
            "count": count,
            "progress": progress
        }
        # Ensure value is a string (in case called with wrong type)
        if not isinstance(value, str):
            value = ""
        
        row_frame = QFrame()
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_frame.setStyleSheet("background-color: transparent;")
        
        # Remove button (far left)
        remove_btn = QPushButton("−")  # U+2212 Minus Sign
        remove_btn.setFixedSize(28, 28)
        # Circular red button style
        # Circular red button style - will be set by update_theme or initial creation
        # We set a temporary style here, but update_theme will override it immediately
        # Use object name for higher CSS specificity to override global stylesheet
        remove_btn.setObjectName("removeKeywordBtn")
        remove_btn.setStyleSheet(f"""
            QPushButton#removeKeywordBtn {{
                background-color: transparent;
                color: {C.ERROR};
                border: 1px solid {C.ERROR};
                border-radius: 14px;
                font-weight: bold;
                font-size: 16px;
                padding-bottom: 2px;
            }}
            QPushButton#removeKeywordBtn:hover {{
                background-color: {C.HOVER};
            }}
            QPushButton#removeKeywordBtn:pressed {{
                background-color: {C.HOVER};
            }}
            QPushButton#removeKeywordBtn:disabled {{
                color: {C.TEXT_PRIMARY};
                border-color: {C.TEXT_PRIMARY};
            }}
        """)
        remove_btn.clicked.connect(lambda: self._remove_keyword_row(row_data))
        row_layout.addWidget(remove_btn)
        
        # Keyword entry
        entry = QLineEdit(value)
        entry.setStyleSheet(get_styles().INPUT_FIELD)
        entry.setPlaceholderText("Enter keyword")
        entry.textChanged.connect(lambda _: self.stateChanged.emit())
        entry.returnPressed.connect(self._on_preview_clicked)
        row_layout.addWidget(entry)
        
        # Status frame (count + progress) - floats right after entry
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(4)
        status_frame.setFixedWidth(100)  # Reduced from 150 for more compact appearance
        
        count_label = QLabel("")
        count_label.setFixedWidth(30)
        count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        count_label.setStyleSheet(f"color: {C.SUCCESS}; font-weight: {Fonts.WEIGHT_BOLD};")
        status_layout.addWidget(count_label)
        
        matches_text = QLabel("matches")
        matches_text.setStyleSheet(f"color: {C.TEXT_SECONDARY};")
        matches_text.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        matches_text.setVisible(False)  # Initially hidden until we have a count
        status_layout.addWidget(matches_text)
        
        progress = QProgressBar()
        progress.setMaximum(0)  # Indeterminate
        progress.setFixedHeight(16)
        progress.setVisible(False)
        status_layout.addWidget(progress)
        
        row_layout.addWidget(status_frame)
        
        # Track row
        row_data = {
            "frame": row_frame,
            "entry": entry,
            "remove_btn": remove_btn,
            "count_label": count_label,
            "matches_text": matches_text,
            "progress": progress,
            "last_value": None,
        }
        self.keyword_rows.append(row_data)
        self.rows_layout.addWidget(row_frame)
        
        # Sync remove button states
        self._sync_remove_buttons()
    
    def _remove_keyword_row(self, row_data: Dict):
        """Remove a keyword row."""
        if len(self.keyword_rows) <= 1:
            return
        
        self.keyword_rows.remove(row_data)
        row_data["frame"].deleteLater()
        self._sync_remove_buttons()
        self.stateChanged.emit()
    
    def _sync_remove_buttons(self):
        """Enable/disable remove buttons based on row count."""
        disabled = len(self.keyword_rows) <= 1
        for row in self.keyword_rows:
            row["remove_btn"].setEnabled(not disabled)

    def _on_clear_clicked(self):
        """Clear all accumulated results and pins."""
        self.preview_results.clear()
        self.preview_label_results.clear()
        self.result_questions.clear()
        self.pin_vars.clear()
        self._pixmap_cache.clear()
        
        # Reset UI counts
        for row in self.keyword_rows:
            row["count_label"].setText("")
            row["matches_text"].setVisible(False)
            row["last_value"] = None
            
        self.preview_status.setText("Results cleared.")
        if self.console:
            self.console.append_log("INFO", "Cleared all keyword search results and pins.")
            
        self._refresh_matches_view()
        self.stateChanged.emit()

    class SearchWorker(QThread):
        """Background thread for keyword search to avoid blocking UI."""
        result_ready = Signal(object, list)  # EnrichedKeywordResult, keywords
        error_occurred = Signal(str)   # Error message
        
        def __init__(self, keyword_service: KeywordSearchService, exam_code: str, keywords: List[str]):
            super().__init__()
            self.keyword_service = keyword_service
            self.exam_code = exam_code
            self.keywords = keywords
        
        def run(self):
            """Execute search in background."""
            try:
                result = self.keyword_service.search(self.exam_code, self.keywords)
                self.result_ready.emit(result, self.keywords)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.error_occurred.emit(str(e))

    def _on_preview_clicked(self):
        """Handle preview button click."""
        if self.preview_running:
            return
        
        if not self.current_exam or not self.metadata_root:
            self.preview_status.setText("Please select an exam first.")
            return
        
        # CRITICAL: Ensure keyword_index is initialized
        if not self.keyword_service:
            self.preview_status.setText("Select an exam first")
            if self.metadata_root:
                self.keyword_service = KeywordSearchService(self.metadata_root)
            else:
                self.preview_status.setText("Failed to initialize keyword service: metadata_root is missing.")
                return
        
        keywords = self.get_current_keywords()
        if not keywords:
            self.preview_status.setText("Enter at least one keyword to preview.")
            return
        
        # Check schema version
        from gcse_toolkit.gui_v2.utils.helpers import _questions_json_path
        import json
        
        path = _questions_json_path(self.metadata_root, self.current_exam)
        if not path:
            self.preview_status.setText("No metadata found for this exam.")
            return
        
        # Check schema version
        schema_version = 1
        try:
            with path.open('r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        # Support both new and legacy schema version keys
                        schema_version = int(data.get('schema_version', data.get('_schema_version', 1)))
                        break
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        
        if schema_version < 5:
            self.preview_status.setText("This exam's metadata predates schema v5. Re-run the extractor.")
            return
        
        # Log search start
        if self.console:
            self.console.append_log("INFO", f"Starting keyword search for exam: {self.current_exam}")
            self.console.append_log("INFO", f"Keywords: {', '.join(keywords)}")
        
        # Start preview
        self.preview_running = True
        self.preview_status.setText("Searching…")
        self.preview_btn.setEnabled(False)
        
        # Show progress on all rows
        for row in self.keyword_rows:
            row["count_label"].setText("…")
            row["progress"].setVisible(True)
        
        # Run search in background thread
        self.search_worker = self.SearchWorker(self.keyword_service, self.current_exam, keywords)
        self.search_worker.result_ready.connect(self._apply_preview_results)
        self.search_worker.error_occurred.connect(self._preview_error)
        
        # Clean up reference when done
        self.search_worker.finished.connect(lambda: setattr(self, 'search_worker', None))
        
        self.search_worker.start()
    
    def _apply_preview_results(self, result: KeywordSearchResult, keywords: List[str]):
        """Apply preview results to UI, respecting year/paper filters."""
        try:
            # 0. Apply year/paper filters to the result
            result = self._filter_results_by_year_paper(result)
            
            # 1. Identify currently pinned QIDs
            pinned_ids = self.get_pinned_ids()
            pinned_qids = set()
            for pid in pinned_ids:
                if "::" in pid:
                    pinned_qids.add(pid.split("::")[0])
                else:
                    pinned_qids.add(pid)
            
            # 2. Preserve data for pinned questions
            preserved_questions = {}
            preserved_labels = {}  # keyword -> qid -> labels
            
            # Keep pinned questions
            for qid in pinned_qids:
                if qid in self.result_questions:
                    preserved_questions[qid] = self.result_questions[qid]
            
            # Keep pinned labels (we need to find which keyword they came from, or just keep them all for that qid)
            # Since we don't track which keyword produced a pin easily without scanning, 
            # we'll just preserve the label structure for pinned QIDs across all keywords.
            for kw, label_map in self.preview_label_results.items():
                for qid, labels in label_map.items():
                    if qid in pinned_qids:
                        if kw not in preserved_labels:
                            preserved_labels[kw] = {}
                        preserved_labels[kw][qid] = labels
            
            # 3. Replace current results with NEW results + PRESERVED pinned data
            self.result_questions = result.questions.copy()
            self.result_questions.update(preserved_questions)
            
            self.preview_results = result.keyword_hits.copy()
            # Note: We don't necessarily need to force preserved QIDs into preview_results (keyword->qids)
            # because that drives the counts. If a keyword is removed, its count should be gone.
            # But if a keyword is still there, we want its count to be accurate to the search.
            
            self.preview_label_results = result.keyword_label_hits.copy()
            # Merge back preserved labels
            for kw, label_map in preserved_labels.items():
                if kw not in self.preview_label_results:
                    self.preview_label_results[kw] = {}
                for qid, labels in label_map.items():
                    if qid not in self.preview_label_results[kw]:
                        self.preview_label_results[kw][qid] = set()
                    self.preview_label_results[kw][qid].update(labels)
            
            # Log results
            if self.console:
                total_questions = len(self.result_questions)
                new_questions = len(result.questions)
                self.console.append_log("INFO", f"Search complete: {new_questions} new matches. Total unique: {total_questions} (including pins)")
            
            # Update counts
            zero_count_keywords = []
            for row in self.keyword_rows:
                value = row["entry"].text().strip()
                row["progress"].setVisible(False)
                
                if value in keywords:
                    # Count from the NEW search results only for accuracy
                    count = len(result.keyword_hits.get(value, set()))
                    row["count_label"].setText(str(count))
                    row["matches_text"].setVisible(True)
                    row["last_value"] = value
                    if count == 0:
                        zero_count_keywords.append(value)
                else:
                    row["count_label"].setText("")
                    row["matches_text"].setVisible(False)
                    row["last_value"] = None
            
            # Update status
            if zero_count_keywords:
                status_msg = f"No matches for: {', '.join(zero_count_keywords)}"
                self.preview_status.setText(status_msg)
                if self.console:
                    self.console.append_log("WARNING", status_msg)
            else:
                self.preview_status.setText("Preview updated. Counts shown next to each keyword.")
                if self.console:
                    # Log individual keyword counts for clarity
                    for row in self.keyword_rows:
                        value = row.get("last_value")
                        if value:
                            count = len(result.keyword_hits.get(value, set()))
                            self.console.append_log("INFO", f"Keyword '{value}': {count} matches")
            
            # Refresh matched questions view
            self._refresh_matches_view()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            if self.console:
                self.console.append_log("ERROR", f"Error applying preview results: {e}")
            self.preview_status.setText(f"Error: {e}")
            
        finally:
            # Re-enable preview
            self.preview_running = False
            self.preview_btn.setEnabled(True)
    
    def _preview_error(self, error: str):
        """Handle preview error."""
        self.preview_status.setText(f"Preview failed: {error}")
        self.preview_running = False
        self.preview_btn.setEnabled(True)
        
        for row in self.keyword_rows:
            row["progress"].setVisible(False)
            row["count_label"].setText("")
            row["matches_text"].setVisible(False)
    
    def _filter_results_by_year_paper(self, result: KeywordSearchResult) -> KeywordSearchResult:
        """
        Filter search results by year and paper filters.
        
        Args:
            result: Original search result from keyword service
            
        Returns:
            Filtered result with only questions matching the year/paper filters
        """
        # If no filters are active, return as-is
        if self.year_filter is None and self.paper_filter is None:
            return result
        
        # Identify which question IDs pass the filter
        passing_qids = set()
        for qid, question in result.questions.items():
            year_ok = self.year_filter is None or question.year in self.year_filter
            paper_ok = self.paper_filter is None or question.paper in self.paper_filter
            if year_ok and paper_ok:
                passing_qids.add(qid)
        
        # If all pass (or none filtered), return as-is
        if len(passing_qids) == len(result.questions):
            return result
        
        # Log filter effect
        filtered_count = len(result.questions) - len(passing_qids)
        if filtered_count > 0:
            logger.debug(f"Year/paper filter removed {filtered_count} questions from preview")
        
        # Filter questions dict
        filtered_questions = {
            qid: q for qid, q in result.questions.items() 
            if qid in passing_qids
        }
        
        # Filter keyword_hits (keyword -> set of qids)
        filtered_hits = {}
        for kw, qids in result.keyword_hits.items():
            filtered_hits[kw] = qids & passing_qids
        
        # Filter keyword_label_hits (keyword -> qid -> labels)
        filtered_label_hits = {}
        for kw, qid_labels in result.keyword_label_hits.items():
            filtered_label_hits[kw] = {
                qid: labels for qid, labels in qid_labels.items()
                if qid in passing_qids
            }
        
        # Filter aggregate_labels (qid -> labels)
        filtered_aggregate = {
            qid: labels for qid, labels in result.aggregate_labels.items()
            if qid in passing_qids
        }
        
        # Import here to avoid circular imports
        from gcse_toolkit.gui_v2.services.keyword_service import EnrichedKeywordResult
        
        return EnrichedKeywordResult(
            keyword_hits=filtered_hits,
            keyword_label_hits=filtered_label_hits,
            aggregate_labels=filtered_aggregate,
            questions=filtered_questions,
        )
    
    def _refresh_matches_view(self):
        """Refresh the matched questions view."""
        import shiboken6
        
        # Save the checked state of all existing checkboxes before clearing
        saved_pin_states = {}
        for pin_key, checkbox in self.pin_vars.items():
            try:
                if shiboken6.isValid(checkbox):
                    saved_pin_states[pin_key] = checkbox.isChecked()
            except RuntimeError:
                pass
        
        # Clear existing UI widgets
        while self.matches_layout.count():
            child = self.matches_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Clear the pin_vars dictionary (we'll recreate checkboxes with saved states)
        self.pin_vars.clear()
        
        # Build question_by_id mapping for cascading pin logic
        self.question_by_id = {qid: q for qid, q in self.result_questions.items()}
        
        # Get colors for styling
        C = get_colors()
        
        if not self.result_questions:
            label = QLabel("Preview keywords to populate this list.")
            label.setStyleSheet(f"color: {C.TEXT_SECONDARY};")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.matches_layout.addWidget(label)
            return
        
        # Helper to check if a QID has any pins
        def is_pinned(qid):
            # Check saved states because pin_vars is cleared
            for key, checked in saved_pin_states.items():
                if checked and (key == qid or key.startswith(f"{qid}::")):
                    return True
            return False

        # Sort questions: Pinned first, then by QID
        sorted_qids = sorted(
            self.result_questions.keys(),
            key=lambda q: (not is_pinned(q), q) # False < True, so pinned (False for 'not pinned') comes first
        )
        
        # Show matched questions
        for qid in sorted_qids:
            question = self.result_questions[qid]
            
            # Find matched labels for this question
            matched_labels = set()
            for label_map in self.preview_label_results.values():
                labels = label_map.get(qid, set())
                matched_labels.update(labels)
            
            # Create question container (no border, minimal padding)
            card = QFrame()
            # Highlight pinned cards slightly
            bg_color = C.SURFACE
            if is_pinned(qid):
                bg_color = getattr(C, 'PINNED_BG', C.SELECTION_BG)
                
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border: 1px solid {C.DIVIDER};
                    border-radius: 6px;
                    padding: 0px;
                }}
            """)
            card_layout = QVBoxLayout(card)

            # Question ID (e.g., "Q11" or "Q8(a)") - small, subtle
            # Format: s24_qp_13_q3 -> S24 QP 13
            formatted_code = qid
            parts = qid.split('_')
            if len(parts) >= 3:
                formatted_code = f"{parts[0].upper()} {parts[1].upper()} {parts[2].upper()}"
            
            code_label = QLabel(formatted_code)
            code_label = QLabel(formatted_code)
            C = get_colors()
            code_label.setStyleSheet(f"color: {C.PRIMARY_BLUE}; font-size: {Fonts.SMALL}; border: none; background: transparent;")
            card_layout.addWidget(code_label)
            
            # Sort labels to ensure consistent display
            sorted_labels = sorted(matched_labels)

            # Show each matched label with pin checkbox
            for label in sorted_labels:
                part_frame = QFrame()
                part_layout = QVBoxLayout(part_frame)
                part_layout.setContentsMargins(0, 4, 0, 4)
                part_layout.setSpacing(4)
                
                # Determine indentation: check if this part is a child of any other matched part
                is_child = False
                current_part_node = question.get_part(label)
                if current_part_node:
                    for other_label in matched_labels:
                        if other_label == label:
                            continue
                        other_part = question.get_part(other_label)
                        if other_part:
                            # Check if current_part is in other_part's descendants
                            for descendant in other_part.iter_all():
                                if descendant == current_part_node and descendant != other_part:
                                    is_child = True
                                    break
                        if is_child:
                            break
                
                # Apply indentation for children
                if is_child:
                    part_frame.setStyleSheet(f"background-color: transparent; border: none; margin-left: 10px;")
                else:
                    part_frame.setStyleSheet(f"background-color: transparent; border: none;")
                
                # Header row: label on left, checkbox on right
                header_row = QWidget()
                header_row_layout = QHBoxLayout(header_row)
                header_row_layout.setContentsMargins(0, 0, 0, 0)
                header_row_layout.setSpacing(8)
                
                # Question label (e.g., "Q3(a)")
                display_label = label
                marks_suffix = ""
                
                # Try to find marks for this part
                part = question.get_part(label)
                if part:
                    marks = part.total_marks
                    if marks is not None:
                        # Style marks in medium grey and normal weight
                        marks_suffix = f" <span style='color: {C.TEXT_SECONDARY}; font-weight: normal;'>[{marks}]</span>"
                
                label_text = QLabel(display_label + marks_suffix)
                label_text.setStyleSheet(f"font-weight: {Fonts.WEIGHT_BOLD}; font-size: 13pt;")
                # Show pin emoji next to label if this specific part is pinned
                pin_key = f"{qid}::{label}"
                if pin_key in saved_pin_states and saved_pin_states[pin_key]:
                    label_text.setText(display_label + marks_suffix + " 📌")
                header_row_layout.addWidget(label_text)
                
                header_row_layout.addStretch()
                
                # Pin checkbox (no text label)
                pin_cb = QCheckBox()
                pin_cb.setStyleSheet(get_styles().CHECKBOX)
                
                # Restore previous checked state if it existed
                if pin_key in saved_pin_states:
                    pin_cb.setChecked(saved_pin_states[pin_key])
                
                # Store checkbox in pin_vars for cascading logic
                self.pin_vars[pin_key] = pin_cb
                
                # Connect the toggled signal to our handler
                pin_cb.toggled.connect(lambda checked, k=pin_key: self._on_pin_toggled(k, checked))
                
                # Enable hover for tooltip
                pin_cb.setMouseTracking(True)
                pin_cb.setProperty("qid", qid)
                pin_cb.setProperty("label", label)
                pin_cb.installEventFilter(self)
                
                header_row_layout.addWidget(pin_cb)
                
                part_layout.addWidget(header_row)
                
                # Text snippet (no border)
                keywords_for_snippet = self.get_current_keywords()
                snippet_html = self._generate_snippet(question, label, keywords_for_snippet)
                
                snippet = QLabel(snippet_html)
                C = get_colors()
                snippet.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-size: 13pt; padding: 4px 0;")
                snippet.setWordWrap(True)
                snippet.setTextFormat(Qt.TextFormat.RichText)
                part_layout.addWidget(snippet)
                
                card_layout.addWidget(part_frame)
            
            self.matches_layout.addWidget(card)
        
        self.matches_layout.addStretch()
    
    def get_current_keywords(self) -> List[str]:
        """Get list of current non-empty keywords."""
        keywords = []
        for row in self.keyword_rows:
            value = row["entry"].text().strip()
            if value:
                keywords.append(value)
        return keywords
    
    def get_pinned_ids(self) -> Set[str]:
        """Get set of pinned question::label IDs."""
        import shiboken6
        pinned = set()
        for pin_key, checkbox in list(self.pin_vars.items()):
            # Check if the C++ object still exists before accessing it
            try:
                if shiboken6.isValid(checkbox) and checkbox.isChecked():
                    pinned.add(pin_key)
            except RuntimeError:
                # Widget was deleted, skip it
                pass
        return pinned
    
    def set_keywords(self, keywords: List[str], pins: List[str]):
        """Set keywords and pins from settings."""
        # Clear existing rows
        for row in self.keyword_rows[:]:
            row["frame"].deleteLater()
        self.keyword_rows.clear()
        
        # Add rows for keywords
        if keywords:
            for kw in keywords:
                self._add_keyword_row(kw)
        else:
            self._add_keyword_row()
        
        # Store saved pins
        self.saved_pins = set(pins)
        
        # Determine if we should auto-preview
        should_preview = bool(keywords) and self.current_exam and self.keyword_service
        
        if self.saved_pins and self.current_exam and self.keyword_service:
            if should_preview:
                self._auto_preview_pending = True
            self._load_pinned_questions()
        elif should_preview:
            # No pins to load, but we have keywords, so preview immediately
            QTimer.singleShot(100, self._on_preview_clicked)

    # Backfill methods removed - relocated to BuildTab

    def _on_pin_toggled(self, key: str, checked: bool):
        """Handle pin checkbox toggles, including cascading to children."""
        from PySide6.QtCore import QSignalBlocker
        
        # Initialize saved_pins if not exists
        if not hasattr(self, 'saved_pins'):
            self.saved_pins = set()
        
        # Update the specific pin
        if checked:
            self.saved_pins.add(key)
        else:
            self.saved_pins.discard(key)
            
        # Cascade to children using metadata
        if "::" in key:
            qid, label = key.split("::", 1)
            
            # Find the question
            question = self.question_by_id.get(qid) if hasattr(self, 'question_by_id') else None
            if not question:
                return
            
            # Get the part
            part = question.get_part(label)
            if not part:
                # Try stripping whitespace
                part = question.get_part(label.strip())
                if not part:
                    return
            
            # Get all descendant labels (excluding self)
            descendant_labels = set()
            for descendant in part.iter_all():
                if descendant != part:
                    descendant_labels.add(descendant.label)
            
            if not descendant_labels:
                return
            
            # Update checkboxes for descendants
            for other_key, cb in self.pin_vars.items():
                if "::" not in other_key:
                    continue
                    
                other_qid, other_label = other_key.split("::", 1)
                
                if other_qid == qid:
                    is_match = other_label in descendant_labels
                    is_match_stripped = other_label.strip() in descendant_labels
                    
                    if is_match or is_match_stripped:
                        # Update UI using QSignalBlocker (best practice)
                        with QSignalBlocker(cb):
                            cb.setChecked(checked)
                        
                        # Update saved pins
                        if checked:
                            self.saved_pins.add(other_key)
                        else:
                            self.saved_pins.discard(other_key)
        
        self.stateChanged.emit()
    
    def eventFilter(self, obj, event):
        """Handle hover events for pin checkboxes."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QCursor, QPixmap
        
        if event.type() == QEvent.Enter:
            qid = obj.property("qid")
            label = obj.property("label")
            
            if qid and label:
                # Find question
                question = self.question_by_id.get(qid) if hasattr(self, 'question_by_id') else None
                if question:
                    # Cache composite pixmap
                    if qid not in self._pixmap_cache:
                        if question.composite_path and question.composite_path.exists():
                            self._pixmap_cache[qid] = QPixmap(str(question.composite_path))
                    
                    # Get bounds for this specific part
                    bounds = question.get_bounds(label)
                    if qid in self._pixmap_cache and bounds:
                        self.tooltip.show_region(
                            self._pixmap_cache[qid],
                            bounds,
                            QCursor.pos()
                        )
                        return True
                        
        elif event.type() == QEvent.Leave:
            self.tooltip.hide()
            
        return super().eventFilter(obj, event)


    class LoadPinsWorker(QThread):
        """Background thread for loading pinned question data."""
        result_ready = Signal(object)  # Dict[str, Question]
        
        def __init__(self, keyword_service: KeywordSearchService, exam_code: str, pins: Set[str]):
            super().__init__()
            self.keyword_service = keyword_service
            self.exam_code = exam_code
            self.pins = pins
        
        def run(self):
            """Load question data for pinned items."""
            try:
                # Extract unique question IDs from pins
                question_ids = set()
                for pin in self.pins:
                    qid = pin.split("::")[0] if "::" in pin else pin
                    question_ids.add(qid)
                
                # Since service has questions cached, get them from cache
                # Empty keyword search will return empty but we can access cache
                self.keyword_service._ensure_exam_loaded(self.exam_code)
                questions_list = self.keyword_service._questions_cache.get(self.exam_code, [])
                
                # Filter to just the pinned questions
                loaded_questions = {}
                for question in questions_list:
                    if question.id in question_ids:
                        loaded_questions[question.id] = question
                
                self.result_ready.emit(loaded_questions)
            except Exception:
                pass


    def _load_pinned_questions(self):
        """Load question data for pinned items."""
        if not self.saved_pins or not self.keyword_service or not self.current_exam:
            return
        
        self.pin_worker = self.LoadPinsWorker(self.keyword_service, self.current_exam, self.saved_pins)
        self.pin_worker.result_ready.connect(self._apply_pinned_questions)
        self.pin_worker.finished.connect(lambda: setattr(self, 'pin_worker', None))
        self.pin_worker.start()

    def _apply_pinned_questions(self, questions: Dict[str, Question]):
        """Merge pinned questions into results and refresh view."""
        # Merge questions
        self.result_questions.update(questions)
        
        # Ensure labels are present in preview_label_results
        # Note: preview_label_results is keyword -> qid -> labels
        # For pinned items, we create a synthetic "__pinned__" keyword entry
        for pin in self.saved_pins:
            if "::" in pin:
                qid, label = pin.split("::", 1)
                if qid in self.result_questions:
                    if "__pinned__" not in self.preview_label_results:
                        self.preview_label_results["__pinned__"] = {}
                    if qid not in self.preview_label_results["__pinned__"]:
                        self.preview_label_results["__pinned__"][qid] = set()
                    self.preview_label_results["__pinned__"][qid].add(label)
        
        self._refresh_matches_view()
        
        # Check the boxes
        for pin_key in self.saved_pins:
            if pin_key in self.pin_vars:
                self.pin_vars[pin_key].setChecked(True)
                
        # Trigger pending preview if any
        if getattr(self, '_auto_preview_pending', False):
            self._auto_preview_pending = False
            QTimer.singleShot(100, self._on_preview_clicked)

    def _generate_snippet(self, question: Question, label: str, keywords: List[str]) -> str:
        """Generate a HTML snippet with highlighted keywords."""
        # Get text blob - use specific label's text, or fall back to root text only
        blob = ""
        if label and question.child_text and label in question.child_text:
            # Use specific child text for the label
            blob = question.child_text[label]
        else:
            # Fall back to root text only (don't aggregate all children)
            blob = question.root_text or ""
            
        if not blob:
            return "(No text available)"
            
        # Clean blob (remove excessive whitespace and repeating dots)
        blob = " ".join(blob.split())
        # Remove repeating dots/periods (e.g., "...." or "......")
        blob = re.sub(r'\.{2,}', '', blob)
        # Remove [##] artifacts
        blob = re.sub(r'\[\d+\]', '', blob)
        
        # Remove leading question labels like (a), (b), (i), (ii)
        # Matches (a) or (i) at the start of the string, with optional whitespace
        blob = re.sub(r'^\s*\([a-zA-Z0-9]+\)\s*', '', blob)
        
        # Find first matching keyword to center on
        hit_keyword = None
        match = None
        
        for kw in keywords:
            if not kw: continue
            # Simple regex for the keyword
            try:
                pattern = re.compile(re.escape(kw), re.IGNORECASE)
                m = pattern.search(blob)
                if m:
                    hit_keyword = kw
                    match = m
                    break
            except re.error:
                continue
                
        if match:
            start = max(0, match.start() - 60)
            end = min(len(blob), match.end() + 60)
            
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(blob) else ""
            
            segment = blob[start:end]
            
            # Highlight all keywords in the segment
            for kw in keywords:
                if not kw: continue
                try:
                    # Use a replacement with styling
                    # We need to be careful not to replace inside HTML tags if we had them, 
                    # but here we are building HTML.
                    # Case insensitive replacement is tricky with simple replace.
                    # We use regex sub.
                    p = re.compile(f"({re.escape(kw)})", re.IGNORECASE)
                    segment = p.sub(r'<span style="background-color: #FFFFAA; font-weight: bold; color: #000000;">\1</span>', segment)
                except re.error:
                    pass
            
            return f"{prefix}{segment}{suffix}"
        else:
            # No match found in text (maybe matched in metadata or another part?)
            # Just return start of blob
            snippet = blob[:150] + ("..." if len(blob) > 150 else "")
            return snippet
