"""
LaTeX to PDF Conversion Service
Converts JSON data containing lesson content into professionally formatted PDFs
"""
import os
import subprocess
import tempfile
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, request, send_file, jsonify
from werkzeug.exceptions import BadRequest

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
API_SECRET = os.getenv("API_SECRET", "default_secret")
MAX_EXERCISES = int(os.getenv("MAX_EXERCISES", "50"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "1048576"))  # 1MB default

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Debug: Log API_SECRET at startup (masked for security)
logger.info(f"API_SECRET loaded: {'*' * (len(API_SECRET) - 4) + API_SECRET[-4:] if len(API_SECRET) > 4 else '****'}")
logger.info(f"API_SECRET length: {len(API_SECRET)}")


def escape_latex(text: str) -> str:
    """
    Escape special LaTeX characters to prevent compilation errors.
    
    Args:
        text: Raw text that may contain LaTeX special characters
        
    Returns:
        Text with special characters properly escaped
    """
    if not text:
        return ""
    
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '\\': r'\textbackslash{}',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text


def validate_exercise(exercise: Dict[str, Any], index: int) -> None:
    """
    Validate a single exercise entry.
    
    Args:
        exercise: Exercise dictionary to validate
        index: Exercise index for error messages
        
    Raises:
        ValueError: If validation fails
    """
    if not isinstance(exercise, dict):
        raise ValueError(f"Exercise {index} must be a dictionary")
    
    if 'question' not in exercise:
        raise ValueError(f"Exercise {index} missing 'question' field")
    
    if not isinstance(exercise['question'], str):
        raise ValueError(f"Exercise {index} 'question' must be a string")
    
    if len(exercise['question'].strip()) == 0:
        raise ValueError(f"Exercise {index} 'question' cannot be empty")


def validate_input_data(data: Dict[str, Any]) -> None:
    """
    Validate the input JSON structure.
    
    Args:
        data: Input JSON data to validate
        
    Raises:
        ValueError: If validation fails
    """
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object")
    
    if 'exercises' not in data:
        raise ValueError("Missing required field: 'exercises'")
    
    exercises = data['exercises']
    if not isinstance(exercises, list):
        raise ValueError("'exercises' must be an array")
    
    if len(exercises) == 0:
        raise ValueError("'exercises' array cannot be empty")
    
    if len(exercises) > MAX_EXERCISES:
        raise ValueError(f"Too many exercises. Maximum allowed: {MAX_EXERCISES}")
    
    for i, exercise in enumerate(exercises, 1):
        validate_exercise(exercise, i)


def generate_latex_source(data: Dict[str, Any]) -> str:
    """
    Convert JSON data into a complete LaTeX document.
    
    Args:
        data: Validated input data containing topic, theory, and exercises
        
    Returns:
        Complete LaTeX document as a string
    """
    # Extract and sanitize topic title
    topic_title = data.get("topic_title", "Daily Lesson")
    topic_title = escape_latex(topic_title)
    
    # Start document
    latex = r"""\documentclass[12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath, amssymb}
\usepackage{geometry}
\geometry{letterpaper, margin=1.0in}
\usepackage{parskip}
\setlength{\parskip}{1em}
\usepackage{fancyhdr}
\usepackage{lastpage}

\pagestyle{fancy}
\fancyhead[L]{%s}
\fancyhead[R]{\today}
\fancyfoot[C]{Page \thepage\ of \pageref{LastPage}}

\begin{document}

""" % topic_title
    
    # Add theory section if present
    theory_content = data.get("theory_content", "").strip()
    if theory_content:
        latex += r"\section*{Theory}" + "\n"
        latex += escape_latex(theory_content) + "\n"
        latex += r"\newpage" + "\n\n"
    
    # Add exercises section
    latex += r"\section*{Exercises}" + "\n\n"
    
    exercises = data.get("exercises", [])
    for i, ex in enumerate(exercises, 1):
        question = escape_latex(ex.get("question", ""))
        difficulty = escape_latex(ex.get("difficulty", "General"))
        hints = ex.get("hints", [])
        
        latex += r"\subsection*{Question %d (%s)}" % (i, difficulty) + "\n"
        latex += question + "\n\n"
        
        # Add hints if present
        if hints and isinstance(hints, list):
            latex += r"\textbf{Hints:}" + "\n"
            latex += r"\begin{itemize}" + "\n"
            for hint in hints:
                if isinstance(hint, str) and hint.strip():
                    latex += r"\item " + escape_latex(hint) + "\n"
            latex += r"\end{itemize}" + "\n\n"
        
        latex += r"\vfill" + "\n"
        latex += r"\textit{(Space for solution...)}" + "\n"
        
        # Add page break except after last exercise
        if i < len(exercises):
            latex += r"\newpage" + "\n\n"
    
    latex += r"\end{document}" + "\n"
    
    return latex


