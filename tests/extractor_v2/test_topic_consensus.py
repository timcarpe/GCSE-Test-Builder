"""Tests for topic consensus logic (GAP-017)."""

import pytest
from gcse_toolkit.core.models.parts import Part, PartKind, Marks, SliceBounds


def make_part(label: str, children=None, top: int = 0) -> Part:
    """Create a minimal Part for testing."""
    # Assign unique tops to children if they exist
    child_parts = []
    if children:
        for i, child in enumerate(children):
            # Recreate child with unique top
            child_parts.append(Part(
                label=child.label,
                kind=child.kind,
                bounds=SliceBounds(left=0, top=(i + 1) * 100, right=100, bottom=(i + 1) * 100 + 50),
                marks=child.marks,
                children=child.children,
            ))
    
    return Part(
        label=label,
        kind=PartKind.QUESTION if label.isdigit() else PartKind.LETTER,
        bounds=SliceBounds(left=0, top=top, right=100, bottom=top + 50),
        marks=Marks.inferred(1),
        children=tuple(child_parts),
    )


class TestIsUnknown:
    """Tests for _is_unknown helper."""
    
    def test_none_is_unknown(self):
        from gcse_toolkit.extractor_v2.classification import _is_unknown
        assert _is_unknown(None) is True
    
    def test_empty_string_is_unknown(self):
        from gcse_toolkit.extractor_v2.classification import _is_unknown
        assert _is_unknown("") is True
    
    def test_unknown_variants(self):
        from gcse_toolkit.extractor_v2.classification import _is_unknown
        assert _is_unknown("Unknown") is True
        assert _is_unknown("00. Unknown") is True
        assert _is_unknown("UNKNOWN") is True
    
    def test_real_topic_not_unknown(self):
        from gcse_toolkit.extractor_v2.classification import _is_unknown
        assert _is_unknown("01. Data representation") is False
        assert _is_unknown("Arrays") is False


class TestPropagateTopics:
    """Tests for propagate_topics function."""
    
    def test_child_topic_propagates_to_unknown_parent(self):
        """Unknown parent adopts first classified child's topic."""
        from gcse_toolkit.extractor_v2.classification import propagate_topics
        
        # Tree: 6 -> (a) -> (i)
        tree = make_part("6", [
            make_part("(a)", [
                make_part("(i)")
            ])
        ])
        
        part_topics = {
            "6": "00. Unknown",
            "(a)": "00. Unknown",
            "(i)": "Arrays"
        }
        
        result = propagate_topics(part_topics, tree)
        
        assert result["(i)"] == "Arrays"
        assert result["(a)"] == "Arrays"  # Adopted from child
        assert result["6"] == "Arrays"    # Adopted from child
    
    def test_sibling_topic_fills_unknown_middle(self):
        """Unknown sibling adopts topic when neighbors agree."""
        from gcse_toolkit.extractor_v2.classification import propagate_topics
        
        # Tree: 6 -> (a), (b), (c)
        tree = make_part("6", [
            make_part("(a)"),
            make_part("(b)"),
            make_part("(c)")
        ])
        
        part_topics = {
            "6": "00. Unknown",
            "(a)": "Arrays",
            "(b)": "00. Unknown",  # Unknown middle
            "(c)": "Arrays"
        }
        
        result = propagate_topics(part_topics, tree)
        
        assert result["(b)"] == "Arrays"  # Filled from neighbors
    
    def test_sibling_topic_no_fill_when_neighbors_disagree(self):
        """Unknown sibling stays Unknown when neighbors have different topics."""
        from gcse_toolkit.extractor_v2.classification import propagate_topics
        
        tree = make_part("6", [
            make_part("(a)"),
            make_part("(b)"),
            make_part("(c)")
        ])
        
        part_topics = {
            "6": "00. Unknown",
            "(a)": "Arrays",
            "(b)": "00. Unknown",
            "(c)": "Loops"  # Different from (a)
        }
        
        result = propagate_topics(part_topics, tree)
        
        assert result["(b)"] == "00. Unknown"  # Not filled


class TestGetConsensusTopic:
    """Tests for get_consensus_topic function."""
    
    def test_returns_most_frequent_topic(self):
        from gcse_toolkit.extractor_v2.classification import get_consensus_topic
        
        part_topics = {
            "6": "00. Unknown",
            "(a)": "Arrays",
            "(b)": "Arrays",
            "(c)": "Loops"
        }
        
        result = get_consensus_topic(part_topics)
        
        assert result == "Arrays"  # 2 vs 1
    
    def test_returns_unknown_when_all_unknown(self):
        from gcse_toolkit.extractor_v2.classification import get_consensus_topic, UNKNOWN_TOPIC
        
        part_topics = {
            "6": "00. Unknown",
            "(a)": "00. Unknown"
        }
        
        result = get_consensus_topic(part_topics)
        
        assert result == UNKNOWN_TOPIC


class TestApplyTopicConsensus:
    """Integration tests for apply_topic_consensus."""
    
    def test_root_gets_topic_from_single_classified_leaf(self):
        """GAP-017 core case: root Unknown, one leaf classified."""
        from gcse_toolkit.extractor_v2.classification import apply_topic_consensus
        
        tree = make_part("6", [
            make_part("(a)", [
                make_part("(i)")
            ])
        ])
        
        part_topics = {
            "6": "00. Unknown",
            "(a)": "00. Unknown",
            "(i)": "01. Data representation"
        }
        
        result = apply_topic_consensus(part_topics, tree, "6")
        
        assert result == "01. Data representation"
    
    def test_fallback_to_most_frequent_when_no_propagation(self):
        """When propagation doesn't reach root, use consensus voting."""
        from gcse_toolkit.extractor_v2.classification import apply_topic_consensus
        
        tree = make_part("6", [
            make_part("(a)"),
            make_part("(b)"),
            make_part("(c)"),
            make_part("(d)")
        ])
        
        part_topics = {
            "6": "00. Unknown",
            "(a)": "Arrays",
            "(b)": "Arrays",
            "(c)": "Arrays",
            "(d)": "Loops"
        }
        
        result = apply_topic_consensus(part_topics, tree, "6")
        
        # Root should get Arrays (3 vs 1)
        assert result == "Arrays"
