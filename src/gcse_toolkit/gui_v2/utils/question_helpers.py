"""
Helper functions for working with V2 Question model.

Provides convenience methods that were available in V1 QuestionRecord
but not in V2 Question.
"""

from typing import Optional

from gcse_toolkit.core.models import Part, Question


def find_part_by_label(question: Question, label: str) -> Optional[Part]:
    """
    Find part by label in question tree.
    
    V2 Questions store parts as a tree (question_node), not a flat list.
    This helper traverses the tree to find a part by label.
    
    Args:
        question: V2 Question object
        label: Part label to find (e.g., "1(a)", "2(b)(i)")
        
    Returns:
        Part if found, None otherwise
        
    Example:
        >>> question = load_single_question(question_dir)
        >>> part = find_part_by_label(question, "1(a)")
        >>> part.total_marks()
        3
    """
    for part in question.question_node.iter_all():
        if part.label == label:
            return part
    return None