def compile_latex_to_pdf(latex_source: str) -> bytes:
    """
    Compile LaTeX source to PDF using Tectonic or pdflatex.
    
    Args:
        latex_source: Complete LaTeX document source
        
    Returns:
        PDF file contents as bytes
        
    Raises:
        RuntimeError: If compilation fails
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        tex_path = Path(temp_dir) / "output.tex"
        pdf_path = Path(temp_dir) / "output.pdf"
        
        # Write LaTeX source
        tex_path.write_text(latex_source, encoding='utf-8')
        logger.info(f"Wrote LaTeX source to {tex_path}")
        
        # Try Tectonic first, fall back to pdflatex
        compilers = [
            {
                "name": "tectonic",
                "cmd": ["tectonic", "-o", temp_dir, str(tex_path)],
                "runs": 1
            },
            {
                "name": "pdflatex",
                "cmd": ["pdflatex", "-interaction=nonstopmode", "-output-directory", temp_dir, str(tex_path)],
                "runs": 2  # Run twice for references
            }
        ]
        
        last_error = None
        
        for compiler in compilers:
            # Check if compiler exists
            try:
                subprocess.run(
                    [compiler["name"], "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.debug(f"{compiler['name']} not available, trying next compiler")
                continue
            
            try:
                # Run compilation (possibly multiple times)
                for run in range(compiler["runs"]):
                    logger.info(f"Running {compiler['name']} (run {run + 1}/{compiler['runs']})")
                    result = subprocess.run(
                        compiler["cmd"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=30,
                        cwd=temp_dir
                    )
                
                logger.info(f"{compiler['name']} compilation successful")
                
                # Check if PDF was created
                if not pdf_path.exists():
                    raise RuntimeError("PDF file was not created")
                
                # Read and return PDF
                return pdf_path.read_bytes()
                
            except subprocess.TimeoutExpired:
                last_error = f"{compiler['name']} compilation timed out"
                logger.error(last_error)
                continue
                
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode('utf-8', errors='replace')
                last_error = f"{compiler['name']} compilation failed: {error_msg}"
                logger.error(last_error)
                continue
        
        # If we get here, all compilers failed
        raise RuntimeError(f"LaTeX compilation failed. Last error: {last_error}")


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for container orchestration."""
    # Check which LaTeX compiler is available
    compilers = []
    
    for compiler_name in ["tectonic", "pdflatex"]:
        try:
            subprocess.run(
                [compiler_name, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            compilers.append(compiler_name)
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            pass
    
    if not compilers:
        return jsonify({
            "status": "unhealthy",
            "error": "No LaTeX compiler available"
        }), 503
    
    return jsonify({
        "status": "healthy",
        "service": "latex-to-pdf",
        "compilers": compilers
    }), 200


@app.route('/convert', methods=['POST'])
def convert_to_pdf():
    """
    Convert JSON lesson data to PDF.
    
    Expected JSON format:
    {
        "topic_title": "Algebra Basics",
        "theory_content": "Theory text here...",
        "exercises": [
            {
                "question": "Solve for x: 2x + 3 = 7",
                "difficulty": "Easy",
                "hints": ["Subtract 3 from both sides", "Then divide by 2"]
            }
        ]
    }
    
    Returns:
        PDF file or error response
    """
    # Verify authentication
    auth_header = request.headers.get('Authorization')
    expected_auth = f"Bearer {API_SECRET}"
    
    # Debug logging
    logger.debug(f"Received Authorization header: {auth_header[:20]}..." if auth_header and len(auth_header) > 20 else f"Received Authorization header: {auth_header}")
    logger.debug(f"Expected Authorization header: {expected_auth[:20]}..." if len(expected_auth) > 20 else f"Expected Authorization header: {expected_auth}")
    logger.debug(f"Header length: {len(auth_header) if auth_header else 0}, Expected length: {len(expected_auth)}")
    logger.debug(f"Headers match: {auth_header == expected_auth}")
    
    if auth_header != expected_auth:
        logger.warning(f"Unauthorized access attempt - Header mismatch")
        logger.warning(f"Received: '{auth_header}'")
        logger.warning(f"Expected: '{expected_auth}'")
        return jsonify({"error": "Unauthorized"}), 401
    
    # Parse and validate input
    try:
        if not request.is_json:
            raise BadRequest("Content-Type must be application/json")
        
        data = request.get_json()
        validate_input_data(data)
        
    except BadRequest as e:
        logger.warning(f"Bad request: {e}")
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error parsing request: {e}")
        return jsonify({"error": "Invalid request format"}), 400
    
    # Generate and compile
    try:
        latex_source = generate_latex_source(data)
        logger.info(f"Generated LaTeX document ({len(latex_source)} bytes)")
        
        pdf_bytes = compile_latex_to_pdf(latex_source)
        logger.info(f"Compiled PDF ({len(pdf_bytes)} bytes)")
        
        # Create temporary file for response
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        try:
            return send_file(
                tmp_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name='lesson.pdf'
            )
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")
        
    except RuntimeError as e:
        logger.error(f"Compilation error: {e}")
        return jsonify({"error": "PDF compilation failed", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle request size limit exceeded."""
    return jsonify({"error": "Request too large"}), 413


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "False").lower() == "true"
    
    logger.info(f"Starting server on port {port}")
    logger.info(f"Max exercises: {MAX_EXERCISES}")
    logger.info(f"Max content length: {MAX_CONTENT_LENGTH} bytes")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
