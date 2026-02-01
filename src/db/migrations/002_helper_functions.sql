-- Optional helper functions for Supabase email artifact queries
-- Run this migration in your Supabase SQL Editor after 001_email_tables.sql

-- Function: Get unused email artifacts
-- Returns sauna-related email artifacts that haven't been used in any newsletter yet
CREATE OR REPLACE FUNCTION get_unused_email_artifacts(
    min_confidence FLOAT DEFAULT 0.5,
    days_back INT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    email_id UUID,
    compressed_content TEXT,
    summary TEXT,
    confidence_score FLOAT,
    processed_at TIMESTAMP,
    sender TEXT,
    subject TEXT,
    email_date TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ea.id,
        ea.email_id,
        ea.compressed_content,
        ea.summary,
        ea.confidence_score,
        ea.processed_at,
        e.sender,
        e.subject,
        e.date AS email_date
    FROM email_artifacts ea
    INNER JOIN emails e ON ea.email_id = e.id
    LEFT JOIN newsletter_artifacts na ON ea.id = na.artifact_id
    WHERE
        ea.is_sauna_related = TRUE
        AND ea.confidence_score >= min_confidence
        AND na.artifact_id IS NULL  -- Not used in any newsletter
        AND (days_back IS NULL OR e.date >= NOW() - INTERVAL '1 day' * days_back)  -- Optional date filter
    ORDER BY ea.confidence_score DESC, e.date DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Get email artifacts by run_id
-- Returns all email artifacts used in a specific newsletter run
CREATE OR REPLACE FUNCTION get_email_artifacts_by_run(run_id_param TEXT)
RETURNS TABLE (
    id UUID,
    email_id UUID,
    compressed_content TEXT,
    summary TEXT,
    confidence_score FLOAT,
    sender TEXT,
    subject TEXT,
    email_date TIMESTAMP,
    used_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ea.id,
        ea.email_id,
        ea.compressed_content,
        ea.summary,
        ea.confidence_score,
        e.sender,
        e.subject,
        e.date AS email_date,
        na.created_at AS used_at
    FROM email_artifacts ea
    INNER JOIN emails e ON ea.email_id = e.id
    INNER JOIN newsletter_artifacts na ON ea.id = na.artifact_id
    WHERE na.run_id = run_id_param
    ORDER BY e.date DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Get email processing statistics
-- Returns summary statistics about email processing
CREATE OR REPLACE FUNCTION get_email_stats()
RETURNS TABLE (
    total_emails BIGINT,
    total_artifacts BIGINT,
    sauna_related BIGINT,
    used_in_newsletters BIGINT,
    unused_sauna_related BIGINT,
    avg_confidence FLOAT,
    latest_processed TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM emails),
        (SELECT COUNT(*) FROM email_artifacts),
        (SELECT COUNT(*) FROM email_artifacts WHERE is_sauna_related = TRUE),
        (SELECT COUNT(DISTINCT artifact_id) FROM newsletter_artifacts),
        (SELECT COUNT(*) FROM email_artifacts ea
         LEFT JOIN newsletter_artifacts na ON ea.id = na.artifact_id
         WHERE ea.is_sauna_related = TRUE AND na.artifact_id IS NULL),
        (SELECT AVG(confidence_score) FROM email_artifacts WHERE is_sauna_related = TRUE),
        (SELECT MAX(processed_at) FROM emails);
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON FUNCTION get_unused_email_artifacts IS 'Returns sauna-related email artifacts not yet used in any newsletter';
COMMENT ON FUNCTION get_email_artifacts_by_run IS 'Returns all email artifacts used in a specific newsletter run_id';
COMMENT ON FUNCTION get_email_stats IS 'Returns summary statistics about email processing and usage';
