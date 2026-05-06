# Health Record API

A full-stack health record management system with backend API and lightweight frontend testing interface.

## Overview

This system provides a complete workflow for managing health records:

1. **Upload** health record files (images, PDFs, text)
2. **Process** with OCR and normalization
3. **Store** structured data with version history
4. **Query** documents and measurements
5. **Evaluate** risk based on configurable rules
6. **Summarize** single reports or trends
7. **Review** with user-prompted workflows

## Key Features

- **Provider Abstraction**: Swap OCR/LLM/storage providers via configuration
- **Version History**: Track OCR revisions and document versions
- **User Isolation**: Complete per-user data separation
- **Modular Architecture**: Five independent modules with clear boundaries
- **Task Management**: Async task execution with retry logic
- **Quality Calibration**: Built-in stability and quality testing

## Quick Start

### Backend

```bash
# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

### Frontend

```bash
# Simply open in browser
open frontend/index.html
# or on Windows
start frontend/index.html
```

See [Quick Start Guide](docs/quick_start.md) for detailed instructions.
See [Frontend Guide](frontend/README.md) for testing interface usage.

### Docker Deployment

```bash
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

See [Docker Deployment](docs/docker_deploy.md) for server deployment details.

For small servers, build `frontend/dist` locally and use:

```bash
docker compose -f docker-compose.lite.yml --env-file .env.docker up -d --build
```

## Documentation

- **[Project Guide](PROJECT_GUIDE.md)** - 项目导读（中文）
- **[Frontend Guide](frontend/README.md)** - 前端测试面板使用说明
- **[Quick Start Guide](docs/quick_start.md)** - Installation and setup
- **[API Documentation](docs/api_documentation.md)** - Complete API reference
- **[Project Overview](docs/project_overview.md)** - Architecture and design
- **[AGENTS.md](AGENTS.md)** - Development rules and guidelines

## Architecture

### Five-Module System

```
┌─────────────────────────────────────────────────────────┐
│                    Module 5: User System                 │
│              (Authentication & Authorization)            │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼───────┐  ┌────────▼────────┐
│   Module 1:    │  │  Module 2:   │  │   Module 3:     │
│   Perception   │  │    Review    │  │  Summary/Trend  │
│                │  │              │  │                 │
│ • File Upload  │  │ • Prompts    │  │ • Single Report │
│ • OCR          │  │ • Conflicts  │  │ • Trends        │
│ • Normalize    │  │ • Evidence   │  │ • Charts        │
└────────┬───────┘  └──────┬───────┘  └────────┬────────┘
         │                 │                   │
         └─────────────────┼───────────────────┘
                           │
                  ┌────────▼────────┐
                  │   Module 4:     │
                  │   Fast Query    │
                  │                 │
                  │ • Documents     │
                  │ • Measurements  │
                  │ • History       │
                  └─────────────────┘
```

### Provider Architecture

All external services go through provider abstractions:

```
Business Logic
      │
      ▼
Provider Interface (OCRProvider, LLMProvider, etc.)
      │
      ├─► Mistral OCR
      ├─► Google Vision
      ├─► OpenAI Compatible
      └─► Local/Stub
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get token
- `GET /api/auth/me` - Get current user

### File Upload
- `POST /api/files/upload` - Upload health record file

### Ingestion
- `POST /api/ingestion/ingest` - Run full ingestion pipeline

### Query
- `GET /api/documents` - List documents
- `GET /api/document-versions/{id}` - Get version details
- `GET /api/measurements` - Query measurements

### Risk
- `POST /api/risk/documents/{id}/evaluate` - Run risk evaluation
- `GET /api/risk/document-versions/{id}/results` - Get risk results

### Summary
- `POST /api/summary/single` - Generate single report summary
- `POST /api/summary/trend` - Generate trend summary
- `GET /api/summary/runs` - List summary history

### Review
- `POST /api/review/run` - Run review workflow
- `GET /api/review/sessions` - List review sessions
- `GET /api/review/sessions/{id}` - Get review details

See [API Documentation](docs/api_documentation.md) for complete reference.

## Demo Scripts

### End-to-End Demo

```bash
# Minimal demo (1 document)
python scripts/demo_e2e.py --scenario minimal

# Quick demo (2 documents)
python scripts/demo_e2e.py --scenario quick

# Full demo (all features)
python scripts/demo_e2e.py --scenario full
```

### Performance Benchmark

```bash
# Run performance tests
python scripts/benchmark_performance.py --iterations 5

