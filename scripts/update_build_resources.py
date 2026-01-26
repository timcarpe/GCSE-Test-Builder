import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import struct
import io

def apply_macos_styling(img: Image.Image, size: int = 1024) -> Image.Image:
    """
    Apply macOS Big Sur+ styling: rounded corners (squircle-ish) and drop shadow.
    Returns a new RGBA image of the specified size.
    """
    # Create valid canvas
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    
    # Target icon size within canvas (leave room for shadow/padding)
    # macOS icons typically use ~82% of the canvas for the actual shape
    icon_size = int(size * 0.82) 
    offset = (size - icon_size) // 2
    
    # 1. Resize source to icon_size
    src_resized = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    
    # 2. Create rounded mask (Squircle approximation)
    # Radius is approx 22.5% of the icon size
    mask = Image.new('L', (icon_size, icon_size), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(icon_size * 0.225)
    draw.rounded_rectangle([(0, 0), (icon_size, icon_size)], radius=radius, fill=255)
    
    # 3. Create Shadow
    # Shadow is a blurred copy of the mask, offset slightly downwards
    shadow_canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_canvas)
    
    # Shadow parameters
    shadow_blur_radius = int(size * 0.02)
    shadow_offset_y = int(size * 0.015)
    shadow_opacity = 80 # 0-255
    
    # Check if standard macOS App icon shadow shape or just drop shadow
    # For simplicity, we draw a black rounded rect and blur it
    shadow_rect = [
        (offset, offset + shadow_offset_y), 
        (offset + icon_size, offset + icon_size + shadow_offset_y)
    ]
    shadow_draw.rounded_rectangle(shadow_rect, radius=radius, fill=(0, 0, 0, shadow_opacity))
    shadow_canvas = shadow_canvas.filter(ImageFilter.GaussianBlur(shadow_blur_radius))
    
    # 4. Composite
    canvas = Image.alpha_composite(canvas, shadow_canvas)
    
    # Cut source with mask
    src_img_styled = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
    src_img_styled.paste(src_resized, (0, 0), mask=mask)
    
    # Paste styled source onto canvas
    canvas.paste(src_img_styled, (offset, offset), mask=src_img_styled)
    
    return canvas

def create_ico(source_img: Image.Image, output_path: Path):
    """Create Windows ICO file with multiple resolutions."""
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    for size in sizes:
        resized = source_img.resize((size, size), Image.Resampling.LANCZOS)
        images.append(resized)
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    print(f"Created: {output_path}")

def create_icns(source_img: Image.Image, output_path: Path):
    """Create macOS ICNS file with multiple resolutions."""
    icon_specs = [
        (b'icp4', 16, 1),    # 16x16
        (b'icp5', 32, 1),    # 32x32
        (b'icp6', 64, 1),    # 64x64
        (b'ic07', 128, 1),   # 128x128
        (b'ic08', 256, 1),   # 256x256
        (b'ic09', 512, 1),   # 512x512
        (b'ic10', 1024, 1),  # 1024x1024
        (b'ic11', 32, 2),    # 16x16@2x
        (b'ic12', 64, 2),    # 32x32@2x
        (b'ic13', 256, 2),   # 128x128@2x
        (b'ic14', 512, 2),   # 256x256@2x
    ]
    
    icons_data = []
    for icon_type, size, scale in icon_specs:
        resized = source_img.resize((size, size), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        resized.save(buffer, format='PNG')
        png_data = buffer.getvalue()
        entry_length = 8 + len(png_data)
        icons_data.append(icon_type + struct.pack('>I', entry_length) + png_data)
    
    all_icons = b''.join(icons_data)
    total_length = 8 + len(all_icons)
    icns_data = b'icns' + struct.pack('>I', total_length) + all_icons
    
    with open(output_path, 'wb') as f:
        f.write(icns_data)
    print(f"Created: {output_path}")

def create_iconset_folder(source_img: Image.Image, output_dir: Path):
    """Create .iconset folder with standard macOS icon names."""
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    
    # (name, size)
    # Standard macOS iconset names
    icons = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]
    
    for name, size in icons:
        resized = source_img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(output_dir / name, 'PNG')
    
    print(f"Created: {output_dir} ({len(icons)} files)")

def main():
    project_root = Path(__file__).resolve().parent.parent
    
    # Check for logo_new.png first, fallback to logo.png
    source_path_new = project_root / "src" / "gcse_toolkit" / "gui_v2" / "styles" / "logo_new.png"
    source_path_orig = project_root / "src" / "gcse_toolkit" / "gui_v2" / "styles" / "logo.png"
    
    if source_path_new.exists():
        source_path = source_path_new
    else:
        source_path = source_path_orig
        
    ico_output = project_root / "build_resources" / "logo.ico"
    icns_output = project_root / "build_resources" / "logo.icns"
    iconset_output = project_root / "build_resources" / "logo.iconset"
    
    if not source_path.exists():
        print(f"Error: Source not found (checked {source_path_new} and {source_path_orig})")
        sys.exit(1)
        
    print(f"Reading source: {source_path}")
    img = Image.open(source_path)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Apply macOS styling
    print("Applying macOS styling (rounded corners + shadow)...")
    styled_img = apply_macos_styling(img)

    create_ico(styled_img, ico_output)
    create_icns(styled_img, icns_output)
    create_iconset_folder(styled_img, iconset_output)
    
    # Cleanup if we used logo_new.png
    if source_path == source_path_new:
        print(f"Renaming {source_path.name} to logo.png...")
        source_path_orig.unlink(missing_ok=True)
        source_path_new.rename(source_path_orig)
        
    print("✅ Build resources updated successfully!")

if __name__ == "__main__":
    main()
