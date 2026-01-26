"""
Module: builder_v2.images.provider

Purpose:
    Abstract interface for accessing question images and slices.
    Provides clean abstraction over different storage formats.

Key Classes:
    - ImageProvider: Abstract base class for image access
    - CompositeImageProvider: Standard V2 provider (crops from composite)
    - ImageNotFoundError: Exception for missing images

Dependencies:
    - PIL: Image manipulation
    - gcse_toolkit.core.models.bounds: SliceBounds

Used By:
    - builder_v2.layout: Page composition
    - builder_v2.controller: Image loading
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image

from gcse_toolkit.core.models import SliceBounds

from .cropper import crop_slice


class ImageNotFoundError(Exception):
    """Image or slice not found."""
    pass


class ImageProvider(ABC):
    """
    Abstract interface for accessing question images.
    
    Provides clean abstraction for getting slices by label.
    Implementations handle the actual storage format.
    """
    
    @abstractmethod
    def get_slice(self, label: str) -> Image.Image:
        """
        Get the image slice for a part label.
        
        Args:
            label: Part label like "1(a)"
            
        Returns:
            Cropped PIL Image
            
        Raises:
            ImageNotFoundError: If label not found
        """
    
    @abstractmethod
    def get_bounds(self, label: str) -> SliceBounds:
        """
        Get bounds for a part label.
        
        Args:
            label: Part label
            
        Returns:
            SliceBounds for the label
            
        Raises:
            ImageNotFoundError: If label not found
        """
    
    @property
    @abstractmethod
    def composite_size(self) -> Tuple[int, int]:
        """
        Get (width, height) of composite image.
        
        Returns:
            Tuple of (width, height) in pixels
        """
    
    @property
    @abstractmethod
    def available_labels(self) -> list[str]:
        """
        Get list of available part labels.
        
        Returns:
            List of all labels that can be requested
        """


class CompositeImageProvider(ImageProvider):
    """
    Provider that crops slices from a composite image.
    
    This is the standard V2 provider. Loads composite image
    once and crops on demand.
    
    Attributes:
        composite_path: Path to composite.png
        bounds: Dict mapping labels to SliceBounds
        
    Example:
        >>> provider = CompositeImageProvider(
        ...     Path("q1/composite.png"),
        ...     {"1(a)": SliceBounds(0, 100), "1(b)": SliceBounds(100, 200)}
        ... )
        >>> slice_img = provider.get_slice("1(a)")
    """
    
    def __init__(
        self,
        composite_path: Path,
        bounds: Dict[str, SliceBounds],
    ) -> None:
        """
        Initialize provider.
        
        Args:
            composite_path: Path to composite.png file
            bounds: Dict mapping part labels to SliceBounds
        """
        self._composite_path = composite_path
        self._bounds = bounds
        self._composite: Optional[Image.Image] = None
    
    def get_slice(self, label: str, *, add_mark_clearance: bool = False) -> Image.Image:
        """Get cropped slice for a label.
        
        Args:
            label: Part label to crop
            add_mark_clearance: If True, add clearance below parts with marks
        """
        bounds = self._bounds.get(label)
        if bounds is None:
            raise ImageNotFoundError(f"No bounds for label: {label}")
        
        composite = self._get_composite()
        return crop_slice(composite, bounds, add_mark_clearance=add_mark_clearance)
    
    def get_bounds(self, label: str) -> SliceBounds:
        """Get bounds for a label."""
        bounds = self._bounds.get(label)
        if bounds is None:
            raise ImageNotFoundError(f"No bounds for label: {label}")
        return bounds
    
    @property
    def composite_size(self) -> Tuple[int, int]:
        """Get composite image size."""
        composite = self._get_composite()
        return composite.size
    
    @property
    def available_labels(self) -> list[str]:
        """Get all available labels."""
        return list(self._bounds.keys())
    
    def _get_composite(self) -> Image.Image:
        """Lazy load composite image."""
        if self._composite is None:
            if not self._composite_path.exists():
                raise ImageNotFoundError(
                    f"Composite not found: {self._composite_path}"
                )
            self._composite = Image.open(self._composite_path)
        return self._composite
    
    def close(self) -> None:
        """Close the composite image and free resources."""
        if self._composite is not None:
            self._composite.close()
            self._composite = None
    
    def __enter__(self) -> "CompositeImageProvider":
        """Context manager entry."""
        return self
    
    def __exit__(self, *args) -> None:
        """Context manager exit - close resources."""
        self.close()


def create_provider_for_question(
    question_dir: Path,
    bounds: Dict[str, SliceBounds],
) -> CompositeImageProvider:
    """
    Create an image provider for a question directory.
    
    Convenience function that creates a CompositeImageProvider
    for a standard V2 question directory.
    
    Args:
        question_dir: Path to question directory containing composite.png
        bounds: Dict mapping labels to SliceBounds
        
    Returns:
        CompositeImageProvider configured for the question
        
    Example:
        >>> provider = create_provider_for_question(
        ...     Path("cache/0478_m24_qp_12_q1"),
        ...     question.get_all_bounds()
        ... )
    """
    composite_path = question_dir / "composite.png"
    return CompositeImageProvider(composite_path, bounds)
