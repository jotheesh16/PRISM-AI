-- ==============================================================================
-- PRISM AI — Supabase Database & Storage Setup Schema
-- Run this in your Supabase Dashboard -> SQL Editor -> Click 'Run'
-- ==============================================================================

-- 1. Enable pgvector for dense 384-dimensional all-MiniLM-L6-v2 embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Workspaces Table
CREATE TABLE IF NOT EXISTS public.spaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default workspace
INSERT INTO public.spaces (id, name)
VALUES ('main', 'Research workspace')
ON CONFLICT (id) DO NOTHING;

-- 3. Documents Metadata Table
CREATE TABLE IF NOT EXISTS public.docs (
    id TEXT PRIMARY KEY,
    space TEXT REFERENCES public.spaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    size BIGINT NOT NULL,
    hash TEXT NOT NULL,
    pages INT DEFAULT 0,
    done INT DEFAULT 0,
    state TEXT DEFAULT 'ready',
    notes TEXT DEFAULT '',
    ocr INT DEFAULT 0,
    scans INT DEFAULT 0,
    generation INT DEFAULT 0,
    storage_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(space, hash)
);

-- 4. Evidence Chunks Table (Text, OCR, Visuals + Vectors)
CREATE TABLE IF NOT EXISTS public.evidence (
    id BIGSERIAL PRIMARY KEY,
    doc TEXT REFERENCES public.docs(id) ON DELETE CASCADE,
    page INT NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    bbox JSONB,
    w REAL,
    h REAL,
    model TEXT,
    vector vector(384),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED
);

-- Search Indexes
CREATE INDEX IF NOT EXISTS idx_evidence_doc ON public.evidence(doc, page);
CREATE INDEX IF NOT EXISTS idx_evidence_tsv ON public.evidence USING GIN(tsv);
CREATE INDEX IF NOT EXISTS idx_evidence_vector ON public.evidence USING hnsw (vector vector_ip_ops);

-- 5. Conversations & Results History
CREATE TABLE IF NOT EXISTS public.conversations (
    id TEXT NOT NULL,
    space TEXT REFERENCES public.spaces(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY(space, id)
);

INSERT INTO public.conversations (id, space)
VALUES ('legacy', 'main')
ON CONFLICT (space, id) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.results (
    id TEXT PRIMARY KEY,
    space TEXT REFERENCES public.spaces(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    payload JSONB NOT NULL,
    conversation TEXT NOT NULL DEFAULT 'legacy',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_space_conv ON public.results(space, conversation);

CREATE TABLE IF NOT EXISTS public.result_docs (
    result TEXT REFERENCES public.results(id) ON DELETE CASCADE,
    doc TEXT REFERENCES public.docs(id) ON DELETE CASCADE,
    PRIMARY KEY(result, doc)
);

-- 6. Disable Row Level Security (RLS) & Grant Access to PostgREST roles
ALTER TABLE public.spaces DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.docs DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.results DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.result_docs DISABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA public TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;

-- 7. Create Public Storage Bucket for PDFs
INSERT INTO storage.buckets (id, name, public)
VALUES ('prism-documents', 'prism-documents', true)
ON CONFLICT (id) DO NOTHING;

-- Grant public read and write access to the bucket
DROP POLICY IF EXISTS "Public Access" ON storage.objects;
CREATE POLICY "Public Access"
ON storage.objects FOR ALL
USING (bucket_id = 'prism-documents')
WITH CHECK (bucket_id = 'prism-documents');
