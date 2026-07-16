# OCR Raport — Indonesian School Report Card Scanner

A production-quality REST API for extracting academic data from Indonesian school report cards (Raport). Supports both PaddleOCR (local) and AI Vision models (DeepSeek, Qwen3-VL) as extraction engines.

---

## Features

- **Dual OCR engines**: PaddleOCR (local) and AI Vision (DeepSeek / Qwen3-VL) — same response format for both
- **Dual-mode OCR**: PPStructure table recognition (Mode 1) with Y-clustering fallback (Mode 2)
- **Subject extraction**: Matches 15 standard subjects including OCR typo variants
- **KKM detection**: Automatically identifies the minimum competency score column
- **Personality data**: Extracts Kelakuan / Kerajinan / Kerapihan grades
- **Attendance data**: Extracts Sakit / Ijin / Alpa counts
- **Handwritten support**: Works on manually-written report cards
- **PDF support**: Auto-converts each page to image, merges results
- **Pluggable storage**: In-memory (default) or Redis-backed document store
- **CORS support**: Configurable allowed origins, methods, and headers

---

## Architecture

```
Presentation   →   app/api/v1/endpoints/      HTTP routing only
Application    →   app/application/           Use-case orchestration + timing
Services       →   app/services/              OCR extraction, matching, parsing
Domain         →   app/domain/                MASTER_SUBJECTS, pure business rules
Infrastructure →   app/infrastructure/        PaddleOCR engine, AI clients, preprocessor, store
```

---

## Folder Structure

```
backend-paddleocr/
├── app/
│   ├── main.py                          # FastAPI app factory
│   ├── api/v1/
│   │   ├── router.py                    # v1 router aggregator (ocr + ai_ocr)
│   │   └── endpoints/
│   │       ├── ocr.py                   # PaddleOCR upload + debug handlers
│   │       └── ai_ocr.py               # AI Vision upload handlers (DeepSeek, Qwen)
│   ├── application/
│   │   ├── ocr_use_case.py             # run_ocr_pipeline()
│   │   └── ai_ocr_use_case.py          # run_ai_ocr_pipeline()
│   ├── core/
│   │   ├── config.py                    # Pydantic Settings (.env)
│   │   ├── logging.py                   # Structured logging + PhaseLogger
│   │   └── exceptions.py               # Custom exception hierarchy
│   ├── domain/
│   │   ├── constants.py                # MASTER_SUBJECTS (15 subjects)
│   │   └── ai_vision_dto.py            # DTOs for AI Vision responses
│   ├── infrastructure/
│   │   ├── ocr/
│   │   │   ├── engine.py               # PaddleOCR + PPStructure singletons
│   │   │   ├── preprocessor.py         # OpenCV preprocessing
│   │   │   ├── pdf_converter.py        # PDF → images
│   │   │   ├── result_flattener.py     # OCR output normalizer
│   │   │   └── column_detector.py      # Table column X-position detection
│   │   ├── ai/
│   │   │   ├── base_client.py          # Abstract AI Vision client
│   │   │   ├── deepseek_client.py      # DeepSeek Vision API client
│   │   │   └── qwen_client.py          # Qwen3-VL Vision API client
│   │   └── storage/
│   │       ├── base.py                 # BaseDocumentStore + DocumentRecord
│   │       ├── in_memory_store.py      # Default in-memory store
│   │       └── redis_store.py          # Redis-backed store (multi-worker)
│   ├── schemas/
│   │   └── ocr_schemas.py              # Pydantic request/response models
│   ├── services/
│   │   ├── ocr_orchestrator.py         # Mode selection + PDF handling
│   │   ├── table_extractor.py          # Mode 1: PPStructure → DataFrame
│   │   ├── row_extractor.py            # Mode 2: Raw OCR + Y-clustering
│   │   ├── mapping_engine.py           # Fuzzy subject/personality/attendance match
│   │   ├── score_parser.py             # parse_score(), is_valid_score()
│   │   ├── kkm_assigner.py             # KKM vs Score column assignment
│   │   ├── response_builder.py         # Dict → Pydantic response models
│   │   ├── ai_prompt_builder.py        # Prompt construction for AI Vision
│   │   └── ai_response_mapper.py       # AI Vision JSON → internal model
│   └── api/
│       └── deps.py                     # FastAPI dependency injection
├── tests/
│   ├── unit/                            # Pure logic tests (no PaddleOCR)
│   └── integration/                     # FastAPI TestClient tests
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
- (Optional) Redis — only needed when using `REDIS_URL` for multi-worker storage
- (Optional) Poppler — only needed if using `pdf2image` as PDF fallback

### 1. Clone & Enter the Project

```bash
git clone <your-repo-url>
cd backend-paddleocr
```

### 2. Create & Activate Virtual Environment

```bash
# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

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

