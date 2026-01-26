"""
Extract Exams Tab (Screen A)
"""
import sys
import logging
import threading
import platform
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox, QGroupBox, QFileDialog, QScrollArea, QMessageBox,
    QSizePolicy, QProgressBar
)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from gcse_toolkit.gui_v2.styles.theme import Colors, Styles, Fonts, apply_shadow, get_colors, get_styles
from gcse_toolkit.gui_v2.widgets.console_widget import ConsoleWidget
from gcse_toolkit.gui_v2.widgets.toggle_switch import ToggleSwitch
from gcse_toolkit.gui_v2.models.settings import SettingsStore
from gcse_toolkit.gui_v2.utils.tooltips import apply_tooltip
from gcse_toolkit.gui_v2.utils.icons import MaterialIcons
from gcse_toolkit.gui_v2.utils.icons import MaterialIcons
from gcse_toolkit.gui_v2.utils.logging_utils import attach_queue_handler, detach_queue_handler
from gcse_toolkit.gui_v2.utils.paths import get_user_document_dir, get_slices_cache_dir
from gcse_toolkit.plugins import supported_exam_codes
from gcse_toolkit.gui_v2.widgets.extraction_overlay import ExtractionOverlay, ExtractionTextBuffer

import queue

logger = logging.getLogger(__name__)

