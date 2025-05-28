import json
import os
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

class TestStorage:
    """
    Class for storing and managing user tests with improved caching and concurrency handling
    """
    def __init__(self, storage_path: str = "user_tests.json"):
        self.storage_path = storage_path
        self.tests = self._load_tests()
        self.lock = threading.RLock()  # For thread safety
        self.last_save_time = time.time()
        self.dirty = False  # Flag to track if changes need to be saved
        
        # Start a background thread to periodically save changes
        self.save_thread = threading.Thread(target=self._auto_save, daemon=True)
        self.save_thread.start()
    
    def _auto_save(self):
        """Background thread to periodically save changes"""
        while True:
            time.sleep(30)  # Check every 30 seconds
            with self.lock:
                if self.dirty and (time.time() - self.last_save_time) > 60:  # Save if dirty and last save was >60 seconds ago
                    self._save_tests()
                    self.dirty = False
                    self.last_save_time = time.time()
    
    def _load_tests(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load tests from file or create empty structure with better error handling"""
        if os.path.exists(self.storage_path):
            try:
                # Try to load the file, with backup handling
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                # If the file is corrupted, try to load from backup
                logging.error(f"Error loading tests (corrupted JSON): {e}")
                backup_path = f"{self.storage_path}.backup"
                if os.path.exists(backup_path):
                    try:
                        with open(backup_path, 'r', encoding='utf-8') as f:
                            logging.info("Loading tests from backup file")
                            return json.load(f)
                    except Exception as backup_error:
                        logging.error(f"Error loading backup: {backup_error}")
            except Exception as e:
                logging.error(f"Error loading tests: {e}")
        return {}
    
    def _save_tests(self) -> None:
        """Save tests to file with backup creation"""
        try:
            # Create a backup of the current file if it exists
            if os.path.exists(self.storage_path):
                backup_path = f"{self.storage_path}.backup"
                try:
                    # Copy current file to backup
                    with open(self.storage_path, 'r', encoding='utf-8') as src:
                        with open(backup_path, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                except Exception as backup_error:
                    logging.error(f"Error creating backup: {backup_error}")
            
            # Write to a temporary file first, then rename for atomic operation
            temp_path = f"{self.storage_path}.temp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.tests, f, ensure_ascii=False, indent=2)
            
            # Rename the temp file to the actual file (atomic operation)
            os.replace(temp_path, self.storage_path)
            self.last_save_time = time.time()
            self.dirty = False
            logging.info("Tests saved successfully")
        except Exception as e:
            logging.error(f"Error saving tests: {e}")
    
    def add_test(self, user_id: int, test_name: str, questions: List[Tuple[str, List[str]]]) -> None:
        """
        Add a new test for a user
        user_id: Telegram user ID
        test_name: Name of the test
        questions: List of (question, [answers]) tuples
        """
        with self.lock:  # Thread safety
            user_id_str = str(user_id)
            
            if user_id_str not in self.tests:
                self.tests[user_id_str] = []
            
            # Convert questions to a serializable format
            serializable_questions = []
            for question, options in questions:
                serializable_questions.append({
                    "question": question,
                    "options": options
                })
            
            # Check if a test with this name already exists
            for test in self.tests[user_id_str]:
                if test["name"] == test_name:
                    # Update existing test
                    test["questions"] = serializable_questions
                    test["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.dirty = True
                    
                    # Save immediately if there are many questions
                    if len(serializable_questions) > 20:
                        self._save_tests()
                    return
            
            # Create new test
            self.tests[user_id_str].append({
                "name": test_name,
                "questions": serializable_questions,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            self.dirty = True
            
            # Save immediately if there are many questions
            if len(serializable_questions) > 20:
                self._save_tests()
    
    def get_user_tests(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all tests for a user
        Each user only sees their own tests, even admins
        """
        with self.lock:  # Thread safety
            user_id_str = str(user_id)
            # Return a deep copy to prevent external modifications
            user_tests = self.tests.get(user_id_str, [])
            return [{**test} for test in user_tests]  # Create a copy of each test dict
    
    def get_test(self, user_id: int, test_index: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific test by index
        Returns formatted questions list [(question, [answers])]
        """
        with self.lock:  # Thread safety
            user_id_str = str(user_id)
            if user_id_str not in self.tests or test_index >= len(self.tests[user_id_str]):
                return None
            
            test = self.tests[user_id_str][test_index]
            
            # Convert serialized questions to the format expected by the bot
            questions = []
            for q in test["questions"]:
                questions.append((q["question"], q["options"]))
            
            return {
                "name": test["name"],
                "questions": questions,
                "created_at": test["created_at"],
                "updated_at": test.get("updated_at", test["created_at"])
            }
    
    def delete_test(self, user_id: int, test_index: int) -> bool:
        """Delete a test by index"""
        with self.lock:  # Thread safety
            user_id_str = str(user_id)
            if user_id_str not in self.tests or test_index >= len(self.tests[user_id_str]):
                return False
            
            self.tests[user_id_str].pop(test_index)
            self.dirty = True
            
            # If this was the last test for this user, clean up
            if not self.tests[user_id_str]:
                del self.tests[user_id_str]
                
            return True
            
    def get_test_by_name(self, user_id: int, test_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific test by name"""
        with self.lock:  # Thread safety
            user_id_str = str(user_id)
            if user_id_str not in self.tests:
                return None
                
            for i, test in enumerate(self.tests[user_id_str]):
                if test["name"] == test_name:
                    # Convert serialized questions to the format expected by the bot
                    questions = []
                    for q in test["questions"]:
                        questions.append((q["question"], q["options"]))
                    
                    return {
                        "name": test["name"],
                        "questions": questions,
                        "created_at": test["created_at"],
                        "updated_at": test.get("updated_at", test["created_at"]),
                        "index": i
                    }
            return None
            
    def cleanup(self):
        """Save any pending changes and clean up resources"""
        with self.lock:
            if self.dirty:
                self._save_tests()
                self.dirty = False
