"""
Build Exams Tab (Screen B)
"""
import sys
import threading
import subprocess
import platform
from typing import List, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox, QComboBox, QScrollArea, QFrame, QStackedWidget, QTabWidget, QMessageBox, QFileDialog, QSizePolicy,
    QProgressBar
)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer, QSize, Signal, QPropertyAnimation
from PySide6.QtGui import QIcon, QPixmap
import base64

from gcse_toolkit.common import get_exam_definition, UnsupportedCodeError
from gcse_toolkit.common import resolve_topic_label, canonical_sub_topic_label
from gcse_toolkit.gui_v2.styles.theme import Colors, Styles, Fonts, apply_shadow, get_colors, get_styles
from gcse_toolkit.gui_v2.widgets.topic_selector import TopicSelector
from gcse_toolkit.gui_v2.widgets.keyword_panel import KeywordPanel
from gcse_toolkit.gui_v2.widgets.console_widget import ConsoleWidget
from gcse_toolkit.gui_v2.widgets.segmented_button import SegmentedButton
from gcse_toolkit.gui_v2.widgets.toggle_switch import ToggleSwitch
from gcse_toolkit.gui_v2.widgets.three_state_button import ThreeStateButtonGroup
from gcse_toolkit.gui_v2.widgets.multi_select_year_filter import MultiSelectYearFilter
from gcse_toolkit.gui_v2.widgets.multi_select_paper_filter import MultiSelectPaperFilter
from gcse_toolkit.gui_v2.models.settings import SettingsStore
from gcse_toolkit.gui_v2.utils.helpers import discover_exam_codes
from gcse_toolkit.gui_v2.utils.tooltips import apply_tooltip
from gcse_toolkit.gui_v2.utils.icons import MaterialIcons
from gcse_toolkit.gui_v2.widgets.builder_overlay import BuilderOverlay

import queue

