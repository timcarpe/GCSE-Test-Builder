"""
Theme definitions for the GCSE Test Builder GUI v2.
"""
import sys
from pathlib import Path

def get_icon_path(filename):
    """Get absolute path to icon file, handling frozen/dev modes."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller bundle
        base_path = Path(sys._MEIPASS) / "gcse_toolkit" / "gui_v2" / "styles" / "icons"
    else:
        # Development mode: relative to this file
        base_path = Path(__file__).resolve().parent / "icons"
    
    return (base_path / filename).as_posix()

class Colors:
    # Primary Colors
    PRIMARY_BLUE = "#0364B8"
    PRIMARY_BLUE_HOVER = "#0A2767"
    PRIMARY_BLUE_PRESSED = "#0A2767"
    
    # Backgrounds
    BACKGROUND = "#f5f5f5"
    SURFACE = "#ffffff"
    HOVER = "#f0f0f0"
    DISABLED_BG = "#e0e0e0"
    
    # Text
    TEXT_PRIMARY = "#1f1f1f"
    TEXT_SECONDARY = "#666666"
    TEXT_DISABLED = "#757575"
    TEXT_ON_PRIMARY = "#ffffff"
    
    # Borders & Dividers
    BORDER = "#e0e0e0"
    DIVIDER = "#eeeeee"
    BORDER_FOCUS = "#28A8EA"
    BORDER_SHADOW = "#000000" # For shadow simulation
    
    # Status
    ERROR = "#d32f2f"
    SUCCESS = "#388e3c"
    WARNING = "#f57c00"
    INFO = "#1976d2"
    
    # Selection
    SELECTION_BG = "#F0F9FF"
    SELECTION_TEXT = "#1f1f1f"
    
    # Tree/List Selection (Specific highlight for rows)
    TREE_SELECTION_BG = "#1490DF" # Match Toggle BG
    TREE_SELECTION_TEXT = "#ffffff"

    # Toggles
    TOGGLE_BG = "#f57c00"  # WARNING orange

    # Icons (Embedded SVGs)
    ICON_CHECK = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIj48L3BvbHlsaW5lPjwvc3ZnPg=="
    ICON_DOWN = get_icon_path("chevron_down.svg")
    ICON_DICE = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjNjY2NjY2IiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHJlY3QgeD0iMiIgeT0iMiIgd2lkdGg9IjIwIiBoZWlnaHQ9IjIwIiByeD0iNSIgcnk9IjUiPjwvcmVjdD48Y2lyY2xlIGN4PSI4IiBjeT0iOCIgcj0iMSIgZmlsbD0iIzY2NjY2NiI+PC9jaXJjbGU+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iMSIgZmlsbD0iIzY2NjY2NiI+PC9jaXJjbGU+PGNpcmNsZSBjeD0iMTYiIGN5PSI4IiByPSIxIiBmaWxsPSIjNjY2NjY2Ij48L2NpcmNsZT48Y2lyY2xlIGN4PSI4IiBjeT0iMTYiIHI9IjEiIGZpbGwgPSIjNjY2NjY2Ij48L2NpcmNsZT48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxIiBmaWxsPSIjNjY2NjY2Ij48L2NpcmNsZT48L3N2Zz4="
    ICON_QUESTION = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2NjY2NjYiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCI+PC9jaXJjbGU+PHBhdGggZD0iTTkuMDkgOWEzIDMgMCAwIDEgNS44MyAxYzAgMi0zIDMtMyAzIj48L3BhdGg+PGxpbmUgeDE9IjEyIiB5MT0iMTciIHgyPSIxMi4wMSIgeTI9IjE3Ij48L2xpbmU+PC9zdmc+"
    
    # Checkbox Icons (PNG Files)
    ICON_CHECKBOX_UNCHECKED = get_icon_path("checkbox_unchecked.png")
    ICON_CHECKBOX_UNCHECKED_HOVER = get_icon_path("checkbox_unchecked_hover.png")
    ICON_CHECKBOX_CHECKED = get_icon_path("checkbox_checked.png")
    ICON_CHECKBOX_CHECKED_HOVER = get_icon_path("checkbox_checked_hover.png")
    ICON_CHECKBOX_DISABLED = get_icon_path("checkbox_disabled.png")
    ICON_CHECKBOX_DISABLED_CHECKED = get_icon_path("checkbox_disabled_checked.png")





class ColorsDark:
    """Dark theme color palette - Modern design inspired by VS Code and GitHub Dark."""
    
    # Primary Colors - Brighter, more vibrant blues for dark backgrounds
    PRIMARY_BLUE = "#3794FF"
    PRIMARY_BLUE_HOVER = "#4FA3FF"
    PRIMARY_BLUE_PRESSED = "#2A7FE8"
    
    # Backgrounds - VS Code Dark+ theme colors
    BACKGROUND = "#1e1e1e"        # VS Code editor background
    SURFACE = "#252526"           # VS Code sidebar/panels
    HOVER = "#21262D"             # Hover state
    DISABLED_BG = "#3D444D"
    
    # Text - High contrast for readability
    TEXT_PRIMARY = "#E6EDF3"      # Near white for primary text
    TEXT_SECONDARY = "#8B949E"    # Muted gray for secondary text
    TEXT_DISABLED = "#9CA3AF"     # Lighter gray for better contrast
    TEXT_ON_PRIMARY = "#FFFFFF"   # Pure white on primary blue
    
    # Borders & Dividers - Subtle but visible
    BORDER = "#30363D"            # Visible border
    DIVIDER = "#21262D"           # Subtle divider
    BORDER_FOCUS = "#3794FF"      # Bright blue focus
    
    # Status - Vibrant but not overwhelming
    ERROR = "#F85149"             # Bright red
    SUCCESS = "#3FB950"           # Bright green
    WARNING = "#D29922"           # Amber/gold
    INFO = "#58A6FF"              # Light blue
    
    # Selection - Blue tint with good contrast
    SELECTION_BG = "#1F6FEB"      # Vibrant blue selection
    SELECTION_TEXT = "#FFFFFF"    # White text on selection
    
    # Tree/List Selection (Specific highlight for rows)
    TREE_SELECTION_BG = "#3794FF" # Match Toggle BG
    TREE_SELECTION_TEXT = "#FFFFFF"
    
    # Toggles - Match WARNING orange
    TOGGLE_BG = "#D29922"

    # Icons - Reuse from light theme (SVGs work on dark backgrounds)
    ICON_CHECK = Colors.ICON_CHECK
    # White Chevron for Dark Mode
    ICON_DOWN = get_icon_path("chevron_down_white.svg")
    ICON_DICE = Colors.ICON_DICE
    
    # Question Mark (White)
    ICON_QUESTION = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNGRkZGRkYiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCI+PC9jaXJjbGU+PHBhdGggZD0iTTkuMDkgOWEzIDMgMCAwIDEgNS44MyAxYzAgMi0zIDMtMyAzIj48L3BhdGg+PGxpbmUgeDE9IjEyIiB5MT0iMTciIHgyPSIxMi4wMSIgeTI9IjE3Ij48L2xpbmU+PC9zdmc+"
    
    # Pinned Item Background
    PINNED_BG = "#1A3B5C"  # Muted dark blue for dark mode (better contrast than bright blue)

    # Checkbox Icons (PNG Base64)
    # Checkbox Icons (PNG Files)
    ICON_CHECKBOX_UNCHECKED = get_icon_path("checkbox_dark_unchecked.png")
    ICON_CHECKBOX_UNCHECKED_HOVER = get_icon_path("checkbox_dark_unchecked_hover.png")
    ICON_CHECKBOX_CHECKED = get_icon_path("checkbox_dark_checked.png")
    ICON_CHECKBOX_CHECKED_HOVER = ICON_CHECKBOX_CHECKED
    ICON_CHECKBOX_DISABLED = get_icon_path("checkbox_dark_disabled.png")
    ICON_CHECKBOX_DISABLED_CHECKED = get_icon_path("checkbox_dark_disabled_checked.png")

class Fonts:
    # Font Families
    UI_FONT = "-apple-system, 'SF Pro Text', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    MONO_FONT = "Consolas, Monaco, Menlo, 'Courier New', monospace"
    
    # Sizes
    H1 = "18pt"
    H2 = "16pt"
    BODY = "14pt"
    SMALL = "12pt"
    CONSOLE = "13pt"
    
    # Weights
    WEIGHT_REGULAR = "400"
    WEIGHT_MEDIUM = "500"
    WEIGHT_BOLD = "600"


class Styles:
    # Common QSS fragments
    
    BUTTON_PRIMARY = f"""
        QPushButton {{
            background-color: {Colors.PRIMARY_BLUE};
            color: {Colors.TEXT_ON_PRIMARY};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: {Fonts.WEIGHT_MEDIUM};
            border: none;
            margin-right: 4px;
            text-align: center;
            qproperty-iconSize: 20px 20px;
        }}
        QPushButton:hover {{
            background-color: {Colors.PRIMARY_BLUE_HOVER};
            margin-top: -1px; /* Simulate lift */
            padding-bottom: 9px; /* Compensate margin */
        }}
        QPushButton:pressed {{
            background-color: {Colors.PRIMARY_BLUE_PRESSED};
            margin-top: 0px;
            padding-bottom: 8px;
        }}
        QPushButton:disabled {{
            background-color: {Colors.DISABLED_BG};
            color: {Colors.TEXT_DISABLED};
        }}
    """
    
    BUTTON_SECONDARY = f"""
        QPushButton {{
            background-color: {Colors.SURFACE};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER};
            border-radius: 6px;
            padding: 8px 16px;
            margin: 2px; /* Add margin for shadow visibility */
            font-weight: {Fonts.WEIGHT_MEDIUM};
            text-align: center;
            qproperty-iconSize: 20px 20px;
        }}
        QPushButton:hover {{
            background-color: {Colors.HOVER};
            border-color: {Colors.BORDER_FOCUS};
            margin-top: 1px; /* Simulate lift - adjusted for base margin */
            padding-bottom: 9px; /* Compensate margin */
        }}
        QPushButton:pressed {{
            background-color: {Colors.BORDER};
            margin-top: 2px;
            padding-bottom: 8px;
        }}
        QPushButton:disabled {{
            background-color: {Colors.DISABLED_BG};
            color: {Colors.TEXT_DISABLED};
            border-color: {Colors.DISABLED_BG};
        }}
    """
    
    INPUT_FIELD = f"""
        QLineEdit, QSpinBox {{
            border: 1px solid {Colors.BORDER};
            border-radius: 6px;
            padding: 8px;
            background: {Colors.SURFACE};
            color: {Colors.TEXT_PRIMARY};
            selection-background-color: {Colors.SELECTION_BG};
            selection-color: {Colors.SELECTION_TEXT};
        }}
        QLineEdit:focus, QSpinBox:focus {{
            border: 1px solid {Colors.BORDER_FOCUS};
        }}
        QLineEdit:disabled {{
            background: {Colors.BACKGROUND};
            color: {Colors.TEXT_DISABLED};
        }}
    """
    
    COMBOBOX = f"""
        QComboBox {{
            border: 1px solid {Colors.BORDER};
            border-radius: 6px;
            padding: 8px 12px;
            background: {Colors.SURFACE};
            color: {Colors.TEXT_PRIMARY};
            min-height: 20px;
        }}
        QComboBox:focus {{
            border: 1px solid {Colors.BORDER_FOCUS};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 30px;
            border-left-width: 0px;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
        }}
        QComboBox::down-arrow {{
            image: url('{Colors.ICON_DOWN}');
            width: 16px;
            height: 16px;
        }}
        QComboBox QAbstractItemView {{
            border: 1px solid {Colors.BORDER};
            selection-background-color: {Colors.SELECTION_BG};
            selection-color: {Colors.SELECTION_TEXT};
            outline: none;
            padding: 4px;
        }}
    """
    
    CHECKBOX = f"""
        QCheckBox {{
            spacing: 8px;
            color: {Colors.TEXT_PRIMARY};
            background-color: transparent;
            border: none;
        }}
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border: none;
        }}
        QCheckBox::indicator:unchecked {{
            image: url('{Colors.ICON_CHECKBOX_UNCHECKED}');
        }}
        QCheckBox::indicator:unchecked:hover {{
            image: url('{Colors.ICON_CHECKBOX_UNCHECKED_HOVER}');
        }}
        QCheckBox::indicator:checked {{
            image: url('{Colors.ICON_CHECKBOX_CHECKED}');
        }}
        QCheckBox::indicator:checked:hover {{
            image: url('{Colors.ICON_CHECKBOX_CHECKED_HOVER}');
        }}
        QCheckBox::indicator:disabled {{
            image: url('{Colors.ICON_CHECKBOX_DISABLED}');
        }}
    """
    
    SCROLLBAR = f"""
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #C1C1C1;
            min-height: 20px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #A8A8A8;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            subcontrol-origin: margin;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: #C1C1C1;
            min-width: 20px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #A8A8A8;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            subcontrol-origin: margin;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
    """
    
    TREE_WIDGET = f"""
        QTreeWidget, QTreeView, QListWidget {{
            border: 1px solid {Colors.BORDER};
            background: {Colors.SURFACE};
            color: {Colors.TEXT_PRIMARY};
            outline: none;
            border-radius: 6px;
            selection-background-color: {Colors.TREE_SELECTION_BG};
            selection-color: {Colors.TREE_SELECTION_TEXT};
        }}
        QTreeWidget::item {{
            padding: 4px;
            background-color: transparent;
        }}
        QTreeWidget::item:hover, QTreeView::item:hover, QListWidget::item:hover {{
            background: {Colors.BACKGROUND};
        }}
        QTreeWidget::item:selected, QTreeView::item:selected, QListWidget::item:selected {{
            background: {Colors.TREE_SELECTION_BG};
            color: {Colors.TREE_SELECTION_TEXT};
        }}
    """
    
    SPLITTER = f"""
        QSplitter::handle {{
            background: {Colors.BORDER};
        }}
        QSplitter::handle:hover {{
            background: #c0c0c0;
        }}
    """


class StylesDark:
    # Common QSS fragments for Dark Mode
    
    BUTTON_PRIMARY = f"""
        QPushButton {{
            background-color: {ColorsDark.SELECTION_BG};
            color: {ColorsDark.TEXT_ON_PRIMARY};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: {Fonts.WEIGHT_MEDIUM};
            border: none;
            text-align: center;
            qproperty-iconSize: 20px 20px;
        }}
        QPushButton:hover {{
            background-color: {ColorsDark.PRIMARY_BLUE};
            margin-top: -1px;
            padding-bottom: 9px;
        }}
        QPushButton:pressed {{
            background-color: {ColorsDark.PRIMARY_BLUE_PRESSED};
            margin-top: 0px;
            padding-bottom: 8px;
        }}
        QPushButton:disabled {{
            background-color: {ColorsDark.DISABLED_BG};
            color: {ColorsDark.TEXT_DISABLED};
        }}
    """
    
    BUTTON_SECONDARY = f"""
        QPushButton {{
            background-color: {ColorsDark.SURFACE};
            color: {ColorsDark.TEXT_PRIMARY};
            border: 1px solid {ColorsDark.BORDER};
            border-radius: 6px;
            padding: 8px 16px;
            margin: 2px; /* Add margin for shadow visibility */
            font-weight: {Fonts.WEIGHT_MEDIUM};
            text-align: center;
            qproperty-iconSize: 20px 20px;
        }}
        QPushButton:hover {{
            background-color: {ColorsDark.HOVER};
            border-color: {ColorsDark.BORDER_FOCUS};
            margin-top: 1px; /* Simulate lift - adjusted for base margin */
            padding-bottom: 9px; /* Compensate margin */
        }}
        QPushButton:pressed {{
            background-color: {ColorsDark.BORDER};
            margin-top: 2px;
            padding-bottom: 8px;
        }}
        QPushButton:disabled {{
            background-color: {ColorsDark.DISABLED_BG};
            color: {ColorsDark.TEXT_DISABLED};
            border-color: {ColorsDark.DISABLED_BG};
        }}
    """
    
    INPUT_FIELD = f"""
        QLineEdit, QSpinBox {{
            border: 1px solid {ColorsDark.BORDER};
            border-radius: 6px;
            padding: 8px;
            background: {ColorsDark.SURFACE};
            color: {ColorsDark.TEXT_PRIMARY};
            selection-background-color: {ColorsDark.SELECTION_BG};
            selection-color: {ColorsDark.SELECTION_TEXT};
        }}
        QLineEdit:focus, QSpinBox:focus {{
            border: 1px solid {ColorsDark.BORDER_FOCUS};
        }}
        QLineEdit:disabled {{
            background: {ColorsDark.BACKGROUND};
            color: {ColorsDark.TEXT_DISABLED};
        }}
    """
    
    COMBOBOX = f"""
        QComboBox {{
            border: 1px solid {ColorsDark.BORDER};
            border-radius: 6px;
            padding: 8px 12px;
            background: {ColorsDark.SURFACE};
            color: {ColorsDark.TEXT_PRIMARY};
            min-height: 20px;
        }}
        QComboBox:focus {{
            border: 1px solid {ColorsDark.BORDER_FOCUS};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 30px;
            border-left-width: 0px;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
        }}
        QComboBox::down-arrow {{
            image: url('{ColorsDark.ICON_DOWN}');
            width: 16px;
            height: 16px;
        }}
        QComboBox QAbstractItemView {{
            border: 1px solid {ColorsDark.BORDER};
            selection-background-color: {ColorsDark.SELECTION_BG};
            selection-color: {ColorsDark.SELECTION_TEXT};
            outline: none;
            padding: 4px;
            background: {ColorsDark.SURFACE};
            color: {ColorsDark.TEXT_PRIMARY};
        }}
    """
    
    CHECKBOX = f"""
        QCheckBox {{
            spacing: 8px;
            color: {ColorsDark.TEXT_PRIMARY};
            background-color: transparent;
            border: none;
        }}
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border: none;
        }}
        QCheckBox::indicator:unchecked {{
            image: url('{ColorsDark.ICON_CHECKBOX_UNCHECKED}');
        }}
        QCheckBox::indicator:unchecked:hover {{
            image: url('{ColorsDark.ICON_CHECKBOX_UNCHECKED_HOVER}');
        }}
        QCheckBox::indicator:checked {{
            image: url('{ColorsDark.ICON_CHECKBOX_CHECKED}');
        }}
        QCheckBox::indicator:checked:hover {{
            image: url('{ColorsDark.ICON_CHECKBOX_CHECKED_HOVER}');
        }}
        QCheckBox::indicator:disabled {{
            image: url('{ColorsDark.ICON_CHECKBOX_DISABLED}');
        }}
    """
    
    SCROLLBAR = f"""
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #4A4A4A;
            min-height: 20px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #606060;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            subcontrol-origin: margin;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: #4A4A4A;
            min-width: 20px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #606060;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            subcontrol-origin: margin;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
    """
    
    TREE_WIDGET = f"""
        QTreeWidget, QTreeView, QListWidget {{
            border: 1px solid {ColorsDark.BORDER};
            background: {ColorsDark.SURFACE};
            color: {ColorsDark.TEXT_PRIMARY};
            outline: none;
            border-radius: 6px;
            selection-background-color: {ColorsDark.TREE_SELECTION_BG};
            selection-color: {ColorsDark.TREE_SELECTION_TEXT};
        }}
        QTreeWidget::item {{
            padding: 4px;
            background-color: transparent;
        }}
        QTreeWidget::item:hover, QTreeView::item:hover, QListWidget::item:hover {{
            background: {ColorsDark.BACKGROUND};
        }}
        QTreeWidget::item:selected, QTreeView::item:selected, QListWidget::item:selected {{
            background: {ColorsDark.TREE_SELECTION_BG};
            color: {ColorsDark.TREE_SELECTION_TEXT};
        }}
    """
    
    SPLITTER = f"""
        QSplitter::handle {{
            background: {ColorsDark.BORDER};
        }}
        QSplitter::handle:hover {{
            background: #555555;
        }}
    """


# Global application stylesheet to enforce the light palette
# across all widgets (helps avoid inheriting OS dark mode on Windows).
GLOBAL_STYLESHEET = f"""
    * {{
        font-family: {Fonts.UI_FONT};
        font-size: {Fonts.BODY};
        color: {Colors.TEXT_PRIMARY};
    }}

    QMainWindow, QWidget {{
        background-color: {Colors.BACKGROUND};
    }}

    QLabel {{
        background-color: transparent;
        color: {Colors.TEXT_PRIMARY};
    }}

    QMenuBar, QMenu {{
        background-color: {Colors.BACKGROUND};
        color: {Colors.TEXT_PRIMARY};
        border: none;
    }}
    QMenu::item:selected {{
        background-color: {Colors.SELECTION_BG};
        color: {Colors.SELECTION_TEXT};
    }}

    QStatusBar {{
        background-color: {Colors.SURFACE};
        color: {Colors.TEXT_SECONDARY};
    }}

    QGroupBox {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 6px;
        margin-top: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        top: -2px;
        padding: 0 4px;
        background-color: {Colors.BACKGROUND};
        color: {Colors.TEXT_PRIMARY};
    }}

    QScrollArea {{
        background: {Colors.BACKGROUND};
        border: none;
    }}
    QScrollArea > QWidget {{
        background: {Colors.BACKGROUND};
    }}
    QScrollArea > QWidget > QWidget {{
        background: {Colors.BACKGROUND};
    }}

    QPlainTextEdit, QTextEdit {{
        background-color: {Colors.SURFACE};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 6px;
        selection-background-color: {Colors.SELECTION_BG};
        selection-color: {Colors.SELECTION_TEXT};
    }}

    QTabWidget::pane {{
        background: {Colors.SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 6px;
        margin-top: 2px;
    }}
    QTabBar::tab {{
        background: {Colors.SURFACE};
        padding: 8px 12px;
        border: 1px solid {Colors.BORDER};
        border-bottom-color: {Colors.BORDER};
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        color: {Colors.PRIMARY_BLUE};
        border-color: {Colors.BORDER_FOCUS};
    }}
    QTabBar::tab:hover {{
        background: {Colors.HOVER};
    }}

    QAbstractItemView {{
        background: {Colors.SURFACE};
        color: {Colors.TEXT_PRIMARY};
        selection-background-color: {Colors.SELECTION_BG};
        selection-color: {Colors.SELECTION_TEXT};
        border: 1px solid {Colors.BORDER};
    }}

    QToolTip {{
        background-color: white;
        color: {Colors.TEXT_PRIMARY};
        border-radius: 3px;
        padding: 4px 8px;
        border: 1px solid #E0E0E0;
    }}

    #mainHeader {{
        background-color: {Colors.SURFACE};
        border-bottom: 1px solid {Colors.BORDER};
    }}
    #mainTitle {{
        color: {Colors.TEXT_PRIMARY};
        font-size: 42pt;
        font-weight: normal;
    }}
