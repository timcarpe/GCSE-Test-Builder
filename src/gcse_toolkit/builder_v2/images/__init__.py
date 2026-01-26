"""
Module: builder_v2.images

Purpose:
    Image access abstractions for the V2 building pipeline.
    Provides clean interface for loading and cropping slices
    from composite images.

Key Classes:
    - ImageProvider: Abstract interface for image access
    - CompositeImageProvider: Standard V2 provider

Key Functions:
    - crop_slice(): Crop region from composite image

Dependencies:
    - PIL: Image manipulation
    - gcse_toolkit.core.models.bounds: SliceBounds

Used By:
    - builder_v2.layout: Page composition
    - builder_v2.controller: Image loading
"""

from .provider import ImageProvider, CompositeImageProvider, ImageNotFoundError
from .cropper import crop_slice, crop_multiple

__all__ = [
    "ImageProvider",
    "CompositeImageProvider",
    "ImageNotFoundError",
    "crop_slice",
    "crop_multiple",
]
