from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap, QColor, QPainter, QPainterPath

class ImageTooltip(QWidget):
    """Floating tooltip that displays an image slice."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)  # Margin for shadow
        
        # Container for content (white background)
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 3px;
            }
        """)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(1, 1, 1, 1)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.container_layout.addWidget(self.image_label)
        
        self.layout.addWidget(self.container)
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.container.setGraphicsEffect(shadow)
        
        self.hide()

    def show_image(self, image_path, pos: QPoint):
        """Show the tooltip with the given image at the specified position."""
        if not image_path or not image_path.exists():
            return
            
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return
        
        # Scale image to 25% of original size
        scaled_width = int(pixmap.width() * 0.35)
        scaled_height = int(pixmap.height() * 0.35)
        pixmap = pixmap.scaled(scaled_width, scaled_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # Get screen dimensions for max bounds
        screen = self.screen().availableGeometry()
        max_width = int(screen.width() * 0.3)
        max_height = int(screen.height() * 0.3)
        
        # Set maximum size on the label container (clips overflow if scaled image still too large)
        self.image_label.setMaximumSize(max_width, max_height)
        
        # Set the pixmap - it will be clipped by the max size with top-left alignment
        self.image_label.setPixmap(pixmap)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # Force resize to minimum to ensure it shrinks if previous image was larger
        self.resize(self.minimumSizeHint())
        self.adjustSize()
        
        # Position logic - float to the right of cursor
        target_pos = pos + QPoint(20, 0)
        
        # Ensure it fits on screen
        if target_pos.x() + self.width() > screen.right():
            # Flip to left
            target_pos = pos - QPoint(self.width() + 20, 0)
            
        if target_pos.y() + self.height() > screen.bottom():
            # Shift up
            target_pos.setY(screen.bottom() - self.height() - 10)
            
        self.move(target_pos)
        self.show()
        self.raise_()

    def show_region(self, pixmap: QPixmap, bounds, pos: QPoint):
        """Show a region of a cached pixmap using bounds.
        
        Crops the pixmap to the specified bounds and displays it,
        dynamically sizing the tooltip based on the region's dimensions.
        """
        if pixmap.isNull():
            return
        
        # Extract region via QPixmap.copy()
        left = bounds.left
        top = bounds.top
        width = (bounds.right if bounds.right else pixmap.width()) - left
        height = bounds.bottom - top
        
        region_pixmap = pixmap.copy(left, top, width, height)
        if region_pixmap.isNull():
            return
        
        # Scale to 35%
        scaled = region_pixmap.scaled(
            int(region_pixmap.width() * 0.35),
            int(region_pixmap.height() * 0.35),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Get screen dimensions for max bounds
        screen = self.screen().availableGeometry()
        max_width = int(screen.width() * 0.4)
        max_height = int(screen.height() * 0.5)
        
        # Clamp to max screen bounds
        final_width = min(scaled.width(), max_width)
        final_height = min(scaled.height(), max_height)
        
        # Set pixmap on label
        self.image_label.setPixmap(scaled)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # Calculate tooltip total size (image + container margins + layout margins)
        # Container layout has 1px margins, main layout has 10px margins
        tooltip_width = final_width + 2 + 20  # 1+1 container + 10+10 main
        tooltip_height = final_height + 2 + 20
        
        # Force the exact size by using resize() directly
        self.resize(tooltip_width, tooltip_height)
        
        # Position to right of cursor
        target_pos = pos + QPoint(20, 0)
        
        if target_pos.x() + tooltip_width > screen.right():
            target_pos = pos - QPoint(tooltip_width + 20, 0)
        if target_pos.y() + tooltip_height > screen.bottom():
            target_pos.setY(screen.bottom() - tooltip_height - 10)
        
        self.move(target_pos)
        self.show()
        self.raise_()



