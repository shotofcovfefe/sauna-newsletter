-- Email gathering and artifact storage schema for Supabase
-- Run this migration in your Supabase SQL Editor

-- Table: emails
-- Stores raw email metadata from Gmail
CREATE TABLE IF NOT EXISTS emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id TEXT UNIQUE NOT NULL,
    sender TEXT,
    sender_name TEXT,
    subject TEXT,
    date TIMESTAMP WITHOUT TIME ZONE,
    raw_body TEXT,
    processed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Table: email_artifacts
-- Stores LLM-compressed, sauna-relevant content from emails
CREATE TABLE IF NOT EXISTS email_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE,
    compressed_content TEXT NOT NULL,
    summary TEXT,
    is_sauna_related BOOLEAN DEFAULT FALSE,
    confidence_score FLOAT,
    gemini_model TEXT,
    processed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    UNIQUE(email_id)
);

-- Table: newsletter_artifacts
-- Junction table tracking which email artifacts have been used in which newsletter runs
CREATE TABLE IF NOT EXISTS newsletter_artifacts (
    artifact_id UUID REFERENCES email_artifacts(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (artifact_id, run_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date DESC);
CREATE INDEX IF NOT EXISTS idx_email_artifacts_email_id ON email_artifacts(email_id);
CREATE INDEX IF NOT EXISTS idx_email_artifacts_sauna_related ON email_artifacts(is_sauna_related) WHERE is_sauna_related = TRUE;
CREATE INDEX IF NOT EXISTS idx_newsletter_artifacts_artifact_id ON newsletter_artifacts(artifact_id);
CREATE INDEX IF NOT EXISTS idx_newsletter_artifacts_run_id ON newsletter_artifacts(run_id);

-- Comments for documentation
COMMENT ON TABLE emails IS 'Raw email metadata fetched from Gmail';
COMMENT ON TABLE email_artifacts IS 'LLM-compressed email content with sauna-relevance classification';
COMMENT ON TABLE newsletter_artifacts IS 'Tracks which email artifacts have been used in newsletter runs to prevent duplication';
COMMENT ON COLUMN emails.message_id IS 'Gmail Message-ID header (unique identifier for deduplication)';
COMMENT ON COLUMN email_artifacts.compressed_content IS 'LLM-summarized key points without HTML/graphics';
COMMENT ON COLUMN email_artifacts.confidence_score IS 'Sauna-relevance confidence score (0.0-1.0)';
COMMENT ON COLUMN newsletter_artifacts.run_id IS 'Links to candidate run ID in data/runs/{run_id}_candidates.json';
