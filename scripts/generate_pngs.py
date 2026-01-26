import os
from PIL import Image, ImageDraw

# Target directory: src/gcse_toolkit/gui_v2/styles/icons
ARTIFACT_DIR = r"G:\Programs\GCSE-Tool-Kit\src\gcse_toolkit\gui_v2\styles\icons"

def create_rounded_rect_box(filename, size=40, fill_color=None, border_color=None, border_width=4, check_color=None):
    """
    Generates a scaled checkbox image (default 40x40 for 20x20 logic).
    """
    # Create transparent image
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Inset to accommodate centered stroke
    # Stroke width 4 => 2px overlap. So padding 2 is minimal.
    padding = max(2, border_width / 2)
    # Right/Bottom coordinate = size - padding - 1 (PIL coordinates are inclusive)
    rect_box = [padding, padding, size - padding - 1, size - padding - 1]
    
    # Scale radius based on size relative to 36px/8px baseline -> approx 22% of size
    radius = int(size * 0.22) 
    
    if border_color:
        # Note: Outline is drawn centered on the rect bounds
        draw.rounded_rectangle(rect_box, radius=radius, fill=fill_color, outline=border_color, width=border_width)
    else:
        draw.rounded_rectangle(rect_box, radius=radius, fill=fill_color)

    # Draw Checkmark
    if check_color:
        # Dynamic checkmark coordinates
        # P1: 22%, 50%
        # P2: 42%, 69%
        # P3: 78%, 30%
        points = [
            (size * 0.22, size * 0.50),
            (size * 0.42, size * 0.69),
            (size * 0.78, size * 0.30)
        ]
        draw.line(points, fill=check_color, width=border_width, joint='curve')

    # Save
    path = os.path.join(ARTIFACT_DIR, filename)
    img.save(path)
    print(f"Generated {path}")

# Colors (Hex)
# Light Mode Colors
L_SURFACE = "#ffffff"
L_BORDER = "#e0e0e0"       # Gray
L_WARNING = "#f57c00"      # Orange
L_WARNING_DARK = "#e65100" # Darker Orange
L_DISABLED_FILL = "#f5f5f5"
L_DISABLED_BORDER = "#e0e0e0"
L_DISABLED_CHECK_FILL = "#e0e0e0"
L_DISABLED_CHECK_MARK = "#757575"

# 1. Unchecked: White fill, Gray border
create_rounded_rect_box("checkbox_unchecked.png", fill_color=L_SURFACE, border_color=L_BORDER)

# 2. Unchecked Hover: White fill, Orange border
create_rounded_rect_box("checkbox_unchecked_hover.png", fill_color=L_SURFACE, border_color=L_WARNING)

# 3. Checked: Orange fill, White check
create_rounded_rect_box("checkbox_checked.png", fill_color=L_WARNING, check_color="white")

# 4. Checked Hover: Dark Orange fill, White check
create_rounded_rect_box("checkbox_checked_hover.png", fill_color=L_WARNING_DARK, check_color="white")

# 5. Disabled: Light Gray fill, Gray border
create_rounded_rect_box("checkbox_disabled.png", fill_color=L_DISABLED_FILL, border_color=L_DISABLED_BORDER)

# 6. Disabled Checked: Gray fill, Gray check
create_rounded_rect_box("checkbox_disabled_checked.png", fill_color=L_DISABLED_CHECK_FILL, check_color=L_DISABLED_CHECK_MARK)


# --- Dark Mode Colors ---
D_SURFACE = "#252526"
D_BORDER = "#30363D" 
D_WARNING = "#D29922" # Warning/Toggle BG
D_DISABLED_BG = "#3D444D"
D_DISABLED_CHECK_MARK = "#8B949E"

# 7. Dark Unchecked
create_rounded_rect_box("checkbox_dark_unchecked.png", fill_color=D_SURFACE, border_color=D_BORDER)

# 8. Dark Unchecked Hover
create_rounded_rect_box("checkbox_dark_unchecked_hover.png", fill_color=D_SURFACE, border_color=D_WARNING)

# 9. Dark Checked
create_rounded_rect_box("checkbox_dark_checked.png", fill_color=D_WARNING, check_color="white")

# 10. Dark Disabled
create_rounded_rect_box("checkbox_dark_disabled.png", fill_color=D_DISABLED_BG, border_color=D_DISABLED_BG)

# 11. Dark Disabled Checked
create_rounded_rect_box("checkbox_dark_disabled_checked.png", fill_color=D_DISABLED_BG, check_color=D_DISABLED_CHECK_MARK)


# --- Output Base64 ---
import base64

def get_base64(filename):
    path = os.path.join(ARTIFACT_DIR, filename)
    with open(path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('ascii')
        return f"data:image/png;base64,{encoded_string}"

print("\n--- BASE64 FOR THEME.PY ---\n")
print(f'ICON_CHECKBOX_UNCHECKED = "{get_base64("checkbox_unchecked.png")}"')
print(f'ICON_CHECKBOX_UNCHECKED_HOVER = "{get_base64("checkbox_unchecked_hover.png")}"')
print(f'ICON_CHECKBOX_CHECKED = "{get_base64("checkbox_checked.png")}"')
print(f'ICON_CHECKBOX_CHECKED_HOVER = "{get_base64("checkbox_checked_hover.png")}"')
print(f'ICON_CHECKBOX_DISABLED = "{get_base64("checkbox_disabled.png")}"')
print(f'ICON_CHECKBOX_DISABLED_CHECKED = "{get_base64("checkbox_disabled_checked.png")}"')

print(f'ICON_CHECKBOX_UNCHECKED = "{get_base64("checkbox_dark_unchecked.png")}"')
print(f'ICON_CHECKBOX_UNCHECKED_HOVER = "{get_base64("checkbox_dark_unchecked_hover.png")}"')
print(f'ICON_CHECKBOX_CHECKED = "{get_base64("checkbox_dark_checked.png")}"')
print(f'ICON_CHECKBOX_DISABLED = "{get_base64("checkbox_dark_disabled.png")}"')
print(f'ICON_CHECKBOX_DISABLED_CHECKED = "{get_base64("checkbox_dark_disabled_checked.png")}"')

