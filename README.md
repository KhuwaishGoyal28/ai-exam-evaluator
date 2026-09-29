# EvalPro — Smart Exam Answer Evaluator

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Open-2ea44f?style=for-the-badge&logo=vercel)](https://ai-exam-evaluator-nine.vercel.app)

Upload a photo or PDF of any handwritten or typed answer sheet and get back:

- **Extracted text** — OCR from every page of the document
- **Rubric score sheet** — 5 parameters × 10 points = 50 points max
- **Annotated checked paper** — red ink marks, tick/cross symbols, margin notes per page (like a real teacher)
- **Downloadable report** — full evaluation JSON stored to cloud
- **Cloud storage** — every file saved to a per-job folder in Supabase

Works for **any exam**: Class 6–8, Class 9–10 Board, Class 11–12 Board, JEE, NEET, UPSC, CLAT, CAT/MBA, College, Language, or any custom paper.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | Python 3.10+ · FastAPI · Uvicorn | REST API, async, typed |
| Evaluation LLM | Groq API (`openai/gpt-oss-120b`) | Fast rubric-based text scoring |
| Vision / OCR | OpenAI GPT-4o-mini Vision | Extract text from images and PDFs |
| PDF handling | pypdf · reportlab · pdf2image | Multi-page extraction, report generation |
| Image annotation | Pillow (PIL) | Red ink marks, margin notes, score banner |
| File storage | Supabase Storage | Per-job cloud folders, public CDN URLs |
| Frontend | React 18 · Vite · TypeScript | Upload UI, results view |
| State | Zustand | Global evaluation state |
| Styling | Tailwind CSS | Utility-first responsive design |

---

## Architecture

```
Browser (React + Vite)
        │
        │  POST /api/v1/evaluate  (multipart/form-data)
        │  file + question (optional)
        ▼
FastAPI Backend
        │
        ├─ 1. store_original_file()
        │       └─→ Supabase: evaluations/{job_id}/original.{ext}
        │
        ├─ 2. run_ocr_pipeline()
        │       ├─ pypdf  → extract text from ALL pages  (text PDFs)
        │       ├─ OpenAI Vision → OCR image/scanned PDFs
        │       └─ confidence_estimator → quality check
        │
        ├─ 3. run_evaluation_pipeline()
        │       ├─ prompt_builder → build rubric prompt
        │       └─ Groq API      → JSON scores + comments
        │
        ├─ 4. run_annotation_pipeline()
        │       ├─ page_extractor    → one image per PDF page
        │       ├─ ink_marker        → tick/cross/wavy underlines
        │       ├─ comment_renderer  → margin comment boxes
        │       ├─ score_banner      → grade + score overlay
        │       └─ checked_pdf_builder → stitch into multi-page PDF
        │
        ├─ 5. store_annotated_file()
        │       └─→ Supabase: evaluations/{job_id}/annotated.jpg
        │
        ├─ 6. store_checked_pdf()  (if implemented)
        │       └─→ Supabase: evaluations/{job_id}/checked.pdf
        │
        └─ 7. store_report()
                └─→ Supabase: evaluations/{job_id}/report.json
        │
        ▼
EvaluateResponse JSON  →  Browser shows score sheet + annotated image
```

### Supabase Folder Structure (per evaluation)

```
answercheck/               ← bucket name
  evaluations/
    {job_id}/
      original.pdf         ← raw upload (preserves original MIME type)
      annotated.jpg        ← first-page preview with score banner
      checked.pdf          ← full checked paper (all pages annotated)
      report.json          ← complete evaluation data
```

---

## Project Structure

```
ai-exam-evaluator/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── controllers/        # pipeline orchestration
│   │   │   └── routes/             # HTTP parsing only
│   │   ├── config/                 # settings.py (pydantic-settings)
│   │   ├── core/                   # constants, exceptions, logging
│   │   ├── middleware/             # exception → HTTP status handlers
│   │   ├── models/
│   │   │   ├── domain/             # pure dataclasses (no I/O)
│   │   │   ├── requests/           # Pydantic input schemas
│   │   │   └── responses/          # Pydantic output schemas
│   │   ├── services/
│   │   │   ├── annotation/         # per-page ink marks, checked PDF builder
│   │   │   ├── evaluation/         # Groq LLM prompt + response mapping
│   │   │   ├── ocr/                # pypdf + OpenAI Vision pipeline
│   │   │   ├── report/             # PDF report builder (reportlab)
│   │   │   └── storage/            # Supabase upload helpers
│   │   └── utils/                  # pure helpers (file, text, image)
│   ├── tests/unit/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   └── render.yaml
│
├── frontend/
│   └── src/
│       ├── api/                    # axios client + evaluationApi
│       ├── components/
│       │   ├── ui/                 # Button, Card, Badge, ProgressBar, ErrorBanner
│       │   └── layout/             # Header, PageLayout
│       ├── features/
│       │   ├── upload/             # DropZone, FilePreview, QuestionInput, UploadForm
│       │   ├── results/            # ImageComparison, ExtractedText
│       │   └── evaluation/         # ScoreSheet, ScoreRing, AnnotationList
│       ├── hooks/                  # useEvaluate, useFilePreview
│       ├── pages/                  # HomePage, ResultsPage, NotFoundPage
│       ├── store/                  # Zustand evaluationStore
│       └── types/                  # TypeScript types (mirrors backend schemas)
│
├── Makefile
├── .gitignore
└── README.md
```

---

## Evaluation Rubric

5 parameters · 10 points each · **50 points maximum**

| # | Parameter | What is measured |
|---|---|---|
| 1 | **Structure** | Logical intro → body → conclusion; coherent transitions |
| 2 | **Content & Accuracy** | Factual correctness, relevant examples, depth of knowledge |
| 3 | **Language & Expression** | Grammar, vocabulary, clarity, appropriate register |
| 4 | **Relevance to Question** | Directly addresses the question; no off-topic padding |
| 5 | **Critical Thinking** | Analysis, reasoning, balanced arguments, original insight |

**Grade mapping:** A ≥ 80% · B ≥ 60% · C ≥ 40% · D < 40%

The rubric is applied at the **level of the exam type selected** — a Class 6 answer is not judged to university standards.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.10 or 3.11 | Backend runtime |
| Node.js | 18+ | Frontend build |
| pip | any recent | Python package manager |
| npm | 9+ | Node package manager |

### API Keys Required

| Service | What it does | Get it here |
|---|---|---|
| **Groq** | Text evaluation LLM (fast, free tier available) | https://console.groq.com/keys |
| **OpenAI** | Vision OCR (reads images and scanned PDFs) | https://platform.openai.com/api-keys |
| **Supabase** | Cloud file storage | https://supabase.com → New project |

---

## Local Setup — Step by Step

### 1. Clone the repository

```bash
git clone https://github.com/your-username/ai-exam-evaluator.git
cd ai-exam-evaluator
```

### 2. Backend setup

```bash
cd backend
```

**Create and activate a virtual environment**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

**Install dependencies**

```bash
pip install -r requirements.txt
```

**Configure environment variables**

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Now open `backend/.env` and fill in these values:

```env
GROQ_API_KEY=gsk_your_key          # from console.groq.com/keys
OPENAI_API_KEY=sk-proj-your_key    # from platform.openai.com/api-keys
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_BUCKET=answercheck
```

**Create the Supabase storage bucket** (one-time setup)

```bash
python create_bucket.py
```

This creates a public bucket called `answercheck` in your Supabase project.

**Run the backend**

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`  
Swagger docs (debug mode): `http://localhost:8000/docs`

### 3. Frontend setup

Open a **new terminal window** and:

```bash
cd frontend
npm install
```

**Configure environment** (for local dev the Vite proxy handles `/api → :8000`, so this file can be left empty)

```bash
# Windows
copy .env.example .env.local

# macOS / Linux
cp .env.example .env.local
```

**Run the frontend**

```bash
npm run dev
```

The app will be available at: `http://localhost:5173`

### 4. Run backend tests

```bash
cd backend
python -m pytest tests/ -v
```

Expected output: **24 passed**

---

## How to Use

1. Open `http://localhost:5173` in your browser
2. **Upload** a photo (JPEG/PNG/WebP) or PDF of any handwritten or typed answer sheet
3. Optionally enter the **exam question or topic**
4. Click **Evaluate Answer Sheet**
5. Wait ~20–40 seconds for:
   - Text extraction (OCR)
   - Rubric evaluation
   - Image annotation
6. View results:
   - Toggle between **Annotated** and **Original** views
   - Read the **score sheet** (5 parameters + grade)
   - Browse **inline annotations** (green ✓ / red ✗ comments)
   - Read **extracted text**, **strengths**, and **improvements**
   - Download the annotated image or full JSON report

---

## Deployment

### Backend → Render (free tier)

1. Push the repo to GitHub
2. Go to [render.com](https://render.com) → **New → Web Service**
3. Connect your GitHub repo
4. Set **Root Directory**: `backend`
5. Render will detect `render.yaml` automatically
6. Add these **Secret** environment variables in the Render dashboard:
   - `GROQ_API_KEY`
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
7. Note the deployed URL: `https://your-api.onrender.com`

### Frontend → Vercel (free tier)

1. Go to [vercel.com](https://vercel.com) → **New Project → Import**
2. Select your GitHub repo
3. Set **Root Directory**: `frontend`
4. Add environment variable:
   ```
   VITE_API_BASE_URL = https://your-api.onrender.com/api/v1
   ```
5. Update `ALLOWED_ORIGINS` in Render to include your Vercel URL
6. Deploy — Vercel auto-detects Vite; `vercel.json` handles SPA routing

---

## Known Limitations

| Area | Current behaviour | Potential improvement |
|---|---|---|
| **OCR accuracy** | Uses GPT-4o-mini Vision — good on clear scans, degrades on very light/messy handwriting | Dedicated OCR engine (Google Vision, AWS Textract) |
| **Groq token limit** | Free tier = 8,000 tokens/min; long documents are truncated to ~1,500 chars for evaluation | Upgrade to Groq paid tier or use OpenAI for evaluation |
| **Annotation placement** | Y-positions divided into equal bands per paragraph — not pixel-precise | Use OCR bounding boxes to anchor comments to exact lines |
| **Persistence** | No database — each evaluation is independent; no history | Add Postgres + auth for per-student progress tracking |
| **Rate limiting** | No per-IP throttle on the `/evaluate` endpoint | Add Redis-backed rate limiting (slowapi) |

---

## Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ | — | Groq API key for evaluation LLM |
| `GROQ_MODEL` | ✅ | `openai/gpt-oss-120b` | Groq model name |
| `GROQ_MAX_TOKENS` | | `1500` | Max output tokens (keep ≤1500 for free tier) |
| `GROQ_TEMPERATURE` | | `0.2` | Lower = more consistent scoring |
| `OPENAI_API_KEY` | ✅ | — | OpenAI key for Vision OCR |
| `OPENAI_VISION_MODEL` | | `gpt-4o-mini` | Vision model |
| `OPENAI_MAX_TOKENS` | | `8192` | Max OCR output tokens |
| `SUPABASE_URL` | ✅ | — | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | — | Service role key (write access) |
| `SUPABASE_BUCKET` | | `answercheck` | Storage bucket name |
| `MAX_UPLOAD_SIZE_MB` | | `10` | Max file upload size |
| `DEBUG` | | `false` | Enables `/docs` endpoint |
| `ALLOWED_ORIGINS` | | `["http://localhost:5173"]` | CORS allowed origins |

### Frontend (`frontend/.env.local`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | Only for prod | (empty) | Backend API URL. Leave empty in local dev — Vite proxies `/api → :8000` |
