# Qlib Agent Instructions

## Build / Lint / Test Commands

### Installation
```bash
# Install from source (editable mode)
pip install -e ".[dev]"

# Install with all extras (dev, lint, docs, package, test, analysis, rl)
make dev

# Build Cython extensions (prerequisite)
make prerequisite
```

### Testing
```bash
# Run all tests (excluding slow tests)
cd tests && python -m pytest . -m "not slow" --durations=0

# Run a specific test file
cd tests && python -m pytest test_data.py -v

# Run a specific test class/method
cd tests && python -m pytest test_data.py::TestDataClass::test_method -v

# Run tests with coverage
python -m pytest tests/ --cov=qlib --cov-report=xml

# Install test dependencies
make test
```

### Linting
```bash
# Run all lint checks
make lint

# Individual lint tools
make black     # Check formatting with black (line length: 120)
make pylint    # Run pylint on qlib/ and scripts/
make flake8    # Run flake8 on qlib/
make mypy      # Run mypy type checking
make nbqa      # Check notebooks with nbqa

# Fix formatting automatically
black . -l 120 --exclude qlib/_version.py
```

### Documentation
```bash
# Generate HTML documentation
make docs-gen

# Install docs dependencies
make docs
```

### Build Package
```bash
# Build wheel
make build

# Upload to PyPI
make upload
```

### Clean
```bash
# Remove build artifacts
make clean

# Deep clean (includes pre-commit hooks and virtualenv)
make deepclean
```

## Code Style Guidelines

### Formatting
- **Line length**: 120 characters (enforced by black)
- **Formatter**: Black 23.7.0
- Use `pre-commit install` to auto-format on commit

### Imports
```python
# Standard library imports first
import os
import sys
from typing import Optional, List, Dict

# Third-party imports second
import numpy as np
import pandas as pd
import torch

# Local imports third
from qlib.utils import some_function
from qlib.data import D
```

### Naming Conventions
- **Modules**: lowercase with underscores (e.g., `data_handler.py`)
- **Classes**: PascalCase (e.g., `Alpha158`, `MLPModel`)
- **Functions/Methods**: lowercase_with_underscores (e.g., `get_data`, `train_model`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_STOCK_NUM`, `DEFAULT_FREQ`)
- **Private**: prefix with underscore (e.g., `_internal_method`)

### Type Hints
- Use type hints for function signatures
- Use `Optional[]` for nullable values
- Use `Union[]` for multiple types (or `|` syntax in Python 3.10+)
- MyPy is configured but excludes most modules (see `.mypy.ini`)

### Error Handling
```python
# Use specific exceptions, not bare except
from qlib.utils.exceptions import QlibException

try:
    result = some_operation()
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise QlibException(f"Operation failed: {e}")
```

### Logging
- Use `loguru` for logging (imported via `qlib.log`)
- Prefer `logger.info()`, `logger.warning()`, `logger.error()` over print
- Use f-strings for log messages: `logger.info(f"Processing {num_stocks} stocks")`

### Docstrings
- Use **Numpydoc style** (see https://numpydoc.readthedocs.io/)
```python
def function_name(param1: int, param2: str) -> bool:
    """
    Short description of the function.

    Parameters
    ----------
    param1 : int
        Description of param1.
    param2 : str
        Description of param2.

    Returns
    -------
    bool
        Description of return value.

    Examples
    --------
    >>> function_name(1, "test")
    True
    """
    pass
```

### pylint Disables
Common patterns to disable when necessary:
```python
# pylint: disable=E1130  # Invalid unary operand
# pylint: disable=W0212  # Access to protected member
# pylint: disable=W0613  # Unused argument
```

### Pre-commit Setup
```bash
pip install -e ".[dev]"
pre-commit install
```

## Project Structure

- `qlib/` - Core source code
  - `backtest/` - Backtesting engine
  - `data/` - Data layer and providers
  - `model/` - ML models and trainers
  - `strategy/` - Trading strategies
  - `workflow/` - Experiment management
  - `rl/` - Reinforcement learning components
  - `utils/` - Utility functions
- `tests/` - Test suite (run with pytest)
- `examples/` - Example workflows and benchmarks
- `scripts/` - Utility scripts (data collection, etc.)
- `docs/` - Sphinx documentation

## CI/CD

GitHub Actions run on PRs and pushes to main:
- Black formatting check
- Pylint code quality
- Flake8 style check
- MyPy type checking
- Unit tests with pytest (Windows, Ubuntu, macOS)
- Documentation build

## Python Version Support

- Python 3.8, 3.9, 3.10, 3.11, 3.12
- Linux, Windows, macOS

## Quick Workflow

```bash
# 1. Setup development environment
make dev

# 2. Make your changes
# ... edit files ...

# 3. Run tests
cd tests && python -m pytest . -m "not slow" -v

# 4. Check linting
make lint

# 5. Fix formatting
black . -l 120 --exclude qlib/_version.py
```