"""

GLOBAL_STYLESHEET_DARK = f"""
    * {{
        font-family: {Fonts.UI_FONT};
        font-size: {Fonts.BODY};
        color: {ColorsDark.TEXT_PRIMARY};
    }}

    QMainWindow, QWidget {{
        background-color: {ColorsDark.BACKGROUND};
    }}
    
    QLabel {{
        color: {ColorsDark.TEXT_PRIMARY};
        background-color: transparent;
    }}

    #mainTitle {{
        font-size: 42pt;
        font-weight: normal;
        color: {ColorsDark.TEXT_PRIMARY};
    }}

    QPushButton {{
        background-color: {ColorsDark.SURFACE};
        color: {ColorsDark.TEXT_PRIMARY};
        border: 1px solid {ColorsDark.BORDER};
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: {Fonts.WEIGHT_MEDIUM};
    }}
    QPushButton:hover {{
        background-color: {ColorsDark.HOVER};
        border-color: {ColorsDark.BORDER_FOCUS};
    }}
    QPushButton:pressed {{
        background-color: {ColorsDark.BORDER};
    }}
    QPushButton:disabled {{
        background-color: {ColorsDark.DISABLED_BG};
        color: {ColorsDark.TEXT_DISABLED};
    }}
    
    /* Remove keyword button - red circle with minus sign */
    QPushButton#removeKeywordBtn {{
        background-color: transparent;
        color: {ColorsDark.ERROR};
        border: 1px solid {ColorsDark.ERROR};
        border-radius: 14px;
        font-weight: bold;
        font-size: 16px;
        padding: 0px;
        padding-bottom: 2px;
    }}
    QPushButton#removeKeywordBtn:hover {{
        background-color: {ColorsDark.HOVER};
    }}
    QPushButton#removeKeywordBtn:disabled {{
        color: {ColorsDark.TEXT_PRIMARY};
        border-color: {ColorsDark.TEXT_PRIMARY};
    }}
    
    QLineEdit, QSpinBox {{
        border: 1px solid {ColorsDark.BORDER};
        border-radius: 6px;
        padding: 8px;
        background: {ColorsDark.SURFACE};
        color: {ColorsDark.TEXT_PRIMARY};
        selection-background-color: {ColorsDark.SELECTION_BG};
        selection-color: {ColorsDark.SELECTION_TEXT};
    }}
    QLineEdit:focus, QSpinBox:focus {{
        border: 1px solid {ColorsDark.BORDER_FOCUS};
    }}
    QLineEdit:disabled {{
        background: {ColorsDark.BACKGROUND};
        color: {ColorsDark.TEXT_DISABLED};
    }}
    
    QComboBox {{
        border: 1px solid {ColorsDark.BORDER};
        border-radius: 6px;
        padding: 8px 12px;
        background: {ColorsDark.SURFACE};
        color: {ColorsDark.TEXT_PRIMARY};
        min-height: 20px;
    }}
    QComboBox:focus {{
        border: 1px solid {ColorsDark.BORDER_FOCUS};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 30px;
        border-left-width: 0px;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }}
    QComboBox QAbstractItemView {{
        border: 1px solid {ColorsDark.BORDER};
        selection-background-color: {ColorsDark.SELECTION_BG};
        selection-color: {ColorsDark.SELECTION_TEXT};
        outline: none;
        padding: 4px;
        background: {ColorsDark.SURFACE};
        color: {ColorsDark.TEXT_PRIMARY};
    }}

    QMenuBar, QMenu {{
        background-color: {ColorsDark.SURFACE};
        color: {ColorsDark.TEXT_PRIMARY};
        border: none;
    }}
    QMenu::item:selected {{
        background-color: {ColorsDark.SELECTION_BG};
        color: {ColorsDark.SELECTION_TEXT};
    }}

    QStatusBar {{
        background-color: {ColorsDark.SURFACE};
        color: {ColorsDark.TEXT_SECONDARY};
    }}

    QGroupBox {{
        background-color: {ColorsDark.SURFACE};
        border: 1px solid {ColorsDark.BORDER};
        border-radius: 6px;
        margin-top: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        top: -2px;
        padding: 0 4px;
        background-color: {ColorsDark.BACKGROUND};
        color: {ColorsDark.TEXT_PRIMARY};
    }}

    QScrollArea {{
        background: {ColorsDark.BACKGROUND};
        border: none;
    }}
    QScrollArea > QWidget {{
        background: {ColorsDark.BACKGROUND};
    }}
    QScrollArea > QWidget > QWidget {{
        background: {ColorsDark.BACKGROUND};
    }}

    QPlainTextEdit, QTextEdit {{
        background-color: {ColorsDark.SURFACE};
        color: {ColorsDark.TEXT_PRIMARY};
        border: 1px solid {ColorsDark.BORDER};
        border-radius: 6px;
        selection-background-color: {ColorsDark.SELECTION_BG};
        selection-color: {ColorsDark.SELECTION_TEXT};
    }}

    QTabWidget::pane {{
        background: {ColorsDark.SURFACE};
        border: 1px solid {ColorsDark.BORDER};
        border-radius: 6px;
        margin-top: 2px;
    }}
    QTabBar::tab {{
        background: {ColorsDark.SURFACE};
        padding: 8px 12px;
        border: 1px solid {ColorsDark.BORDER};
        border-bottom-color: {ColorsDark.BORDER};
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
        color: {ColorsDark.TEXT_PRIMARY};
    }}
    QTabBar::tab:selected {{
        color: {ColorsDark.PRIMARY_BLUE};
        border-color: {ColorsDark.BORDER_FOCUS};
    }}
    QTabBar::tab:hover {{
        background: {ColorsDark.HOVER};
    }}

    QAbstractItemView {{
        background: {ColorsDark.SURFACE};
        color: {ColorsDark.TEXT_PRIMARY};
        selection-background-color: {ColorsDark.SELECTION_BG};
        selection-color: {ColorsDark.SELECTION_TEXT};
        border: 1px solid {ColorsDark.BORDER};
    }}

    QToolTip {{
        background-color: white;
        color: {Colors.TEXT_PRIMARY};
        border-radius: 3px;
        padding: 4px 8px;
        border: 1px solid #E0E0E0;
    }}

    #mainHeader {{
        background-color: {ColorsDark.BACKGROUND};
        border-bottom: 1px solid {ColorsDark.BORDER};
    }}
    #mainTitle {{
        color: #FFFFFF;
    }}