> **Note**: If you get `No module named uvicorn` after activating the venv, the venv is empty — run `pip install -r requirements.txt` to install all packages.

### 4. Configure Environment

```bash
copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux
```

Edit `.env` and fill in the required values. See the [Environment Variables](#environment-variables) table below.

### 5. Run the Server

```bash
# Development (auto-reload)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> ⚠️ **Note**: PaddleOCR is not thread-safe across multiple workers. Always use `--workers 1`.

---

## Environment Variables

All variables are **required** unless marked optional. Copy `.env.example` to `.env` and fill in the values.

### Application

| Variable           | Example                    | Description                  |
| ------------------ | -------------------------- | ---------------------------- |
| `APP_TITLE`        | `OCR Raport API`           | API title shown in Swagger   |
| `APP_DESCRIPTION`  | `School report card OCR`   | API description              |
| `APP_VERSION`      | `1.0.0`                    | API version string           |
| `DEBUG`            | `false`                    | Enable debug mode            |

### CORS

| Variable                    | Example                             | Description                                    |
| --------------------------- | ----------------------------------- | ---------------------------------------------- |
| `CORS_ORIGINS`              | `["*"]`                             | Allowed origins (JSON array)                   |
| `CORS_ALLOW_CREDENTIALS`    | `true`                              | Allow credentials                              |
| `CORS_ALLOW_METHODS`        | `["*"]`                             | Allowed HTTP methods                           |
| `CORS_ALLOW_HEADERS`        | `["*"]`                             | Allowed request headers                        |

### File Upload

| Variable               | Example                        | Description                      |
| ---------------------- | ------------------------------ | -------------------------------- |
| `UPLOAD_DIR`           | `uploads`                      | Directory for uploaded files     |
| `MAX_UPLOAD_SIZE_MB`   | `20`                           | Maximum upload size in MB        |
| `ALLOWED_EXTENSIONS`   | `[".png",".jpg",".jpeg",".pdf"]` | Accepted file extensions       |

### OCR Engine

| Variable                        | Example | Description                                    |
| ------------------------------- | ------- | ---------------------------------------------- |
| `OCR_LANG`                      | `en`    | PaddleOCR language model                       |
| `OCR_DET_THRESH`                | `0.3`   | Text detection threshold                       |
| `OCR_BOX_THRESH`                | `0.4`   | Bounding box confidence threshold              |
| `OCR_USE_TEXTLINE_ORIENTATION`  | `false` | Enable textline orientation detection          |
| `OCR_WARMUP_ON_STARTUP`         | `false` | Pre-initialize PaddleOCR engines at boot       |
| `OCR_USE_GPU`                   | `false` | Enable GPU inference                           |
| `OCR_USE_MKLDNN`                | `false` | Enable Intel MKL-DNN acceleration              |
| `OCR_CPU_THREADS`               | `4`     | Number of CPU threads for inference            |

### Image Processing

| Variable                        | Example | Description                              |
| ------------------------------- | ------- | ---------------------------------------- |
| `PREPROCESSING_DENOISE_ENABLED` | `true`  | Enable OpenCV denoising                  |
| `PDF_RENDER_SCALE`              | `2.0`   | PDF-to-image DPI multiplier              |
| `IMAGE_MAX_WIDTH`               | `2000`  | Max image width before downscaling (px)  |
| `IMAGE_MAX_PIXELS`              | `8000000` | Max total pixels before downscaling   |

### Subject Matching

| Variable                   | Example | Description                                 |
| -------------------------- | ------- | ------------------------------------------- |
| `FUZZY_MATCH_THRESHOLD`    | `60`    | Minimum fuzzy match score (0–100)           |
| `Y_CLUSTER_TOLERANCE`      | `20`    | Y-axis row clustering tolerance (px)        |
| `SCORE_ZONE_FALLBACK_RATIO`| `0.5`   | Fallback ratio for score zone detection     |

### Redis (optional)

| Variable     | Example                   | Description                                   |
| ------------ | ------------------------- | --------------------------------------------- |
| `REDIS_URL`  | `redis://localhost:6379/0` | Redis connection URL. Leave empty to use in-memory store |

### AI Vision Service

| Variable              | Example                          | Description                              |
| --------------------- | -------------------------------- | ---------------------------------------- |
| `AI_HOST`             | `https://api.deepseek.com`       | Base host for AI API calls               |
| `AI_API_KEY`          | `sk-...`                         | API key for AI Vision service            |
| `DEEPSEEK_ENDPOINT`   | `/v1/chat/completions`           | DeepSeek API endpoint path               |
| `QWEN_ENDPOINT`       | `/v1/chat/completions`           | Qwen API endpoint path                   |
| `DEEPSEEK_MODEL`      | `deepseek-vl2`                   | DeepSeek Vision model name               |
| `QWEN_MODEL`          | `qwen-vl-plus`                   | Qwen Vision model name                   |
| `REQUEST_TIMEOUT`     | `60`                             | HTTP timeout in seconds                  |
| `MAX_RETRY`           | `3`                              | Max retry attempts on transient errors   |

### Logging

| Variable    | Example   | Description                              |
| ----------- | --------- | ---------------------------------------- |
| `LOG_LEVEL` | `INFO`    | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_FILE`  | _(empty)_ | Optional log file path                   |

---

## API Reference

Interactive docs: `http://localhost:8000/docs`

---

### Unified OCR Endpoints (`/api/v1/ocr`)

Semua engine tersedia di bawah prefix yang sama. Response schema **identik** untuk ketiga engine — bisa ganti engine tanpa ubah frontend.

| Method | Endpoint | Engine | Keterangan |
|--------|----------|--------|------------|
| `POST` | `/api/v1/ocr/paddle` | PaddleOCR (local) | Cepat, ringan, tanpa API key |
| `POST` | `/api/v1/ocr/deepseek` | qwen3-vl:8b* | AI Vision |
| `POST` | `/api/v1/ocr/qwen` | qwen3-vl:8b | AI Vision |

*) Sementara diarahkan ke qwen3-vl karena deepseek-ocr:3b belum kompatibel via Ollama API standard.

