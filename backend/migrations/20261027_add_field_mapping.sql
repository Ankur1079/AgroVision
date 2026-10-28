-- Additive migration only: preserves existing AgroVision farm/field/crop data.
-- Run against the existing agrovision database once before starting the updated API.
ALTER TABLE fields ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION NULL;
ALTER TABLE fields ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION NULL;
ALTER TABLE fields ADD COLUMN IF NOT EXISTS boundary_geojson TEXT NULL;

-- Farm latitude/longitude are already present in the starter schema. This migration
-- intentionally does not drop, truncate, recreate, or reset any table or volume.
