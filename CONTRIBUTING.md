# Contributing to Shift Planner

Thank you for your interest in contributing to Shift Planner! This document provides guidelines and instructions for contributing.

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Git
- Docker (optional, for containerized development)

### Setup Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/kiriazisPE/Vardiologio_1.git
   cd Vardiologio_1/shift_planner
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Edit .env and add your API keys
   # OPENAI_API_KEY=your-key-here
   ```

5. **Run the application**
   ```bash
   streamlit run main.py
   ```

## 📝 Development Workflow

### Branch Strategy
- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features
- `fix/*` - Bug fixes
- `hotfix/*` - Critical production fixes

### Creating a Feature

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, documented code
   - Follow existing code style
   - Add tests for new functionality

3. **Test your changes**
   ```bash
   # Run tests
   pytest
   
   # Check code quality
   black --check .
   flake8 .
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest test_backend_durability.py
```

### Writing Tests
- Place tests in files starting with `test_`
- Use descriptive test names
- Cover edge cases and error conditions
- Mock external dependencies (OpenAI API, etc.)

## 📏 Code Style

### Python Style Guide
- Follow [PEP 8](https://pep8.org/)
- Use [Black](https://black.readthedocs.io/) for formatting
- Maximum line length: 120 characters
- Use type hints where possible

### Code Formatting
```bash
# Format code
black .

# Sort imports
isort .

# Check linting
flake8 . --max-line-length=120
```

### Commit Message Convention
Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new scheduling algorithm
fix: resolve timezone conversion bug
docs: update API documentation
test: add tests for shift swapping
chore: update dependencies
refactor: simplify database queries
```

## 🐳 Docker Development

### Build and run locally
```bash
cd shift_planner

# Build image
docker build -t shift-planner:dev .

# Run container
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=your-key \
  shift-planner:dev
```

### Using Docker Compose
```bash
docker-compose up -d
```

## 🔍 Code Review Process

### Before Submitting PR
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] No sensitive data in commits
- [ ] CHANGELOG updated (for significant changes)

### PR Review Checklist
- Code quality and readability
- Test coverage
- Performance implications
- Security considerations
- Documentation completeness

## 📚 Project Structure

```
shift_planner/
├── main.py              # Main Streamlit application
├── backend.py           # Business logic and scheduling
├── db.py                # Database operations
├── models.py            # Data models
├── scheduler.py         # Core scheduling algorithms
├── dspy_scheduler.py    # AI-powered scheduling
├── ui_pages.py          # UI components
├── test_*.py            # Test files
└── assets/              # Static files
```

## 🔐 Security

### Reporting Security Issues
- **DO NOT** create public GitHub issues for security vulnerabilities
- Email security concerns to: [maintainer email]
- Include detailed description and reproduction steps

### Security Best Practices
- Never commit API keys or secrets
- Use environment variables for configuration
- Validate and sanitize user input
- Keep dependencies updated

## 📖 Documentation

### Code Documentation
- Use docstrings for all functions and classes
- Include examples in docstrings
- Update README.md for significant changes

### Documentation Style
```python
def schedule_shift(employee_id: int, date: str, shift_type: str) -> bool:
    """
    Schedule a shift for an employee.
    
    Args:
        employee_id: Unique identifier for the employee
        date: Shift date in ISO format (YYYY-MM-DD)
        shift_type: Type of shift ('morning', 'evening', 'night')
    
    Returns:
        True if scheduling successful, False otherwise
    
    Raises:
        ValueError: If date format is invalid
        
    Example:
        >>> schedule_shift(123, '2025-01-15', 'morning')
        True
    """
    pass
```

## 🎯 Areas for Contribution

### Priority Areas
- [ ] Additional scheduling algorithms
- [ ] Performance optimizations
- [ ] UI/UX improvements
- [ ] Test coverage expansion
- [ ] Documentation improvements
- [ ] Internationalization (i18n)

### Good First Issues
Look for issues labeled `good first issue` in the GitHub repository.

## 💬 Getting Help

- **Documentation**: Check README.md and DOCUMENTATION.md
- **Issues**: Search existing GitHub issues
- **Discussions**: Use GitHub Discussions for questions
- **Community**: Join our community chat [if applicable]

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## 🙏 Recognition

Contributors will be acknowledged in:
- README.md Contributors section
- Release notes
- CHANGELOG.md

---

Thank you for contributing to Shift Planner! Your efforts help make this project better for everyone. 🎉