class ExtractTab(QWidget):
    # Signal to communicate from worker thread to main thread
    # exam_code, success, error_message
    extraction_finished = Signal(str, bool, object)
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
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Center Panel (60% width -> 20% margins)
        self.center_panel = QWidget()
        self.center_layout = QVBoxLayout(self.center_panel)
        self.center_layout.setContentsMargins(0, 24, 0, 24)
        self.center_layout.setSpacing(16)
        
        # Beta Warning
        self.beta_warning = QLabel(
            "Thank you for trying GCSE Test Builder! This is program is still in beta!!\n"
            "I am actively making improvements to PDF cropping, topic categorization, and exam building."
        )
        self.beta_warning.setStyleSheet(f"color: {Colors.WARNING}; font-size: {Fonts.H2};")
        self.beta_warning.setWordWrap(True)
        self.center_layout.addWidget(self.beta_warning)
        
        # Description
        self.desc_label = QLabel(
            "This program extracts question slices for supported GCSE and AS/A Level exams, extracting all questions and sub questions as image slices as well as building a metadata database for the extracted exams.\n"
            "\nPlace your question paper and mark scheme PDFs in <exam_code>_<series>_qp/ms_<series>.pdf format."
        )
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.BODY};")
        self.center_layout.addWidget(self.desc_label)
        
        # Supported Codes
        codes = sorted(supported_exam_codes())
        code_text = ", ".join(codes) if codes else "None"
        self.supported_codes_label = QLabel(f"Supported Exam Codes: {code_text}")
        self.supported_codes_label.setWordWrap(True)
        self.supported_codes_label.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; font-weight: {Fonts.WEIGHT_MEDIUM}; margin-bottom: 8px;")
        self.center_layout.addWidget(self.supported_codes_label)
        
        self.center_layout.addSpacing(16)
        
        # Input Folders
        pdf_default = self.settings.get_pdf_input_path() or str(get_user_document_dir("Source PDFs"))
        self.pdf_input_container, self.pdf_input_entry, self.pdf_browse_btn, self.pdf_open_btn = self._create_folder_input(
            "Exam PDFs Folder",
            pdf_default,
            "browse",
            tooltip="Folder containing the source exam PDFs (question papers and mark schemes).",
        )
        self.pdf_input_entry.textChanged.connect(self._on_pdf_path_changed)
        self.pdf_browse_btn.clicked.connect(lambda: self._browse_folder(self.pdf_input_entry, "Select PDF Input Folder"))
        
        self.center_layout.addWidget(self.pdf_input_container)
        

        self.center_layout.addStretch()


        # Extract Button
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()  # Push button to the right
        
        self.extract_btn = QPushButton("Extract Exams")
        self.extract_btn.setIcon(MaterialIcons.file_export())
        self.extract_btn.setStyleSheet(Styles.BUTTON_PRIMARY)
        self.extract_btn.setFixedHeight(48)
        self.extract_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.extract_btn.clicked.connect(self._on_extract_clicked)
        apply_shadow(self.extract_btn, blur_radius=12, y_offset=4)
        
        # specific width or auto? "Normal button" usually means auto width but maybe with min width
        self.extract_btn.setMinimumWidth(160) 
        
        btn_layout.addWidget(self.extract_btn)
        
        self.center_layout.addWidget(btn_container)
        
        # Add to main layout with 12.5% margins (12.5-75-12.5 ratio)
        # Using 1:6:1 ratio which is equivalent to 12.5%:75%:12.5%
        self.layout.addStretch(1)
        self.layout.addWidget(self.center_panel, stretch=6)
        self.layout.addStretch(1)
        
        # Connect extraction finished signal
        self.extraction_finished.connect(self._handle_extraction_finished)


    def _create_folder_input(
        self,
        label_text: str,
        default_path: str,
        btn_type: str = "browse",
        tooltip: Optional[str] = None,
    ) -> Tuple[QWidget, QLineEdit, QPushButton, QPushButton]:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label_text)
        layout.addWidget(lbl)
        apply_tooltip(lbl, tooltip)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        entry = QLineEdit(default_path)
        entry.setStyleSheet(Styles.INPUT_FIELD)
        entry.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(entry)
        apply_tooltip(entry, tooltip)
        
        # Browse Button
        browse_btn = QPushButton("Change folder")
        browse_btn.setIcon(MaterialIcons.folder_open())
        browse_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        browse_btn.setStyleSheet(Styles.BUTTON_SECONDARY)
        row_layout.addWidget(browse_btn)
        apply_tooltip(browse_btn, "Choose a different folder")

        # Open Button
        open_btn = QPushButton("Open")
        open_btn.setIcon(MaterialIcons.folder())
        open_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        open_btn.setStyleSheet(Styles.BUTTON_SECONDARY)
        open_btn.clicked.connect(lambda: self._open_folder(entry.text()))
        row_layout.addWidget(open_btn)
        apply_tooltip(open_btn, "Open folder in file explorer")

        layout.addWidget(row)
        return container, entry, browse_btn, open_btn

    def _browse_folder(self, entry: QLineEdit, title: str):
        current = entry.text()
        directory = QFileDialog.getExistingDirectory(self, title, current)
        if directory:
            entry.setText(directory)

    def _on_pdf_path_changed(self, text: str):
        self.settings.set_pdf_input_path(text)




    def _open_folder(self, path_str: str):
        """Open folder using shared utility."""
        from gcse_toolkit.gui_v2.utils.helpers import open_folder_in_browser
        
        path = Path(path_str)
        success, error = open_folder_in_browser(path)
        
        if not success:
            self.console.append_log("ERROR", error)
            QMessageBox.warning(self, "Error", error)

    def _on_extract_clicked(self):
        """Handle Extract Exams button click."""
        pdf_input = self.pdf_input_entry.text()
        slice_output = self.settings.get_metadata_root() or str(get_slices_cache_dir())
        
        
        if not Path(pdf_input).exists():
            QMessageBox.warning(self, "Validation Error", "PDF input folder does not exist.")
            return
        
        # Scan for exam codes
        from gcse_toolkit.common import supported_exam_codes, get_exam_definition, UnsupportedCodeError
        from gcse_toolkit.gui_v2.utils.helpers import scan_exam_sources
        from gcse_toolkit.gui_v2.widgets.exam_selection_dialog import ExamSelectionDialog
        
        pdf_root = Path(pdf_input)
        supported_codes = set(supported_exam_codes())
        supported_map, unsupported_map, invalid_files = scan_exam_sources(pdf_root, supported_codes)
        
        # Log scan results
        self._log_exam_scan_results(pdf_root, supported_map, unsupported_map, invalid_files)
        
        if not supported_map:
            QMessageBox.information(
                self,
                "No Exams Found",
                "No supported exam PDFs were found in the input folder.\n\n"
                "Please ensure your PDFs are named correctly (e.g., 4037_s23_qp_12.pdf)."
            )
            return
        
        # Get friendly names for dialog
        display_names = {}
        for code in supported_map.keys():
            try:
                defn = get_exam_definition(code)
                display_names[code] = defn.name
            except UnsupportedCodeError:
                display_names[code] = ""
        
        # Show selection dialog
        dialog = ExamSelectionDialog(self, supported_map, display_names)
        if not dialog.exec():  # User cancelled (exec returns 0 for rejected, 1 for accepted)
            self.console.append_log("INFO", "Extraction cancelled by user.")
            return
        
        selection = dialog.result
        if not selection:
            self.console.append_log("INFO", "No exam codes selected.")
            return
        
        # Confirm extraction
        # Confirm extraction
        selection = sorted(set(selection))
        
        # Use custom message box to ensure icon visibility in dark mode
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirm Extraction")
        msg_box.setText(f"Extract slices for the following exam codes?\n\n{', '.join(selection)}\n\n"
                        "Existing slices for these exams may be overwritten.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        # Custom icon via QtAwesome
        icon_color = get_colors().TEXT_PRIMARY
        msg_box.setIconPixmap(MaterialIcons.question(color=icon_color).pixmap(64, 64))
        
        reply = msg_box.exec()
        
        if reply != QMessageBox.StandardButton.Yes:
            self.console.append_log("INFO", "Extraction cancelled by user.")
            return
        
        # Build extraction queue (V2 uses per-exam-code batching)
        self._pending_extraction_queue = []
        for code in selection:
            config = self._build_extraction_config(code, pdf_input, slice_output)
            pdf_paths = supported_map[code]
            # Queue format: (code, config, pdf_paths, slice_output, pdf_input)
            self._pending_extraction_queue.append((code, config, pdf_paths, slice_output, pdf_input))
        
        self.console.append_log("INFO", f"Queued {len(self._pending_extraction_queue)} exam codes for extraction")
        self._run_next_extraction()
    
    def _log_exam_scan_results(
        self,
        exams_root: Path,
        supported: dict[str, list[Path]],
        unsupported: dict[str, list[Path]],
        invalid: list[Path]
    ):
        """Log the results of exam scanning."""
        if supported:
            summary = ", ".join(f"{code} ({len(files)} PDF{'s' if len(files) != 1 else ''})" 
                              for code, files in sorted(supported.items()))
            self.console.append_log("INFO", f"Supported exam codes detected: {summary}")
        else:
            self.console.append_log("WARNING", "No supported exam codes were detected in the exams directory.")
        
        for code, files in sorted(unsupported.items()):
            names = ", ".join(f.name for f in files[:3])
            if len(files) > 3:
                names += f" (and {len(files) - 3} more)"
            self.console.append_log("WARNING", f"Ignoring unsupported exam code '{code}': {names}")
        
        for path in invalid[:5]:  # Limit to first 5
            self.console.append_log("WARNING", f"Ignoring file with invalid naming pattern: {path.name}")
        
        if len(invalid) > 5:
            self.console.append_log("WARNING", f"... and {len(invalid) - 5} more invalid files")
    
    def _build_extraction_config(self, exam_code: str, pdf_input: str, slice_output: str):
        """Build ExtractionConfig for extracting a specific exam code using V2 API."""
        from gcse_toolkit.extractor_v2 import ExtractionConfig
        
        # Debug overlay is enabled when diagnostics is enabled
        run_diagnostics = self.settings.get_run_diagnostics()
        
        return ExtractionConfig(
            debug_overlay=run_diagnostics,  # Tied to diagnostics setting
            run_diagnostics=run_diagnostics,
        )
    
    def _run_next_extraction(self):
        """Run the next extraction using V2 internal API."""
        if not hasattr(self, '_pending_extraction_queue') or not self._pending_extraction_queue:
            # All done
            return
        
        code, config, pdf_paths, slice_output, pdf_input = self._pending_extraction_queue.pop(0)
        
        # Disable UI
        self.set_ui_locked(True)
        self.extract_btn.setText(f"Extracting {code}...")
        
        # Show extraction overlay on first extraction
        if not hasattr(self, '_extraction_overlay') or self._extraction_overlay is None:
            mw = QApplication.instance().activeWindow()
            if mw:
                # Create shared text buffer for overlay
                if not hasattr(self, '_text_buffer'):
                    self._text_buffer = ExtractionTextBuffer()
                
                self._extraction_overlay = ExtractionOverlay(mw, self._text_buffer)
                self._extraction_overlay.show()
                self._extraction_overlay.raise_()
        self.console.append_log("INFO", f"Extracting {code} ({len(pdf_paths)} PDFs)")
        
        # Show progress bar in status bar if not already there
        if not hasattr(self, 'progress_bar'):
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setMaximumHeight(12)
            self.progress_bar.setFixedWidth(200)
            
            mw = QApplication.instance().activeWindow()
            if mw and hasattr(mw, 'status_bar'):
                mw.status_bar.addPermanentWidget(self.progress_bar)
        
        # Set busy cursor
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        # Initialize accumulators if this is the first extraction
        if not hasattr(self, '_extraction_stats'):
            self._extraction_stats = {'qp_count': 0, 'question_count': 0, 'warnings': []}
        
        # Run in thread using V2 API
        import logging
        from gcse_toolkit.gui_v2.utils.logging_utils import attach_queue_handler, detach_queue_handler
        
        # CRITICAL: Convert self.log_queue to a standard Python queue for the thread
        # The PySide6 signal queue can't be accessed from worker threads
        import queue
        from PySide6.QtCore import Signal, QObject
        
        def run_extraction():
            from gcse_toolkit.extractor_v2 import extract_question_paper, ExtractionResult
            from dataclasses import dataclass
            
            @dataclass
            class ExtractionSummary:
                """Summary of extraction for one exam code."""
                pdf_count: int
                question_count: int
                warnings: list
            
            success = False
            error = None
            summary = None
            handler = None
            try:
                # Attach log handler to capture module logs
                handler = attach_queue_handler(self.log_queue, "gcse_toolkit")
                
                # Process each PDF using V2 per-PDF API
                total_questions = 0
                all_warnings = []
                
                # IMPORTANT: output_dir should be the cache root, NOT cache/exam_code
                # The pipeline internally creates: output_dir/exam_code/topic/question_id/
                # So if we pass cache/exam_code, it becomes cache/exam_code/exam_code/topic/...
                output_dir = Path(slice_output)  # Just the cache root!
                
                # CRITICAL: Delete stale metadata files before first PDF extraction
                # V2 uses append mode for questions.jsonl, so we need to clean before starting
                # Also delete detection_diagnostics.json to prevent stale diagnostic data
                metadata_dir = output_dir / code / "_metadata"
                stale_files = [
                    metadata_dir / "questions.jsonl",
                    metadata_dir / "detection_diagnostics.json",
                ]
                for stale_file in stale_files:
                    if stale_file.exists():
                        try:
                            stale_file.unlink()
                            logger.debug(f"Cleaned stale {stale_file.name} for {code}")
                        except OSError as e:
                            logger.warning(f"Could not delete stale {stale_file.name}: {e}")
                
                # PARALLEL EXTRACTION: Use ProcessPoolExecutor for concurrent PDF processing
                # Each PDF runs in a separate process for PyMuPDF isolation
                # Dynamic worker count: use most cores but leave 1 for GUI responsiveness
                import os
                cpu_count = os.cpu_count() or 4
                max_workers = min(cpu_count - 1, len(pdf_paths), 8)  # Cap at 8, leave 1 core for GUI
                max_workers = max(2, max_workers)  # Minimum 2 workers
                
                # Create shared diagnostics collector if enabled (requires sequential processing)
                from gcse_toolkit.extractor_v2.diagnostics import DiagnosticsCollector
                shared_collector = DiagnosticsCollector() if config.run_diagnostics else None
                
                if len(pdf_paths) == 1 or config.run_diagnostics:
                    # Single PDF or diagnostics enabled - sequential processing
                    # (diagnostics collector can't be shared across processes)
                    for pdf_path in pdf_paths:
                        try:
                            result = extract_question_paper(
                                pdf_path=pdf_path,
                                output_dir=output_dir,
                                exam_code=code,
                                config=config,
                                markscheme_search_dirs=[Path(pdf_input)],
                                diagnostics_collector=shared_collector,
                            )
                            total_questions += result.question_count
                            all_warnings.extend(result.warnings)
                            
                            # Populate text buffer with extracted question texts
                            self._populate_text_buffer(output_dir, code)
                        except Exception as e:
                            all_warnings.append(f"{pdf_path.name}: {e}")
                else:
                    # Multiple PDFs - use ThreadPoolExecutor for parallel extraction
                    # NOTE: Using threads instead of processes because:
                    # 1. ProcessPoolExecutor spawns new app instances that show in macOS dock
                    # 2. PDF extraction is I/O-bound (file reads/writes), so threads work well
                    # 3. Simpler code without multiprocessing complexity
                    from concurrent.futures import ThreadPoolExecutor
                    
                    logger.info(f"Processing {len(pdf_paths)} PDFs with {max_workers} threads")
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Submit all extraction tasks
                        future_to_pdf = {
                            executor.submit(
                                extract_question_paper,
                                pdf_path=pdf_path,
                                output_dir=output_dir,
                                exam_code=code,
                                config=config,
                                markscheme_search_dirs=[Path(pdf_input)],
                            ): pdf_path
                            for pdf_path in pdf_paths
                        }
                        
                        # Collect results as they complete
                        for future in as_completed(future_to_pdf):
                            pdf_path = future_to_pdf[future]
                            try:
                                result = future.result()
                                total_questions += result.question_count
                                all_warnings.extend(result.warnings)
                                
                                # Populate text buffer with extracted question texts
                                self._populate_text_buffer(output_dir, code)
                            except Exception as e:
                                all_warnings.append(f"{pdf_path.name}: {e}")
                
                # Save diagnostics report if we have a shared collector with issues
                if shared_collector and shared_collector.issue_count > 0:
                    diagnostics_report = shared_collector.generate_report()
                    diagnostics_path = output_dir / code / "_metadata" / "detection_diagnostics.json"
                    diagnostics_report.save(diagnostics_path)
                    logger.info(f"Detection diagnostics: {shared_collector.issue_count} issues found for {code}")
                
                summary = ExtractionSummary(
                    pdf_count=len(pdf_paths),
                    question_count=total_questions,
                    warnings=all_warnings
                )
                success = True
            except Exception as e:
                error = str(e)
                success = False
            finally:
                # Detach log handler
                if handler:
                    detach_queue_handler(handler, "gcse_toolkit")
                # Always emit signal to finish extraction on main thread
                # Pass summary when success, or error string when failed
                self.extraction_finished.emit(code, success, summary if success else error)
        
        thread = threading.Thread(target=run_extraction, daemon=True)
        thread.start()
    
    def _handle_extraction_finished(self, code: str, success: bool, result):
        """Handle extraction completion (success or failure) for one exam code."""
        # Restore UI state first
        self.extract_btn.setText("Extract Exams")
        
        # Restore cursor
        QApplication.restoreOverrideCursor()
        
        # Remove progress bar and overlay if this was the last one or if we failed
        if not hasattr(self, '_pending_extraction_queue') or not self._pending_extraction_queue:
             if hasattr(self, 'progress_bar'):
                self.progress_bar.deleteLater()
                del self.progress_bar
             # Hide extraction overlay
             if hasattr(self, '_extraction_overlay') and self._extraction_overlay:
                 self._extraction_overlay.hide()
                 self._extraction_overlay.deleteLater()
                 self._extraction_overlay = None
             # Clean up text buffer
             if hasattr(self, '_text_buffer'):
                 del self._text_buffer
             # Only unlock UI if all extractions are done
             self.set_ui_locked(False)
        
        if success:
            self.console.append_log("SUCCESS", f"Extraction of {code} completed successfully!")
            
            # Accumulate stats from ExtractionSummary (result param contains summary when success)
            if hasattr(result, 'pdf_count'):
                self._extraction_stats['qp_count'] += result.pdf_count
                self._extraction_stats['question_count'] += result.question_count
                self._extraction_stats['warnings'].extend(result.warnings)
            
            # Check if there are more extractions to run
            if hasattr(self, '_pending_extraction_queue') and self._pending_extraction_queue:
                # Run next extraction
                self._run_next_extraction()
            else:
                # All done - show final report
                stats = self._extraction_stats
                warning_count = len(stats['warnings'])
                
                # Build report message
                report_lines = [f"Processed {stats['qp_count']} question papers, extracted {stats['question_count']} questions."]
                
                if warning_count > 0:
                    report_lines.append(f"\n{warning_count} warning(s) occurred during extraction.")
                    QMessageBox.warning(self, "Extraction Complete", "\n".join(report_lines))
                else:
                    QMessageBox.information(self, "Extraction Complete", "\n".join(report_lines))
                
                # Reset stats for next run
                self._extraction_stats = {'qp_count': 0, 'question_count': 0, 'warnings': []}
        else:
            # Handle error (result contains error string when not success)
            msg = str(result) if result else "Unknown error during extraction."
            self.console.append_log("ERROR", f"Extraction of {code} failed: {msg}")
            
            # Ask if user wants to continue with remaining exams
            if hasattr(self, '_pending_extraction_queue') and self._pending_extraction_queue:
                reply = QMessageBox.question(
                    self,
                    "Extraction Failed",
                    f"Extraction of {code} failed:\n\n{msg}\n\n"
                    f"Continue with {len(self._pending_extraction_queue)} remaining exam(s)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._run_next_extraction()
                else:
                    self._pending_extraction_queue.clear()
                    # Hide overlay on user cancel
                    if hasattr(self, '_extraction_overlay') and self._extraction_overlay:
                        self._extraction_overlay.hide()
                        self._extraction_overlay.deleteLater()
                        self._extraction_overlay = None
                    self.set_ui_locked(False)
            else:
                QMessageBox.critical(self, "Extraction Failed", f"Failed to extract {code}:\n\n{msg}")
                # Hide overlay on error
                if hasattr(self, '_extraction_overlay') and self._extraction_overlay:
                    self._extraction_overlay.hide()
                    self._extraction_overlay.deleteLater()
                    self._extraction_overlay = None
                self.set_ui_locked(False)

    def set_ui_locked(self, locked: bool):
        """Lock or unlock UI elements during processing."""
        self.extract_btn.setEnabled(not locked)
        self.pdf_input_entry.setEnabled(not locked)
        self.pdf_browse_btn.setEnabled(not locked)
        self.pdf_open_btn.setEnabled(not locked)
        
        # Emit signal to notify parent (e.g. to lock navigation)
        self.ui_locked.emit(locked)

    def update_theme(self):
        """Update styles when theme changes."""
        C = get_colors()
        S = get_styles()
        
        # Update Description
        self.desc_label.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-size: {Fonts.BODY};")
        
        # Update Inputs
        self.pdf_input_entry.setStyleSheet(S.INPUT_FIELD)
        self.pdf_browse_btn.setStyleSheet(S.BUTTON_SECONDARY)
        self.pdf_browse_btn.setIcon(MaterialIcons.folder_open())
        self.pdf_open_btn.setStyleSheet(S.BUTTON_SECONDARY)
        self.pdf_open_btn.setIcon(MaterialIcons.folder())
        
        # Update Extract Button
        self.extract_btn.setStyleSheet(S.BUTTON_PRIMARY)
        self.extract_btn.setIcon(MaterialIcons.file_export())

    def highlight_extract_button(self):
        """Highlight the extract button with a pulsing green border animation."""
        from gcse_toolkit.gui_v2.utils.attention import pulse_button
        pulse_button(self.extract_btn)
    
    def _populate_text_buffer(self, output_dir: Path, exam_code: str):
        """
        Read extracted question texts from metadata and add to buffer.
        
        Called after each PDF extraction to populate the overlay's text pool.
        """
        import json
        
        if not hasattr(self, '_text_buffer') or self._text_buffer is None:
            return
        
        # Read from the questions.jsonl file
        jsonl_path = output_dir / exam_code / "_metadata" / "questions.jsonl"
        if not jsonl_path.exists():
            return
        
        try:
            with jsonl_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        root_text = data.get("root_text", "")
                        if root_text:
                            self._text_buffer.add(root_text)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