"""

# Append Scrollbar Styles
GLOBAL_STYLESHEET += Styles.SCROLLBAR
GLOBAL_STYLESHEET_DARK += StylesDark.SCROLLBAR


def apply_global_stylesheet(app) -> None:
    """
    Apply the shared light-mode stylesheet and default font to the QApplication.
    """
    from PySide6.QtGui import QFont

    # Set a sane default font family/size so widgets without explicit styling stay consistent.
    font = QFont()
    font.setFamily(Fonts.UI_FONT.split(",")[0].strip(" '\""))
    try:
        font.setPointSize(int(Fonts.BODY.replace("pt", "")))
    except ValueError:
        pass
    app.setFont(font)

    app.setStyleSheet(GLOBAL_STYLESHEET)

def apply_theme(app, is_dark: bool = False) -> None:
    """
    Apply the appropriate stylesheet (light or dark) to the QApplication.
    """
    from PySide6.QtGui import QFont
    if is_dark:
        app.setStyleSheet(GLOBAL_STYLESHEET_DARK)
    else:
        app.setStyleSheet(GLOBAL_STYLESHEET)

# Module-level dark mode state (set explicitly when theme changes)
_is_dark_mode = False

def set_dark_mode(is_dark: bool):
    """Explicitly set the dark mode state. Called by MainWindow._apply_theme."""
    global _is_dark_mode
    _is_dark_mode = is_dark

def get_colors():
    """Get the appropriate color palette based on current theme."""
    global _is_dark_mode
    return ColorsDark if _is_dark_mode else Colors


def get_styles():
    """Get the appropriate styles based on current theme."""
    global _is_dark_mode
    return StylesDark if _is_dark_mode else Styles

def apply_shadow(widget, blur_radius=20, x_offset=2, y_offset=4, color=None):
    """Apply a soft shadow to a widget."""
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    from PySide6.QtGui import QColor
    
    if color is None:
        color = QColor(0, 0, 0, 45) # Default soft shadow (reduced from 40)
        
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setXOffset(x_offset)
    shadow.setYOffset(y_offset)
    shadow.setColor(color)
    widget.setGraphicsEffect(shadow)
