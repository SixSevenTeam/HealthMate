-- V1__init_schema.sql
-- Initialize database schema for HealthMate application
-- Idempotent migration - safe to run multiple times

-- Enable UUID extension (safe to run multiple times)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ========================
-- SCHEMA: auth
-- ========================
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
                                          id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                          email         VARCHAR(255) UNIQUE NOT NULL,
                                          password_hash VARCHAR(255) NOT NULL,
                                          first_name    VARCHAR(100),
                                          last_name     VARCHAR(100),
                                          birth_date    DATE,
                                          is_active     BOOLEAN NOT NULL DEFAULT true,
                                          created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                          updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON auth.users(is_active);

-- ========================
-- SCHEMA: profile
-- ========================
CREATE SCHEMA IF NOT EXISTS profile;

CREATE TABLE IF NOT EXISTS profile.medical_profiles (
                                                        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                                        user_id      UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
                                                        height_cm    INTEGER,
                                                        weight_kg    DECIMAL(5,2),
                                                        blood_type   VARCHAR(5),
                                                        diagnoses    TEXT NOT NULL DEFAULT '[]',
                                                        allergies    TEXT NOT NULL DEFAULT '[]',
                                                        updated_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_medical_profiles_user_id ON profile.medical_profiles(user_id);

-- ========================
-- SCHEMA: medications
-- ========================
CREATE SCHEMA IF NOT EXISTS medications;

CREATE TABLE IF NOT EXISTS medications.drugs (
                                                 id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                                 trade_name          VARCHAR(255) NOT NULL,
                                                 international_name  VARCHAR(255),
                                                 atx_code            VARCHAR(20),
                                                 min_dose            DECIMAL(10,3),
                                                 max_dose            DECIMAL(10,3),
                                                 dose_unit           VARCHAR(20),
                                                 is_in_rag           BOOLEAN NOT NULL DEFAULT false,
                                                 created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                                 updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drugs_trade_name ON medications.drugs(trade_name);
CREATE INDEX IF NOT EXISTS idx_drugs_international_name ON medications.drugs(international_name);
CREATE INDEX IF NOT EXISTS idx_drugs_atx_code ON medications.drugs(atx_code);
CREATE INDEX IF NOT EXISTS idx_drugs_is_in_rag ON medications.drugs(is_in_rag);

-- Trigram indexes for fuzzy search
CREATE INDEX IF NOT EXISTS idx_drugs_trade_name_trgm ON medications.drugs USING gin(trade_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_drugs_international_name_trgm ON medications.drugs USING gin(international_name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS medications.user_medications (
                                                            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                                            user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                                                            drug_id      UUID NULL REFERENCES medications.drugs(id) ON DELETE SET NULL,
                                                            custom_name  VARCHAR(255),
                                                            dose_amount  DECIMAL(10,3) NOT NULL,
                                                            dose_unit    VARCHAR(20) NOT NULL,
                                                            instructions TEXT,
                                                            start_date   DATE,
                                                            end_date     DATE NULL,
                                                            is_active    BOOLEAN NOT NULL DEFAULT true,
                                                            created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                                            updated_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                                            CONSTRAINT ck_user_medications_dose_positive
                                                                CHECK (dose_amount > 0),
                                                            CONSTRAINT ck_user_medications_name_or_drug
                                                                CHECK (drug_id IS NOT NULL OR (custom_name IS NOT NULL AND btrim(custom_name) <> '')),
                                                            CONSTRAINT ck_user_medications_dates
                                                                CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_user_medications_user_id ON medications.user_medications(user_id);
CREATE INDEX IF NOT EXISTS idx_user_medications_drug_id ON medications.user_medications(drug_id);
CREATE INDEX IF NOT EXISTS idx_user_medications_is_active ON medications.user_medications(is_active);
CREATE INDEX IF NOT EXISTS idx_user_medications_user_active ON medications.user_medications(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_medications_user_active_dates ON medications.user_medications(user_id, is_active, start_date, end_date);

CREATE TABLE IF NOT EXISTS medications.schedules (
                                                     id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                                     user_medication_id  UUID NOT NULL REFERENCES medications.user_medications(id) ON DELETE CASCADE,
                                                     time_of_day         TIME NOT NULL,
                                                     days_of_week        INTEGER[] NOT NULL,
                                                     created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                                     CONSTRAINT ck_schedules_days_valid
                                                         CHECK (array_length(days_of_week, 1) > 0 AND days_of_week <@ ARRAY[1, 2, 3, 4, 5, 6, 7])
);

CREATE INDEX IF NOT EXISTS idx_schedules_user_medication_id ON medications.schedules(user_medication_id);

CREATE TABLE IF NOT EXISTS medications.intake_logs (
                                                       id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                                       user_medication_id  UUID NOT NULL REFERENCES medications.user_medications(id) ON DELETE CASCADE,
                                                       scheduled_at        TIMESTAMP WITH TIME ZONE NOT NULL,
                                                       taken_at            TIMESTAMP WITH TIME ZONE NULL,
                                                       status              VARCHAR(20) NOT NULL DEFAULT 'pending',
                                                       confirmed_via       VARCHAR(20) NULL,
                                                       created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                                       CONSTRAINT ck_intake_logs_status_valid
                                                           CHECK (status IN ('pending', 'taken', 'missed', 'skipped')),
                                                       CONSTRAINT ck_intake_logs_taken_fields
                                                           CHECK (status <> 'taken' OR taken_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_intake_logs_user_medication_id ON medications.intake_logs(user_medication_id);
CREATE INDEX IF NOT EXISTS idx_intake_logs_scheduled_at ON medications.intake_logs(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_intake_logs_status ON medications.intake_logs(status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_intake_logs_medication_scheduled ON medications.intake_logs(user_medication_id, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_intake_logs_medication_scheduled_status ON medications.intake_logs(user_medication_id, scheduled_at, status);

-- ========================
-- SCHEMA: chat
-- ========================
CREATE SCHEMA IF NOT EXISTS chat;

CREATE TABLE IF NOT EXISTS chat.conversations (
                                                  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                                  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                                                  title           VARCHAR(255),
                                                  status          VARCHAR(20) NOT NULL DEFAULT 'active',
                                                  anamnesis_state JSONB NULL,
                                                  created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                                  updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON chat.conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON chat.conversations(status);

CREATE TABLE IF NOT EXISTS chat.messages (
                                             id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                             conversation_id     UUID NOT NULL REFERENCES chat.conversations(id) ON DELETE CASCADE,
                                             role                VARCHAR(20) NOT NULL,
                                             content             TEXT NOT NULL,
                                             drug_reference      UUID NULL REFERENCES medications.drugs(id) ON DELETE SET NULL,
                                             rag_source          VARCHAR(255) NULL,
                                             created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON chat.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON chat.messages(role);