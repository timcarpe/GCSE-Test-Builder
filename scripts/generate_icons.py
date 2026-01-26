import base64

def create_svg(fill, stroke, stroke_width, check_color=None, full_fill=False):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none">'
    
    # Box
    if full_fill:
        # No border offset for fully filled checked state
        svg += f'<rect x="0" y="0" width="18" height="18" rx="4" fill="{fill}" />'
    else:
        # Inset for border stroke
        svg += f'<rect x="1" y="1" width="16" height="16" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" />'
    
    # Checkmark
    if check_color:
        svg += f'<path d="M4 9 L7.5 12.5 L14 5.5" stroke="{check_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />'
    
    svg += '</svg>'
    return base64.b64encode(svg.encode('utf-8')).decode('ascii')

# Colors from theme.py
# Light Mode
# Unchecked: White fill, Gray border
LIGHT_UNCHECKED = create_svg('#ffffff', '#e0e0e0', '2')
# Hover: White fill, Orange border
LIGHT_UNCHECKED_HOVER = create_svg('#ffffff', '#f57c00', '2')
# Checked: Orange fill, White check
LIGHT_CHECKED = create_svg('#f57c00', None, None, 'white', full_fill=True)
# Checked Hover: Darker Orange fill, White check
LIGHT_CHECKED_HOVER = create_svg('#e65100', None, None, 'white', full_fill=True)
# Disabled: Light Gray fill, Gray border
LIGHT_DISABLED = create_svg('#f5f5f5', '#e0e0e0', '2')
# Disabled Checked: Gray fill, Dark Gray check
LIGHT_DISABLED_CHECKED = create_svg('#e0e0e0', None, None, '#757575', full_fill=True)

# Dark Mode (ColorsDark)
d_surface = '#252526'
d_border = '#30363D' 
d_warning = '#D29922' # Warning/Toggle BG
d_disabled_bg = '#3D444D'

# Unchecked: Dark Surface fill, Dark Border
DARK_UNCHECKED = create_svg(d_surface, d_border, '2')
# Hover: Dark Surface fill, Warning border
DARK_UNCHECKED_HOVER = create_svg(d_surface, d_warning, '2')
# Checked: Warning fill, White check
DARK_CHECKED = create_svg(d_warning, None, None, 'white', full_fill=True)
# Disabled: Disabled BG fill, Disabled BG border
DARK_DISABLED = create_svg(d_disabled_bg, d_disabled_bg, '2')
# Disabled Checked: Disabled BG fill, Gray check
DARK_DISABLED_CHECKED = create_svg(d_disabled_bg, None, None, '#8B949E', full_fill=True) # Text Secondary

print(f"LIGHT_UNCHECKED = \"data:image/svg+xml;base64,{LIGHT_UNCHECKED}\"")
print(f"LIGHT_UNCHECKED_HOVER = \"data:image/svg+xml;base64,{LIGHT_UNCHECKED_HOVER}\"")
print(f"LIGHT_CHECKED = \"data:image/svg+xml;base64,{LIGHT_CHECKED}\"")
print(f"LIGHT_CHECKED_HOVER = \"data:image/svg+xml;base64,{LIGHT_CHECKED_HOVER}\"")
print(f"LIGHT_DISABLED = \"data:image/svg+xml;base64,{LIGHT_DISABLED}\"")
print(f"LIGHT_DISABLED_CHECKED = \"data:image/svg+xml;base64,{LIGHT_DISABLED_CHECKED}\"")

print(f"DARK_UNCHECKED = \"data:image/svg+xml;base64,{DARK_UNCHECKED}\"")
print(f"DARK_UNCHECKED_HOVER = \"data:image/svg+xml;base64,{DARK_UNCHECKED_HOVER}\"")
print(f"DARK_CHECKED = \"data:image/svg+xml;base64,{DARK_CHECKED}\"")
print(f"DARK_DISABLED = \"data:image/svg+xml;base64,{DARK_DISABLED}\"")
print(f"DARK_DISABLED_CHECKED = \"data:image/svg+xml;base64,{DARK_DISABLED_CHECKED}\"")
