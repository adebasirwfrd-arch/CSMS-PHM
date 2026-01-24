import os
import json
import asyncio
from services.supabase_service import supabase_service
from database import (
    PROJECTS_FILE, TASKS_FILE, SCHEDULES_FILE, 
    COMMENTS_FILE, CSMS_PB_FILE, RELATED_DOCS_FILE
)

async def migrate_data():
    """
    Migrate data from local JSON files to Supabase
    """
    print("🚀 Starting Migration to Supabase...")
    
    if not supabase_service.enabled:
        print("❌ Supabase is NOT enabled. Please set SUPABASE_URL and SUPABASE_KEY first.")
        return

    # 1. Migrate Projects
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, 'r') as f:
            projects = json.load(f)
            print(f"📦 Found {len(projects)} projects")
            for p in projects:
                # Check if exists first to avoid duplicates
                existing = supabase_service.get_project(p['id'])
                if not existing:
                    supabase_service.create_project(p)
                    print(f"   ✅ Migrated project: {p.get('name')}")
                else:
                    print(f"   ⚠️ Skipping existing project: {p.get('name')}")

    # 2. Migrate Tasks
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, 'r') as f:
            tasks = json.load(f)
            print(f"📦 Found {len(tasks)} tasks")
            # Use batch insert for speed
            if tasks:
                existing_ids = [t['id'] for t in supabase_service.get_tasks()]
                new_tasks = [t for t in tasks if t['id'] not in existing_ids]
                if new_tasks:
                    supabase_service.batch_create_tasks(new_tasks)
                    print(f"   ✅ Batch migrated {len(new_tasks)} tasks")
                else:
                    print("   ⚠️ All tasks already exist")

    # 3. Migrate Schedules
    if os.path.exists(SCHEDULES_FILE):
        with open(SCHEDULES_FILE, 'r') as f:
            schedules = json.load(f)
            print(f"📦 Found {len(schedules)} schedules")
            for s in schedules:
                supabase_service.save_schedule(s)
                print(f"   ✅ Migrated schedule: {s.get('title')}")

    # 4. Migrate Comments
    if os.path.exists(COMMENTS_FILE):
        with open(COMMENTS_FILE, 'r') as f:
            comments = json.load(f)
            print(f"📦 Found {len(comments)} comments")
            for c in comments:
                supabase_service.save_comment(c)
                print("   ✅ Migrated comment")

    print("\n✨ Migration Complete!")

if __name__ == "__main__":
    asyncio.run(migrate_data())
