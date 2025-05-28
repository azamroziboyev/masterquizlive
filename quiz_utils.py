from docx import Document
import random
import os
import logging
import re
import functools
import threading
from concurrent.futures import ThreadPoolExecutor

# For AI-based parsing
import nltk
from nltk.tokenize import sent_tokenize

logger = logging.getLogger(__name__)

# Thread-local storage for NLTK resources to avoid repeated downloads
_thread_local = threading.local()

# Cache for expensive operations
_cache_lock = threading.RLock()
_parse_cache = {}

def memoize(func):
    """Simple memoization decorator for functions with hashable arguments"""
    cache = {}
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = str(args) + str(sorted(kwargs.items()))
        with _cache_lock:
            if key not in cache:
                cache[key] = func(*args, **kwargs)
            return cache[key]
    return wrapper

@memoize
def convert_format(doc, file_type="docx"):
    """
    Convert document format to quiz format
    Supports both Word (.docx) and text (.txt) files
    Returns a tuple: (questions, has_errors)
    where questions is a list of tuples: (question, [answers])
    and has_errors is a boolean indicating if formatting errors were detected and fixed
    
    file_type: "docx" for Word documents, "txt" for text files
    """
    questions = []
    current_question = None
    options = []
    
    # Flag to track if any formatting errors were detected and fixed
    has_errors = False
    
    try:
        # Extract text content based on file type
        paragraph_texts = []
        
        if file_type == "docx":
            # Parse Word document
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:  # Only add non-empty paragraphs
                    paragraph_texts.append(text)
        else:  # txt format
            # Parse text file content
            if isinstance(doc, str):
                paragraph_texts = [line.strip() for line in doc.strip().split('\n') if line.strip()]
            else:
                paragraph_texts = [line.strip() for line in doc if line.strip()]
        
        # First check for question format markers
        has_question_mark_format = any(text.startswith("?") for text in paragraph_texts)
        has_plus_minus_format = any(text.startswith("+") or text.startswith("-") for text in paragraph_texts)
        has_hash_format = any(text.startswith("#") for text in paragraph_texts)
        has_separator_format = any(text == "++++" or text.startswith("+++++") or 
                                 text == "====" or text.startswith("=====") for text in paragraph_texts)
        
        # Determine the most likely format based on markers
        if has_question_mark_format and has_plus_minus_format:
            # Process using the new format (?Question, +Correct, -Wrong)
            for text in paragraph_texts:
                # Check for the new format: ?savol
                if text.startswith("?"):
                    # Save the previous question if exists
                    if current_question and options:
                        questions.append((current_question, options))
                        options = []
                    
                    current_question = text[1:].strip()  # Remove the '?' prefix
                    
                # Answer format: +to'g'ri javob (correct) or -noto'g'ri javob (wrong)
                elif text.startswith("+"):
                    correct_answer = text[1:].strip()
                    options.insert(0, correct_answer)  # Put correct answer first
                    
                elif text.startswith("-"):
                    wrong_answer = text[1:].strip()
                    options.append(wrong_answer)
        
        elif has_separator_format or has_hash_format:
            # Process using the old format with ==== and +++++
            i = 0
            while i < len(paragraph_texts):
                text = paragraph_texts[i]
                
                # Question separator
                if text == "++++" or text.startswith("+++++"):
                    if current_question and options:
                        questions.append((current_question, options))
                        current_question = None
                        options = []
                        
                # Options separator (skip)
                elif text == "====" or text.startswith("====="):
                    pass
                    
                # New question (if we don't have one yet and it doesn't start with #)
                elif not current_question and not text.startswith('#'):
                    current_question = text
                    
                # Correct answer
                elif text.startswith('#'):
                    correct_answer = text[1:].strip()
                    options.insert(0, correct_answer)  # Put correct answer first
                    
                # Wrong answer
                elif text and current_question:
                    options.append(text.strip())
                    
                i += 1
        
        else:
            # No clear format markers, try to parse as simple question/answer format
            i = 0
            while i < len(paragraph_texts):
                text = paragraph_texts[i]
                
                # If text ends with a question mark, treat it as a question
                if text.endswith('?') or (not current_question and not any(opt in text.lower() for opt in ['a)', 'b)', 'c)', '1)', '2)'])):
                    # Save previous question if exists
                    if current_question and options:
                        questions.append((current_question, options))
                        options = []
                    
                    current_question = text
                    
                # Otherwise, treat it as an option
                elif current_question:
                    # If this looks like an option (A), B), etc.)
                    if re.match(r'^[A-Za-z0-9][).\s]|^\([A-Za-z0-9]\)', text):
                        # If this is the first option, assume it's correct
                        if not options:
                            options.insert(0, text)  # Put first option as correct answer
                        else:
                            options.append(text)
                    else:
                        # If not a clear option format but we have a question, treat as an option
                        options.append(text)
                
                i += 1
                
        # Add the last question if we haven't done so already
        if current_question and options:
            questions.append((current_question, options))
        
        # Check for and fix formatting errors in questions
        fixed_questions = []
        for question, opts in questions:
            # Check if there are too many options (more than 4 is likely a formatting error)
            if len(opts) > 4:
                has_errors = True
                # Keep only the first 4 options (first one is correct, plus 3 wrong options)
                fixed_opts = opts[:4]
                fixed_questions.append((question, fixed_opts))
                logger.warning(f"Fixed question with too many options: {question[:30]}...")
            # Check if there are duplicate options
            elif len(set(opts)) < len(opts):
                has_errors = True
                # Remove duplicates while preserving order
                seen = set()
                fixed_opts = []
                for opt in opts:
                    if opt not in seen:
                        seen.add(opt)
                        fixed_opts.append(opt)
                fixed_questions.append((question, fixed_opts))
                logger.warning(f"Fixed question with duplicate options: {question[:30]}...")
            # Check for very long options that might indicate formatting issues
            elif any(len(opt) > 150 for opt in opts):
                has_errors = True
                # Truncate long options
                fixed_opts = [opt[:150] + '...' if len(opt) > 150 else opt for opt in opts]
                fixed_questions.append((question, fixed_opts))
                logger.warning(f"Fixed question with very long options: {question[:30]}...")
            else:
                # No issues with this question
                fixed_questions.append((question, opts))
        
        # Replace original questions with fixed ones
        questions = fixed_questions
        
        # If we couldn't parse any questions or if some questions have too few options,
        # try AI-based extraction as a fallback
        if not questions or any(len(q[1]) < 2 for q in questions):
            ai_questions, ai_has_errors = ai_extract_questions(doc, file_type)
            if ai_questions:
                # If AI extraction found questions, use those instead
                # Combine error flags
                return ai_questions, (has_errors or ai_has_errors)
            
    except Exception as e:
        logger.error(f"Error parsing document: {e}")
        has_errors = True
        
    return questions, has_errors

