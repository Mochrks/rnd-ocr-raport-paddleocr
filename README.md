# OCR Raport — Indonesian School Report Card Scanner

A production-quality REST API for extracting academic data from Indonesian school report cards (Raport) using PaddleOCR. Supports both digital PDFs and scanned/handwritten report cards.

---

## Features

- **Dual-mode OCR**: PPStructure table recognition (Mode 1) with Y-clustering fallback (Mode 2)
- **Subject extraction**: Matches 12+ standard subjects including OCR typo variants
- **KKM detection**: Automatically identifies the minimum competency score column
- **Personality data**: Extracts Kelakuan / Kerajinan / Kerapihan grades
- **Attendance data**: Extracts Sakit / Ijin / Alpa counts
- **Handwritten support**: Works on manually-written report cards
- **PDF support**: Auto-converts each page to image, merges results

---

## Architecture

```
Presentation   →   app/api/v1/endpoints/      HTTP routing only
Application    →   app/application/           Use-case orchestration + timing
Services       →   app/services/              OCR extraction, matching, parsing
Domain         →   app/domain/                MASTER_SUBJECTS, pure business rules
Infrastructure →   app/infrastructure/        PaddleOCR engine, preprocessor, store
```

---

## Folder Structure

```
backend-paddleocr/
├── app/
│   ├── main.py                          # FastAPI app factory
│   ├── api/v1/
│   │   ├── router.py                    # v1 router aggregator
│   │   └── endpoints/ocr.py             # Upload + debug HTTP handlers
│   ├── application/
│   │   └── ocr_use_case.py             # run_ocr_pipeline()
│   ├── core/
│   │   ├── config.py                    # Pydantic Settings (.env)
│   │   ├── logging.py                   # Structured logging + PhaseLogger
│   │   └── exceptions.py               # Custom exception hierarchy
│   ├── domain/
│   │   └── constants.py                # MASTER_SUBJECTS (all 15 subjects)
│   ├── infrastructure/
│   │   ├── ocr/
│   │   │   ├── engine.py               # PaddleOCR + PPStructure singletons
│   │   │   ├── preprocessor.py         # OpenCV preprocessing
│   │   │   ├── pdf_converter.py        # PDF → images
│   │   │   ├── result_flattener.py     # OCR output normalizer
│   │   │   └── column_detector.py      # Table column X-position detection
│   │   └── storage/
│   │       └── document_store.py       # In-memory document registry
│   ├── schemas/
│   │   └── ocr_schemas.py              # Pydantic request/response models
│   ├── services/
│   │   ├── ocr_orchestrator.py         # Mode selection + PDF handling
│   │   ├── table_extractor.py          # Mode 1: PPStructure → DataFrame
│   │   ├── row_extractor.py            # Mode 2: Raw OCR + Y-clustering
│   │   ├── mapping_engine.py           # Fuzzy subject/personality/attendance match
│   │   ├── score_parser.py             # parse_score(), is_valid_score()
│   │   ├── kkm_assigner.py             # KKM vs Score column assignment
│   │   └── response_builder.py         # Dict → Pydantic response models
│   └── utils/
│       └── text_normalizer.py          # OCR text normalization
├── tests/
│   ├── unit/                            # Pure logic tests (no PaddleOCR)
│   │   ├── test_score_parser.py
│   │   ├── test_mapping_engine.py
│   │   ├── test_personality_guard.py
│   │   └── test_kkm_assigner.py
│   ├── integration/                     # FastAPI TestClient tests
│   └── fixtures/sample_reports/        # Sample images for manual testing
├── uploads/                             # Runtime uploads (git-ignored)
├── .env                                 # Local environment (git-ignored)
├── .env.example                         # Environment template
├── requirements.txt                     # Production dependencies
├── requirements-dev.txt                 # Dev/test dependencies
└── pytest.ini                          # Pytest configuration
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- pip
- (Optional) Poppler — only needed if using `pdf2image` as PDF fallback

### 1. Clone & Enter the Project

```bash
git clone <your-repo-url>
cd backend-paddleocr
```

### 2. Create & Activate Virtual Environment

```bash
# Windows (Command Prompt / PowerShell)
python -m venv venv
venv\Scripts\activate

# Windows (Git Bash)
python -m venv venv
source venv/Scripts/activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Production
pip install -r requirements.txt

# + Development tools (for testing)
pip install -r requirements-dev.txt
```

### 4. Configure Environment

```bash
copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux
```

Edit `.env` as needed. All settings have sensible defaults — the app works without changes.

### 5. Run the Server

```bash
# Development (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

#or
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> ⚠️ **Note**: PaddleOCR is not thread-safe across multiple workers. Use `--workers 1`.

---

## Environment Variables

