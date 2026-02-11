# GCSE Test Builder

> Build custom practice exams from official past papers in minutes.

## What is GCSE Test Builder?

GCSE Test Builder is a desktop application that lets you create tailored 
practice exams by extracting and recombining questions from PDF past papers.

Teachers and students can:
- Extract questions from Cambridge IGCSE/A-Level PDF papers
- Filter by topic, year, or keyword
- Generate custom practice papers targeting specific marks
- Include or exclude mark schemes

## How It Works

1. **Extract** - Drop your PDF exam papers into the input folder and click Extract
2. **Filter** - Select topics or search keywords to find relevant questions
3. **Generate** - Set your target marks and generate a custom PDF

## Features

- Smart question detection with hierarchical part recognition
- Topic-based filtering using exam board syllabus structure
- Keyword search across all extracted questions
- Mark target optimization (e.g., "give me 50 marks on Algorithms")
- PDF and ZIP export formats
- Mark scheme inclusion option
- Dark mode interface

## Installation

### Download (Recommended)

Download the latest release for your platform:
- [Windows (.exe)](https://github.com/timcarpe/GCSE-Test-Builder/releases)
- [macOS (.dmg)](https://github.com/timcarpe/GCSE-Test-Builder/releases)

### Run from Source

Requires Python 3.11+

```bash
git clone https://github.com/timcarpe/GCSE-Tool-Kit.git
cd GCSE-Tool-Kit
pip install -e .
python run_gui_v2.py
```

## Supported Exams

Currently supports Cambridge IGCSE/A-Level exams:
- 0450 Business Studies
- 0455 Economics
- 0478 Computer Science
- 0580 Mathematics
- 0610 Biology
- 0620 Chemistry
- 0653 Combined Science
- 9618 A-Level Computer Science

Adding new exams is possible via the plugin system.

## Documentation

- [Architecture Overview](docs/architecture/README.md)
- [Plugin Development](src/gcse_toolkit/plugins/README.md)

## License

Polyform Noncommercial License 1.0.0 - See [LICENSE.txt](LICENSE.txt)

## Disclaimer

This tool is for educational use. Users are responsible for ensuring their 
use of exam materials complies with relevant copyright and licensing terms.
