# Implementation status — milestone 1

## Implemented in starter
- Registration with Argon2 password hashing
- JWT login and current-user endpoint
- PostgreSQL models for users, farms, fields, crop cycles and tasks
- Owner-scoped API access for farms and descendant records
- Positive area and crop-date validation
- Dashboard counts computed from persisted records
- Role-based admin and advisor API endpoints
- Farm advisor assignments, farmer advisory requests, and recommendations
- Audit logging for role, assignment, and advisory changes
- Alembic migration support for advisory categories, priorities, and action items
- Responsive React/TypeScript dashboard and farm registration form
- Empty states and explicit disclosure that external integrations are not connected

## Not implemented yet
- Complete baseline migration history and migration-based production deployment
- Admin/advisor portal UI in the frontend
- Field/crop/task forms in frontend (API endpoints exist)
- Weather provider integration
- Genuine trained crop-health model and evaluation
- Official market price integration
- Soil, input inventory, irrigation records, harvest, sales and exports
- Automated test suite and deployment configuration

## Evidence policy
Record test outcomes only after running the tests. Never invent performance results, prediction metrics, market observations or screenshots of functionality that has not been implemented.
