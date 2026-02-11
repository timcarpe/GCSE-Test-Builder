import sys

from pathlib import Path

sys.path.append(str(Path("scripts/Plugin Generation Simplified/1) Generate Initial Plugin")))

from syllabus_parser import SyllabusParser  # noqa: E402


def test_syllabus_parser_v2_topics_and_subtopics():
    pdf_path = Path("scripts/Plugin Generation/_Syllabus/0478/0478.pdf")
    if not pdf_path.exists():
        pytest.skip("0478.pdf not found in Plugin Generation/_Syllabus/0478/")
    
    parser = SyllabusParser()
    topics = parser.parse(str(pdf_path))

    assert len(topics) == 10
    codes = [t.code for t in topics]
    assert codes == [str(i) for i in range(1, 11)]

    topic7 = next(t for t in topics if t.code == "7")
    assert len(topic7.subtopics) == 0

    # Verify all topics have valid descriptions (keywords extracted).
    # Subtopics may be empty depending on syllabus structure.
    for topic in topics:
        assert topic.description, f"Topic {topic.code} should have a description"
