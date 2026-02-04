-- CSMS Management System Schema
-- Run this in your Supabase SQL Editor

-- 1. Projects Table
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    contractor_name TEXT,
    risk_level TEXT,
    description TEXT,
    start_date DATE,
    end_date DATE,
    status TEXT DEFAULT 'Upcoming', -- Upcoming, InProgress, Completed, OnHold
    contract_value TEXT,
    well_name TEXT,
    rig_down DATE, 
    pic_name TEXT,
    pic_email TEXT,
    pic_manager_email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tasks Table
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    code TEXT,
    title TEXT,
    well_name TEXT,
    category TEXT,
    status TEXT DEFAULT 'Upcoming', -- Upcoming, In Progress, Completed
    description TEXT,
    start_date DATE,
    end_date DATE,
    attachments JSONB DEFAULT '[]'::jsonb, -- Stores array of {filename, file_id, ...}
    score INTEGER DEFAULT 0, -- Performance score (0, 3, 6, 10)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Schedules Table
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    project_name TEXT,
    well_name TEXT,
    schedule_type TEXT, -- mwt, hse_committee, etc.
    mwt_plan_date DATE,
    hse_meeting_date DATE,
    csms_pb_date DATE,
    hseplan_date DATE,
    spr_date DATE,
    hazid_hazop_date DATE,
    pic_name TEXT,
    assigned_to_email TEXT,
    status TEXT DEFAULT 'Scheduled',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Comments Table (Home Feed)
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    author_name TEXT,
    content TEXT,
    attachment_filename TEXT,
    attachment_data TEXT, -- Base64 data if needed, or link
    likes INTEGER DEFAULT 0,
    replies JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. CSMS PB (Performance Board) Records
CREATE TABLE IF NOT EXISTS csms_pb (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    period TEXT,
    score NUMERIC,
    notes TEXT,
    attachments JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Related Documents
CREATE TABLE IF NOT EXISTS related_docs (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    well_name TEXT,
    doc_name TEXT,
    filename TEXT,
    drive_file_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. App Logs (for debugging)
CREATE TABLE IF NOT EXISTS app_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    level TEXT, -- INFO, ERROR, WARN
    service TEXT, -- API, DB, DRIVE, EMAIL
    message TEXT,
    details TEXT, -- Stack trace or JSON
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS) is generally good practice, 
-- but for initial service account usage we often just need existing tables.
-- If you access this from client-side JS directly, you'll need Policies.
-- For this Python backend using Service Key (if used) or authenticated client, it should work.

