# automation/scheduler.py
import schedule
import time
import threading
from datetime import datetime
import subprocess
import sys
import os

class AutoScheduler:
    def __init__(self):
        self.is_running = True
        self.log_file = 'automation_scheduler.log'
        
    def log(self, message):
        """Log scheduler activity"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}\n"
        
        print(log_message.strip())
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_message)
        except:
            pass
    
    def run_auto_post(self):
        """Run the auto-post script"""
        self.log("Starting daily auto-post job...")
        
        try:
            # Run auto_post.py
            script_path = os.path.join(os.path.dirname(__file__), '..', 'auto_post.py')
            
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )
            
            if result.returncode == 0:
                self.log("✅ Auto-post completed successfully")
                self.log(f"Output: {result.stdout[:200]}...")
            else:
                self.log(f"❌ Auto-post failed with code {result.returncode}")
                self.log(f"Error: {result.stderr}")
                
        except Exception as e:
            self.log(f"❌ Error running auto-post: {e}")
    
    def check_system(self):
        """Periodic system check"""
        self.log("System check: Scheduler is running")
    
    def start_scheduler(self):
        """Start the scheduler"""
        self.log("🤖 Starting SA Updates Automation Scheduler")
        
        # Schedule daily auto-post at 9:00 AM
        schedule.every().day.at("09:00").do(self.run_auto_post)
        
        # Schedule system check every 6 hours
        schedule.every(6).hours.do(self.check_system)
        
        # Run immediately on startup (optional)
        # self.run_auto_post()
        
        self.log("✅ Scheduler started successfully")
        self.log("📅 Next auto-post: Daily at 09:00")
        
        # Keep the scheduler running
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        self.log("Scheduler stopped")

def start_background_scheduler():
    """Start scheduler in background thread"""
    scheduler = AutoScheduler()
    thread = threading.Thread(target=scheduler.start_scheduler, daemon=True)
    thread.start()
    return scheduler

if __name__ == "__main__":
    # Run scheduler directly for testing
    scheduler = AutoScheduler()
    try:
        scheduler.start_scheduler()
    except KeyboardInterrupt:
        scheduler.stop()
        print("\nScheduler stopped by user")