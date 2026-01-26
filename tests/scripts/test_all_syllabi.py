"""Test syllabus parser on all syllabi to check for noise regression."""
import sys
from pathlib import Path

# Use new parser location
sys.path.insert(0, str(Path('scripts/Plugin Generation Simplified/1) Generate Initial Plugin')))
from syllabus_parser import SyllabusParser
from pathlib import Path

syllabi = [
    ('0478', 'scripts/Plugin Generation/_Syllabus/0478/0478.pdf'),
]

p = SyllabusParser(topic_mode=True)

for code, path in syllabi:
    if not Path(path).exists():
        print(f"\n{'='*60}\n{code}: FILE NOT FOUND\n{'='*60}")
        continue
        
    print(f"\n{'='*60}\n{code}\n{'='*60}")
    try:
        topics = p.parse(path)
        for t in topics[:5]:  # Show first 5 topics
            print(f"\n{t.code}. {t.title}")
            print(f"  {t.description}")
        if len(topics) > 5:
            print(f"\n  ... and {len(topics)-5} more topics")
    except Exception as e:
        print(f"  ERROR: {e}")
