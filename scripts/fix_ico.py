"""Fix ICO generation with proper multi-resolution support."""
from PIL import Image
from pathlib import Path

# Load source PNG
source = Path("src/gcse_toolkit/gui_v2/styles/logo.png")
output = Path("build_resources/logo.ico")

img = Image.open(source)

# Create resized versions for ICO
sizes = [16, 24, 32, 48, 64, 128, 256]
images = []
for size in sizes:
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    images.append(resized)

# Save as ICO with all sizes
img.save(output, format='ICO', sizes=[(s, s) for s in sizes])

print(f"Created ICO: {output}")
print(f"File size: {output.stat().st_size} bytes")
print(f"Sizes included: {sizes}")
