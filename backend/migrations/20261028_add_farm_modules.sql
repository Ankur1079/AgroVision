-- Additive migration for Crop Cycle History and Modules F-I.
-- Run against the existing agrovision database. Does not drop or reset records.
ALTER TABLE crop_cycles ADD COLUMN IF NOT EXISTS expected_harvest_quantity DOUBLE PRECISION;
ALTER TABLE crop_cycles ADD COLUMN IF NOT EXISTS expected_harvest_unit VARCHAR(40);

CREATE TABLE IF NOT EXISTS crop_observations (
 id SERIAL PRIMARY KEY, crop_cycle_id INTEGER NOT NULL REFERENCES crop_cycles(id) ON DELETE CASCADE,
 observation_type VARCHAR(40) NOT NULL DEFAULT 'note', observed_on DATE NOT NULL DEFAULT CURRENT_DATE,
 growth_stage VARCHAR(80), germination_percent DOUBLE PRECISION, note TEXT, photo_path VARCHAR(500), created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_crop_observations_crop_cycle_id ON crop_observations(crop_cycle_id);

CREATE TABLE IF NOT EXISTS irrigation_records (
 id SERIAL PRIMARY KEY, crop_cycle_id INTEGER NOT NULL REFERENCES crop_cycles(id) ON DELETE CASCADE,
 irrigation_date DATE NOT NULL DEFAULT CURRENT_DATE, method VARCHAR(80) NOT NULL, water_source VARCHAR(120),
 soil_moisture_percent DOUBLE PRECISION, duration_minutes DOUBLE PRECISION, quantity_liters DOUBLE PRECISION,
 quantity_is_estimated BOOLEAN NOT NULL DEFAULT FALSE, crop_stage VARCHAR(80), notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_irrigation_records_crop_cycle_id ON irrigation_records(crop_cycle_id);

CREATE TABLE IF NOT EXISTS irrigation_recommendations (
 id SERIAL PRIMARY KEY, crop_cycle_id INTEGER NOT NULL REFERENCES crop_cycles(id) ON DELETE CASCADE,
 status VARCHAR(20) NOT NULL DEFAULT 'suggested', recommended_on DATE NOT NULL DEFAULT CURRENT_DATE,
 suggested_task VARCHAR(160) NOT NULL, reason TEXT NOT NULL, inputs_json TEXT NOT NULL, estimated_water_liters DOUBLE PRECISION,
 decision_note TEXT, task_id INTEGER REFERENCES farm_tasks(id) ON DELETE SET NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_irrigation_recommendations_crop_cycle_id ON irrigation_recommendations(crop_cycle_id);

CREATE TABLE IF NOT EXISTS soil_test_records (
 id SERIAL PRIMARY KEY, farm_id INTEGER NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
 field_id INTEGER REFERENCES fields(id) ON DELETE SET NULL, sample_date DATE NOT NULL, testing_source VARCHAR(160),
 ph DOUBLE PRECISION, nitrogen DOUBLE PRECISION, phosphorus DOUBLE PRECISION, potassium DOUBLE PRECISION,
 nutrient_unit VARCHAR(40), attachment_path VARCHAR(500), notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_soil_test_records_farm_id ON soil_test_records(farm_id);
CREATE INDEX IF NOT EXISTS ix_soil_test_records_field_id ON soil_test_records(field_id);

CREATE TABLE IF NOT EXISTS farm_input_records (
 id SERIAL PRIMARY KEY, farm_id INTEGER NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
 field_id INTEGER REFERENCES fields(id) ON DELETE SET NULL, crop_cycle_id INTEGER REFERENCES crop_cycles(id) ON DELETE SET NULL,
 input_type VARCHAR(40) NOT NULL, product_name VARCHAR(160) NOT NULL, quantity DOUBLE PRECISION NOT NULL,
 unit VARCHAR(40) NOT NULL, cost DOUBLE PRECISION NOT NULL DEFAULT 0, applied_on DATE NOT NULL,
 inventory_quantity DOUBLE PRECISION, notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_farm_input_records_farm_id ON farm_input_records(farm_id);
CREATE INDEX IF NOT EXISTS ix_farm_input_records_crop_cycle_id ON farm_input_records(crop_cycle_id);

CREATE TABLE IF NOT EXISTS market_price_records (
 id SERIAL PRIMARY KEY, crop_name VARCHAR(100) NOT NULL, market_name VARCHAR(160) NOT NULL, location VARCHAR(160) NOT NULL,
 price DOUBLE PRECISION NOT NULL, unit VARCHAR(40) NOT NULL, price_date DATE NOT NULL, source VARCHAR(200) NOT NULL,
 is_sample BOOLEAN NOT NULL DEFAULT FALSE, created_by INTEGER REFERENCES users(id) ON DELETE SET NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_market_price_records_crop_name ON market_price_records(crop_name);
CREATE INDEX IF NOT EXISTS ix_market_price_records_market_name ON market_price_records(market_name);

CREATE TABLE IF NOT EXISTS harvest_records (
 id SERIAL PRIMARY KEY, crop_cycle_id INTEGER NOT NULL REFERENCES crop_cycles(id) ON DELETE CASCADE,
 harvest_date DATE NOT NULL, quantity DOUBLE PRECISION NOT NULL, unit VARCHAR(40) NOT NULL,
 quality_grade VARCHAR(80), storage_location VARCHAR(160), notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_harvest_records_crop_cycle_id ON harvest_records(crop_cycle_id);

CREATE TABLE IF NOT EXISTS sale_records (
 id SERIAL PRIMARY KEY, harvest_id INTEGER NOT NULL REFERENCES harvest_records(id) ON DELETE CASCADE,
 sale_date DATE NOT NULL, quantity DOUBLE PRECISION NOT NULL, unit VARCHAR(40) NOT NULL, unit_price DOUBLE PRECISION NOT NULL,
 buyer_name VARCHAR(160), notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_sale_records_harvest_id ON sale_records(harvest_id);

CREATE TABLE IF NOT EXISTS farm_notifications (
 id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title VARCHAR(160) NOT NULL, message TEXT NOT NULL, due_date DATE, status VARCHAR(20) NOT NULL DEFAULT 'unread',
 source_type VARCHAR(40) NOT NULL DEFAULT 'task', created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_farm_notifications_user_id ON farm_notifications(user_id);
