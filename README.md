# Doc Report OCR Service

A production-quality REST API for extracting academic data from Indonesian school report cards (Raport) using PaddleOCR.

---

## Features

- **Local OCR Engine**: Fast and secure processing using PaddleOCR without external API dependencies.
- **Dual-mode OCR**: PPStructure table recognition (Mode 1) with Y-clustering fallback (Mode 2).
- **Subject extraction**: Matches 15 standard subjects including OCR typo variants.
- **KKM detection**: Automatically identifies the minimum competency score column.
- **Personality data**: Extracts Kelakuan / Kerajinan / Kerapihan grades.
- **Attendance data**: Extracts Sakit / Ijin / Alpa counts.
- **Handwritten support**: Works on manually-written report cards.
- **PDF support**: Auto-converts each page to image, merges results.
- **Pluggable storage**: In-memory (default) or Redis-backed document store.
- **CORS support**: Configurable allowed origins, methods, and headers.

---

## Architecture

```
Presentation   →   app/api/v1/endpoints/      HTTP routing only
Application    →   app/application/           Use-case orchestration + timing
Services       →   app/services/              OCR extraction, mapping, parsers, extractors
Domain         →   app/domain/                MASTER_SUBJECTS, pure business rules
Infrastructure →   app/infrastructure/        PaddleOCR engine, data files, storage
```

---

## Folder Structure

```
backend-paddleocr/
├── app/
│   ├── main.py                          # FastAPI app factory
│   ├── api/
│   │   ├── deps.py                      # FastAPI dependency injection
│   │   └── v1/
│   │       ├── router.py                # v1 router aggregator
│   │       └── endpoints/               # All HTTP handlers
│   │           ├── raport_route.py      # PaddleOCR raport upload handler
│   │           ├── ai_route.py          # Qwen AI upload handler (Raport, KTP, KK, Akta, KP)
│   │           ├── akta_route.py        # Akta routes
│   │           ├── kk_route.py          # KK routes
│   │           ├── kp_route.py          # KP routes
│   │           └── ktp_route.py         # KTP routes
│   ├── application/
│   │   └── ocr_use_case.py              # run_ocr_pipeline()
│   ├── core/
│   │   ├── config.py                    # Pydantic Settings (.env)
│   │   ├── logging.py                   # Structured logging + PhaseLogger
│   │   └── exceptions.py                # Custom exception hierarchy
│   ├── domain/
│   │   ├── constants.py                 # Constants & Enums
│   │   └── ai_vision_dto.py             # DTOs
│   ├── infrastructure/
│   │   ├── ocr/
│   │   │   ├── engine.py                # PaddleOCR + PPStructure singletons
│   │   │   ├── preprocessor.py          # OpenCV preprocessing
│   │   │   ├── pdf_converter.py         # PDF → images
│   │   │   ├── result_flattener.py      # OCR output normalizer
│   │   │   └── column_detector.py       # Table column X-position detection
│   │   ├── storage/
│   │   │   ├── base.py                  # BaseDocumentStore + DocumentRecord
│   │   │   ├── in_memory_store.py       # Default in-memory store
│   │   │   └── redis_store.py           # Redis-backed store (multi-worker)
│   │   └── data/
│   │       └── postal_code_data.csv     # Master postal code data
│   ├── schemas/
│   │   └── ...                          # Pydantic request/response models
│   ├── services/
│   │   ├── ocr_orchestrator.py          # Mode selection + PDF handling
│   │   ├── table_extractor.py           # Mode 1: PPStructure → DataFrame
│   │   ├── row_extractor.py             # Mode 2: Raw OCR + Y-clustering
│   │   ├── mapping_engine.py            # Fuzzy subject/personality/attendance match
│   │   ├── score_parser.py              # parse_score(), is_valid_score()
│   │   ├── kkm_assigner.py              # KKM vs Score column assignment
│   │   ├── response_builder.py          # Dict → Pydantic response models
│   │   ├── extractors/                  # Custom extractors (KK header/table)
│   │   ├── parsers/                     # Specific parsers for documents
│   │   ├── preprocess/                  # Preprocessing routines
│   │   ├── fuzzy/                       # Matchers (education, religion, etc)
│   │   └── akta/                        # Akta specific processing
│   ├── utils/                           # Validators, helpers
│   └── worker/                          # Celery background tasks
├── uploads/                             # Runtime uploads (git-ignored)
├── .env                                 # Local environment (git-ignored)
├── .env.example                         # Environment template
└── requirements.txt                     # Production dependencies
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

| Variable          | Example                  | Description                |
| ----------------- | ------------------------ | -------------------------- |
| `APP_TITLE`       | `Doc Report OCR Service` | API title shown in Swagger |
| `APP_DESCRIPTION` | `School report card OCR` | API description            |
| `APP_VERSION`     | `1.0.0`                  | API version string         |
| `DEBUG`           | `false`                  | Enable debug mode          |

### CORS

| Variable                 | Example | Description                  |
| ------------------------ | ------- | ---------------------------- |
| `CORS_ORIGINS`           | `["*"]` | Allowed origins (JSON array) |
| `CORS_ALLOW_CREDENTIALS` | `true`  | Allow credentials            |
| `CORS_ALLOW_METHODS`     | `["*"]` | Allowed HTTP methods         |
| `CORS_ALLOW_HEADERS`     | `["*"]` | Allowed request headers      |

### File Upload

| Variable             | Example                          | Description                  |
| -------------------- | -------------------------------- | ---------------------------- |
| `UPLOAD_DIR`         | `uploads`                        | Directory for uploaded files |
| `MAX_UPLOAD_SIZE_MB` | `20`                             | Maximum upload size in MB    |
| `ALLOWED_EXTENSIONS` | `[".png",".jpg",".jpeg",".pdf"]` | Accepted file extensions     |

### OCR Engine

| Variable                       | Example | Description                              |
| ------------------------------ | ------- | ---------------------------------------- |
| `OCR_LANG`                     | `en`    | PaddleOCR language model                 |
| `OCR_DET_THRESH`               | `0.3`   | Text detection threshold                 |
| `OCR_BOX_THRESH`               | `0.4`   | Bounding box confidence threshold        |
| `OCR_USE_TEXTLINE_ORIENTATION` | `false` | Enable textline orientation detection    |
| `OCR_WARMUP_ON_STARTUP`        | `false` | Pre-initialize PaddleOCR engines at boot |
| `OCR_USE_GPU`                  | `false` | Enable GPU inference                     |
| `OCR_USE_MKLDNN`               | `false` | Enable Intel MKL-DNN acceleration        |
| `OCR_CPU_THREADS`              | `4`     | Number of CPU threads for inference      |

### Image Processing

| Variable                        | Example   | Description                             |
| ------------------------------- | --------- | --------------------------------------- |
| `PREPROCESSING_DENOISE_ENABLED` | `true`    | Enable OpenCV denoising                 |
| `PDF_RENDER_SCALE`              | `2.0`     | PDF-to-image DPI multiplier             |
| `IMAGE_MAX_WIDTH`               | `2000`    | Max image width before downscaling (px) |
| `IMAGE_MAX_PIXELS`              | `8000000` | Max total pixels before downscaling     |

### AI Models

| Variable          | Example                   | Description                        |
| ----------------- | ------------------------- | ---------------------------------- |
| `AI_HOST`         | `http://10.10.5.141:8080` | Base URL for Qwen AI Model         |
| `AI_API_KEY`      | `your_api_key_here`       | Bearer token for AI Model          |
| `QWEN_ENDPOINT`   | `/v1/chat/completions`    | Qwen API Endpoint path             |
| `QWEN_MODEL`      | `qwen3-vl:8b`             | Qwen Model identifier              |
| `REQUEST_TIMEOUT` | `120`                     | Timeout in seconds for AI requests |
| `MAX_RETRY`       | `2`                       | Max retry attempts for AI requests |

