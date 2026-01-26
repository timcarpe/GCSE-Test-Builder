from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QApplication
import sys
from gcse_toolkit.gui_v2.styles.theme import Colors, ColorsDark

app = QApplication(sys.argv)

def check_icon(name, data_url):
    print(f"Checking {name}...", end=" ")
    if not data_url:
        print("MISSING!")
        return
    
    # Remove data prefix
    # Qt QPixmap can load directly from file, but for data url we might need to be careful
    # QPixmap.loadFromData handles raw bytes.
    # QImage.loadFromData handles raw bytes.
    
    # We strip 'data:image/png;base64,'
    header, encoded = data_url.split(',', 1)
    
    import base64
    try:
        data = base64.b64decode(encoded)
        pixmap = QPixmap()
        success = pixmap.loadFromData(data, "PNG")
        
        if success:
            print(f"OK ({pixmap.width()}x{pixmap.height()})")
        else:
            print("FAILED to load pixmap!")
    except Exception as e:
        print(f"ERROR: {e}")

print("--- Light Mode ---")
check_icon("UNCHECKED", Colors.ICON_CHECKBOX_UNCHECKED)
check_icon("CHECKED", Colors.ICON_CHECKBOX_CHECKED)

print("\n--- Dark Mode ---")
check_icon("UNCHECKED", ColorsDark.ICON_CHECKBOX_UNCHECKED)
check_icon("CHECKED", ColorsDark.ICON_CHECKBOX_CHECKED)
