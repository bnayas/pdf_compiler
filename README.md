# PDF Compiler

A Dockerized Flask service that converts JSON lesson data into professionally formatted PDFs using LaTeX compilation. Uses Tectonic compiler for a small image size (~200-300MB vs 1GB+ with full TeX Live).

## Features

- Converts JSON lesson data to PDF via LaTeX
- Small Docker image using Tectonic compiler
- RESTful API with health check endpoint
- Supports theory content and exercises with hints
- Proper LaTeX escaping for special characters

## Quick Start

### Using Docker Compose (Recommended)

1. Build and start the service:
```bash
docker-compose up --build
```

2. The service will be available at `http://localhost:8080`

### Using Docker

1. Build the image:
```bash
docker build -t pdf-compiler .
```

2. Run the container:
```bash
docker run -d \
  -p 8080:8080 \
  -e API_SECRET=your_secret_here \
  pdf-compiler
```

## API Endpoints

### Health Check

```bash
curl http://localhost:8080/health
```

Returns the service status and available LaTeX compilers.

### Convert JSON to PDF

```bash
curl -X POST http://localhost:8080/convert \
  -H "Authorization: Bearer your_secret_here" \
  -H "Content-Type: application/json" \
  -d @example_lesson.json \
  --output lesson.pdf
```

## JSON Format

The service expects JSON in the following format:

```json
{
  "topic_title": "Introduction to Calculus: Limits",
  "theory_content": "Theory explanation here...",
  "exercises": [
    {
      "question": "Solve for x: 2x + 3 = 7",
      "difficulty": "Easy",
      "hints": [
        "Subtract 3 from both sides",
        "Then divide by 2"
      ]
    }
  ]
}
```

### Required Fields

- `exercises`: Array of exercise objects (at least one required)
  - `question`: The exercise question (required)

### Optional Fields

- `topic_title`: Title of the lesson (default: "Daily Lesson")
- `theory_content`: Theory section content
- `difficulty`: Exercise difficulty level
- `hints`: Array of hint strings

See `example_lesson.json` for a complete example.

## Environment Variables

- `PORT`: Server port (default: `8080`)
- `API_SECRET`: Secret for API authentication (default: `default_secret`)
- `MAX_EXERCISES`: Maximum number of exercises allowed (default: `50`)
- `MAX_CONTENT_LENGTH`: Maximum request size in bytes (default: `1048576` = 1MB)
- `DEBUG`: Enable debug mode (default: `false`)

## Development

### Local Setup

1. Install dependencies:
```bash
pip install -e .
```

2. Run the Flask app:
```bash
python app.py
```

### Testing with Example

```bash
# Set API secret
export API_SECRET=test_secret

# Convert example lesson
curl -X POST http://localhost:8080/convert \
  -H "Authorization: Bearer test_secret" \
  -H "Content-Type: application/json" \
  -d @example_lesson.json \
  --output output.pdf
```

## Docker Image Details

- **Base Image**: `python:3.12-slim` (~150MB)
- **LaTeX Compiler**: Tectonic v0.15.0 (~50MB)
- **Total Image Size**: ~200-300MB

The image uses Tectonic, a modern Rust-based LaTeX engine that's much smaller than traditional TeX Live distributions while maintaining compatibility.

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

### GPL v3 Summary

The GNU General Public License is a free, copyleft license that allows you to:

- **Use** the software for any purpose
- **Modify** the software to suit your needs
- **Distribute** the software and your modifications
- **Share** the source code

**Important**: If you distribute this software (modified or unmodified), you must:
- Include the original copyright notice
- Include a copy of the GPL v3 license
- Make the source code available under the same GPL v3 license
- Document any changes you made

### Full License Text

See the [LICENSE](LICENSE) file in this repository for the complete GPL v3 license text.

### More Information

- [GNU GPL v3 Official Page](https://www.gnu.org/licenses/gpl-3.0.html)
- [GPL v3 FAQ](https://www.gnu.org/licenses/gpl-faq.html)

