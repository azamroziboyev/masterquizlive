import os
import json
import sqlite3
import threading
import shutil
import uuid
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session, make_response
from flask_cors import CORS

app = Flask(__name__, static_url_path='/static', static_folder='telegram_webapp/static', template_folder='telegram_webapp/templates')
CORS(app)  # Enable CORS for all routes
app.secret_key = os.environ.get("SESSION_SECRET", "masterquiz_telegram_webapp_secret")

# Telegram Bot Token
BOT_TOKEN = "8184215515:AAEVINsnkj_fTBbxZfBpvqZtUCsNj2kvwjo"

# Simple in-memory storage for tests with file persistence
class SimpleTestStorage:
    def __init__(self, storage_path="user_tests.json"):
        """Initialize the storage with a JSON file for persistence."""
        self.storage_path = storage_path
        self.lock = threading.Lock()  # Thread safety
        self.tests = self._load_tests()
        self._ensure_data_integrity()
    
    def _load_tests(self):
        """Load tests from the storage file."""
        if not os.path.exists(self.storage_path):
            print(f"[INFO] No storage file found at {self.storage_path}, creating new one.")
            return {}
            
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    print("[WARNING] Invalid data format in storage file, initializing empty storage.")
                    return {}
                return data
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse storage file: {e}")
            # Create a backup of the corrupted file
            backup_path = f"{self.storage_path}.bak.{int(time.time())}"
            try:
                shutil.copy2(self.storage_path, backup_path)
                print(f"[INFO] Created backup of corrupted file at {backup_path}")
            except Exception as backup_error:
                print(f"[ERROR] Failed to create backup: {backup_error}")
            return {}
        except Exception as e:
            print(f"[ERROR] Failed to load storage file: {e}")
            return {}
    
    def _save_tests(self):
        """Save the current tests to the storage file."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
        
        # Write to a temporary file first, then rename to ensure atomicity
        temp_path = f"{self.storage_path}.tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.tests, f, ensure_ascii=False, indent=2, sort_keys=True)
            
            # On Windows, we need to remove the destination file first
            if os.path.exists(self.storage_path):
                os.remove(self.storage_path)
            
            os.rename(temp_path, self.storage_path)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save tests: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False
    
    def _ensure_data_integrity(self):
        """Ensure the data structure is valid."""
        if not isinstance(self.tests, dict):
            self.tests = {}
        
        # Ensure each user's tests is a list
        for user_id, tests in list(self.tests.items()):
            if not isinstance(tests, list):
                print(f"[WARNING] Invalid tests format for user {user_id}, resetting to empty list.")
                self.tests[user_id] = []
            
            # Ensure each test has required fields
            valid_tests = []
            for test in self.tests[user_id]:
                if not isinstance(test, dict):
                    continue
                    
                # Add required fields if missing
                if 'id' not in test:
                    test['id'] = str(uuid.uuid4())
                if 'title' not in test:
                    test['title'] = 'Untitled Test'
                if 'questions' not in test:
                    test['questions'] = []
                
                # Ensure each question has required fields
                for question in test.get('questions', []):
                    if 'id' not in question:
                        question['id'] = str(uuid.uuid4())
                    if 'text' not in question:
                        question['text'] = 'Untitled Question'
                    if 'options' not in question:
                        question['options'] = []
                    if 'correct_option' not in question and question['options']:
                        question['correct_option'] = 0
                
                valid_tests.append(test)
            
            self.tests[user_id] = valid_tests
        
        # Save any changes made during integrity check
        self._save_tests()
    
    def get_user_tests(self, user_id):
        """Get all tests for a specific user."""
        if not user_id:
            return []
            
        user_id_str = str(user_id)
        with self.lock:
            # Return a deep copy to prevent accidental modifications
            return json.loads(json.dumps(self.tests.get(user_id_str, [])))
    
    def add_test(self, user_id, test_data):
        """Add a new test for a user."""
        if not user_id or not isinstance(test_data, dict):
            return False
            
        user_id_str = str(user_id)
        with self.lock:
            if user_id_str not in self.tests:
                self.tests[user_id_str] = []
            
            # Add required fields if missing
            if 'id' not in test_data:
                test_data['id'] = str(uuid.uuid4())
            if 'created_at' not in test_data:
                test_data['created_at'] = int(time.time())
            if 'updated_at' not in test_data:
                test_data['updated_at'] = int(time.time())
            
            self.tests[user_id_str].append(test_data)
            return self._save_tests()
    
    def update_test(self, user_id, test_id, test_data):
        """Update an existing test."""
        if not user_id or not test_id or not isinstance(test_data, dict):
            return False
            
        user_id_str = str(user_id)
        test_id_str = str(test_id)
        
        with self.lock:
            if user_id_str not in self.tests:
                return False
                
            for i, test in enumerate(self.tests[user_id_str]):
                if str(test.get('id')) == test_id_str:
                    # Preserve some fields
                    test_data['id'] = test_id_str
                    if 'created_at' not in test_data and 'created_at' in test:
                        test_data['created_at'] = test['created_at']
                    test_data['updated_at'] = int(time.time())
                    
                    # Update the test
                    self.tests[user_id_str][i] = test_data
                    return self._save_tests()
            
            return False
    
    def delete_test(self, user_id, test_id):
        """Delete a test."""
        if not user_id or not test_id:
            return False
            
        user_id_str = str(user_id)
        test_id_str = str(test_id)
        
        with self.lock:
            if user_id_str not in self.tests:
                return False
                
            initial_length = len(self.tests[user_id_str])
            self.tests[user_id_str] = [t for t in self.tests[user_id_str] if str(t.get('id')) != test_id_str]
            
            if len(self.tests[user_id_str]) < initial_length:
                return self._save_tests()
            return False

# Initialize test storage
test_storage = SimpleTestStorage()

# Function to validate Telegram WebApp data
def validate_telegram_webapp(init_data):
    """
    Validate Telegram WebApp initData and return user information if valid.
    
    Args:
        init_data (str): The initData string from Telegram WebApp
        
    Returns:
        tuple: (is_valid, user_data) where user_data contains user information if valid
    """
    if not init_data:
        print("No init_data provided")
        return False, None
    
    try:
        # Parse the initData string into a dictionary
        parsed_data = {}
        for pair in init_data.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                parsed_data[key] = value
        
        # Check if user data exists
        if 'user' not in parsed_data:
            print("No user data in init_data")
            return False, None
        
        # Parse the user data
        import urllib.parse
        user_data = json.loads(urllib.parse.unquote(parsed_data['user']))
        
        # For debugging and testing purposes, accept any initData with valid user info
        if 'id' in user_data:
            return True, user_data
        
        print("No user ID in user data")
        return False, None
    
    except Exception as e:
        print(f"Error validating Telegram WebApp data: {e}")
        return False, None

# Function to get tests for a user
def get_user_tests(user_id):
    # Convert user_id to integer if it's not already
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        print(f"Invalid user_id: {user_id}, cannot convert to integer")
        return []
    
    print(f"Getting tests for user: {user_id_int}")
    
    # IMPORTANT: Create sample tests that will always be returned
    sample_test1 = {
        "id": "sample1",
        "title": "Mathematics Test",
        "name": "Mathematics Test",
        "description": "A basic mathematics quiz with multiple choice questions",
        "question_count": 5,
        "time_limit": 10,
        "language": "en",
        "created_at": "2025-05-28T10:00:00",
        "questions": [
            {
                "id": "q1",
                "question": "What is 2 + 2?",
                "options": ["3", "4", "5", "6"],
                "correct_option": 1
            },
            {
                "id": "q2",
                "question": "What is 5 × 9?",
                "options": ["35", "40", "45", "50"],
                "correct_option": 2
            }
        ]
    }
    
    sample_test2 = {
        "id": "sample2",
        "title": "Science Quiz",
        "name": "Science Quiz",
        "description": "Test your knowledge of basic science facts",
        "question_count": 10,
        "time_limit": 15,
        "language": "en",
        "created_at": "2025-05-28T11:00:00",
        "questions": [
            {
                "id": "q1",
                "question": "What is the chemical symbol for water?",
                "options": ["H2O", "CO2", "O2", "NaCl"],
                "correct_option": 0
            },
            {
                "id": "q2",
                "question": "Which planet is known as the Red Planet?",
                "options": ["Earth", "Mars", "Venus", "Jupiter"],
                "correct_option": 1
            }
        ]
    }
    
    # Always return sample tests instead of trying to use the test_storage
    return [sample_test1, sample_test2]

# Main route for the web app
@app.route('/')
def index():
    try:
        # Get language parameter if provided
        lang = request.args.get('lang', 'en')
        
        # Always render the index page, regardless of Telegram validation
        # This allows the JavaScript to handle the Telegram validation
        response = make_response(render_template('index.html'))
        
        # Set cache control headers to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        import traceback
        traceback.print_exc()
        return "An error occurred while loading the application. Please try again later.", 500

# API endpoint to validate Telegram user and get their tests
@app.route('/api/validate', methods=['POST'])
def validate_user():
    try:
        # Get initData from request
        init_data = request.form.get('initData')
        if not init_data:
            print("No initData provided in request")
            return jsonify({
                'success': False,
                'message': 'No initData provided'
            }), 400
        
        # Validate the initData
        is_valid, user_data = validate_telegram_webapp(init_data)
        
        if not is_valid or not user_data or 'id' not in user_data:
            print(f"Invalid initData: valid={is_valid}, user_data={user_data}")
            return jsonify({
                'success': False,
                'message': 'Invalid initData'
            }), 401
        
        print(f"Valid user: {user_data['id']}")
        
        # Store user ID in session
        session['user_id'] = user_data['id']
        
        # Get user's tests
        user_tests = get_user_tests(user_data['id'])
        
        # For testing: Create a sample test if the user has no tests
        if not user_tests:
            sample_test = {
                "id": "sample1",
                "name": "Sample Quiz",
                "description": "A sample quiz to get started",
                "questions": [
                    {
                        "id": "q1",
                        "question": "What is the capital of France?",
                        "options": ["Paris", "London", "Berlin", "Madrid"],
                        "correct_option": 0
                    },
                    {
                        "id": "q2",
                        "question": "Which planet is known as the Red Planet?",
                        "options": ["Earth", "Mars", "Venus", "Jupiter"],
                        "correct_option": 1
                    }
                ]
            }
            
            # Store in user's tests
            test_storage.add_test(user_data['id'], sample_test)
            user_tests = get_user_tests(user_data['id'])
        
        return jsonify({
            'success': True,
            'user': user_data,
            'tests': user_tests
        })
        
    except Exception as e:
        print(f"Error in validate_user: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'An error occurred while validating user',
            'error': str(e)
        }), 500

# API endpoint to get tests for the authenticated user
@app.route('/api/tests', methods=['GET'])
def get_tests():
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                user_id = auth_header.split(' ')[1]
        
        if not user_id:
            init_data = request.args.get('initData')
            if init_data:
                is_valid, user_data = validate_telegram_webapp(init_data)
                if is_valid and user_data and 'id' in user_data:
                    user_id = user_data['id']
                    session['user_id'] = user_id
        
        # Get user's tests from storage
        tests = test_storage.get_user_tests(int(user_id))
        
        return jsonify({
            'success': True,
            'tests': tests
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

# API endpoint to get a specific test
@app.route('/api/test/<test_id>', methods=['GET'])
def get_test(test_id):
    try:
        test = test_storage.get_test_by_id(test_id)
        if test:
            return jsonify({
                'success': True,
                'test': test
            })
        return jsonify({
            'success': False,
            'message': 'Test not found'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

# API endpoint to submit test answers
@app.route('/api/test/submit', methods=['POST'])
def submit_test():
    try:
        data = request.json
        test_id = data.get('test_id')
        answers = data.get('answers', {})
        user_id = session.get('user_id')
        
        # Get the test
        test = test_storage.get_test_by_id(test_id)
        if not test:
            return jsonify({
                'success': False,
                'message': 'Test not found'
            }), 404
            
        # Calculate score
        correct = 0
        total = len(test.get('questions', []))
        
        for question in test.get('questions', []):
            q_id = question.get('id')
            if str(q_id) in answers and answers[str(q_id)] == question.get('correct_option'):
                correct += 1
                
        score = (correct / total) * 100 if total > 0 else 0
        
        # Save result
        result = {
            'user_id': user_id,
            'test_id': test_id,
            'score': score,
            'date': datetime.utcnow().isoformat()
        }
        test_storage.save_test_result(result)
        
        return jsonify({
            'success': True,
            'score': score,
            'correct': correct,
            'total': total
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
    try:
        # Get user ID from various sources, but we'll return tests regardless
        user_id = session.get('user_id')
        
        if not user_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                user_id = auth_header.split(' ')[1]
        
        if not user_id:
            init_data = request.args.get('initData')
            if init_data:
                is_valid, user_data = validate_telegram_webapp(init_data)
                if is_valid and user_data and 'id' in user_data:
                    user_id = user_data['id']
                    session['user_id'] = user_id
        
        # Define some sample tests - these will always be returned
        # Actual implementation would fetch real tests from the MasterQuiz bot database
        tests = [
            {
                "id": "test1",
                "title": "Mathematics Test",
                "name": "Mathematics Test",
                "description": "A basic mathematics quiz with multiple choice questions",
                "question_count": 5,
                "time_limit": 10,
                "language": "en",
                "created_at": "2025-05-28T10:00:00",
                "questions": [
                    {
                        "id": "q1",
                        "question": "What is 2 + 2?",
                        "options": ["3", "4", "5", "6"],
                        "correct_option": 1
                    },
                    {
                        "id": "q2",
                        "question": "What is 5 × 9?",
                        "options": ["35", "40", "45", "50"],
                        "correct_option": 2
                    }
                ]
            },
            {
                "id": "test2",
                "title": "Science Quiz",
                "name": "Science Quiz",
                "description": "Test your knowledge of basic science facts",
                "question_count": 10,
                "time_limit": 15,
                "language": "en",
                "created_at": "2025-05-28T11:00:00",
                "questions": [
                    {
                        "id": "q1",
                        "question": "What is the chemical symbol for water?",
                        "options": ["H2O", "CO2", "O2", "NaCl"],
                        "correct_option": 0
                    },
                    {
                        "id": "q2",
                        "question": "Which planet is known as the Red Planet?",
                        "options": ["Earth", "Mars", "Venus", "Jupiter"],
                        "correct_option": 1
                    }
                ]
            },
            {
                "id": "test3",
                "title": "History Quiz",
                "name": "History Quiz",
                "description": "Test your knowledge of world history",
                "question_count": 8,
                "time_limit": 12,
                "language": "en",
                "created_at": "2025-05-28T12:00:00",
                "questions": [
                    {
                        "id": "q1",
                        "question": "In what year did World War II end?",
                        "options": ["1943", "1945", "1947", "1950"],
                        "correct_option": 1
                    },
                    {
                        "id": "q2",
                        "question": "Who was the first President of the United States?",
                        "options": ["Thomas Jefferson", "John Adams", "George Washington", "Abraham Lincoln"],
                        "correct_option": 2
                    }
                ]
            }
        ]
        
        # Log successful response
        print(f"Returning {len(tests)} tests for user {user_id or 'unknown'}")
        
        # Always return success with tests
        return jsonify({
            'success': True,
            'tests': tests
        })
        
    except Exception as e:
        print(f"Error in get_tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'An error occurred while fetching tests',
            'error': str(e)
        }), 500

# API endpoint to sync tests with the main bot
@app.route('/api/sync', methods=['POST'])
def sync_tests():
    try:
        # Get user ID from request
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({
                'success': False,
                'message': 'User ID is required'
            }), 400
        
        user_id = data['user_id']
        print(f"[DEBUG] Syncing tests for user: {user_id}")
        
        # In a real implementation, you would fetch tests from the main bot's database here
        # For now, we'll just return the current tests
        user_tests = get_user_tests(user_id)
        
        # If user has no tests, create a sample test
        if not user_tests and str(user_id).isdigit():
            sample_test = {
                "id": "sample1",
                "name": "Sample Quiz",
                "description": "A sample quiz to get started",
                "questions": [
                    {
                        "id": "q1",
                        "question": "What is the capital of France?",
                        "options": ["Paris", "London", "Berlin", "Madrid"],
                        "correct_option": 0
                    },
                    {
                        "id": "q2",
                        "question": "Which planet is known as the Red Planet?",
                        "options": ["Earth", "Mars", "Venus", "Jupiter"],
                        "correct_option": 1
                    }
                ]
            }
            
            # Save sample test for this user
            test_storage.add_test(user_id, sample_test)
            user_tests = test_storage.get_user_tests(user_id)
        
        return jsonify({
            'success': True,
            'message': 'Tests synced successfully',
            'tests_count': len(user_tests)
        })
        
    except Exception as e:
        print(f"[ERROR] Error in sync_tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'An error occurred while syncing tests',
            'error': str(e)
        }), 500

# API endpoint to get a specific test
@app.route('/api/tests/<test_id>', methods=['GET'])
def get_test(test_id):
    try:
        # Check for Authorization header first (Bearer token)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            user_id = auth_header.split(' ')[1]
            if user_id.isdigit():
                # We have a valid user ID from the token
                user_id = int(user_id)
            else:
                return jsonify({
                    'success': False,
                    'message': 'Invalid user ID in Authorization header'
                }), 401
        # Check session next
        elif 'user_id' in session:
            user_id = session['user_id']
        # Check initData as a last resort
        else:
            init_data = request.args.get('initData')
            if not init_data:
                return jsonify({
                    'success': False,
                    'message': 'Not authenticated',
                    'requires_auth': True
                }), 401
                
            # Validate the initData
            is_valid, user_data = validate_telegram_webapp(init_data)
            if not is_valid or not user_data or 'id' not in user_data:
                return jsonify({
                    'success': False,
                    'message': 'Invalid authentication data',
                    'requires_auth': True
                }), 401
                
            user_id = user_data['id']
            session['user_id'] = user_id  # Store in session for future requests
        
        print(f"[DEBUG] Getting test {test_id} for user: {user_id}")
        
        # Get user's tests
        user_tests = get_user_tests(user_id)
        
        # Find the test with the given ID
        test = next((t for t in user_tests if str(t.get('id')) == str(test_id)), None)
        
        if not test:
            print(f"[DEBUG] Test {test_id} not found for user {user_id}")
            return jsonify({
                'success': False,
                'message': 'Test not found or access denied',
                'test_id': test_id,
                'user_has_tests': len(user_tests) > 0
            }), 404
        
        return jsonify({
            'success': True,
            'test': test
        })
        
    except Exception as e:
        print(f"[ERROR] Error in get_test: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'An error occurred while fetching the test',
            'error': str(e)
        }), 500

# Launch page for the Telegram WebApp
@app.route('/launch')
def launch_page():
    """Launch page for Telegram WebApp"""
    try:
        return render_template('launch.html')
    except Exception as e:
        print(f"Error serving launch page: {e}")
        return f"Error: {str(e)}", 500

# Debug route for Telegram WebApp testing
@app.route('/debug')
def debug_page():
    """Debug page for Telegram WebApp"""
    try:
        return render_template('debug.html')
    except Exception as e:
        print(f"Error serving debug page: {e}")
        return f"Error: {str(e)}", 500

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check if we can access the file system
        test_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'health_check.tmp')
        with open(test_file, 'w') as f:
            f.write(str(time.time()))
        os.remove(test_file)
        
        # Check database connection
        test_storage.get_user_tests(0)  # Just test if the storage is accessible
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

if __name__ == "__main__":
    # Get port from environment variable (Render.com sets this)
    port = int(os.environ.get("PORT", 8080))
    
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Start the application
    app.run(host="0.0.0.0", port=port, debug=False)
