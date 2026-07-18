# Contributing to SkyBuddy

Thank you for interest in contributing to SkyBuddy! This document provides guidelines for contributing.

## Code of Conduct

Be respectful and inclusive. We're building a tool for everyone.

## How to Contribute

### Reporting Bugs

1. Check if the bug already exists in [Issues](https://github.com/HaroldMate1/SkyBuddy/issues)
2. If not, create a new issue using the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md)
3. Include steps to reproduce, expected behavior, and environment details

### Suggesting Features

1. Check existing [Issues](https://github.com/HaroldMate1/SkyBuddy/issues) for similar requests
2. Create a new issue using the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md)
3. Explain the use case and benefits

### Submitting Code

1. **Fork** the repository
2. **Create a branch** for your feature: `git checkout -b feature/your-feature-name`
3. **Make changes** following the code style below
4. **Test** your changes locally
5. **Commit** with clear messages: `git commit -m "Add feature: description"`
6. **Push** to your fork: `git push origin feature/your-feature-name`
7. **Create a Pull Request** with a clear description

## Code Style

### Python

- Follow PEP 8 style guide
- Use type hints where possible
- Keep functions focused and small
- Add docstrings to public functions
- Use descriptive variable names

### Example

```python
def add_watched_route(
    self,
    name: str,
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: Optional[str] = None,
    target_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Add a route to monitor for price changes.
    
    Args:
        name: Friendly name for the route
        origin: IATA airport code
        destination: IATA airport code
        outbound_date: Departure date (YYYY-MM-DD)
        return_date: Return date (optional)
        target_price: Alert when price drops below this
    
    Returns:
        Dict with route details and current price
    """
    # Implementation
    pass
```

## Areas for Contribution

### High Priority

- [ ] Web interface for price tracking dashboard
- [ ] Email digest reports (daily/weekly)
- [ ] Additional flight APIs (native Kayak, Skyscanner APIs)
- [ ] Performance optimization for large route monitoring

### Medium Priority

- [ ] Carbon footprint calculator
- [ ] Mobile app (React Native or Flutter)
- [ ] Additional loyalty program support
- [ ] Airport amenity integration

### Low Priority

- [ ] More visualization options
- [ ] Social features (share deals with friends)
- [ ] Flight change notifications
- [ ] Travel insurance recommendations

## Development Setup

### Prerequisites

- Python 3.8+
- git

### Setup

```bash
# Clone the repo
git clone https://github.com/HaroldMate1/SkyBuddy.git
cd SkyBuddy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install dev dependencies
pip install pytest pytest-cov flake8
```

### Testing Your Changes

```bash
# Test imports
python -c "from scripts.agent_integration import create_agent; print('✓ OK')"

# Test a module
python scripts/flight_scraper.py BIO BOG 2026-12-04 2027-01-08

# Run linting
flake8 scripts/
```

## Pull Request Process

1. **Update README** if you add new features
2. **Update CLAUDE.md** if you change the LLM interface
3. **Add tests** if applicable
4. **Ensure** all existing tests pass
5. **Reference** the issue in your PR description

### PR Template

```markdown
## Description
Brief description of changes

## Related Issue
Closes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Enhancement
- [ ] Documentation

## Testing
- [ ] Tested locally
- [ ] Added tests
- [ ] All tests pass

## Checklist
- [ ] Code follows style guide
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No breaking changes
```

## Commit Message Guidelines

- Use clear, descriptive titles
- Reference issues when applicable
- Use present tense: "Add feature" not "Added feature"
- Keep first line under 70 characters

### Examples

```
Add recommendation scoring to flights
Fix price alert trigger condition
Update documentation for Hermes adapter
Refactor loyalty card storage
```

## Licensing

By contributing, you agree that your contributions will be licensed under the same license as the project (open source).

## Questions?

- Check [README.md](README.md) for feature documentation
- Check [CLAUDE.md](CLAUDE.md) for integration details
- Open a GitHub Discussion
- Email: haroldmateomojicaurrego@gmail.com

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md (to be added)
- Release notes
- GitHub contributors page

## Future Direction

SkyBuddy is evolving to support:
- More flight APIs and data sources
- Broader agent ecosystem
- Enterprise features (team management, API tiers)
- Advanced analytics and predictions

---

Thank you for making SkyBuddy better! ✈️
