# Roadmap

This roadmap documents the upcoming phases of development for the **Document to Excel** project.

## Future Phases

### Phase 2: Database Migration
- Integrate **PostgreSQL** or **SQLite** database using SQLAlchemy.
- Implement the persistence logic inside `backend/app/repository/document_repository.py`.
- Keep the service layers unchanged.

### Phase 3: Authentication & Multi-Tenancy
- Add user accounts, authorization, and secure JWT tokens.
- Add organization/tenant models to segregate uploaded receipts.

### Phase 4: S3/Blob Storage Support
- Move uploaded file storage from local temp directories to cloud object storage.
- Support storing raw receipts and extracted spreadsheets historically.
