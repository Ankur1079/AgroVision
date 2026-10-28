-- Additive Module J migration. Run against the existing agrovision database.
-- Does not drop or reset any existing data.
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS farm_advisor_assignments (
  id SERIAL PRIMARY KEY,
  farm_id INTEGER NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
  advisor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assigned_by INTEGER NOT NULL REFERENCES users(id),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_farm_advisor UNIQUE (farm_id, advisor_id)
);
CREATE INDEX IF NOT EXISTS ix_farm_advisor_assignments_farm_id ON farm_advisor_assignments(farm_id);
CREATE INDEX IF NOT EXISTS ix_farm_advisor_assignments_advisor_id ON farm_advisor_assignments(advisor_id);

CREATE TABLE IF NOT EXISTS advisor_review_requests (
  id SERIAL PRIMARY KEY,
  farm_id INTEGER NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
  field_id INTEGER REFERENCES fields(id) ON DELETE SET NULL,
  crop_cycle_id INTEGER REFERENCES crop_cycles(id) ON DELETE SET NULL,
  requested_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assigned_advisor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  title VARCHAR(180) NOT NULL,
  description TEXT NOT NULL,
  crop_health_context TEXT,
  status VARCHAR(30) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_advisor_review_requests_farm_id ON advisor_review_requests(farm_id);
CREATE INDEX IF NOT EXISTS ix_advisor_review_requests_field_id ON advisor_review_requests(field_id);
CREATE INDEX IF NOT EXISTS ix_advisor_review_requests_crop_cycle_id ON advisor_review_requests(crop_cycle_id);
CREATE INDEX IF NOT EXISTS ix_advisor_review_requests_requested_by ON advisor_review_requests(requested_by);
CREATE INDEX IF NOT EXISTS ix_advisor_review_requests_assigned_advisor_id ON advisor_review_requests(assigned_advisor_id);
CREATE INDEX IF NOT EXISTS ix_advisor_review_requests_status ON advisor_review_requests(status);

CREATE TABLE IF NOT EXISTS advisor_reviews (
  id SERIAL PRIMARY KEY,
  request_id INTEGER NOT NULL REFERENCES advisor_review_requests(id) ON DELETE CASCADE,
  advisor_id INTEGER NOT NULL REFERENCES users(id),
  comments TEXT NOT NULL,
  recommendations TEXT NOT NULL,
  status VARCHAR(30) NOT NULL,
  follow_up_date DATE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_advisor_reviews_request_id ON advisor_reviews(request_id);
CREATE INDEX IF NOT EXISTS ix_advisor_reviews_advisor_id ON advisor_reviews(advisor_id);

CREATE TABLE IF NOT EXISTS crop_categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  description TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_crop_categories_name ON crop_categories(name);

CREATE TABLE IF NOT EXISTS supported_model_classes (
  id SERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  model_name VARCHAR(120) NOT NULL DEFAULT 'default',
  description TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_supported_model_classes_name ON supported_model_classes(name);

CREATE TABLE IF NOT EXISTS integration_configs (
  id SERIAL PRIMARY KEY,
  provider_type VARCHAR(30) NOT NULL,
  provider_name VARCHAR(120) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  settings_json TEXT NOT NULL DEFAULT '{}',
  secret_env_var VARCHAR(120),
  updated_by INTEGER NOT NULL REFERENCES users(id),
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_integration_configs_provider_type ON integration_configs(provider_type);

CREATE TABLE IF NOT EXISTS system_events (
  id SERIAL PRIMARY KEY,
  event_type VARCHAR(40) NOT NULL,
  severity VARCHAR(20) NOT NULL DEFAULT 'error',
  source VARCHAR(120) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  message TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TIMESTAMP,
  resolved_by INTEGER REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS ix_system_events_event_type ON system_events(event_type);
CREATE INDEX IF NOT EXISTS ix_system_events_severity ON system_events(severity);
CREATE INDEX IF NOT EXISTS ix_system_events_status ON system_events(status);
CREATE INDEX IF NOT EXISTS ix_system_events_created_at ON system_events(created_at);

CREATE TABLE IF NOT EXISTS audit_logs (
  id SERIAL PRIMARY KEY,
  actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR(100) NOT NULL,
  entity_type VARCHAR(80) NOT NULL,
  entity_id INTEGER,
  details JSON,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs(actor_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs(entity_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs(actor_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs(entity_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at);


