"""Material Design icons via QtAwesome."""
import qtawesome as qta
from gcse_toolkit.gui_v2.styles.theme import Colors

class MaterialIcons:
    """Centralized Material Design icon definitions using QtAwesome."""
    
    # Navigation & Actions
    @staticmethod
    def folder_open():
        """Browse/Open folder icon."""
        return qta.icon('mdi6.folder-open-outline', color=Colors.TEXT_SECONDARY)
    
    @staticmethod
    def folder():
        """Folder icon (subtle)."""
        return qta.icon('mdi6.folder-outline', color=Colors.TEXT_SECONDARY)
    
    @staticmethod
    def refresh():
        """Reload/refresh icon."""
        return qta.icon('mdi6.refresh', color=Colors.TEXT_SECONDARY)
    
    @staticmethod
    def play():
        """Generate/execute action icon."""
        return qta.icon('mdi6.play-circle-outline', color=Colors.TEXT_ON_PRIMARY)
    
    @staticmethod
    def file_export():
        """Extract/export icon."""
        return qta.icon('mdi6.file-export-outline', color=Colors.TEXT_ON_PRIMARY)
    
    @staticmethod
    def dice():
        """Randomize icon."""
        return qta.icon('mdi6.dice-5-outline', color=Colors.TEXT_SECONDARY)
    
    @staticmethod
    def plus(color=None):
        """Add/plus icon."""
        return qta.icon('mdi6.plus', color=color or Colors.TEXT_ON_PRIMARY)
    
    @staticmethod
    def magnify(color=None):
        """Search/preview icon."""
        return qta.icon('mdi6.magnify', color=color or Colors.TEXT_ON_PRIMARY)
    
    @staticmethod
    def delete():
        """Clear/delete icon."""
        return qta.icon('mdi6.delete-outline', color=Colors.ERROR)
    
    @staticmethod
    def content_copy():
        """Copy icon."""
        return qta.icon('mdi6.content-copy', color=Colors.TEXT_SECONDARY)
    
    @staticmethod
    def content_save():
        """Save icon."""
        return qta.icon('mdi6.content-save-outline', color=Colors.TEXT_SECONDARY)

    @staticmethod
    def close():
        """Close/X icon."""
        return qta.icon('mdi6.close', color=Colors.TEXT_SECONDARY)

    @staticmethod
    def question(color=None):
        """Question mark icon."""
        return qta.icon('mdi6.help-circle-outline', color=color or Colors.TEXT_SECONDARY)

    @staticmethod
    def settings(color=None):
        """Settings gear icon."""
        return qta.icon('mdi6.cog-outline', color=color or Colors.TEXT_SECONDARY)