#### POST `/api/v1/ocr/paddle`

Upload gambar atau PDF raport, ekstrak menggunakan **PaddleOCR** (local engine).

**Request:**
- `Content-Type: multipart/form-data`
- `file`: File raport (PNG, JPG, JPEG, PDF)

**Response:**

```json
{
  "documentId": "DOCPDL1A2B3C4D",
  "status": "SUCCESS",
  "accuracy": 87.5,
  "processingTime": 2.14,
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

#### POST `/api/v1/ocr/deepseek`

Upload gambar atau PDF raport, ekstrak menggunakan **AI Vision** (DeepSeek / qwen3-vl:8b).

#### POST `/api/v1/ocr/qwen`

Upload gambar atau PDF raport, ekstrak menggunakan **Qwen3-VL Vision** (qwen3-vl:8b).

**Request (semua endpoint):**
- `Content-Type: multipart/form-data`
- `file`: File raport (PNG, JPG, JPEG, PDF)

**Error responses (AI Vision):**

| Status | Cause |
|--------|-------|
| `400` | Tipe file tidak didukung |
| `401` | API key tidak valid / tidak ada |
| `403` | Quota habis / forbidden |
| `413` | File terlalu besar |
| `422` | AI mengembalikan response yang tidak bisa di-parse |
| `503` | AI service tidak tersedia |
| `504` | Request timeout |

---

### Legacy PaddleOCR Endpoints (`/api/v1/academic`)

Endpoint lama, tetap aktif untuk backward compatibility.

#### POST `/api/v1/academic/report/upload`

Sama seperti `/api/v1/ocr/paddle` — upload dan langsung dapat hasil OCR.

#### GET `/api/v1/academic/report/status/{documentId}`

Cek status dan hasil dokumen yang sudah diproses sebelumnya.

#### GET `/api/v1/academic/report/{documentId}/debug`

Debug endpoint — kembalikan raw OCR text, bounding boxes, detected rows, dan column layout.

**Response includes:**
- `raw_text`: Semua teks yang terdeteksi
- `total_detections`: Jumlah kata
- `detections`: Posisi, confidence, dan klasifikasi per kata
- `rows`: Baris hasil Y-clustering
- `detected_columns`: Posisi kolom X (subject, KKM, score, grade)
- `score_zone_start`: Batas kiri zona nilai

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
| Poor accuracy on images  | Increase `IMAGE_MAX_WIDTH` or `PDF_RENDER_SCALE` |

### Adjusting PDF Resolution

```dotenv
# Higher = better quality, slower conversion
PDF_RENDER_SCALE=3.0   # ~300 DPI
```

### Switching Storage Backend

By default the app uses an in-memory store that resets on restart. For persistent or multi-instance deployments, set `REDIS_URL`:

```dotenv
REDIS_URL=redis://localhost:6379/0
```

The app will automatically switch to `RedisDocumentStore` when this is set.

---

## Dependencies

### Production (`requirements.txt`)

- `fastapi[all]` — Web framework + Swagger UI
- `uvicorn[standard]` — ASGI server with hot-reload support
- `pydantic>=2.7.0` — Data validation
- `pydantic-settings>=2.3.0` — `.env` configuration loading
- `python-multipart>=0.0.9` — Multipart form data parsing
- `paddlepaddle==3.2.0` — PaddlePaddle deep learning framework
- `paddleocr` — OCR engine + PPStructure
- `opencv-python-headless>=4.9.0` — Image preprocessing
- `rapidfuzz==3.10.1` — Fast fuzzy string matching
- `pandas>=2.2.0`, `lxml>=5.2.0` — Table HTML parsing
- `pymupdf>=1.24.0` — PDF to image conversion
- `celery>=5.4.0` — Task queue (for async processing)
- `redis>=5.0.0` — Redis client for persistent document store
- `httpx>=0.27.0` — Async HTTP client for AI Vision API calls

### Development (`requirements-dev.txt`)

- `pytest>=8.0.0` — Test runner
- `pytest-asyncio>=0.23.0` — Async test support
- `httpx>=0.27.0` — Async HTTP client for FastAPI TestClient
- `ruff>=0.4.0` — Linter + formatter
- `mypy>=1.10.0` — Static type checker

---

## Notes

- PaddleOCR downloads model weights on first use (~500 MB). Ensure internet access on first run.
- The `uploads/` directory is git-ignored. Keep test images in `tests/fixtures/sample_reports/`.
- The in-memory `DocumentStore` resets on every server restart. For R&D this is fine; use `REDIS_URL` for anything persistent.
- AI Vision endpoints require a valid `AI_API_KEY`. Without it, all AI OCR requests will return `401`.
- All four endpoints (`/ocr/paddle`, `/ocr/deepseek`, `/ocr/qwen`, `/academic/report/upload`) return the exact same JSON schema — you can swap engines without changing the client.
- `/ocr/paddle` dan `/academic/report/upload` menggunakan engine yang sama (PaddleOCR). Endpoint `/academic/report/upload` tetap aktif untuk backward compatibility.