def parse_text_file(file_content):
    """
    Parse text file content to extract questions and answers
    Supports the ?savol +to'g'ri -noto'g'ri format
    Returns a tuple: (questions, has_errors)
    """
    return convert_format(file_content, file_type="txt")

@memoize
def ai_extract_questions(content, file_type="txt"):
    """
    Use AI techniques to extract questions and answers from unformatted text
    Returns a tuple: (questions, has_errors) where:
    - questions is a list of tuples: (question, [answers]) where the first answer is the correct one
    - has_errors is a boolean indicating if formatting errors were detected and fixed
    
    This uses rule-based NLP techniques to identify questions and potential answers
    without requiring specific formatting markers.
    """
    questions = []
    has_errors = False
    
    try:
        # Download NLTK resources if not already present (thread-safe)
        if not hasattr(_thread_local, 'nltk_downloaded'):
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                nltk.download('punkt', quiet=True)
            _thread_local.nltk_downloaded = True
        
        # Extract text based on file type
        if file_type == "docx":
            # For docx, content is a Document object
            text = "\n".join([para.text for para in content.paragraphs if para.text.strip()])
        else:
            # For txt, content is already a string
            text = content if isinstance(content, str) else "\n".join(content)
        
        # Check if we've already processed this exact text
        cache_key = hash(text)
        with _cache_lock:
            if cache_key in _parse_cache:
                return _parse_cache[cache_key]
        
        # Split text into paragraphs
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        
        # Process paragraphs to identify questions and answers
        i = 0
        while i < len(paragraphs):
            current_para = paragraphs[i]
            
            # Identify potential questions (ends with ? or numbered items like "1." or "Question 1:")
            is_question = False
            if current_para.endswith('?'):
                is_question = True
            elif re.match(r'^\d+\.\s', current_para) and len(current_para) > 3:  # Numbered item (e.g., "1. What is...")
                is_question = True
            elif re.search(r'question\s+\d+[:.\s]', current_para.lower()):
                is_question = True
            elif re.match(r'^[A-Za-z]\)\s', current_para) and len(current_para) > 3:  # Lettered item (e.g., "A) What is...")
                is_question = True
            elif re.search(r'question|savol|вопрос', current_para.lower()):
                is_question = True
            
            if is_question:
                question_text = current_para
                options = []
                correct_answer = None
                
                # Look ahead for potential answers (usually in the next 2-6 lines)
                j = i + 1
                
                # Look for options in subsequent paragraphs
                while j < len(paragraphs) and len(options) < 6:  # Limit to 6 options max
                    option_para = paragraphs[j]
                    
                    # Skip empty lines
                    if not option_para.strip():
                        j += 1
                        continue
                    
                    # Check if this paragraph is an option (A), a), 1), etc.)
                    option_match = re.match(r'^[A-Za-z0-9][).\s]|^\([A-Za-z0-9]\)', option_para)
                    
                    # Check for options with + or - prefixes (common in some formats)
                    plus_minus_match = re.match(r'^[+\-]\s', option_para)
                    
                    if option_match or plus_minus_match:
                        # This is an option
                        if plus_minus_match:
                            # Handle +/- format
                            is_correct = option_para.startswith('+')
                            option_text = option_para[1:].strip()
                            
                            if is_correct:
                                # This is marked as correct with +
                                correct_answer = option_text
                                options.insert(0, option_text)  # Put correct answer first
                            else:
                                # This is marked as incorrect with -
                                options.append(option_text)
                        else:
                            # Standard option format (A, B, C, etc.)
                            option_text = option_para.lstrip('ABCDEFGabcdefg0123456789(). 	')
                            
                            # If this is the first option, assume it's correct
                            if correct_answer is None:
                                correct_answer = option_text
                                options.insert(0, option_text)  # Put correct answer first
                            else:
                                options.append(option_text)  # Add as wrong answer
                        
                        j += 1
                    else:
                        # If we've already found at least one option and this isn't an option,
                        # we're done with this question
                        if options:
                            break
                        # If we haven't found any options yet, check if this could be a correct answer
                        # (no option marker, but could be the answer)
                        elif len(option_para) < 100:  # Reasonable length for an answer
                            correct_answer = option_para
                            options.append(correct_answer)
                            j += 1
                        else:
                            # Not an option and too long to be an answer
                            break
                    if options:
                        # Check for formatting issues
                        if len(options) > 4:
                            has_errors = True
                            # Keep only the first 4 options
                            options = options[:4]
                            logger.warning(f"AI extraction fixed question with too many options: {question_text[:30]}...")
                        
                        # Check for duplicate options
                        if len(set(options)) < len(options):
                            has_errors = True
                            # Remove duplicates while preserving order
                            seen = set()
                            fixed_opts = []
                            for opt in options:
                                if opt not in seen:
                                    seen.add(opt)
                                    fixed_opts.append(opt)
                            options = fixed_opts
                            logger.warning(f"AI extraction fixed question with duplicate options: {question_text[:30]}...")
                        
                        questions.append((question_text, options))
        
        # If we still couldn't identify any questions, fall back to the original parser
        if not questions:
            logger.warning("AI extraction couldn't identify questions, falling back to standard parser")
            return convert_format(content, file_type=file_type)
            
    except Exception as e:
        logger.error(f"Error in AI question extraction: {e}")
        # Fall back to the original parser
        return convert_format(content, file_type=file_type)
    
    return questions, has_errors