class BuildTab(QWidget):
    # Signal to communicate from worker thread to main thread
    # success, error_message
    generation_finished = Signal(bool, object)
    ui_locked = Signal(bool)

    def __init__(self, console: Optional[ConsoleWidget] = None, settings: Optional[SettingsStore] = None, log_queue: Optional[queue.Queue] = None, parent=None):
        super().__init__(parent)
        self.console = console or ConsoleWidget()
        if settings is None:
            from gcse_toolkit.gui_v2.utils.paths import get_settings_path
            self.settings = SettingsStore(get_settings_path())
        else:
            self.settings = settings
        self.log_queue = log_queue or queue.Queue()
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(24)
        
        # --- Left Column: Filter Tabs (Topics/Keywords) ---
        self.left_column = QWidget()
        self.left_layout = QVBoxLayout(self.left_column)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)
        
        # Segmented Toggle
        self.filter_toggle = SegmentedButton("Topics", "Keywords")
        self.filter_toggle.valueChanged.connect(self._on_filter_mode_changed)
        self.left_layout.addWidget(self.filter_toggle)
        
        # Stacked Content
        self.filter_stack = QStackedWidget()
        
        # Topics View
        self.topic_selector = TopicSelector()
        # Wrap in a frame for padding/border if needed, but selector has its own scroll
        self.filter_stack.addWidget(self.topic_selector)
        
        # Keywords View
        self.keyword_panel = KeywordPanel(console=console)
        self.filter_stack.addWidget(self.keyword_panel)
        
        self.left_layout.addWidget(self.filter_stack)
        
        # Add frame styling to the stack container if desired
        # Add frame styling to the stack container if desired
        C = get_colors()
        self.filter_stack.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {C.SURFACE};
                border: 1px solid {C.BORDER};
                border-top: none; /* Connected to toggle */
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 12px; /* Added padding as requested */
            }}
        """)
        
        self.layout.addWidget(self.left_column, stretch=1)
        
        # --- Right Column: Exam Generation Controls ---
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 12)
        self.right_layout.setSpacing(16)
        
        # Exam Name Label (displayed above selector)
        self.exam_name_label = QLabel("")
        C = get_colors()
        self.exam_name_label.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-size: 14px; font-weight: {Fonts.WEIGHT_MEDIUM};")
        self.right_layout.addWidget(self.exam_name_label)
        
        
        # Exam Code Row
        self.exam_row = QWidget()
        self.exam_layout = QHBoxLayout(self.exam_row)
        self.exam_layout.setContentsMargins(0, 0, 0, 0)
        self.exam_layout.setSpacing(8)

        exam_label = QLabel("Choose Exam Code:")
        exam_label.setFixedWidth(140)
        self.exam_layout.addWidget(exam_label)
        apply_tooltip(exam_label, "Select which extracted exam set to build from")
        
        self.exam_combo = QComboBox()
        self.exam_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.exam_combo.setStyleSheet(Styles.COMBOBOX)
        self.exam_combo.currentIndexChanged.connect(self._on_exam_changed)
        self.exam_layout.addWidget(self.exam_combo)
        apply_tooltip(self.exam_combo, "Select which extracted exam set to build from")

        # Year Filter Dropdown (Multi-Select with Checkboxes)
        self.year_filter = MultiSelectYearFilter()
        self.year_filter.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.year_filter.setStyleSheet(get_styles().COMBOBOX)
        self.year_filter.selectionChanged.connect(self._on_year_filter_changed)
        self.exam_layout.addWidget(self.year_filter)
        apply_tooltip(self.year_filter, "Filter questions by exam year (multi-select)")

        # Paper Filter Dropdown (Multi-Select with Checkboxes)
        self.paper_filter = MultiSelectPaperFilter()
        self.paper_filter.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.paper_filter.setStyleSheet(get_styles().COMBOBOX)
        self.paper_filter.selectionChanged.connect(self._on_paper_filter_changed)
        self.exam_layout.addWidget(self.paper_filter)
        apply_tooltip(self.paper_filter, "Filter questions by paper number (multi-select)")

        # Reload button (icon-only, matching dice button)
        self.reload_btn = QPushButton("")
        self.reload_btn.setIcon(MaterialIcons.refresh())
        self.reload_btn.setIconSize(QSize(24, 24))
        self.reload_btn.setFixedSize(40, 40)
        self.reload_btn.setStyleSheet(Styles.BUTTON_SECONDARY)
        self.reload_btn.clicked.connect(self._refresh_exam_codes)
        self.exam_layout.addWidget(self.reload_btn)
        apply_tooltip(self.reload_btn, "Re-scan the metadata root for extracted exam sets")
        
        # Removed addStretch() to allow year_filter to expand to the reload button
        self.right_layout.addWidget(self.exam_row)
        
        # Configuration Container (Split 50/50)
        config_container = QWidget()
        config_layout = QHBoxLayout(config_container)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(24)

        # Left Column: Inputs
        left_config_widget = QWidget()
        left_config_layout = QVBoxLayout(left_config_widget)
        left_config_layout.setContentsMargins(0, 0, 0, 0)
        left_config_layout.setSpacing(16)
        
        # Right Column: Toggles
        right_config_widget = QWidget()
        right_config_layout = QVBoxLayout(right_config_widget)
        right_config_layout.setContentsMargins(0, 0, 0, 0)
        right_config_layout.setSpacing(16)

        config_layout.addWidget(left_config_widget, stretch=1)
        config_layout.addWidget(right_config_widget, stretch=1)
        
        self.right_layout.addWidget(config_container)

        # -- Left Column Content --
        self.target_marks = self._add_param_row(left_config_layout, "Target Marks:", "40")
        self.tolerance = self._add_param_row(left_config_layout, "Mark Tolerance:", "2")

        # Seed Row
        seed_row = QWidget()
        seed_layout = QHBoxLayout(seed_row)
        seed_layout.setContentsMargins(0, 0, 0, 0)
        seed_layout.setSpacing(8)
        
        seed_label = QLabel("Seed:")
        seed_label.setFixedWidth(140)
        seed_layout.addWidget(seed_label)
        apply_tooltip(seed_label, "Random seed for selection tie-breaking.")

        self.seed = QLineEdit("12345")
        self.seed.setStyleSheet(Styles.INPUT_FIELD)
        self.seed.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        seed_layout.addWidget(self.seed)
        apply_tooltip(self.seed, "Random seed for selection tie-breaking.")

        self.randomize_seed_btn = QPushButton("")
        self.randomize_seed_btn.setIcon(MaterialIcons.dice())
        self.randomize_seed_btn.setIconSize(QSize(24, 24))
        self.randomize_seed_btn.setFixedSize(40, 40)
        self.randomize_seed_btn.setStyleSheet(Styles.BUTTON_SECONDARY)
        self.randomize_seed_btn.clicked.connect(self._randomize_seed)
        seed_layout.addWidget(self.randomize_seed_btn)
        apply_tooltip(self.randomize_seed_btn, "Randomise the selection seed.")

        left_config_layout.addWidget(seed_row)
        left_config_layout.addStretch()

        # -- Right Column Content --
        # Part Selection Mode (three-state: All / Prune / Skip)
        self.part_mode_row = QWidget()
        part_mode_layout = QHBoxLayout(self.part_mode_row)
        part_mode_layout.setContentsMargins(0, 0, 0, 0)
        part_mode_layout.setSpacing(8)
        
        part_mode_label = QLabel("Part Selection")
        part_mode_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        apply_tooltip(part_mode_label, "Controls how sub-parts can be excluded:\n• All: Include all matching parts\n• Prune: Remove from end only\n• Skip: Remove from anywhere")
        part_mode_layout.addWidget(part_mode_label)
        part_mode_layout.addStretch(1)
        
        self.part_mode_selector = ThreeStateButtonGroup("All", "Prune", "Skip")
        self.part_mode_selector.setValue(2)  # Default to Skip
        apply_tooltip(self.part_mode_selector, "All = full questions only | Prune = remove trailing parts | Skip = remove any parts")
        part_mode_layout.addWidget(self.part_mode_selector)
        
        right_config_layout.addWidget(self.part_mode_row)
        
        self.toggle_force = self._add_toggle_row(right_config_layout, "Force topic representation")
        self.toggle_markschemes = self._add_toggle_row(right_config_layout, "Include Mark Schemes")
        self.toggle_labels = self._add_toggle_row(right_config_layout, "Show Exam Code Labels")
        self.toggle_labels.setChecked(True)
        
        # New Backfill toggle (relocated from KeywordPanel)
        self.toggle_backfill = self._add_toggle_row(right_config_layout, "Keyword Backfill")
        self.toggle_backfill.setChecked(True)
        self.backfill_row = self.toggle_backfill.parentWidget()
        # Initially hide if not in keyword mode
        self.backfill_row.setVisible(False)

        # Add stretch to right config column to push toggles up
        # right_config_layout.addStretch() 
        # Commented out stretch to align with left input fields more naturally if needed, 
        # but adding it ensures they stay at top.
        right_config_layout.addStretch()
        
        # Add stretch to main right layout (scrollable part)
        self.right_layout.addStretch()

        # --- Footer (Floating Bottom) ---
        self.footer_widget = QWidget()
        self.footer_layout = QVBoxLayout(self.footer_widget)
        self.footer_layout.setContentsMargins(0, 24, 0, 0) # Top margin to separate from scroll
        self.footer_layout.setSpacing(16)
        
        # 1. Output Format (Moved to Footer Top)
        # Wrap in a horizontal layout to allow constraining width to 50%
        format_wrapper_widget = QWidget()
        format_wrapper_layout = QHBoxLayout(format_wrapper_widget)
        format_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        format_wrapper_layout.setSpacing(0)

        # The actual control container (50% width)
        format_inner_container = QWidget()
        format_inner_layout = QHBoxLayout(format_inner_container)
        format_inner_layout.setContentsMargins(0, 0, 0, 0)
        format_inner_layout.setSpacing(8)
        
        format_label = QLabel("Output Format:")
        format_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        format_inner_layout.addWidget(format_label)
        
        format_inner_layout.addStretch() # Push toggle to right of this 50% container
        apply_tooltip(format_label, "Choose output format: PDF only, ZIP archive of slice images, or both")
        
        self.output_format = ThreeStateButtonGroup("PDF", "ZIP", "BOTH")
        format_inner_layout.addWidget(self.output_format)
        
        # Add to wrapper: [Inner Container (50%)] [Stretch (50%)]
        format_wrapper_layout.addWidget(format_inner_container, stretch=1)
        format_wrapper_layout.addStretch(1)
        
        self.footer_layout.addWidget(format_wrapper_widget)

        # 2. Output Directory
        self.out_row = QWidget()
        self.out_layout = QVBoxLayout(self.out_row)
        self.out_layout.setContentsMargins(0, 0, 0, 0)
        self.out_layout.setSpacing(4)
        
        out_label = QLabel("Output Directory:")
        self.out_layout.addWidget(out_label)
        apply_tooltip(out_label, "Destination directory for generated PDFs and summary.")

        controls_row = QWidget()
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self.out_entry = QLineEdit()
        self.out_entry.setStyleSheet(Styles.INPUT_FIELD)
        self.out_entry.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        controls_layout.addWidget(self.out_entry)
        apply_tooltip(self.out_entry, "Destination directory for generated PDFs and summary.")

        self.browse_out_btn = QPushButton("Change folder")
        self.browse_out_btn.setIcon(MaterialIcons.folder_open())
        self.browse_out_btn.setStyleSheet(Styles.BUTTON_SECONDARY)
        self.browse_out_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.browse_out_btn.clicked.connect(self._browse_output_dir)
        controls_layout.addWidget(self.browse_out_btn)
        apply_tooltip(self.browse_out_btn, "Choose a different folder")

        self.open_out_btn = QPushButton("Open")
        self.open_out_btn.setIcon(MaterialIcons.folder())
        self.open_out_btn.setStyleSheet(Styles.BUTTON_SECONDARY)
        self.open_out_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.open_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_out_btn.clicked.connect(self._open_output_dir)
        controls_layout.addWidget(self.open_out_btn)
        apply_tooltip(self.open_out_btn, "Open output directory in file explorer")
        
        self.out_layout.addWidget(controls_row)
        self.footer_layout.addWidget(self.out_row)
        
        # 3. Generate Button
        self.gen_btn = QPushButton("Generate Exam")
        self.gen_btn.setIcon(MaterialIcons.play())
        self.gen_btn.setStyleSheet(Styles.BUTTON_PRIMARY)
        self.gen_btn.setFixedHeight(48)
        self.gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gen_btn.clicked.connect(self._on_generate_clicked)
        apply_shadow(self.gen_btn, blur_radius=20)
        
        # Wrapper for shadow
        btn_wrapper = QWidget()
        btn_wrapper_layout = QHBoxLayout(btn_wrapper)
        btn_wrapper_layout.setContentsMargins(0, 0, 0, 8)
        btn_wrapper_layout.addWidget(self.gen_btn)
        
        self.footer_layout.addWidget(btn_wrapper, alignment=Qt.AlignmentFlag.AlignRight)

        # Structure Right Side: Scroll Area + Footer
        self.right_scroll = QScrollArea()
        self.right_scroll.setWidget(self.right_panel)
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.right_scroll.setStyleSheet("background-color: transparent;")
        
        right_container = QWidget()
        right_container_layout = QVBoxLayout(right_container)
        right_container_layout.setContentsMargins(0, 0, 0, 0)
        right_container_layout.setSpacing(0)
        right_container_layout.addWidget(self.right_scroll, stretch=1)
        right_container_layout.addWidget(self.footer_widget, stretch=0)
        
        self.layout.addWidget(right_container, stretch=1)
        
        # Connect auto-save signals
        # Connect UI changes to auto-save settings
        self.target_marks.editingFinished.connect(self.save_current_settings)
        self.tolerance.editingFinished.connect(self.save_current_settings)
        self.seed.editingFinished.connect(self.save_current_settings)
        self.out_entry.editingFinished.connect(self.save_current_settings)
        
        self.part_mode_selector.valueChanged.connect(lambda: self.save_current_settings())
        self.toggle_force.toggled.connect(lambda: self.save_current_settings())
        self.toggle_markschemes.toggled.connect(lambda: self.save_current_settings())
        self.toggle_labels.toggled.connect(lambda: self.save_current_settings())
        self.toggle_backfill.toggled.connect(lambda: self.save_current_settings())
        self.output_format.valueChanged.connect(lambda: self.save_current_settings())
        
        self.topic_selector.selectionChanged.connect(self.save_current_settings)
        self.keyword_panel.stateChanged.connect(self.save_current_settings)
        
        # Connect settings signals
        self.settings.metadataRootChanged.connect(lambda _: self._refresh_exam_codes())
        
        # Initial Load
        self._refresh_exam_codes()
        # We don't need to set current_exam_code here as _refresh_exam_codes calls _on_exam_changed
        # self.current_exam_code = self.exam_combo.currentText()
        
        # Connect generation finished signal
        self.generation_finished.connect(self._finish_generation)

    def showEvent(self, event):
        """Refresh exam metadata when Build tab becomes visible."""
        super().showEvent(event)
        # Refresh exam codes to pick up any new extractions
        self._refresh_exam_codes()

    def _randomize_seed(self):
        """Generate a random seed value."""
        import random
        self.seed.setText(str(random.randint(1, 99999)))
        self.save_current_settings()

    def _browse_output_dir(self):
        """Open directory picker for output directory."""
        from PySide6.QtWidgets import QFileDialog
        from gcse_toolkit.gui_v2.utils.paths import get_user_document_dir
        
        current_dir = self.out_entry.text() or str(get_user_document_dir("Generated Exams"))
        
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            current_dir,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if directory:
            self.out_entry.setText(directory)
            self.save_current_settings()

    def _open_output_dir(self):
        """Open output directory in file explorer."""
        from gcse_toolkit.gui_v2.utils.helpers import open_folder_in_browser
        from PySide6.QtWidgets import QMessageBox
        
        path = Path(self.out_entry.text())
        success, error = open_folder_in_browser(path)
        
        if not success:
            self.console.append_log("ERROR", error)
            QMessageBox.warning(self, "Error", error)

    def _refresh_exam_codes(self):
        root_str = self.settings.get_metadata_root()
        if not root_str:
            pass
            
        from gcse_toolkit.gui_v2.utils.paths import get_slices_cache_dir
        default_cache = get_slices_cache_dir()
        root = Path(root_str) if root_str else default_cache
        if not root.exists():
            root = default_cache
            
        codes = sorted(discover_exam_codes(root))
        
        # Try to restore last selected exam code from settings
        last_selected_code = self.settings.get_selected_exam_code()
        current_code = self.exam_combo.currentData() or last_selected_code
        
        self.exam_combo.blockSignals(True)
        self.exam_combo.clear()
        
        for code in codes:
            self.exam_combo.addItem(code, code)
        
        self.exam_combo.blockSignals(False)
        
        # Restore selection (prefer current, fallback to last selected, then first)
        index = self.exam_combo.findData(current_code)
        if index >= 0:
            self.exam_combo.setCurrentIndex(index)
            # Force reload even if index didn't change (e.g. re-extraction)
            self._on_exam_changed(self.exam_combo.itemData(index), force_refresh=True)
        elif self.exam_combo.count() > 0:
            self.exam_combo.setCurrentIndex(0)
            # Manually trigger change since we blocked signals
            self._on_exam_changed(self.exam_combo.itemData(0), force_refresh=True)
        else:
            self._on_exam_changed("", force_refresh=True)

    def _on_exam_changed(self, code: str, force_refresh: bool = False):
        # Handle index change signal which passes int
        if isinstance(code, int):
            code = self.exam_combo.itemData(code)
            
        # Save previous exam settings if we have a valid previous code
        if hasattr(self, 'current_exam_code') and self.current_exam_code and self.current_exam_code != code:
            pass

        self.current_exam_code = code
        
        # Save selected exam code to settings for next launch
        if code:
            self.settings.set_selected_exam_code(code)
        
        if not code:
            self.exam_name_label.setText("")
            return
            
        try:
            defn = get_exam_definition(code)
            self.exam_name_label.setText(defn.name)
        except UnsupportedCodeError:
            self.exam_name_label.setText("Unknown Exam Code")
        
        # Load topics for this exam
        meta_root_str = self.settings.get_metadata_root()
        if meta_root_str:
            meta_root = Path(meta_root_str)
            self.topic_selector.load_topics_for_exam(code, meta_root)
            # Also set context for keyword panel
            self.keyword_panel.set_exam_context(code, meta_root, force_refresh=force_refresh)
            # Populate year filter for this exam
            self._populate_year_filter(code, meta_root)
            # Populate paper filter for this exam
            self._populate_paper_filter(code, meta_root)
        
        # Load settings for this exam
        self._load_exam_settings(code)


    def _current_filter_mode(self) -> str:
        """Get current filter mode."""
        return "Topics" if self.filter_stack.currentIndex() == 0 else "Keywords"

    def _populate_year_filter(self, exam_code: str, metadata_root: Path) -> None:
        """Populate year filter dropdown with available years from metadata."""
        from gcse_toolkit.gui_v2.utils.helpers import discover_years_for_exam
        
        # Discover and populate available years
        years = discover_years_for_exam(exam_code, metadata_root)
        self.year_filter.populate_years(years)

    def _on_year_filter_changed(self) -> None:
        """Handle year filter selection change."""
        # Update border styling based on selection
        self._update_year_filter_style()
        
        # Get current filter values
        selected_years = self.year_filter.get_selected_years()
        selected_papers = self.paper_filter.get_selected_papers()
        
        # Update keyword panel filters
        self.keyword_panel.set_filters(
            years=list(selected_years) if selected_years else None,
            papers=list(selected_papers) if selected_papers else None,
        )
        
        # Refresh topic counts for selected years
        if hasattr(self, 'current_exam_code') and self.current_exam_code:
            meta_root_str = self.settings.get_metadata_root()
            if meta_root_str:
                meta_root = Path(meta_root_str)
                
                # Refresh topics with year and paper filters
                self.topic_selector.load_topics_for_exam(
                    self.current_exam_code, 
                    meta_root,
                    year_filter=selected_years if selected_years else None,
                    paper_filter=selected_papers if selected_papers else None
                )
                
                # Restore saved topic selections after reloading
                settings = self.settings.get_exam_settings(self.current_exam_code)
                if settings:
                    self.topic_selector.set_selected_topics(settings.topics, settings.sub_topics)
        
        # Save settings when year filter changes
        self.save_current_settings()

    def _update_year_filter_style(self) -> None:
        """Update year filter styling based on whether a year filter is active."""
        is_filtering = self.year_filter.is_filtering_active()
        C = get_colors()
        
        if is_filtering:  # Specific years selected (not all)
            # Red border to indicate active filter
            self.year_filter.setStyleSheet(f"""
                QComboBox {{
                    background-color: {C.SURFACE};
                    color: {C.TEXT_PRIMARY};
                    border: 2px solid #e74c3c;  /* Red border */
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 14px;
                }}
                QComboBox:hover {{
                    border: 2px solid #c0392b;  /* Darker red on hover */
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 30px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url('{C.ICON_DOWN}');
                    width: 16px;
                    height: 16px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {C.SURFACE};
                    color: {C.TEXT_PRIMARY};
                    selection-background-color: {C.SELECTION_BG};
                    selection-color: {C.SELECTION_TEXT};
                    border: 1px solid {C.BORDER};
                    outline: none;
                }}
            """)
        else:  # All years selected
            # Normal styling
            self.year_filter.setStyleSheet(get_styles().COMBOBOX)

    def _on_paper_filter_changed(self) -> None:
        """Handle paper filter selection change."""
        # Update border styling based on selection
        self._update_paper_filter_style()
        
        # Get current filter values
        selected_years = self.year_filter.get_selected_years()
        selected_papers = self.paper_filter.get_selected_papers()
        
        # Update keyword panel filters
        self.keyword_panel.set_filters(
            years=list(selected_years) if selected_years else None,
            papers=list(selected_papers) if selected_papers else None,
        )
        
        # Refresh topic counts for selected papers
        if hasattr(self, 'current_exam_code') and self.current_exam_code:
            meta_root_str = self.settings.get_metadata_root()
            if meta_root_str:
                meta_root = Path(meta_root_str)
                
                # Refresh topics with year and paper filters
                self.topic_selector.load_topics_for_exam(
                    self.current_exam_code, 
                    meta_root,
                    year_filter=selected_years if selected_years else None,
                    paper_filter=selected_papers if selected_papers else None
                )
                
                # Restore saved topic selections after reloading
                settings = self.settings.get_exam_settings(self.current_exam_code)
                if settings:
                    self.topic_selector.set_selected_topics(settings.topics, settings.sub_topics)
        
        # Save settings when paper filter changes
        self.save_current_settings()

    def _update_paper_filter_style(self) -> None:
        """Update paper filter styling based on whether a paper filter is active."""
        is_filtering = self.paper_filter.is_filtering_active()
        C = get_colors()
        
        if is_filtering:  # Specific papers selected (not all)
            # Red border to indicate active filter
            self.paper_filter.setStyleSheet(f"""
                QComboBox {{
                    background-color: {C.SURFACE};
                    color: {C.TEXT_PRIMARY};
                    border: 2px solid #e74c3c;  /* Red border */
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 14px;
                }}
                QComboBox:hover {{
                    border: 2px solid #c0392b;  /* Darker red on hover */
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 30px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url('{C.ICON_DOWN}');
                    width: 16px;
                    height: 16px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {C.SURFACE};
                    color: {C.TEXT_PRIMARY};
                    selection-background-color: {C.SELECTION_BG};
                    selection-color: {C.SELECTION_TEXT};
                    border: 1px solid {C.BORDER};
                    outline: none;
                }}
            """)
        else:  # All papers selected - apply full inline styling to ensure consistency
            self.paper_filter.setStyleSheet(f"""
                QComboBox {{
                    background-color: {C.SURFACE};
                    color: {C.TEXT_PRIMARY};
                    border: 1px solid {C.BORDER};
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 14px;
                }}
                QComboBox:hover {{
                    border: 1px solid {C.BORDER_FOCUS};
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 30px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url('{C.ICON_DOWN}');
                    width: 16px;
                    height: 16px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {C.SURFACE};
                    color: {C.TEXT_PRIMARY};
                    selection-background-color: {C.SELECTION_BG};
                    selection-color: {C.SELECTION_TEXT};
                    border: 1px solid {C.BORDER};
                    outline: none;
                }}
            """)

    def _populate_paper_filter(self, exam_code: str, metadata_root: Path) -> None:
        """Populate paper filter dropdown with available papers from metadata."""
        from gcse_toolkit.gui_v2.utils.helpers import discover_papers_for_exam
        
        # Discover and populate available papers
        papers = discover_papers_for_exam(exam_code, metadata_root)
        self.paper_filter.populate_papers(papers)



    def _load_exam_settings(self, code: str):
        try:
            self._load_exam_settings_impl(code)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to load settings for {code}: {e}. Using defaults."
            )
            # Reset to defaults on failure
            self.target_marks.setText("40")
            self.tolerance.setText("2")
            import random
            self.seed.setText(str(random.randint(1, 99999)))
            from gcse_toolkit.gui_v2.utils.paths import get_user_document_dir
            output_dir = get_user_document_dir("Generated Exams") / code
            self.out_entry.setText(str(output_dir))
            self.filter_stack.setCurrentIndex(0)

    def _load_exam_settings_impl(self, code: str):
        settings = self.settings.get_exam_settings(code)
        if not settings:
            # Defaults
            self.target_marks.setText("40")
            self.tolerance.setText("2")
            import random
            self.seed.setText(str(random.randint(1, 99999)))
            
            # Default output dir - use frozen-aware path
            from gcse_toolkit.gui_v2.utils.paths import get_user_document_dir
            output_dir = get_user_document_dir("Generated Exams") / code
            self.out_entry.setText(str(output_dir))
            
            # Default to Topics tab
            self.filter_stack.setCurrentIndex(0)
            return
            
        self.target_marks.setText(str(settings.target_marks))
        self.tolerance.setText(str(settings.tolerance))
        self.seed.setText(str(settings.seed))
        if settings.output_dir:
            self.out_entry.setText(settings.output_dir)
        else:
            # Default output dir - use frozen-aware path
            from gcse_toolkit.gui_v2.utils.paths import get_user_document_dir
            output_dir = get_user_document_dir("Generated Exams") / code
            self.out_entry.setText(str(output_dir))
            
        self.part_mode_selector.setValue(settings.part_mode)
        self.toggle_force.setChecked(settings.force_topic_representation)
        
        # Restore export options
        format_map = {"pdf": 0, "zip": 1, "both": 2}
        self.output_format.setValue(format_map.get(settings.output_format, 0))
        self.toggle_markschemes.setChecked(settings.include_markschemes)
        if hasattr(settings, "show_labels"):
            self.toggle_labels.setChecked(settings.show_labels)
        
        # Restore filter mode
        filter_mode = self.settings.get_filter_tab()
        if filter_mode == "Keywords":
            self.filter_toggle.set_index(1)
            self.filter_stack.setCurrentIndex(1)
            self.keyword_panel.set_keywords(settings.keywords, settings.keyword_pins)
            
            # Always show backfill toggle in Keyword mode
            self.backfill_row.setVisible(True)
            if hasattr(settings, "allow_keyword_backfill"):
                self.toggle_backfill.setChecked(settings.allow_keyword_backfill)
            else:
                self.toggle_backfill.setChecked(True) # Default ON
        else:
            self.filter_toggle.set_index(0)
            self.filter_stack.setCurrentIndex(0)
            self.backfill_row.setVisible(False)
        
        # Restore year selection
        if settings.selected_year:
            # Treat selected_year as a list if it's a string (backwards compatibility)
            if isinstance(settings.selected_year, str):
                self.year_filter.set_selected_years([settings.selected_year])
            else:
                self.year_filter.set_selected_years(settings.selected_year)
        else:
            self.year_filter.set_selected_years(None)  # All years
        
        # Update year filter border styling
        self._update_year_filter_style()
        
        # Restore paper filter selection
        if settings.selected_papers:
            self.paper_filter.set_selected_papers(settings.selected_papers)
        else:
            self.paper_filter.set_selected_papers(None)  # All papers
        
        # Update paper filter border styling  
        self._update_paper_filter_style()
        
        # Refresh topics with restored year and paper filters
        meta_root_str = self.settings.get_metadata_root()
        if meta_root_str:
            meta_root = Path(meta_root_str)
            selected_years = self.year_filter.get_selected_years()
            selected_papers = self.paper_filter.get_selected_papers()
            
            self.topic_selector.load_topics_for_exam(
                code,
                meta_root,
                year_filter=selected_years if selected_years else None,
                paper_filter=selected_papers if selected_papers else None
            )
        
        # Set topic/sub-topic selections
        self.topic_selector.set_selected_topics(settings.topics, settings.sub_topics)

    def _on_filter_mode_changed(self, index: int):
        """Handle filter toggle change."""
        self.filter_stack.setCurrentIndex(index)
        mode = "Keywords" if index == 1 else "Topics"
        self.settings.set_filter_tab(mode)
        
        # Update settings model
        if self.current_exam_code:
            settings = self.settings.get_exam_settings(self.current_exam_code)
            if settings:
                settings.filter_mode = mode
                self.settings.set_exam_settings(self.current_exam_code, settings)

        # Auto-refresh data for the new mode
        self._refresh_current_mode(mode)
        
        # Hide irrelevant controls in Keyword mode
        is_keyword_mode = (mode == "Keywords")
        self.part_mode_row.setVisible(not is_keyword_mode)
        if self.toggle_force.parent():
            self.toggle_force.parent().setVisible(not is_keyword_mode)
        
        # Backfill toggle visibility - only in keyword mode
        if hasattr(self, 'backfill_row'):
            self.backfill_row.setVisible(is_keyword_mode)

    def _refresh_current_mode(self, mode: str):
        """Refresh data for the current filter mode."""
        if not hasattr(self, 'current_exam_code') or not self.current_exam_code:
            return
        
        meta_root_str = self.settings.get_metadata_root()
        if not meta_root_str:
            return
        meta_root = Path(meta_root_str)
        
        if mode == "Topics":
            # Reload topic counts with active filters
            selected_years = self.year_filter.get_selected_years()
            selected_papers = self.paper_filter.get_selected_papers()
            self.topic_selector.load_topics_for_exam(
                self.current_exam_code,
                meta_root,
                year_filter=selected_years if selected_years else None,
                paper_filter=selected_papers if selected_papers else None
            )
            
            # Restore saved topic selections after reloading
            settings = self.settings.get_exam_settings(self.current_exam_code)
            if settings:
                self.topic_selector.set_selected_topics(settings.topics, settings.sub_topics)
        else:
            # Keywords mode - trigger preview if keywords exist
            keywords = self.keyword_panel.get_current_keywords()
            if keywords:
                # We can reuse the preview slot logic if accessible, 
                # or just trigger the button click if simpler/safer
                if hasattr(self.keyword_panel, '_on_preview_clicked'):
                    self.keyword_panel._on_preview_clicked()

    def update_theme(self):
        """Update styles when theme changes."""
        C = get_colors()
        S = get_styles()
        
        # Update Filter Stack Style
        self.filter_stack.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {C.SURFACE};
                border: 1px solid {C.BORDER};
                border-top: none; /* Connected to toggle */
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 12px;
            }}
        """)
        
        # Propagate to children
        self.filter_toggle.update_theme()
        self.keyword_panel.update_theme()
        self.topic_selector.update_theme()
        
        # Update Exam Name Label
        self.exam_name_label.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-weight: {Fonts.WEIGHT_MEDIUM};")
        
        # Update Toggles
        self.part_mode_selector.update_theme()
        self.toggle_force.update_theme()
        
        # Update Buttons & Inputs
        self.exam_combo.setStyleSheet(S.COMBOBOX)
        self.reload_btn.setStyleSheet(S.BUTTON_SECONDARY)
        self.reload_btn.setIcon(MaterialIcons.refresh())
        
        self.seed.setStyleSheet(S.INPUT_FIELD)
        self.randomize_seed_btn.setStyleSheet(S.BUTTON_SECONDARY)
        self.randomize_seed_btn.setIcon(MaterialIcons.dice())
        
        self.out_entry.setStyleSheet(S.INPUT_FIELD)
        self.browse_out_btn.setStyleSheet(S.BUTTON_SECONDARY)
        self.browse_out_btn.setIcon(MaterialIcons.folder_open())
        self.open_out_btn.setStyleSheet(S.BUTTON_SECONDARY)
        self.open_out_btn.setIcon(MaterialIcons.folder())
        
        self.gen_btn.setStyleSheet(S.BUTTON_PRIMARY)
        self.gen_btn.setIcon(MaterialIcons.play())
        
        # Update new export controls
        self.output_format.update_theme()
        self.toggle_markschemes.update_theme()
        
        # Update year filter styling (refresh based on current selection)
        self._update_year_filter_style()
        
        # Update paper filter styling (refresh based on current selection)\n        self._update_paper_filter_style()
        
        # Update Parameter Inputs (target_marks, tolerance)
        # They are QLineEdits created in _add_param_row, we need to find them or store them better?
        # We stored them as self.target_marks and self.tolerance
        self.target_marks.setStyleSheet(S.INPUT_FIELD)
        self.tolerance.setStyleSheet(S.INPUT_FIELD)

    def save_current_settings(self):
        """Save current settings for the selected exam."""
        code = self.exam_combo.currentData()
        if not code:
            return
        
        from gcse_toolkit.gui_v2.models.settings import ExamSettings
        
        # Get filter mode and related data
        filter_mode = self._current_filter_mode()
        if filter_mode == "Keywords":
            keywords = self.keyword_panel.get_current_keywords()
            keyword_pins = list(self.keyword_panel.get_pinned_ids())
            topics = []
            sub_topics = {}
        else:
            keywords = []
            keyword_pins = []
            topics = self.topic_selector.get_selected_topics()
            sub_topics = self.topic_selector.get_selected_sub_topics()
        
        # Get keyword backfill setting if in keyword mode
        allow_keyword_backfill = True
        if filter_mode == "Keywords":
            allow_keyword_backfill = self.toggle_backfill.isChecked()
        
        # Get export options
        format_map = ["pdf", "zip", "both"]
        output_format = format_map[self.output_format.value()]
        
        # Get selected years (list of years or None for all)
        selected_years = self.year_filter.get_selected_years()
        selected_year = selected_years if selected_years else None  # None means all years
        
        # Get selected papers (list of paper numbers or None for all)
        selected_papers = self.paper_filter.get_selected_papers()
        selected_papers_list = selected_papers if selected_papers else None  # None means all papers
        
        settings = ExamSettings(
            topics=topics,
            target_marks=int(self.target_marks.text()) if self.target_marks.text().isdigit() else 40,
            tolerance=int(self.tolerance.text()) if self.tolerance.text().isdigit() else 2,
            seed=int(self.seed.text()) if self.seed.text().isdigit() else 12345,
            output_dir=self.out_entry.text(),
            sub_topics=sub_topics,
            filter_mode=filter_mode,
            keywords=keywords,
            keyword_pins=keyword_pins,
            part_mode=self.part_mode_selector.value(),
            force_topic_representation=self.toggle_force.isChecked(),
            output_format=output_format,
            include_markschemes=self.toggle_markschemes.isChecked(),
            show_labels=self.toggle_labels.isChecked(),
            selected_year=selected_year,
            selected_papers=selected_papers_list,
            allow_keyword_backfill=allow_keyword_backfill,
        )
        
        self.settings.set_exam_settings(code, settings)

    def _add_param_row(self, layout, label: str, default: str) -> QLineEdit:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label)
        lbl.setFixedWidth(140)
        row_layout.addWidget(lbl)

        entry = QLineEdit(default)
        entry.setStyleSheet(Styles.INPUT_FIELD)
        entry.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        help_text = None
        if "Target Marks" in label:
            help_text = "Target total marks for the generated exam (e.g., 40)."
        elif "Tolerance" in label:
            help_text = "Acceptable deviation from target marks (e.g., ±2)"
        if help_text:
            apply_tooltip(lbl, help_text)
            apply_tooltip(entry, help_text)

        row_layout.addWidget(entry)

        layout.addWidget(row)
        return entry

    def _add_toggle_row(self, layout, label: str) -> ToggleSwitch:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(lbl)

        row_layout.addStretch(1)

        toggle = ToggleSwitch()
        toggle.setFixedSize(36, 18)
        toggle.setChecked(True)
        row_layout.addWidget(toggle)

        # Add tooltips based on label
        tooltip_text = None
        lower_label = label.lower()
        if "pruning" in lower_label:
            tooltip_text = "Allow dropping sub-parts of multi-part questions to meet mark constraints"
        elif "skipping" in lower_label:
            tooltip_text = "Completely exclude parts that don't match the selected topics"
        elif "backfill" in lower_label:
            tooltip_text = "Enable greedy backfill using keyword matches to meet mark target"
        elif "labels" in lower_label:
            tooltip_text = "Allow skipping intermediate sub-parts (e.g., select (a) and (c) but not (b))"
        elif "representation" in lower_label:
            tooltip_text = "Ensure at least one question from each selected topic appears in the exam"
        if tooltip_text:
            apply_tooltip(lbl, tooltip_text)
            apply_tooltip(toggle, tooltip_text)

        layout.addWidget(row)
        return toggle

    def _parse_log_level(self, line: str) -> str:
        """Parse log level from a line of output.
        
        Backend outputs lines like 'INFO message' or 'WARNING message'.
        Extract the level if present, otherwise default to INFO.
        """
        line = line.strip()
        # Check for common log level prefixes
        if line.startswith("INFO "):
            return "INFO"
        elif line.startswith("WARNING "):
            return "WARNING"
        elif line.startswith("ERROR "):
            return "ERROR"
        elif line.startswith("CRITICAL "):
            return "ERROR"
        elif line.startswith("DEBUG "):
            return "INFO"  # Treat debug as info in GUI
        else:
            # No recognized prefix, default to INFO
            return "INFO"

    def _on_generate_clicked(self):
        """Handle Generate Exam button click."""
        # Check for outdated metadata first
        from gcse_toolkit.gui_v2.utils.helpers import check_metadata_versions
        from gcse_toolkit.gui_v2.utils.paths import get_slices_cache_dir
        from PySide6.QtWidgets import QMessageBox
        
        root_str = self.settings.get_metadata_root()
        root = Path(root_str) if root_str else get_slices_cache_dir()
        
        outdated = check_metadata_versions(root)
        if outdated:
            codes_list = "\n".join(f"• {code}" for code in sorted(outdated.keys()))
            QMessageBox.warning(
                self,
                "Outdated Exam Data",
                f"Cannot generate exams. The following exams use an outdated data format:\n\n{codes_list}\n\nPlease re-extract these exams first."
            )
            return
        
        # Save current settings first
        self.save_current_settings()
        
        # Get context for logging
        exam_code = self.exam_combo.currentData()
        filter_mode = self._current_filter_mode()
        target_marks = self.target_marks.text()
        tolerance = self.tolerance.text()
        
        # Log generation start with context
        self.console.append_log("INFO", f"Starting exam generation for {exam_code}")
        if filter_mode == "Topics":
            topics = self.topic_selector.get_selected_topics()
            self.console.append_log("INFO", f"Filter mode: Topics - {', '.join(topics) if topics else 'All'}")
        else:
            keywords = self.keyword_panel.get_current_keywords()
            self.console.append_log("INFO", f"Filter mode: Keywords - {', '.join(keywords) if keywords else 'None'}")
        
        self.console.append_log("INFO", f"Parameters: Target marks={target_marks}, Tolerance=±{tolerance}, Seed={self.seed.text()}")
        
        # Validate inputs
        validation_error = self._validate_inputs()
        if validation_error:
            self.console.append_log("ERROR", f"Validation failed: {validation_error}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Validation Error", validation_error)
            return

        # Disable UI during generation
        self.set_ui_locked(True)
        self.gen_btn.setText("Generating...")
        
        # Show progress bar in status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(12)
        self.progress_bar.setFixedWidth(200)
        
        # Add to status bar (need access to main window)
        mw = QApplication.instance().activeWindow()
        if mw and hasattr(mw, 'status_bar'):
            mw.status_bar.addPermanentWidget(self.progress_bar)
            
        # Set busy cursor
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        self.console.append_log("INFO", "Building exam using internal API...")
        
        # Show builder overlay
        mw = QApplication.instance().activeWindow()
        if mw:
            self._builder_overlay = BuilderOverlay(mw)
            self._builder_overlay.show()
            self._builder_overlay.raise_()
        
        # Build config from UI settings (MUST be done on main thread)
        try:
            config = self._build_generation_config()
        except ValueError as e:
            self.console.append_log("ERROR", f"Configuration Error: {e}")
            self.set_ui_locked(False)
            QApplication.restoreOverrideCursor()
            return
            
        # Run in worker thread using V2 API
        def run_generation(config):
            from gcse_toolkit.builder_v2 import build_exam, BuildError
            from gcse_toolkit.builder_v2 import BuilderConfig
            from gcse_toolkit.common import topic_sub_topics
            from gcse_toolkit.gui_v2.utils.logging_utils import attach_queue_handler, detach_queue_handler
            
            success = False
            error: Optional[str] = None
            handler = None
            try:
                # Attach log handler to capture module logs
                handler = attach_queue_handler(self.log_queue, "gcse_toolkit")
                
                # Run the V2 builder
                result = build_exam(config)
                
                # Store output directory for opening after completion
                self._last_output_dir = result.questions_pdf.parent
                
                self.log_queue.put((f"Generated exam with {result.total_marks} marks on {result.page_count} pages", "INFO"))
                self.log_queue.put((f"Output: {result.questions_pdf}", "INFO"))
                if result.markscheme_pdf:
                    self.log_queue.put((f"Markscheme: {result.markscheme_pdf}", "INFO"))
                success = True
            except BuildError as e:
                import traceback
                traceback.print_exc()
                error = str(e)
                success = False
                self._last_output_dir = None
            except Exception as e:
                import traceback
                traceback.print_exc()
                error = f"Unexpected error: {str(e)}"
                success = False
                self._last_output_dir = None
            finally:
                # Detach log handler
                if handler:
                    detach_queue_handler(handler, "gcse_toolkit")
                # Always emit signal to finish generation on main thread
                self.generation_finished.emit(success, error)
        
        import threading
        thread = threading.Thread(target=run_generation, args=(config,), daemon=True)
        thread.start()

    def _validate_inputs(self) -> Optional[str]:
        """Validate generation inputs. Returns error message or None if valid."""
        # Check exam selected
        exam_code = self.exam_combo.currentData()
        if not exam_code:
            return "Please select an exam code."
        
        # Check metadata root exists
        meta_root_str = self.settings.get_metadata_root()
        if not meta_root_str or not Path(meta_root_str).exists():
            return "Metadata root does not exist. Please extract exams first."
            
        # Check slices exist for this exam
        slices_path = Path(meta_root_str) / exam_code
        if not slices_path.exists():
            return f"Slices for exam '{exam_code}' not found in metadata root.\nPlease go to the Extract tab and extract this exam first."
        
        # Validate parameters
        try:
            target_marks = int(self.target_marks.text())
            if target_marks < 0:
                return "Target marks cannot be negative."
            if target_marks == 0:
                # TEMPORARILY DISABLED: "Output all questions" feature
                # The confirmation popup in this flow was causing the overlay to hang
                # when errors occurred after the popup was dismissed.
                # For now, 0 marks is treated as an error.
                import logging
                logging.getLogger(__name__).error(
                    "Target marks set to 0 - 'output all questions' feature is currently disabled"
                )
                return "Target marks must be greater than 0."
                
                # --- COMMENTED OUT: "Output all questions" feature ---
                # # Special case: output all questions
                # # Must have exactly one topic selected, no sub-topics
                # filter_mode = self._current_filter_mode()
                # if filter_mode != "Topics":
                #     return "Mark target 0 (all questions) is only available in Topics mode."
                # 
                # topics = self.topic_selector.get_selected_topics()
                # sub_topics = self.topic_selector.get_selected_sub_topics()
                # 
                # if len(topics) != 1 or sub_topics:
                #     return "Mark target 0 (all questions) requires exactly one topic selected (no sub-topics)."
                # 
                # # Show confirmation dialog
                # from PySide6.QtWidgets import QMessageBox
                # reply = QMessageBox.question(
                #     self,
                #     "Output All Questions?",
                #     f"You have entered 0 for mark target.\n\n"
                #     f"This will output ALL questions from the selected topic '{topics[0]}'.\n\n"
                #     f"⚠️ This may take some time depending on the number of questions.\n\n"
                #     f"Do you want to continue?",
                #     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                #     QMessageBox.StandardButton.No
                # )
                # if reply != QMessageBox.StandardButton.Yes:
                #     return "Generation cancelled."
                # --- END COMMENTED OUT ---
        except ValueError:
            return "Target marks must be a valid integer."
        
        try:
            tolerance = int(self.tolerance.text())
            if tolerance < 0:
                return "Tolerance cannot be negative."
        except ValueError:
            return "Tolerance must be a valid integer."
        
        try:
            seed = int(self.seed.text())
        except ValueError:
            return "Seed must be a valid integer."
        
        # Check filter mode specific validation
        filter_mode = self._current_filter_mode()
        
        if filter_mode == "Topics":
            topics = self.topic_selector.get_selected_topics()
            sub_topics = self.topic_selector.get_selected_sub_topics()
            if not topics and not sub_topics:
                return "Please select at least one topic or sub-topic."
        else:  # Keywords
            keywords = self.keyword_panel.get_current_keywords()
            if not keywords:
                return "Please enter at least one keyword."
            
            # Check if preview has been run
            if not self.keyword_panel.preview_results:
                return "Please run 'Preview Keywords' to verify matches before generating."
                
            # Check for zero-hit keywords
            zero_hits = []
            for kw in keywords:
                hits = self.keyword_panel.preview_results.get(kw, set())
                if not hits:
                    zero_hits.append(kw)
            
            if zero_hits:
                return f"The following keywords have 0 matches:\n{', '.join(zero_hits)}\n\nPlease remove them or change your search terms."
            
            # Check pinned marks (optional warning, but good to have)
            # For now, we enforce that pinned items don't exceed target marks if possible
            # But calculating exact pinned marks requires QuestionRecord access which is in KeywordPanel
            # We'll skip the strict mark check for now to avoid complexity, relying on the builder to handle it
        
        return None

    def _build_generation_config(self):
        """Build BuilderConfig for exam generation using V2 API."""
        from gcse_toolkit.builder_v2 import BuilderConfig
        from gcse_toolkit.common import resolve_topic_label, canonical_sub_topic_label, topic_sub_topics
        from gcse_toolkit.gui_v2.utils.paths import get_cache_dir
        
        meta_root_str = self.settings.get_metadata_root()
        meta_root = Path(meta_root_str)
        exam_code = self.exam_combo.currentData()
        output_dir = Path(self.out_entry.text()) if self.out_entry.text() else None
        filter_mode = self._current_filter_mode()
        
        # Parse numeric values
        target_marks = int(self.target_marks.text().strip())
        tolerance = int(self.tolerance.text().strip())
        seed = int(self.seed.text().strip())
        
        # Collect topics and keywords
        topics: set = set()
        keywords: List[str] = []
        keyword_questions: set = set()
        keyword_parts: set = set()
        
        if filter_mode == "Keywords":
            # Keyword mode
            keywords = self.keyword_panel.get_current_keywords()
            
            # Add pinned question parts
            pinned = self.keyword_panel.get_pinned_ids()
            for pin_key in sorted(pinned):
                if "::" in pin_key:
                    keyword_parts.add(pin_key)
                else:
                    keyword_questions.add(pin_key)
        else:
            # Topic mode
            selected_topics = self.topic_selector.get_selected_topics()
            
            # Canonicalize topics
            for topic in selected_topics:
                canonical_topic = resolve_topic_label(topic, exam_code)
                if canonical_topic:
                    topics.add(canonical_topic)
        
        # Get selected years and papers
        selected_years_list = self.year_filter.get_selected_years()
        selected_years = list(selected_years_list) if selected_years_list else None
        
        selected_papers_list = self.paper_filter.get_selected_papers()
        selected_papers = list(selected_papers_list) if selected_papers_list else None
        
        # Get export format option
        format_map = ["pdf", "zip", "both"]
        output_format = format_map[self.output_format.value()]
        export_zip = output_format in ("zip", "both")
        
        # Map part_mode selector index to PartMode enum
        from gcse_toolkit.builder_v2.selection.part_mode import PartMode
        part_mode_map = {0: PartMode.ALL, 1: PartMode.PRUNE, 2: PartMode.SKIP}
        part_mode = part_mode_map[self.part_mode_selector.value()]
        
        # Build the V2 config
        return BuilderConfig(
            cache_path=meta_root,
            exam_code=exam_code,
            target_marks=target_marks,
            tolerance=tolerance,
            seed=seed,
            output_dir=output_dir,
            topics=list(topics) if topics else [],
            keywords=keywords if keywords else [],
            keyword_questions=list(keyword_questions) if keyword_questions else [],
            keyword_part_pins=list(keyword_parts) if keyword_parts else [],
            keyword_mode=bool(keywords or keyword_questions or keyword_parts),
            part_mode=part_mode,
            force_topic_coverage=self.toggle_force.isChecked(),
            include_markscheme=self.toggle_markschemes.isChecked(),
            show_question_ids=self.toggle_labels.isChecked(),
            years=selected_years,
            papers=selected_papers,
            export_zip=export_zip,
            show_footer=self.settings.get_show_footer(),
            allow_keyword_backfill=self.toggle_backfill.isChecked() if filter_mode == "Keywords" else True,
        )
    
    def _finish_generation(self, success: bool, error: Optional[str]) -> None:
        """Restore UI state after generation and optionally open the output folder."""
        # Restore cursor
        QApplication.restoreOverrideCursor()
        
        # Remove progress bar
        if hasattr(self, 'progress_bar'):
            self.progress_bar.deleteLater()
            del self.progress_bar
        
        # Hide builder overlay
        if hasattr(self, '_builder_overlay') and self._builder_overlay:
            self._builder_overlay.hide()
            self._builder_overlay.deleteLater()
            self._builder_overlay = None
            
        # Atomic UI reset: Always re-enable button first
        self.set_ui_locked(False)
        self.gen_btn.setText("Generate Exam")
        
        if success:
            exam_code = self.exam_combo.currentData()
            output_dir = self.out_entry.text()
            self.console.append_log("SUCCESS", f"Exam {exam_code} generated successfully!")
            
            # Flash output directory field
            self.out_entry.setStyleSheet(f"border: 2px solid {Colors.SUCCESS};")
            QTimer.singleShot(500, lambda: self.out_entry.setStyleSheet(get_styles().INPUT_FIELD))
            self.console.append_log("INFO", f"Output directory: {output_dir}")
            self.console.append_log("INFO", "Opening output folder...")
            self._open_output_folder()
        else:
            msg = error or "Unknown error during generation."
            self.console.append_log("ERROR", f"Generation failed: {msg}")
            self.console.append_log("INFO", "Please check the console log above for details.")
            QMessageBox.critical(
                self,
                "Generation Failed",
                f"Failed to generate exam:\n\n{msg}",
            )

    def set_ui_locked(self, locked: bool):
        """Lock or unlock UI elements during processing."""
        self.gen_btn.setEnabled(not locked)
        self.filter_toggle.setEnabled(not locked)
        self.topic_selector.setEnabled(not locked)
        self.keyword_panel.setEnabled(not locked)
        self.toggle_backfill.setEnabled(not locked)
        self.exam_combo.setEnabled(not locked)
        self.reload_btn.setEnabled(not locked)
        self.target_marks.setEnabled(not locked)
        self.tolerance.setEnabled(not locked)
        self.seed.setEnabled(not locked)
        self.randomize_seed_btn.setEnabled(not locked)
        self.part_mode_selector.setEnabled(not locked)
        self.toggle_force.setEnabled(not locked)
        self.out_entry.setEnabled(not locked)
        self.browse_out_btn.setEnabled(not locked)
        self.toggle_markschemes.setEnabled(not locked)
        self.output_format.setEnabled(not locked)
        self.toggle_labels.setEnabled(not locked)
        
        # Emit signal to notify parent
        self.ui_locked.emit(locked)

    def _open_output_folder(self):
        """Open the output folder in system file browser."""
        from gcse_toolkit.gui_v2.utils.helpers import open_folder_in_browser
        
        # Prefer the stored output path from the most recent generation
        target = getattr(self, '_last_output_dir', None)
        
        if target and target.exists():
            self.console.append_log("INFO", f"Opening: {target}")
        else:
            # Fallback: scan for newest run folder
            raw = self.out_entry.text().strip()
            if not raw:
                QMessageBox.warning(self, "Error", "No output directory specified.")
                return
            output_root = Path(raw)
            try:
                output_root.mkdir(parents=True, exist_ok=True)
                subdirs = [p for p in output_root.iterdir() if p.is_dir()]
                valid_runs = [
                    p for p in subdirs 
                    if (p / "questions.pdf").exists() or (p / "slices.zip").exists()
                ]
                if valid_runs:
                    target = max(valid_runs, key=lambda p: p.stat().st_mtime)
                elif subdirs:
                    target = max(subdirs, key=lambda p: p.stat().st_mtime)
                else:
                    target = output_root
            except Exception as e:
                self.console.append_log("WARN", f"Error finding folder: {e}")
                target = output_root if output_root.exists() else None
        
        if not target:
            QMessageBox.warning(self, "Error", "Could not determine output folder.")
            return
            
        success, error = open_folder_in_browser(target)
        if not success and error:
            self.console.append_log("ERROR", error)
            QMessageBox.warning(self, "Error", error)
