"""
Topic Selector for the Build tab.
Displays topics and sub-topics with checkboxes and expand/collapse functionality.
"""
from pathlib import Path
from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QCheckBox, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from gcse_toolkit.gui_v2.styles.theme import Colors, Styles, Fonts, get_styles, get_colors
from gcse_toolkit.gui_v2.utils.helpers import load_topics
from gcse_toolkit.gui_v2.utils.tooltips import apply_tooltip
from gcse_toolkit.common import FALLBACK_SUB_TOPIC

class TopicSelector(QWidget):
    """
    Topic selector widget with expand/collapse sub-topics and selection logic.
    Tracks topic/sub-topic selections and syncs with "Select All" checkbox.
    """
    
    selectionChanged = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(12)
        
        # --- Selection Tree ---
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.setIndentation(20)
        S = get_styles()
        self.tree.setStyleSheet(S.TREE_WIDGET)
        self.layout.addWidget(self.tree)
        apply_tooltip(self.tree, "Select topics and expand to refine by sub-topics.")
        
        # Select All Header
        self.select_all_item = QTreeWidgetItem(self.tree)
        self.select_all_cb = QCheckBox("Select All")
        S = get_styles()
        self.select_all_cb.setStyleSheet(S.CHECKBOX)
        self.select_all_cb.toggled.connect(self._on_select_all_toggled)
        self.tree.setItemWidget(self.select_all_item, 0, self.select_all_cb)
        apply_tooltip(self.select_all_cb, "Select or deselect every topic.")
        
        # State tracking
        self.current_exam = None
        self.topics_list: List[str] = []
        self.topic_counts: Dict[str, int] = {}
        self.sub_topic_counts: Dict[str, Dict[str, int]] = {}
        
        self.topic_items: Dict[str, QTreeWidgetItem] = {}
        self.topic_checkboxes: Dict[str, QCheckBox] = {}
        self.sub_topic_items: Dict[str, Dict[str, QTreeWidgetItem]] = {}
        self.sub_topic_checkboxes: Dict[str, Dict[str, QCheckBox]] = {}

    def load_topics_for_exam(self, exam_code: str, metadata_root: Path, year_filter: Optional[List[str]] = None, paper_filter: Optional[List[int]] = None):
        """Load topics from metadata for the given exam code."""
        self.current_exam = exam_code
        
        # Clear existing
        self._clear_topics()
        
        # Load topics (with optional year and paper filters)
        topics_list, counts, sub_counts = load_topics(metadata_root, exam_code, year_filter=year_filter, paper_filter=paper_filter)
        self.topics_list = topics_list
        self.topic_counts = counts
        self.sub_topic_counts = sub_counts
        
        # Populate UI
        self._populate_topics()

    def _clear_topics(self):
        """Clear all topics from the tree, preserving Select All."""
        # Remove all items except "Select All" (index 0)
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount() - 1, 0, -1):
            root.removeChild(root.child(i))
            
        self.topic_items.clear()
        self.topic_checkboxes.clear()
        self.sub_topic_items.clear()
        self.sub_topic_checkboxes.clear()

    def _populate_topics(self):
        """Populate topics using native Qt tree widget features."""
        for topic in self.topics_list:
            count = self.topic_counts.get(topic, 0)
            
            # Create topic item
            topic_item = QTreeWidgetItem(self.tree)
            self.topic_items[topic] = topic_item
            
            # Create topic checkbox
            topic_cb = QCheckBox(f"{topic} ({count})")
            S = get_styles()
            topic_cb.setStyleSheet(S.CHECKBOX)
            topic_cb.toggled.connect(lambda checked, t=topic: self._on_topic_toggled(t, checked))
            self.topic_checkboxes[topic] = topic_cb
            self.tree.setItemWidget(topic_item, 0, topic_cb)
            apply_tooltip(topic_cb, "Toggle whether this topic can contribute questions.")
            
            # Add sub-topics as children (using native tree hierarchy)
            sub_topics = self.sub_topic_counts.get(topic, {})
            if sub_topics:
                self.sub_topic_items[topic] = {}
                self.sub_topic_checkboxes[topic] = {}
                for sub_topic, sub_count in sub_topics.items():
                    if sub_topic == FALLBACK_SUB_TOPIC:
                        continue
                    sub_item = QTreeWidgetItem(topic_item)
                    self.sub_topic_items[topic][sub_topic] = sub_item
                    
                    sub_cb = QCheckBox(f"{sub_topic} ({sub_count})")
                    S = get_styles()
                    sub_cb.setStyleSheet(S.CHECKBOX)
                    sub_cb.toggled.connect(lambda checked, t=topic, st=sub_topic: self._on_sub_topic_toggled(t, st, checked))
                    self.sub_topic_checkboxes[topic][sub_topic] = sub_cb
                    self.tree.setItemWidget(sub_item, 0, sub_cb)
                    apply_tooltip(sub_cb, "Toggle whether this specific sub-topic can contribute questions.")
                
                # Start collapsed
                topic_item.setExpanded(False)



    def _on_topic_toggled(self, topic: str, checked: bool):
        """Handle topic checkbox toggle - sync with sub-topics."""
        # Set all sub-topics to same state
        if topic in self.sub_topic_checkboxes:
            for sub_cb in self.sub_topic_checkboxes[topic].values():
                sub_cb.blockSignals(True)
                sub_cb.setChecked(checked)
                sub_cb.blockSignals(False)
        
        # Auto-expand if checked and has subtopics
        if topic in self.topic_items:
            topic_item = self.topic_items[topic]
            if checked:
                topic_item.setExpanded(True)
            else:
                topic_item.setExpanded(False)
        
        # Sync select all
        self._sync_select_all()
        self.selectionChanged.emit()

    def _on_sub_topic_toggled(self, topic: str, sub_topic: str, checked: bool):
        """Handle sub-topic checkbox toggle - sync with parent and manage expansion."""
        if topic in self.sub_topic_checkboxes:
            any_checked = any(cb.isChecked() for cb in self.sub_topic_checkboxes[topic].values())
            all_checked = all(cb.isChecked() for cb in self.sub_topic_checkboxes[topic].values())
            
            # Update parent checkbox
            if topic in self.topic_checkboxes:
                self.topic_checkboxes[topic].blockSignals(True)
                self.topic_checkboxes[topic].setChecked(any_checked)
                self.topic_checkboxes[topic].blockSignals(False)
            
            # Auto-expand/collapse based on selection state
            if topic in self.topic_items:
                topic_item = self.topic_items[topic]
                if any_checked and not all_checked:
                    # Partial selection - keep expanded
                    topic_item.setExpanded(True)
                elif all_checked:
                    # All selected - can collapse for cleaner view
                    topic_item.setExpanded(False)
                elif not any_checked:
                    # None selected - collapse
                    topic_item.setExpanded(False)
        
        # Sync select all
        self._sync_select_all()
        self.selectionChanged.emit()

    def _on_select_all_toggled(self, checked: bool):
        """Handle Select All checkbox toggle."""
        # Block signals to avoid recursion
        for topic, cb in self.topic_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
            
            # Also set sub-topics
            if topic in self.sub_topic_checkboxes:
                for sub_cb in self.sub_topic_checkboxes[topic].values():
                    sub_cb.blockSignals(True)
                    sub_cb.setChecked(checked)
                    sub_cb.blockSignals(False)
                
                # Expand if checked
                if checked and topic in self.topic_items:
                    self.topic_items[topic].setExpanded(True)
        
        self.selectionChanged.emit()

    def _sync_select_all(self):
        """Sync Select All checkbox based on topic states."""
        if not self.topic_checkboxes:
            self.select_all_cb.blockSignals(True)
            self.select_all_cb.setChecked(False)
            self.select_all_cb.blockSignals(False)
            return
        
        # Check if all topics (and their sub-topics if any) are selected
        all_selected = True
        for topic, cb in self.topic_checkboxes.items():
            if not cb.isChecked():
                all_selected = False
                break
            
            # Check sub-topics
            if topic in self.sub_topic_checkboxes:
                if not all(sub_cb.isChecked() for sub_cb in self.sub_topic_checkboxes[topic].values()):
                    all_selected = False
                    break
        
        self.select_all_cb.blockSignals(True)
        self.select_all_cb.setChecked(all_selected)
        self.select_all_cb.blockSignals(False)

    def get_selected_topics(self) -> List[str]:
        """
        Get list of selected topics.
        Includes the topic when any sub-topic is selected (or no sub-topics exist),
        mirroring the v1 behaviour so partial selections still count as a topic filter.
        """
        result = []
        for topic, cb in self.topic_checkboxes.items():
            if not cb.isChecked():
                continue
                
            # Check if has subtopics with visible checkboxes
            sub_cbs = self.sub_topic_checkboxes.get(topic, {})
            if sub_cbs:
                # Count topic as selected if any sub-topic is checked
                any_sub_selected = any(
                    sub_cb.isChecked() 
                    for sub_cb in sub_cbs.values()
                )
                if any_sub_selected:
                    result.append(topic)
            else:
                # No visible subtopics (or all filtered like FALLBACK_SUB_TOPIC),
                # include the topic directly when parent is checked
                result.append(topic)
        
        return result

    def get_selected_sub_topics(self) -> Dict[str, List[str]]:
        """
        Get dict of selected sub-topics per topic.
        Only includes entries where NOT all subtopics are selected (partial selection).
        This matches v1 behavior.
        """
        result = {}
        for topic, sub_cbs in self.sub_topic_checkboxes.items():
            selected = [sub for sub, cb in sub_cbs.items() if cb.isChecked()]
            
            # Only include if partial selection (not all selected, not none selected)
            if selected and len(selected) < len(sub_cbs):
                result[topic] = selected
        
        return result

    def set_selected_topics(self, topics: List[str], sub_topics: Dict[str, List[str]]):
        """Set selected topics and sub-topics (e.g., from saved settings)."""
        # First, uncheck all
        for cb in self.topic_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        
        for sub_cbs in self.sub_topic_checkboxes.values():
            for cb in sub_cbs.values():
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
        
        # Set topics
        for topic in topics:
            if topic in self.topic_checkboxes:
                topic_cb = self.topic_checkboxes[topic]
                
                # Check if has sub-topics
                if topic in self.sub_topic_checkboxes:
                    # Set sub-topics
                    selected_subs = sub_topics.get(topic, [])
                    if not selected_subs:
                        # Select all sub-topics
                        for sub_cb in self.sub_topic_checkboxes[topic].values():
                            sub_cb.blockSignals(True)
                            sub_cb.setChecked(True)
                            sub_cb.blockSignals(False)
                    else:
                        for sub in selected_subs:
                            if sub in self.sub_topic_checkboxes[topic]:
                                self.sub_topic_checkboxes[topic][sub].blockSignals(True)
                                self.sub_topic_checkboxes[topic][sub].setChecked(True)
                                self.sub_topic_checkboxes[topic][sub].blockSignals(False)
                    
                    # Set parent based on sub-topics
                    any_sub_checked = any(cb.isChecked() for cb in self.sub_topic_checkboxes[topic].values())
                    topic_cb.blockSignals(True)
                    topic_cb.setChecked(any_sub_checked)
                    topic_cb.blockSignals(False)
                else:
                    # No sub-topics, just check the topic
                    topic_cb.blockSignals(True)
                    topic_cb.setChecked(True)
                    topic_cb.blockSignals(False)
        
        # Sync select all
        self._sync_select_all()
    def update_theme(self):
        """Update styles when theme changes."""
        S = get_styles()
        
        # Update Tree
        self.tree.setStyleSheet(S.TREE_WIDGET)
        
        # Update Select All
        self.select_all_cb.setStyleSheet(S.CHECKBOX)
        
        # Update Topics
        for topic_cb in self.topic_checkboxes.values():
            topic_cb.setStyleSheet(S.CHECKBOX)
            
        # Update Sub-topics
        for sub_cbs in self.sub_topic_checkboxes.values():
            for sub_cb in sub_cbs.values():
                sub_cb.setStyleSheet(S.CHECKBOX)