# Save results to file
python scripts/benchmark_performance.py --format json --output results.json
```

### Quality Calibration

```bash
# Run quality checks
python scripts/quality_calibration_run.py --format text
```

## Testing

```bash
# Run all tests
pytest

# Run specific module tests
pytest tests/test_module1_contract.py
pytest tests/test_module2_contract.py
pytest tests/test_module3_contract.py
pytest tests/test_module4_contract.py

# Run with coverage
pytest --cov=app --cov-report=html
```

## Performance Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Authentication | < 100ms | ~60ms |
| File Upload | < 200ms | ~20ms |
| Full Ingestion | < 2000ms | ~250ms |
| Query Operations | < 100ms | ~10ms |
| Risk Evaluation | < 500ms | ~65ms |
| Summary Generation | < 1000ms | ~15ms |

## Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# Database
DATABASE_URL=sqlite:///./health_records.db

# Authentication
AUTH_SECRET_KEY=your-secret-key
AUTH_TOKEN_EXPIRE_MINUTES=60

# OCR Provider
OCR_PROVIDER=plaintext
OCR_BASE_URL=https://api.example.com/v1
OCR_API_KEY=your-api-key

# LLM Provider
LLM_PROVIDER=stub
LLM_PROVIDER_BASE_URL=https://api.example.com/v1
LLM_PROVIDER_API_KEY=your-api-key
```

### Supported Providers

**OCR Providers:**
- `plaintext` - Simple text parser (testing)
- `openai_compatible_vision` - OpenAI-compatible vision API
- `baidu_ocr` - Baidu OCR REST API
- `stub` - No-op stub (testing)

**LLM Providers:**
- `stub` - Template-based responses (testing)
- `openai_compatible` - OpenAI-compatible API (future)

**Storage Providers:**
- `database_inline` - Store files in database (default)
- `local_filesystem` - Store files on disk (future)
- `s3` - Store files in S3 (future)

## Project Structure

```
mog_v2/
├── app/
│   ├── api/v1/           # API routes
│   ├── core/             # Configuration and utilities
│   ├── models/           # Database models
│   ├── schemas/          # Request/response schemas
│   ├── services/         # Business logic
│   ├── providers/        # External service abstractions
│   ├── repositories/     # Data access layer
│   ├── modules/          # Module façades
│   └── main.py           # Application entry point
├── migrations/           # Database migrations
├── tests/                # Test suite
├── scripts/              # Utility scripts
├── docs/                 # Documentation
├── sample_data/          # Sample test data
└── .env.example          # Example configuration
```

## Development Guidelines

### Architecture Rules (from AGENTS.md)

1. **No frontend code** - Backend-only API
2. **Provider abstraction** - All external services through interfaces
3. **Module boundaries** - Keep modules loosely coupled
4. **User isolation** - Complete per-user data separation
5. **Version history** - Preserve all OCR and document revisions
6. **No PII in logs** - Sanitize all logging output

### Adding Features

1. Identify which module owns the feature
2. Write tests first (TDD)
3. Implement following module boundaries
4. Run tests and quality checks
5. Update documentation

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Review and edit migration file

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

## Current Status

### Completed
- ✅ Five-module architecture
- ✅ User authentication and isolation
- ✅ File upload and OCR processing
- ✅ Document normalization and versioning
- ✅ Measurement extraction and querying
- ✅ Risk evaluation engine
- ✅ Summary generation (single and trend)
- ✅ Review workflow
- ✅ Provider abstraction layer
- ✅ Task management and retry logic
- ✅ Quality calibration framework

### In Progress
- 🔄 OCR stability improvements
- 🔄 Provider diversity (multiple OCR options)
- 🔄 Production hardening

### Future
- 📋 Real LLM integration
- 📋 Guideline retrieval (RAG)
- 📋 Frontend application
- 📋 Advanced analytics

## Known Issues

### OCR Stability
The current OCR provider shows variability across repeated runs on the same image. This is being addressed through:
- Stability probing and measurement
- Provider comparison testing
- Quality scoring and intelligent retry

See [Quality Hardening Notes](docs/quality_hardening_notes.md) for details.

## Contributing

Please read [AGENTS.md](AGENTS.md) for development guidelines and architecture rules.

## License

[Specify your license here]

## Support

For issues or questions, please refer to the project repository.

---

**Interactive Documentation**: http://localhost:8000/docs (when server is running)
