import pytest
import sys
from pathlib import Path
from PIL import Image

# Add src to sys.path so we can import gcse_toolkit
SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if SRC_PATH.as_posix() not in sys.path:
    sys.path.insert(0, SRC_PATH.as_posix())


# Common test fixtures
@pytest.fixture
def tmp_exam_code():
    """Return a test exam code."""
    return "0000"


@pytest.fixture
def sample_image(tmp_path: Path):
    """Create a simple test image."""
    img = Image.new("RGB", (200, 100), color="white")
    img_path = tmp_path / "sample.png"
    img.save(img_path)
    return img_path
