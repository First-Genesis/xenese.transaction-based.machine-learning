-- TML Platform Database Schema Creation
-- Creating initial schema for PostgreSQL with TimescaleDB

-- Create the database if not exists
-- Note: This needs to be run as a superuser
-- CREATE DATABASE tml_production;

-- Connect to the database
\c tml_production;

-- Create tables
CREATE TABLE IF NOT EXISTS "Transactions" (
    "Id" uuid NOT NULL PRIMARY KEY,
    "Data" jsonb NOT NULL,
    "Source" character varying(100) NOT NULL,
    "Metadata" jsonb NOT NULL,
    "Status" integer NOT NULL,
    "CreatedAt" timestamp with time zone NOT NULL,
    "ProcessedAt" timestamp with time zone NULL,
    "ProcessingTimeMs" double precision NULL,
    "ModelId" uuid NULL,
    "ErrorDetails" text NULL
);

CREATE TABLE IF NOT EXISTS "Models" (
    "Id" uuid NOT NULL PRIMARY KEY,
    "TransactionId" uuid NOT NULL,
    "ParentModelId" uuid NULL,
    "InheritanceDepth" integer NOT NULL,
    "Status" integer NOT NULL,
    "CreatedAt" timestamp with time zone NOT NULL,
    "UpdatedAt" timestamp with time zone NOT NULL,
    "Version" integer NOT NULL,
    "Parameters" jsonb NOT NULL,
    "Location" jsonb NOT NULL,
    "Metrics" jsonb NOT NULL,
    "PhysicsValidation" jsonb NOT NULL,
    "ArtifactLocation" character varying(500) NULL,
    CONSTRAINT "FK_Models_Transactions_TransactionId" 
        FOREIGN KEY ("TransactionId") 
        REFERENCES "Transactions" ("Id") 
        ON DELETE CASCADE,
    CONSTRAINT "FK_Models_Models_ParentModelId" 
        FOREIGN KEY ("ParentModelId") 
        REFERENCES "Models" ("Id") 
        ON DELETE SET NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS "IX_Transactions_CreatedAt" ON "Transactions" ("CreatedAt");
CREATE INDEX IF NOT EXISTS "IX_Transactions_Status" ON "Transactions" ("Status");
CREATE INDEX IF NOT EXISTS "IX_Transactions_Source" ON "Transactions" ("Source");

CREATE INDEX IF NOT EXISTS "IX_Models_TransactionId" ON "Models" ("TransactionId");
CREATE INDEX IF NOT EXISTS "IX_Models_ParentModelId" ON "Models" ("ParentModelId");
CREATE INDEX IF NOT EXISTS "IX_Models_Status" ON "Models" ("Status");
CREATE INDEX IF NOT EXISTS "IX_Models_CreatedAt" ON "Models" ("CreatedAt");
CREATE INDEX IF NOT EXISTS "IX_Models_InheritanceDepth" ON "Models" ("InheritanceDepth");

-- Create GIN indexes for JSONB columns for fast queries
CREATE INDEX IF NOT EXISTS "IX_Transactions_Data_GIN" ON "Transactions" USING GIN ("Data");
CREATE INDEX IF NOT EXISTS "IX_Transactions_Metadata_GIN" ON "Transactions" USING GIN ("Metadata");
CREATE INDEX IF NOT EXISTS "IX_Models_Parameters_GIN" ON "Models" USING GIN ("Parameters");
CREATE INDEX IF NOT EXISTS "IX_Models_Location_GIN" ON "Models" USING GIN ("Location");
CREATE INDEX IF NOT EXISTS "IX_Models_Metrics_GIN" ON "Models" USING GIN ("Metrics");

-- Create migration history table (for Entity Framework compatibility)
CREATE TABLE IF NOT EXISTS "__EFMigrationsHistory" (
    "MigrationId" character varying(150) NOT NULL,
    "ProductVersion" character varying(32) NOT NULL,
    CONSTRAINT "PK___EFMigrationsHistory" PRIMARY KEY ("MigrationId")
);

-- Record the migration
INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
VALUES ('20241204_InitialCreate', '8.0.0')
ON CONFLICT ("MigrationId") DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tml_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tml_user;

-- Enable TimescaleDB extension (if available)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Convert Transactions table to hypertable (if TimescaleDB is available)
-- Note: This will fail gracefully if TimescaleDB is not installed
DO $$
BEGIN
    PERFORM create_hypertable('Transactions', 'CreatedAt', if_not_exists => TRUE);
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'TimescaleDB not available or table already converted: %', SQLERRM;
END $$;

-- Verify schema creation
SELECT 
    'Tables Created' AS status,
    COUNT(*) AS count 
FROM information_schema.tables 
WHERE table_schema = 'public' 
    AND table_name IN ('Transactions', 'Models');

SELECT 
    'Indexes Created' AS status,
    COUNT(*) AS count 
FROM pg_indexes 
WHERE schemaname = 'public' 
    AND tablename IN ('Transactions', 'Models');

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Database schema created successfully!';
    RAISE NOTICE '✅ Tables: Transactions, Models';
    RAISE NOTICE '✅ Indexes: All performance indexes created';
    RAISE NOTICE '✅ JSONB indexes: GIN indexes for fast queries';
    RAISE NOTICE '✅ Migration recorded in __EFMigrationsHistory';
END $$;