def calculate_points(correct, total, system=100):
    """
    Calculate points based on scoring system
    system: 100 for 100-point system, 50 for 50-point system
    """
    if total == 0:
        return 0
    
    points = (correct / total) * system
    return round(points, 1)

def get_result_message(correct, total, lang="uz"):
    """
    Generate detailed test result message with improved formatting
    """
    if total == 0:
        return "Test natijasi yo'q" if lang == "uz" else "Нет результатов теста"
    
    wrong = total - correct
    percentage = (correct / total) * 100
    points_100 = calculate_points(correct, total, 100)
    points_50 = calculate_points(correct, total, 50)
    
    # Add emoji based on performance
    performance_emoji = "🎯"
    if percentage >= 90:
        performance_emoji = "🏆"
    elif percentage >= 70:
        performance_emoji = "🌟"
    elif percentage >= 50:
        performance_emoji = "👍"
    else:
        performance_emoji = "📚"
    
    # Create a progress bar
    bar_length = 10
    filled_length = int(round(bar_length * correct / total))
    progress_bar = "▓" * filled_length + "░" * (bar_length - filled_length)
    
    # Simplified results as requested
    if lang == "uz":
        result_message = f"""<b>{performance_emoji} TEST NATIJASI {performance_emoji}</b>

📊 <b>Foiz:</b> <code>{percentage:.1f}%</code>
{progress_bar}
💯 <b>Ball:</b> <code>{points_100}/100</code>
"""
    else:  # Russian
        result_message = f"""<b>{performance_emoji} РЕЗУЛЬТАТЫ ТЕСТА {performance_emoji}</b>

📊 <b>Процент:</b> <code>{percentage:.1f}%</code>
{progress_bar}
💯 <b>Баллы:</b> <code>{points_100}/100</code>
"""
    
    # Add a motivational message based on score
    if lang == "uz":
        if percentage >= 90:
            result_message += "\n🏆 <b>Ajoyib natija!</b> Tabriklaymiz!"
        elif percentage >= 70:
            result_message += "\n👏 <b>Yaxshi natija!</b> Davom eting!"
        elif percentage >= 50:
            result_message += "\n👍 <b>O'rtacha natija.</b> Ko'proq mashq qiling!"
        else:
            result_message += "\n📚 <b>Ko'proq o'qish va mashq qilish kerak!</b>"
    else:  # Russian
        if percentage >= 90:
            result_message += "\n🏆 <b>Отличный результат!</b> Поздравляем!"
        elif percentage >= 70:
            result_message += "\n👏 <b>Хороший результат!</b> Продолжайте!"
        elif percentage >= 50:
            result_message += "\n👍 <b>Средний результат.</b> Нужно больше практики!"
        else:
            result_message += "\n📚 <b>Нужно больше читать и практиковаться!</b>"
    
    return result_message