### Subject Matching

| Variable                    | Example | Description                             |
| --------------------------- | ------- | --------------------------------------- |
| `FUZZY_MATCH_THRESHOLD`     | `60`    | Minimum fuzzy match score (0–100)       |
| `Y_CLUSTER_TOLERANCE`       | `20`    | Y-axis row clustering tolerance (px)    |
| `SCORE_ZONE_FALLBACK_RATIO` | `0.5`   | Fallback ratio for score zone detection |

### Redis (optional)

| Variable    | Example                    | Description                                              |
| ----------- | -------------------------- | -------------------------------------------------------- |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. Leave empty to use in-memory store |

### Logging

| Variable    | Example   | Description                              |
| ----------- | --------- | ---------------------------------------- |
| `LOG_LEVEL` | `INFO`    | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_FILE`  | _(empty)_ | Optional log file path                   |

---

## API Reference

Interactive docs: `http://localhost:8000/docs`

---

### OCR Paddle Endpoints (`/api/v1/ocr`)

Semua endpoint ini diproses secara lokal menggunakan **PaddleOCR**.

- **POST `/api/v1/ocr/raport`**: Ekstrak data dari dokumen Raport.
- **POST `/api/v1/ocr/ktp`**: Ekstrak data dari dokumen KTP.
- **POST `/api/v1/ocr/kk`**: Ekstrak data dari dokumen KK.
- **POST `/api/v1/ocr/akta`**: Ekstrak data dari dokumen Akta.
- **POST `/api/v1/ocr/kp`**: Ekstrak data dari dokumen Kartu Pelajar (KP).

### OCR AI Endpoints (/api/v1/ocr/ai)

Semua endpoint AI menggunakan model Qwen Vision. Response schema disamakan dengan endpoint PaddleOCR untuk kemudahan integrasi.

- **POST /api/v1/ocr/ai/raport**: Ekstrak Raport menggunakan Qwen.
- **POST /api/v1/ocr/ai/ktp**: Ekstrak KTP menggunakan Qwen (Under Construction).
- **POST /api/v1/ocr/ai/kk**: Ekstrak KK menggunakan Qwen (Under Construction).
- **POST /api/v1/ocr/ai/akta**: Ekstrak Akta menggunakan Qwen (Under Construction).
- **POST /api/v1/ocr/ai/kp**: Ekstrak Kartu Pelajar (KP) menggunakan Qwen (Under Construction).
