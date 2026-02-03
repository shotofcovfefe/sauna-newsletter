-- Sauna News table for daily news sidebar
-- Run this migration in your Supabase SQL Editor after 002_helper_functions.sql

-- Create enum for news types
CREATE TYPE news_type AS ENUM ('opening', 'closure', 'major_news', 'expansion', 'other');

-- Table: sauna_news
-- Stores daily scraped London sauna news for website sidebar
CREATE TABLE IF NOT EXISTS sauna_news (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    source_url TEXT,
    published_at TIMESTAMP WITH TIME ZONE,
    scraped_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    news_type news_type NOT NULL DEFAULT 'other',
    venue_name TEXT,
    is_featured BOOLEAN DEFAULT FALSE,
    content_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sauna_news_published_at ON sauna_news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_sauna_news_scraped_at ON sauna_news(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_sauna_news_content_hash ON sauna_news(content_hash);
CREATE INDEX IF NOT EXISTS idx_sauna_news_news_type ON sauna_news(news_type);
CREATE INDEX IF NOT EXISTS idx_sauna_news_is_featured ON sauna_news(is_featured) WHERE is_featured = TRUE;

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_sauna_news_updated_at ON sauna_news;
CREATE TRIGGER update_sauna_news_updated_at
    BEFORE UPDATE ON sauna_news
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security
ALTER TABLE sauna_news ENABLE ROW LEVEL SECURITY;

-- Create policy for public read access (no authentication needed)
DROP POLICY IF EXISTS "Allow public read access" ON sauna_news;
CREATE POLICY "Allow public read access"
    ON sauna_news
    FOR SELECT
    TO anon
    USING (true);

-- Create policy for authenticated insert (for the scraping service)
DROP POLICY IF EXISTS "Allow authenticated insert" ON sauna_news;
CREATE POLICY "Allow authenticated insert"
    ON sauna_news
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- Create policy for authenticated update
DROP POLICY IF EXISTS "Allow authenticated update" ON sauna_news;
CREATE POLICY "Allow authenticated update"
    ON sauna_news
    FOR UPDATE
    TO authenticated
    USING (true);

-- Create view for recent featured news (convenience)
CREATE OR REPLACE VIEW recent_featured_news AS
SELECT
    id,
    title,
    summary,
    source_url,
    published_at,
    news_type,
    venue_name,
    scraped_at
FROM sauna_news
WHERE is_featured = TRUE
  AND scraped_at >= NOW() - INTERVAL '14 days'
ORDER BY published_at DESC NULLS LAST, scraped_at DESC
LIMIT 10;

-- Create view for recent news (all types, last 14 days)
CREATE OR REPLACE VIEW recent_news AS
SELECT
    id,
    title,
    summary,
    source_url,
    published_at,
    news_type,
    venue_name,
    scraped_at
FROM sauna_news
WHERE scraped_at >= NOW() - INTERVAL '14 days'
ORDER BY published_at DESC NULLS LAST, scraped_at DESC
LIMIT 20;

-- Grant access to views
GRANT SELECT ON recent_featured_news TO anon, authenticated;
GRANT SELECT ON recent_news TO anon, authenticated;

-- Comments for documentation
COMMENT ON TABLE sauna_news IS 'Stores daily scraped London sauna news from Perplexity API for website sidebar';
COMMENT ON COLUMN sauna_news.content_hash IS 'MD5 hash of title+summary for deduplication';
COMMENT ON COLUMN sauna_news.is_featured IS 'Manually curated or algorithmically selected top stories (shown with star badge)';
COMMENT ON COLUMN sauna_news.published_at IS 'Original publication date of the news (if available)';
COMMENT ON COLUMN sauna_news.scraped_at IS 'When this was scraped by our system';
COMMENT ON COLUMN sauna_news.news_type IS 'Type of news: opening, closure, major_news, expansion, or other';
