"""
Supabase Database Service
Provides persistent storage for CSMS application data
"""
import os
from typing import List, Dict, Optional
from datetime import datetime
import json

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("[WARN] supabase-py not installed. Run: pip install supabase")

class SupabaseService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "")
        self.key = os.getenv("SUPABASE_KEY", "")
        self.client: Optional[Client] = None
        self.enabled = False
        
        print("[SUPABASE] Initializing Supabase Service...")
        print(f"  [DEBUG] SUPABASE_URL: {self.url[:30] + '...' if self.url else 'NOT SET'}")
        print(f"  [DEBUG] SUPABASE_KEY: {'SET' if self.key else 'NOT SET'}")
        
        if not SUPABASE_AVAILABLE:
            print("[ERROR] supabase-py package not installed")
            return
            
        if not self.url or not self.key:
            print("[ERROR] SUPABASE_URL or SUPABASE_KEY not set")
            return
        
        try:
            self.client = create_client(self.url, self.key)
            self.enabled = True
            print("[OK] Supabase client initialized!")
        except Exception as e:
            print(f"[ERROR] Supabase initialization failed: {e}")
            self.enabled = False
    
    # ==================== PROJECTS ====================
    
    def get_projects(self) -> List[Dict]:
        if not self.enabled:
            return []
        try:
            result = self.client.table('projects').select("*").execute()
            return result.data or []
        except Exception as e:
            print(f"[ERROR] Error fetching projects: {e}")
            return []
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        if not self.enabled:
            return None
        try:
            result = self.client.table('projects').select("*").eq('id', project_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[ERROR] Error fetching project {project_id}: {e}")
            return None
    
    def create_project(self, project_data: Dict) -> Dict:
        print(f"[SUPABASE] create_project called, enabled={self.enabled}")
        print(f"[SUPABASE] Project data: {project_data}")
        if not self.enabled:
            print("[SUPABASE] Not enabled, returning data as-is")
            return project_data
        try:
            print(f"[SUPABASE] Attempting insert into 'projects'...")
            response = self.client.table('projects').insert(project_data).execute()
            
            # Check for error in response (some versions of supabase-py return it)
            if hasattr(response, 'error') and response.error:
                print(f"[SUPABASE ERROR] API returned error: {response.error}")
                return project_data
                
            if response.data:
                print(f"[SUPABASE] SUCCESS! Project created: {response.data[0]['id']}")
                return response.data[0]
            else:
                print(f"[SUPABASE] WARNING: No data returned from insert. Response: {response}")
                return project_data
        except Exception as e:
            print(f"[SUPABASE CRITICAL ERROR] Exception during insert: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return project_data
    
    def update_project(self, project_id: str, updates: Dict) -> Optional[Dict]:
        if not self.enabled:
            return None
        try:
            result = self.client.table('projects').update(updates).eq('id', project_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[ERROR] Error updating project: {e}")
            return None
    
    def delete_project(self, project_id: str) -> bool:
        if not self.enabled:
            return False
        try:
            self.client.table('projects').delete().eq('id', project_id).execute()
            return True
        except Exception as e:
            print(f"[ERROR] Error deleting project: {e}")
            return False
    
    # ==================== TASKS ====================
    
    def get_tasks(self, project_id: str = None) -> List[Dict]:
        if not self.enabled:
            return []
        try:
            query = self.client.table('tasks').select("*")
            if project_id:
                query = query.eq('project_id', project_id)
            result = query.execute()
            tasks = result.data or []
            # Parse attachments JSON for each task
            for task in tasks:
                if 'attachments' in task and isinstance(task['attachments'], str):
                    try:
                        task['attachments'] = json.loads(task['attachments'])
                    except:
                        task['attachments'] = []
            return tasks
        except Exception as e:
            print(f"[ERROR] Error fetching tasks: {e}")
            return []
    
    def create_task(self, task_data: Dict) -> Dict:
        print(f"[SUPABASE] create_task called, enabled={self.enabled}")
        if not self.enabled:
            return task_data
        try:
            # Convert attachments list to JSON string
            if 'attachments' in task_data and isinstance(task_data['attachments'], list):
                task_data['attachments'] = json.dumps(task_data['attachments'])
            print(f"[SUPABASE] Inserting task: {task_data.get('title', 'unknown')}")
            result = self.client.table('tasks').insert(task_data).execute()
            print(f"[SUPABASE] Task insert result: {result.data[0]['id'] if result.data else 'NO DATA'}")
            task = result.data[0] if result.data else task_data
            if 'attachments' in task and isinstance(task['attachments'], str):
                task['attachments'] = json.loads(task['attachments'])
            return task
        except Exception as e:
            print(f"[ERROR] Error creating task: {e}")
            import traceback
            traceback.print_exc()
            return task_data
    
    def update_task(self, task_id: str, updates: Dict) -> Optional[Dict]:
        if not self.enabled:
            return None
        try:
            if 'attachments' in updates and isinstance(updates['attachments'], list):
                updates['attachments'] = json.dumps(updates['attachments'])
            result = self.client.table('tasks').update(updates).eq('id', task_id).execute()
            task = result.data[0] if result.data else None
            if task and 'attachments' in task and isinstance(task['attachments'], str):
                task['attachments'] = json.loads(task['attachments'])
            return task
        except Exception as e:
            print(f"[ERROR] Error updating task: {e}")
            return None
    
    def batch_create_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Batch insert multiple tasks in a single API call - much faster!"""
        if not self.enabled or not tasks:
            return tasks
        try:
            # Convert attachments to JSON strings
            for task in tasks:
                if 'attachments' in task and isinstance(task['attachments'], list):
                    task['attachments'] = json.dumps(task['attachments'])
            
            print(f"[SUPABASE] Batch inserting {len(tasks)} tasks in ONE call...")
            result = self.client.table('tasks').insert(tasks).execute()
            print(f"[SUPABASE] Batch insert complete: {len(result.data) if result.data else 0} tasks created")
            
            # Parse attachments back for each task
            returned_tasks = result.data or tasks
            for task in returned_tasks:
                if 'attachments' in task and isinstance(task['attachments'], str):
                    try:
                        task['attachments'] = json.loads(task['attachments'])
                    except:
                        task['attachments'] = []
            return returned_tasks
        except Exception as e:
            print(f"[ERROR] Batch task insert failed: {e}")
            return tasks
    
    def delete_task(self, task_id: str) -> bool:
        if not self.enabled:
            return False
        try:
            self.client.table('tasks').delete().eq('id', task_id).execute()
            return True
        except Exception as e:
            print(f"[ERROR] Error deleting task: {e}")
            return False
    
    # ==================== SCHEDULES ====================
    
    def get_schedules(self) -> List[Dict]:
        if not self.enabled:
            return []
        try:
            result = self.client.table('schedules').select("*").execute()
            return result.data or []
        except Exception as e:
            print(f"[ERROR] Error fetching schedules: {e}")
            return []
    
    def save_schedule(self, schedule_data: Dict) -> Dict:
        if not self.enabled:
            return schedule_data
        try:
            result = self.client.table('schedules').insert(schedule_data).execute()
            return result.data[0] if result.data else schedule_data
        except Exception as e:
            print(f"[ERROR] Error creating schedule: {e}")
            return schedule_data
    
    def delete_schedule(self, schedule_id: str) -> bool:
        if not self.enabled:
            return False
        try:
            self.client.table('schedules').delete().eq('id', schedule_id).execute()
            return True
        except Exception as e:
            print(f"[ERROR] Error deleting schedule: {e}")
            return False
    
    # ==================== COMMENTS ====================
    
    def get_comments(self) -> List[Dict]:
        if not self.enabled:
            return []
        try:
            result = self.client.table('comments').select("*").order('created_at', desc=True).execute()
            comments = result.data or []
            for comment in comments:
                if 'replies' in comment and isinstance(comment['replies'], str):
                    try:
                        comment['replies'] = json.loads(comment['replies'])
                    except:
                        comment['replies'] = []
            return comments
        except Exception as e:
            print(f"[ERROR] Error fetching comments: {e}")
            return []
    
    def save_comment(self, comment_data: Dict) -> Dict:
        if not self.enabled:
            return comment_data
        try:
            if 'replies' in comment_data and isinstance(comment_data['replies'], list):
                comment_data['replies'] = json.dumps(comment_data['replies'])
            result = self.client.table('comments').insert(comment_data).execute()
            return result.data[0] if result.data else comment_data
        except Exception as e:
            print(f"[ERROR] Error creating comment: {e}")
            return comment_data
    
    def update_comment(self, comment_id: str, updates: Dict) -> Optional[Dict]:
        if not self.enabled:
            return None
        try:
            if 'replies' in updates and isinstance(updates['replies'], list):
                updates['replies'] = json.dumps(updates['replies'])
            result = self.client.table('comments').update(updates).eq('id', comment_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[ERROR] Error updating comment: {e}")
            return None
    
    def delete_comment(self, comment_id: str) -> bool:
        if not self.enabled:
            return False
        try:
            self.client.table('comments').delete().eq('id', comment_id).execute()
            return True
        except Exception as e:
            print(f"[ERROR] Error deleting comment: {e}")
            return False
    
    # ==================== CSMS PB ====================
    
    def get_csms_pb_records(self) -> List[Dict]:
        if not self.enabled:
            return []
        try:
            result = self.client.table('csms_pb').select("*").execute()
            records = result.data or []
            for record in records:
                if 'attachments' in record and isinstance(record['attachments'], str):
                    try:
                        record['attachments'] = json.loads(record['attachments'])
                    except:
                        record['attachments'] = []
            return records
        except Exception as e:
            print(f"[ERROR] Error fetching CSMS PB: {e}")
            return []
    
    def save_csms_pb(self, pb_data: Dict) -> Dict:
        if not self.enabled:
            return pb_data
        try:
            if 'attachments' in pb_data and isinstance(pb_data['attachments'], list):
                pb_data['attachments'] = json.dumps(pb_data['attachments'])
            result = self.client.table('csms_pb').insert(pb_data).execute()
            return result.data[0] if result.data else pb_data
        except Exception as e:
            print(f"[ERROR] Error creating CSMS PB: {e}")
            return pb_data
    
    def update_csms_pb(self, pb_id: str, updates: Dict) -> Optional[Dict]:
        if not self.enabled:
            return None
        try:
            result = self.client.table('csms_pb').update(updates).eq('id', pb_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[ERROR] Error updating CSMS PB: {e}")
            return None
    
    def delete_csms_pb(self, pb_id: str) -> bool:
        if not self.enabled:
            return False
        try:
            self.client.table('csms_pb').delete().eq('id', pb_id).execute()
            return True
        except Exception as e:
            print(f"[ERROR] Error deleting CSMS PB: {e}")
            return False
    
    # ==================== RELATED DOCS ====================
    
    def get_related_docs(self) -> List[Dict]:
        if not self.enabled:
            return []
        try:
            result = self.client.table('related_docs').select("*").execute()
            return result.data or []
        except Exception as e:
            print(f"[ERROR] Error fetching related docs: {e}")
            return []
    
    def save_related_doc(self, doc_data: Dict) -> Dict:
        if not self.enabled:
            return doc_data
        try:
            result = self.client.table('related_docs').insert(doc_data).execute()
            return result.data[0] if result.data else doc_data
        except Exception as e:
            print(f"[ERROR] Error creating related doc: {e}")
            return doc_data
    
    def delete_related_doc(self, doc_id: str) -> bool:
        if not self.enabled:
            return False
        try:
            self.client.table('related_docs').delete().eq('id', doc_id).execute()
            return True
        except Exception as e:
            print(f"[ERROR] Error deleting related doc: {e}")
            return False

    # ==================== LOGGING ====================

    def log_event(self, level: str, service: str, message: str, details: str = None) -> bool:
        """Log an event to the app_logs table"""
        if not self.enabled:
            return False
        try:
            log_data = {
                "level": level,
                "service": service,
                "message": message,
                "details": details,
                "created_at": datetime.now().isoformat()
            }
            self.client.table('app_logs').insert(log_data).execute()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to write log to Supabase: {e}")
            return False

# Global instance
supabase_service = SupabaseService()