| Variable                        | Default   | Description                              |
| ------------------------------- | --------- | ---------------------------------------- |
| `DEBUG`                         | `false`   | Enable debug mode                        |
| `LOG_LEVEL`                     | `INFO`    | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_FILE`                      | _(none)_  | Optional log file path                   |
| `UPLOAD_DIR`                    | `uploads` | Directory for uploaded files             |
| `MAX_UPLOAD_SIZE_MB`            | `20`      | Maximum upload size                      |
| `OCR_LANG`                      | `en`      | PaddleOCR language model                 |
| `OCR_DET_THRESH`                | `0.3`     | Text detection threshold                 |
| `OCR_BOX_THRESH`                | `0.4`     | Bounding box threshold                   |
| `OCR_WARMUP_ON_STARTUP`         | `false`   | Pre-initialize engines at boot           |
| `PREPROCESSING_DENOISE_ENABLED` | `true`    | Enable OpenCV denoising                  |
| `PDF_RENDER_SCALE`              | `2.0`     | PDF-to-image DPI multiplier              |
| `FUZZY_MATCH_THRESHOLD`         | `60`      | Minimum fuzzy match score (0–100)        |
| `Y_CLUSTER_TOLERANCE`           | `20`      | Y-axis row clustering tolerance (px)     |

---

## API Reference

Interactive docs: `http://localhost:8000/docs`

### POST `/api/v1/academic/report/upload`

Upload a report card image or PDF for OCR extraction.

**Request:**

- `Content-Type: multipart/form-data`
- `file`: The report card file (PNG, JPG, JPEG, PDF)

**Response:**

```json
{
  "documentId": "DOC1A2B3C4",
  "status": "SUCCESS",
  "accuracy": 87.5,
  "processingTime": 3.21,
  "subjects": [
    {
      "subjectId": 1,
      "subjectName": "Agama",
      "originalText": "Pendidikan Agama Islam",
      "category": "Umum",
      "kkm": 70.0,
      "score": 85.0,
      "accuracy": 91.2
    }
  ],
  "personality": {
    "kelakuan": { "grade": "A", "accuracy": 89.0 },
    "kerajinan": { "grade": "B", "accuracy": 87.0 },
    "kerapihan": { "grade": "A", "accuracy": 90.0 }
  },
  "attendance": {
    "sakit": { "value": 2, "accuracy": 95.0 },
    "ijin": { "value": 1, "accuracy": 95.0 },
    "alpa": { "value": 0, "accuracy": 95.0 }
  }
}
```

---

### GET `/api/v1/academic/report/{documentId}/debug`

Returns raw OCR output for a previously uploaded document — useful for diagnosing extraction issues.

**Response includes:**

- `raw_text`: All detected text, one word per line
- `total_detections`: Word count
- `detections`: Per-word position, confidence, and value classification
- `rows`: Y-clustered rows
- `detected_columns`: Column X positions (subject, KKM, score, grade)
- `score_zone_start`: Computed left boundary of the value zone

---

## Running Tests

```bash
# All unit tests (no PaddleOCR required)
pytest tests/unit/ -v

# With logging output
pytest tests/unit/ -v --log-cli-level=INFO

# Single test file
pytest tests/unit/test_score_parser.py -v
```

---

## Development Workflow

### Adding a New Subject

Edit `app/domain/constants.py` only:

```python
{
    "id": 16,
    "subject_name": "Baru Subject",
    "category": "Umum",
    "aliases": ["Baru Subject", "BS", "Baru"],
},
```

No other files need changing.

### Tuning OCR Performance

| Symptom                  | Setting to adjust                          |
| ------------------------ | ------------------------------------------ |
| Slow on digital PDFs     | Set `PREPROCESSING_DENOISE_ENABLED=false`  |
| Cold start latency       | Set `OCR_WARMUP_ON_STARTUP=true`           |
| Too many false matches   | Increase `FUZZY_MATCH_THRESHOLD` (e.g. 70) |
| Missing subjects         | Decrease `FUZZY_MATCH_THRESHOLD` (e.g. 55) |
| Misaligned row detection | Adjust `Y_CLUSTER_TOLERANCE`               |

### Adjusting PDF Resolution

```dotenv
# Higher = better quality, slower conversion
PDF_RENDER_SCALE=3.0   # 300 DPI
```

---

## Dependencies

### Production (`requirements.txt`)

- `fastapi[all]` — Web framework
- `uvicorn[standard]` — ASGI server
- `paddlepaddle==3.2.0` — PaddlePaddle deep learning framework
- `paddleocr` — OCR engine
- `opencv-python-headless` — Image preprocessing
- `rapidfuzz` — Fast fuzzy string matching
- `pandas`, `lxml` — Table HTML parsing
- `pymupdf` (optional) — PDF to image conversion

### Development (`requirements-dev.txt`)

- `pytest` — Test runner
- `httpx` — Async HTTP client for FastAPI tests
- `ruff` — Linter + formatter
- `mypy` — Static type checker

---

## Notes

- PaddleOCR downloads model weights on first use (~500MB). Ensure internet access on first run.
- The `uploads/` directory is git-ignored. Keep test files in `tests/fixtures/sample_reports/`.
- The in-memory `DocumentStore` is reset on every server restart. This is acceptable for R&D use.
