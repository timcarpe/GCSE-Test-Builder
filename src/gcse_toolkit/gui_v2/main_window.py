"""
Main Window for the GCSE Test Builder GUI v2.
"""
import sys
import queue
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QStackedWidget, QPushButton, QLabel, 
    QStatusBar, QApplication, QMenuBar, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
import time
from PySide6.QtGui import QIcon, QAction, QKeySequence, QPixmap

from gcse_toolkit.gui_v2.styles.theme import Colors, Styles, Fonts, apply_shadow, GLOBAL_STYLESHEET, GLOBAL_STYLESHEET_DARK, ColorsDark, get_styles, set_dark_mode
from gcse_toolkit.gui_v2.widgets.console_widget import ConsoleWidget
from gcse_toolkit.gui_v2.widgets.extract_tab import ExtractTab
from gcse_toolkit.gui_v2.widgets.build_tab import BuildTab
from gcse_toolkit.gui_v2.widgets.segmented_toggle import SegmentedToggle
from gcse_toolkit.gui_v2.models.settings import SettingsStore
from gcse_toolkit.gui_v2.utils.helpers import open_folder_in_browser
from gcse_toolkit.gui_v2.utils.paths import get_user_plugins_dir
from gcse_toolkit import __version__

class StorageWorker(QThread):
    """Background worker for calculating storage sizes."""
    finished = Signal(dict)
    
    def run(self):
        from gcse_toolkit.gui_v2.utils.storage import get_storage_info
        try:
            result = get_storage_info()
            self.finished.emit(result)
        except Exception:
            self.finished.emit({})


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Storage cache for async updates
        self._storage_cache = None
        self._storage_cache_time = 0
        self._storage_worker = None
        
        self.setWindowTitle("GCSE Test Builder")
        self.resize(1375, 900)
        self.setMinimumSize(1200, 720)  # Increased from 960x640 to prevent squashing
        
        # --- Menu Bar ---
        self.menu_bar = self.menuBar()
        
        # File Menu
        file_menu = self.menu_bar.addMenu("File")
        # Unified Quit action
        exit_action = QAction("Quit", self)
        exit_action.setShortcut(QKeySequence())
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help Menu
        help_menu = self.menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        support_action = QAction("Support", self)
        support_action.triggered.connect(self._open_support_page)
        help_menu.addAction(support_action)
        
        # Storage Menu
        storage_menu = self.menu_bar.addMenu("Storage")
        
        # Non-interactive info action (will be updated when menu shown)
        self.storage_info_action = QAction("Calculating...", self)
        self.storage_info_action.setEnabled(False)
        storage_menu.addAction(self.storage_info_action)
        
        storage_menu.addSeparator()
        
        # Clear Cache
        clear_cache_action = QAction("Clear Cache...", self)
        clear_cache_action.triggered.connect(self._clear_cache_with_confirmation)
        storage_menu.addAction(clear_cache_action)
        
        # Open Cache Folder
        open_cache_action = QAction("Open Cache Folder", self)
        open_cache_action.triggered.connect(self._open_cache_folder)
        storage_menu.addAction(open_cache_action)
        
        storage_menu.addSeparator()
        
        # Clear Keyword Cache
        clear_keyword_cache_action = QAction("Clear Keyword Cache", self)
        clear_keyword_cache_action.triggered.connect(self._clear_keyword_cache)
        storage_menu.addAction(clear_keyword_cache_action)
        
        # Reset GUI Settings
        reset_settings_action = QAction("Reset GUI Settings...", self)
        reset_settings_action.triggered.connect(self._reset_gui_settings)
        storage_menu.addAction(reset_settings_action)
        
        # Update storage info when menu is about to show
        storage_menu.aboutToShow.connect(self._update_storage_menu_info)
        
        # Settings Menu (was View)
        settings_menu = self.menuBar().addMenu("Settings")
        
        # Dark Mode Toggle
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        # self.dark_mode_action.setShortcut(QKeySequence("Ctrl+D")) # Shortcuts sometimes conflict
        self.dark_mode_action.triggered.connect(self._toggle_theme)
        settings_menu.addAction(self.dark_mode_action)
        
        # Show PDF Footer Toggle
        self.show_footer_action = QAction("Show PDF Footer", self)
        self.show_footer_action.setCheckable(True)
        self.show_footer_action.setChecked(True)  # Default on, will sync after settings init
        self.show_footer_action.triggered.connect(self._toggle_footer)
        settings_menu.addAction(self.show_footer_action)
        
        settings_menu.addSeparator()
        
        # Open Plugins Folder
        self.plugins_action = QAction("Open Plugins Folder", self)
        self.plugins_action.triggered.connect(self._open_plugins_folder)
        settings_menu.addAction(self.plugins_action)
        
        # Initialize Settings
        from gcse_toolkit.gui_v2.utils.paths import get_settings_path
        self.project_root = Path.cwd()
        settings_path = get_settings_path()
        self.settings = SettingsStore(settings_path)
        
        # Set dark mode state BEFORE creating widgets (so they initialize with correct colors)
        set_dark_mode(self.settings.get_dark_mode())
        
        # Initialize Logging
        self.log_queue = queue.Queue()
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self._drain_log_queue)
        self.log_timer.start(100)
        
        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # --- Header ---
        self.header = QWidget()
        self.header.setObjectName("mainHeader")
        self.header.setFixedHeight(100)
        # Style is now handled by global stylesheet via ID selector
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(24, 15, 12, 15)  # Less right margin for gear
        self.header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Logo Icon (high-res with drop shadow, scaled to match text size)
        logo_label = QLabel()
        logo_path = Path(__file__).parent / "styles" / "logo.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            # Scale to fit header text
            scaled_pixmap = pixmap.scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        self.header_layout.addWidget(logo_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        self.title_label = QLabel("GCSE Test Builder")
        self.title_label.setObjectName("mainTitle")
        # Font size controlled by stylesheet (#mainTitle selector)
        self.header_layout.addWidget(self.title_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        self.header_layout.addStretch()  # Push everything after this to the right
        
        # Navigation Toggle (floats right with gear)
        self.nav_toggle = SegmentedToggle("Exam Extractor", "Exam Builder")
        self.nav_toggle.valueChanged.connect(self._switch_tab)
        apply_shadow(self.nav_toggle, blur_radius=20, y_offset=4)
        self.header_layout.addWidget(self.nav_toggle)
        
        # Settings Gear Button (top right, 8px gap from toggle)
        from gcse_toolkit.gui_v2.utils.icons import MaterialIcons
        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(MaterialIcons.settings())
        self.settings_btn.setIconSize(self.settings_btn.iconSize() * 2)
        self.settings_btn.setFixedSize(48, 48)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setContentsMargins(8, 0, 0, 0)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 24px;
                margin-left: 8px;
            }
            QPushButton:hover {
                background: rgba(128, 128, 128, 0.2);
                border-radius: 24px;
            }
        """)
        self.settings_btn.clicked.connect(self._show_settings_menu)
        self.header_layout.addWidget(self.settings_btn)
        
        self.main_layout.addWidget(self.header)
        
        # --- Main Content Splitter ---
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(8)  # Larger handle for easier grabbing
        self.splitter.setOpaqueResize(True)  # Smooth resizing
        self.splitter.setChildrenCollapsible(False)  # Prevent snapping to zero
        self.splitter.setStyleSheet(Styles.SPLITTER)
        
        # Stacked Widget for Tabs
        self.stack = QStackedWidget()
        
        # Console
        self.console = ConsoleWidget()
        
        # Restore UI state with fallback for invalid settings
        geometry = self.settings.get_window_geometry()
        if geometry:
            try:
                restored = self.restoreGeometry(bytes.fromhex(geometry))
                if not restored:
                    self._apply_default_geometry()
            except Exception:
                self._apply_default_geometry()
        else:
            self._apply_default_geometry()
            
        splitter_state = self.settings.get_splitter_state()
        if splitter_state:
            try:
                self.splitter.restoreState(bytes.fromhex(splitter_state))
            except Exception:
                pass  # Use default splitter state
            
        # Restore active tab
        main_tab_idx = self.settings.get_main_tab()
        if main_tab_idx is not None:
            try:
                self.stack.setCurrentIndex(main_tab_idx)
                # Update sidebar buttons
                self.nav_toggle.set_index(main_tab_idx)
            except Exception:
                pass  # Use default tab
        
        # Create Tabs
        # Create Tabs
        self.extract_tab = ExtractTab(self.console, self.settings, self.log_queue)
        self.build_tab = BuildTab(self.console, self.settings, self.log_queue)
        
        # Connect locking signals
        self.extract_tab.ui_locked.connect(self._on_ui_locked)
        self.build_tab.ui_locked.connect(self._on_ui_locked)
        
        self.stack.addWidget(self.extract_tab)
        self.stack.addWidget(self.build_tab)
        
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self.console)
        
        # Set Splitter Ratios
        if not splitter_state:
            # Default to hidden console (collapsed to bottom)
            # Give main content all weight, console zero
            self.splitter.setStretchFactor(0, 1)
            self.splitter.setStretchFactor(1, 0)
            
            # Also try to set sizes to ensure it starts collapsed
            # We need to wait for layout? No, we can suggest it here.
            # Usually strict [large, 0] works if non-collapsible is respected (it stops at min height)
            # Since collapsible is False, it will stop at min height (40px) which is effectively "closed" but visible header
            # To match "hidden", we might need collapsible=True.
            # But earlier user said specific snapping issues.
            # Let's keep collapsible=False for now as it provides a handle to open it back up easily.
            self.splitter.setSizes([99999, 0])
        else:
             # Just set stretch factors to allow fluid resize if they dragged it out
             self.splitter.setStretchFactor(0, 65)
             self.splitter.setStretchFactor(1, 35)
        
        self.main_layout.addWidget(self.splitter)
        
        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(f"background-color: {Colors.SURFACE}; color: {Colors.TEXT_SECONDARY};")
        self.status_bar.showMessage("Ready")
        self.setStatusBar(self.status_bar)
        
        # Connect Navigation
        # self.btn_extract.clicked.connect(lambda: self._switch_tab(0))
        # self.btn_build.clicked.connect(lambda: self._switch_tab(1))
        
        # Restore State
        self._restore_state()
        
        # Apply initial theme
        is_dark = self.settings.get_dark_mode()
        self.dark_mode_action.setChecked(is_dark)
        self._apply_theme(is_dark)
        
        # Sync footer toggle from settings
        self.show_footer_action.setChecked(self.settings.get_show_footer())

        # Session flag for one-time version warning
        self._version_warning_shown = False
        
        # Setup popup queue for sequential dialogs
        from gcse_toolkit.gui_v2.utils.popup_queue import StartupPopupQueue
        self._popup_queue = StartupPopupQueue(self)
        self._popup_queue.enqueue(self._validate_plugins_on_startup)  # First: check plugin health
        self._popup_queue.enqueue(self._check_metadata_versions_on_startup)
        self._popup_queue.enqueue(self._check_plugin_updates_on_startup)
        self._popup_queue.enqueue(self._maybe_show_tutorial)
        
        # Start popup queue after window is fully visible
        QTimer.singleShot(500, self._popup_queue.start)

        # Run startup diagnostics (non-blocking, no popup)
        QTimer.singleShot(1000, self._log_diagnostics)
        
        # Start background storage calculation on startup
        QTimer.singleShot(1500, self._start_storage_calculation)

    def _apply_default_geometry(self):
        """Apply sensible default window geometry when saved state is invalid."""
        self.resize(1375, 900)
        # Center on primary screen
        if QApplication.primaryScreen():
            screen_geo = QApplication.primaryScreen().availableGeometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(max(0, x), max(0, y))

    def _validate_plugins_on_startup(self):
        """Validate all plugins and prompt to reseed if any are corrupted/missing.
        
        This runs first in the popup queue to ensure plugin health before
        any other checks that depend on plugins.
        """
        from gcse_toolkit.plugins import (
            get_initialization_error,
            list_exam_plugins,
            seed_plugins_from_bundle
        )
        
        # Check for initialization errors (discovery failures)
        init_error = get_initialization_error()
        if init_error:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Plugin Error")
            msg.setText("Some plugins could not be loaded.")
            msg.setInformativeText(
                f"{init_error}\n\n"
                "Would you like to reset plugins from the bundle?"
            )
            reseed_btn = msg.addButton("Reset Plugins", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton("Continue Anyway", QMessageBox.ButtonRole.RejectRole)
            
            msg.exec()
            
            if msg.clickedButton() == reseed_btn:
                # Force reseed ALL plugins
                try:
                    # Get all plugin codes that exist
                    all_codes = [p.code for p in list_exam_plugins()]
                    seed_plugins_from_bundle(force_update_codes=all_codes if all_codes else None)
                    self.console.append_log("INFO", "Plugins reset from bundle successfully.")
                except Exception as e:
                    self.console.append_log("ERROR", f"Failed to reset plugins: {e}")
        
        self._popup_queue.notify_complete()

    def _check_metadata_versions_on_startup(self):
        """Show warning if any exams have outdated metadata schema."""
        if self._version_warning_shown:
            self._popup_queue.notify_complete()
            return
            
        from gcse_toolkit.gui_v2.utils.helpers import check_metadata_versions
        from gcse_toolkit.gui_v2.utils.paths import get_slices_cache_dir
        
        root_str = self.settings.get_metadata_root()
        root = Path(root_str) if root_str else get_slices_cache_dir()
        
        if not root.exists():
            self._popup_queue.notify_complete()
            return
            
        outdated = check_metadata_versions(root)
        
        if outdated:
            self._show_version_warning(outdated)
            self._version_warning_shown = True
        else:
            self._popup_queue.notify_complete()
    
    def _show_version_warning(self, outdated: dict):
        """Display warning dialog for outdated exams with version details."""
        from gcse_toolkit.core.schemas.validator import QUESTION_SCHEMA_VERSION
        
        # Build list showing exam code and version mismatch
        codes_list = "\n".join(
            f"• {code} (v{version} → v{QUESTION_SCHEMA_VERSION})"
            for code, version in sorted(outdated.items())
        )
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Outdated Exam Data")
        msg.setText(f"Some extracted exams use an outdated data format (current: v{QUESTION_SCHEMA_VERSION}):")
        msg.setInformativeText(codes_list + "\n\nRe-extract these exams to access the latest features.")
        
        extract_btn = msg.addButton("Extract Now", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
                
        if msg.clickedButton() == extract_btn:
            self._switch_tab(0)  # Switch to Extract tab
            # Trigger highlight on extract button
            if hasattr(self.extract_tab, 'highlight_extract_button'):
                self.extract_tab.highlight_extract_button()
        
        # Notify queue that this popup is complete
        self._popup_queue.notify_complete()

    def _check_plugin_updates_on_startup(self):
        """Check for and prompt about plugin updates."""
        import sys
        from gcse_toolkit.plugins import check_plugin_updates, seed_plugins_from_bundle
        
        # In dev mode, plugins are used directly from source - no seeding needed
        if not getattr(sys, 'frozen', False):
            self._popup_queue.notify_complete()
            return
        
        updates = check_plugin_updates()
        
        if not updates:
            # No updates, but still seed any missing plugins
            seed_plugins_from_bundle()
            self._popup_queue.notify_complete()
            return
        
        self._show_plugin_update_dialog(updates)
    
    def _show_plugin_update_dialog(self, updates):
        """Show plugin update selection dialog."""
        from gcse_toolkit.gui_v2.widgets.plugin_update_dialog import PluginUpdateDialog
        from gcse_toolkit.plugins import seed_plugins_from_bundle
        
        dialog = PluginUpdateDialog(
            updates,
            parent=self,
            on_complete=self._popup_queue.notify_complete
        )
        
        if dialog.exec():
            selected_codes = dialog.get_selected_codes()
            if selected_codes:
                seed_plugins_from_bundle(force_update_codes=selected_codes)
                self.console.append_log("INFO", f"Updated plugins: {', '.join(selected_codes)}")
            else:
                # Ensure any missing plugins are still seeded
                seed_plugins_from_bundle()
        else:
            # Dialog cancelled, still seed missing plugins
            seed_plugins_from_bundle()

    def _maybe_show_tutorial(self):
        """Show first-launch tutorial if not previously seen."""
        if self.settings.has_seen_tutorial():
            self._popup_queue.notify_complete()
            return
        
        from gcse_toolkit.gui_v2.widgets.tutorial_overlay import TutorialOverlay, TutorialStep
        
        # Ensure we start on Extract tab
        self._switch_tab(0, animate=False)
        
        steps = [
            # Step 1: Source folder (Extract tab)
            TutorialStep(
                target_widget=self.extract_tab.pdf_input_container,
                title="Load Your Past Papers",
                message="Place your past paper PDFs in this folder, or click 'Change folder' to point to an existing folder containing your exam papers.",
                callout_position="bottom"
            ),
            # Step 2: Extract button
            TutorialStep(
                target_widget=self.extract_tab.extract_btn,
                title="Extract Questions",
                message="Click here to scan your PDFs and extract individual questions. This creates a searchable database of all questions.",
                callout_position="top"
            ),
            # Step 3: Navigation toggle - explain tab switching
            TutorialStep(
                target_widget=self.nav_toggle,
                title="Switch Between Tabs",
                message="Use this toggle to switch between the Extract tab (where you import PDFs) and the Build tab (where you create practice exams).",
                callout_position="bottom"
            ),
            # Step 4: Topic Mode (Build tab) - needs tab switch - highlight left column to show toggle
            TutorialStep(
                target_widget=self.build_tab.left_column,
                title="Topic Mode",
                message="In Topic Mode, filter questions by syllabus topic. Select topics and sub-topics to include in your practice exam.",
                callout_position="right",
                before_show=lambda: self._switch_tab(1, animate=True)
            ),
            # Step 5: Keyword Mode - switch to keywords tab - highlight left column to show toggle
            TutorialStep(
                target_widget=self.build_tab.left_column,
                title="Keyword Mode",
                message="In Keyword Mode, search for questions using keywords. Great for finding specific question types or concepts.",
                callout_position="right",
                before_show=lambda: self.build_tab.filter_toggle.set_index(1)  # Switch to Keywords
            ),
            # Step 6: Settings area - highlight entire right panel
            TutorialStep(
                target_widget=self.build_tab.right_panel,
                title="Configure Your Exam",
                message="Adjust settings like target marks, tolerance, and advanced options. Toggle mark schemes on or off.",
                callout_position="left",
                before_show=lambda: self.build_tab.filter_toggle.set_index(0)  # Switch back to Topics
            ),
            # Step 7: Generate button
            TutorialStep(
                target_widget=self.build_tab.gen_btn,
                title="Build Your Exam!",
                message="When ready, click Generate Exam to create your custom practice paper as a PDF.",
                callout_position="top"
            ),
        ]
        
        self._tutorial = TutorialOverlay(self.central_widget, steps)
        self._tutorial.finished.connect(self._on_tutorial_finished)
        self._tutorial.show()
        self._tutorial.raise_()

    def _on_tutorial_finished(self):
        """Handle tutorial completion."""
        self.settings.set_tutorial_seen(True)
        # Return to Extract tab after tutorial
        self._switch_tab(0, animate=True)
        self._tutorial = None
        # Notify queue that tutorial is complete
        self._popup_queue.notify_complete()

    def _log_diagnostics(self):
        """Log diagnostic information to help debug path issues."""
        from gcse_toolkit.gui_v2.utils.paths import is_frozen, get_slices_cache_dir, get_app_data_dir, get_settings_path
        from gcse_toolkit.gui_v2.utils.helpers import discover_exam_codes
        from pathlib import Path
        
        self.console.append_log("INFO", "=== Startup Diagnostics ===")
        self.console.append_log("INFO", f"Frozen Mode: {is_frozen()}")
        self.console.append_log("INFO", f"App Data Dir: {get_app_data_dir()}")
        self.console.append_log("INFO", f"Settings Path: {get_settings_path()}")
        
        default_slices = get_slices_cache_dir()
        self.console.append_log("INFO", f"Default Slices Cache: {default_slices}")
        
        settings_root = self.settings.get_metadata_root()
        self.console.append_log("INFO", f"Settings Metadata Root: {settings_root}")
        
        target_root = Path(settings_root) if settings_root else default_slices
        self.console.append_log("INFO", f"Effective Scan Root: {target_root}")
        
        if target_root.exists():
            codes = discover_exam_codes(target_root)
            self.console.append_log("INFO", f"Discovered Exam Codes: {codes}")
            if not codes:
                 # Check subdirs if any
                 try:
                     self.console.append_log("WARNING", f"No codes found. content: {[p.name for p in target_root.iterdir() if p.is_dir()]}")
                 except Exception as e:
                     self.console.append_log("ERROR", f"Error listing dir: {e}")
        else:
            self.console.append_log("WARNING", f"Scan Root does not exist: {target_root}")
            
        self.console.append_log("INFO", "===========================")

    def _toggle_theme(self, checked: bool):
        """Handle dark mode toggle."""
        self._apply_theme(checked)
        self.settings.set_dark_mode(checked)

    def _toggle_footer(self, checked: bool):
        """Handle footer visibility toggle with Ko-Fi support prompt."""
        if not checked:
            # User is trying to disable footer - show support dialog
            from gcse_toolkit.gui_v2.widgets.kofi_dialog import KoFiSupportDialog
            
            dialog = KoFiSupportDialog(self)
            dialog.exec()
            
            if dialog.should_disable_footer():
                # User clicked "Open Ko-Fi / Disable Footer"
                self.settings.set_show_footer(False)
                self.console.append_log("INFO", "PDF footer disabled")
            else:
                # User cancelled - revert toggle
                self.show_footer_action.setChecked(True)
        else:
            # Re-enabling footer - no dialog needed
            self.settings.set_show_footer(True)
            self.console.append_log("INFO", "PDF footer enabled")

    def _open_plugins_folder(self):
        """Open the user plugins directory in file explorer."""
        path = get_user_plugins_dir()
        success, error = open_folder_in_browser(path)
        if not success:
            QMessageBox.warning(self, "Error", f"Could not open plugins folder:\n{error}")

    def _clear_cache_with_confirmation(self):
        """Show confirmation dialog and clear cache if confirmed."""
        from gcse_toolkit.gui_v2.utils.storage import get_storage_info, format_size
        from gcse_toolkit.gui_v2.utils.paths import get_slices_cache_dir
        import shutil
        
        storage = get_storage_info()
        cache_size = format_size(storage['slices_cache_bytes'])
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Clear Cache")
        msg.setText(f"Are you sure you want to clear the slices cache?")
        msg.setInformativeText(
            f"This will delete {cache_size} of extracted question data.\n\n"
            f"You can re-extract exams anytime, but this operation cannot be undone."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            cache_dir = get_slices_cache_dir()
            try:
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                    cache_dir.mkdir(parents=True, exist_ok=True)  # Recreate empty
                    self.console.append_log("INFO", f"Cache cleared: {cache_size} freed")
                    QMessageBox.information(self, "Success", "Cache cleared successfully")
                else:
                    self.console.append_log("WARNING", "Cache directory does not exist")
            except Exception as e:
                self.console.append_log("ERROR", f"Failed to clear cache: {e}")
                QMessageBox.critical(self, "Error", f"Failed to clear cache:\n{e}")

    def _open_cache_folder(self):
        """Open the slices cache directory in file browser."""
        from gcse_toolkit.gui_v2.utils.paths import get_slices_cache_dir
        
        path = get_slices_cache_dir()
        # Ensure directory exists before opening
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        success, error = open_folder_in_browser(path)
        if not success:
            QMessageBox.warning(self, "Error", f"Could not open cache folder:\n{error}")

    def _open_crash_logs_folder(self):
        """Open the crash logs directory in file browser."""
        from gcse_toolkit.gui_v2.utils.crashlog import get_crashlog_dir
        
        path = get_crashlog_dir()
        success, error = open_folder_in_browser(path)
        if not success:
            QMessageBox.warning(self, "Error", f"Could not open crash logs folder:\n{error}")

    def _clear_keyword_cache(self):
        """Clear the keyword search cache."""
        from gcse_toolkit.gui_v2.utils.paths import get_cache_dir
        import shutil
        
        cache_dir = get_cache_dir()
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)
                self.console.append_log("INFO", "Keyword cache cleared successfully.")
            except Exception as e:
                self.console.append_log("ERROR", f"Failed to clear keyword cache: {e}")
                QMessageBox.warning(self, "Error", f"Could not clear keyword cache:\n{e}")
        else:
            self.console.append_log("INFO", "Keyword cache is already empty.")

    def _reset_gui_settings(self):
        """Reset GUI settings to defaults with confirmation."""
        from gcse_toolkit.gui_v2.utils.paths import get_settings_path
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Reset GUI Settings")
        msg.setText("Are you sure you want to reset all GUI settings to defaults?")
        msg.setInformativeText(
            "This will clear:\n"
            "• Window size and position\n"
            "• Theme preference\n"
            "• Saved folder paths\n"
            "• Filter selections\n\n"
            "The application will close after reset."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            settings_path = get_settings_path()
            try:
                if settings_path.exists():
                    settings_path.unlink()
                self.console.append_log("INFO", "GUI settings reset. Application will now close.")
                # Close the application
                QApplication.instance().quit()
            except Exception as e:
                self.console.append_log("ERROR", f"Failed to reset settings: {e}")
                QMessageBox.critical(self, "Error", f"Could not reset settings:\n{e}")


    def _update_storage_menu_info(self):
        """Update the storage info text in the menu bar (async)."""
        # Show cached value immediately
        if self._storage_cache:
            self._display_storage_info(self._storage_cache)
        else:
            self.storage_info_action.setText("Calculating...")
        
        # Trigger background refresh if stale
        if self._needs_storage_refresh():
            self._start_storage_calculation()
    
    def _display_storage_info(self, storage: dict):
        """Format and display storage info in menu."""
        from gcse_toolkit.gui_v2.utils.storage import format_size
        
        try:
            total_bytes = storage.get('slices_cache_bytes', 0) + storage.get('input_pdfs_bytes', 0)
            info_text = (
                f"Cache: {format_size(storage.get('slices_cache_bytes', 0))}  |  "
                f"PDFs: {format_size(storage.get('input_pdfs_bytes', 0))}  |  "
                f"Total: {format_size(total_bytes)}"
            )
            self.storage_info_action.setText(info_text)
        except Exception:
            self.storage_info_action.setText("Error calculating storage")
    
    def _needs_storage_refresh(self) -> bool:
        """Check if storage cache needs refreshing."""
        if not self._storage_cache:
            return True
        # Refresh if older than 5 minutes
        return time.time() - self._storage_cache_time > 300
    
    def _start_storage_calculation(self):
        """Start background storage calculation."""
        if self._storage_worker and self._storage_worker.isRunning():
            return  # Already calculating
        
        self._storage_worker = StorageWorker()
        self._storage_worker.finished.connect(self._on_storage_calculated)
        self._storage_worker.start()
    
    def _on_storage_calculated(self, storage: dict):
        """Handle completed storage calculation."""
        if storage:
            self._storage_cache = storage
            self._storage_cache_time = time.time()
            self._display_storage_info(storage)

    def _show_settings_menu(self):
        """Show settings popup menu at the gear button."""
        menu = QMenu(self)
        
        # Dark Mode Toggle
        dark_action = menu.addAction("Dark Mode")
        dark_action.setCheckable(True)
        dark_action.setChecked(self.dark_mode_action.isChecked())
        dark_action.triggered.connect(lambda checked: (self._toggle_theme(checked), self.dark_mode_action.setChecked(checked)))
        
        # Run Diagnostics Toggle (off by default)
        diag_action = menu.addAction("Run Diagnostics")
        diag_action.setCheckable(True)
        diag_action.setChecked(self.settings.get_run_diagnostics())
        diag_action.triggered.connect(lambda checked: self.settings.set_run_diagnostics(checked))
        
        menu.addSeparator()
        
        # Storage submenu
        storage_menu = menu.addMenu("Storage")
        
        # Use cached storage (async calculation)
        from gcse_toolkit.gui_v2.utils.storage import format_size
        storage = self._storage_cache or {}
        if not storage:
            self._start_storage_calculation()
        
        # Non-interactive info items (disabled styling)
        slices_info = storage_menu.addAction(
            f"Slices Cache: {format_size(storage.get('slices_cache_bytes', 0))}"
        )
        slices_info.setEnabled(False)
        
        pdfs_info = storage_menu.addAction(
            f"Input PDFs: {format_size(storage.get('input_pdfs_bytes', 0))}"
        )
        pdfs_info.setEnabled(False)
        
        total_bytes = storage.get('slices_cache_bytes', 0) + storage.get('input_pdfs_bytes', 0)
        total_info = storage_menu.addAction(
            f"Total: {format_size(total_bytes)}"
        )
        total_info.setEnabled(False)
        
        storage_menu.addSeparator()
        
        # Interactive actions
        clear_cache_action = storage_menu.addAction("Clear Cache...")
        clear_cache_action.triggered.connect(self._clear_cache_with_confirmation)
        
        open_cache_action = storage_menu.addAction("Open Cache Folder")
        open_cache_action.triggered.connect(self._open_cache_folder)
        
        storage_menu.addSeparator()
        
        clear_keyword_cache_action = storage_menu.addAction("Clear Keyword Cache")
        clear_keyword_cache_action.triggered.connect(self._clear_keyword_cache)
        
        reset_settings_action = storage_menu.addAction("Reset GUI Settings...")
        reset_settings_action.triggered.connect(self._reset_gui_settings)
        
        menu.addSeparator()
        
        # Open Plugins Folder
        plugins_action = menu.addAction("Open Plugins Folder")
        plugins_action.triggered.connect(self._open_plugins_folder)
        
        # Open Crash Logs (only show in frozen mode if logs exist)
        from gcse_toolkit.gui_v2.utils.paths import is_frozen
        if is_frozen():
            from gcse_toolkit.gui_v2.utils.crashlog import get_crashlog_dir
            crash_dir = get_crashlog_dir()
            if crash_dir.exists() and any(crash_dir.glob("crash_*.log")):
                crash_logs_action = menu.addAction("Open Crash Logs")
                crash_logs_action.triggered.connect(self._open_crash_logs_folder)
        
        menu.addSeparator()
        
        # About
        about_action = menu.addAction("About")
        about_action.triggered.connect(self._show_about)
        
        # Show menu below the button
        menu.exec(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))

    def _apply_theme(self, is_dark: bool):
        """Apply the selected theme stylesheet."""
        # Set global dark mode state FIRST (before any widgets read colors)
        set_dark_mode(is_dark)
        
        app = QApplication.instance()
        if is_dark:
            app.setStyleSheet(GLOBAL_STYLESHEET_DARK)
        else:
            app.setStyleSheet(GLOBAL_STYLESHEET)
            
        # Get the appropriate styles class
        S = get_styles()
        C = ColorsDark if is_dark else Colors
            
        # Propagate theme update to tabs
        if hasattr(self.extract_tab, 'update_theme'):
            self.extract_tab.update_theme()
            
        if hasattr(self.build_tab, 'update_theme'):
            self.build_tab.update_theme()
            
        # Update navigation toggle
        if hasattr(self.nav_toggle, 'update_theme'):
            self.nav_toggle.update_theme()
            
        # Header and Title styles are handled by global stylesheet via ID selectors
        # #mainHeader and #mainTitle
        
        # Update splitter style
        
        # Update splitter style
        self.splitter.setStyleSheet(S.SPLITTER)
        
        # Update status bar style
        self.status_bar.setStyleSheet(f"background-color: {C.SURFACE}; color: {C.TEXT_SECONDARY};")
        
        # Update Console
        if hasattr(self.console, 'update_theme'):
            self.console.update_theme()
            
        # macOS: Set title bar appearance to match theme
        if sys.platform == "darwin":
            try:
                from AppKit import NSApplication, NSAppearance, NSAppearanceNameDarkAqua, NSAppearanceNameAqua
                ns_app = NSApplication.sharedApplication()
                appearance_name = NSAppearanceNameDarkAqua if is_dark else NSAppearanceNameAqua
                ns_app.setAppearance_(NSAppearance.appearanceNamed_(appearance_name))
            except ImportError:
                pass

    def _switch_tab(self, index: int, animate: bool = True):
        self.stack.setCurrentIndex(index)
        # Only animate if explicitly requested AND window is visible
        if animate and self.isVisible():
            self.nav_toggle.set_index(index)
        else:
            self.nav_toggle.set_index_immediate(index)
        
        # Save state
        self.settings.set_main_tab(index)

    def _restore_state(self):
        from gcse_toolkit.gui_v2.utils.paths import get_slices_cache_dir
        
        # Restore Main Tab
        tab_idx = self.settings.get_main_tab()
        self._switch_tab(tab_idx, animate=False)
        
        # Restore Metadata Root (ensure it exists and is valid)
        meta_root = self.settings.get_metadata_root()
        default_root = get_slices_cache_dir()
        
        # Reset to default if no path set OR if the stored path doesn't exist
        # (handles stale paths from prior versions/locations)
        if not meta_root or not Path(meta_root).exists():
            self.settings.set_metadata_root(str(default_root))

    def _drain_log_queue(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
                if isinstance(msg, tuple) and len(msg) == 2:
                    text, level = msg
                    self.console.append_log(level, text)
                else:
                    self.console.append_log("INFO", str(msg))
                self.log_queue.task_done()
            except queue.Empty:
                break

    def _open_support_page(self):
        """Open Ko-Fi support page in browser."""
        import webbrowser
        webbrowser.open("https://ko-fi.com/timcarpe")

    def _show_about(self):
        QMessageBox.about(
            self,
            "About GCSE Test Builder",
            "<h3>GCSE Test Builder</h3>"
            f"<p>Version: {__version__}</p>"
            "<p>A tool for extracting and building GCSE exams.</p>"
            "<p>Created by Timothy Carpenter</p>"
            "<p>Removing barriers to education.</p>"
            '<p><a href="https://ko-fi.com/timcarpe">Support me on Ko-Fi ☕</a></p>'
            '<p>Copyright 2026 Timothy Carpenter<br>'
            'Licensed under the <a href="https://polyformproject.org/licenses/noncommercial/1.0.0/">Polyform Noncommercial License 1.0.0</a></p>'
        )

    def closeEvent(self, event):
        """Save UI state on close."""
        # Cleanup any running threads in build tab
        if hasattr(self, 'build_tab') and hasattr(self.build_tab, 'keyword_panel'):
            self.build_tab.keyword_panel.cleanup()
        
        self.settings.set_window_geometry(self.saveGeometry().toHex().data().decode())
        self.settings.set_splitter_state(self.splitter.saveState().toHex().data().decode())
        self.settings.set_main_tab(self.stack.currentIndex())
        super().closeEvent(event)

    def _on_ui_locked(self, locked: bool):
        """Handle UI lock signal from tabs."""
        self.nav_toggle.setEnabled(not locked)
        self.dark_mode_action.setEnabled(not locked)
        self.settings_btn.setEnabled(not locked)
