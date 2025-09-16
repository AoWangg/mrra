# Contributing to MRRA

We welcome contributions to the MRRA (Mobility Retrieve-and-Reflect Agent) project! This document provides guidelines for contributing to the project.

## Table of Contents
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)
- [Community Guidelines](#community-guidelines)

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment
4. Make your changes
5. Submit a pull request

## How to Contribute

### Types of Contributions

- **Bug Reports**: Help us identify and fix issues
- **Feature Requests**: Suggest new features or improvements
- **Code Contributions**: Submit bug fixes, new features, or improvements
- **Documentation**: Improve or add to our documentation
- **Examples**: Provide usage examples or tutorials

### Areas for Contribution

- Core algorithm improvements
- New MCP tool integrations
- Performance optimizations
- Test coverage expansion
- Documentation improvements
- Example notebooks and tutorials

## Development Setup

### Prerequisites
- Python 3.10 or higher
- Git

### Installation

1. Clone your fork:
```bash
git clone https://github.com/your-username/mrra.git
cd mrra
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e .[dev,mcp]
```

4. Set up pre-commit hooks (optional but recommended):
```bash
pip install pre-commit
pre-commit install
```

### Environment Variables

For testing with LLM functionality, you may need to set:
```bash
export MRRA_API_KEY="your-api-key"
export MRRA_API_PROVIDER="openai-compatible"
export MRRA_API_MODEL="your-model"
export MRRA_API_BASE_URL="your-endpoint"
```

## Code Standards

### Code Style
- Follow PEP 8 guidelines
- Use `ruff` for linting and formatting:
  ```bash
  ruff check .
  ruff format .
  ```

### Code Quality
- Write clear, readable code with meaningful variable names
- Add docstrings to all public functions and classes
- Include type hints where appropriate
- Keep functions focused and modular

### Testing
- Write tests for new functionality
- Ensure existing tests pass:
  ```bash
  pytest
  ```
- Aim for good test coverage of core functionality

### Documentation
- Update relevant documentation for any changes
- Include docstrings with examples for public APIs
- Update CHANGELOG.md for notable changes

## Submitting Changes

### Pull Request Process

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**:
   - Follow the code standards above
   - Include tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**:
   ```bash
   ruff check .
   ruff format .
   pytest
   ```

4. **Commit Your Changes**:
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```
   
   Use conventional commit messages:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `test:` for test additions
   - `refactor:` for code refactoring

5. **Push to Your Fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request**:
   - Go to the GitHub repository
   - Click "New Pull Request"
   - Provide a clear title and description
   - Reference any related issues

### Pull Request Guidelines

- **Clear Description**: Explain what your PR does and why
- **Small, Focused Changes**: Keep PRs focused on a single feature or fix
- **Tests Included**: Include tests for new functionality
- **Documentation Updated**: Update docs for user-facing changes
- **No Breaking Changes**: Avoid breaking existing APIs without discussion

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Clear Title**: Summarize the issue in the title
2. **Environment Details**:
   - Python version
   - MRRA version
   - Operating system
   - Relevant dependencies
3. **Steps to Reproduce**: Detailed steps to reproduce the issue
4. **Expected Behavior**: What you expected to happen
5. **Actual Behavior**: What actually happened
6. **Code Sample**: Minimal code that reproduces the issue
7. **Error Messages**: Full error messages and stack traces

### Feature Requests

For feature requests, please include:

1. **Clear Description**: What feature you'd like to see
2. **Use Case**: Why this feature would be useful
3. **Proposed Solution**: Ideas on how it could be implemented
4. **Alternatives**: Alternative solutions you've considered

## Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Respect different viewpoints and experiences

### Communication

- Use clear, concise language
- Be patient with questions and discussions
- Provide helpful, actionable feedback
- Ask questions if anything is unclear

### Getting Help

- Check existing issues and documentation first
- Use GitHub Issues for bug reports and feature requests
- Join discussions in existing issues and pull requests
- Reach out to maintainers for guidance on larger contributions

## Development Workflow

### Branching Strategy
- `main`: Stable release branch
- `develop`: Integration branch for new features
- Feature branches: `feature/description`
- Bug fix branches: `fix/description`

### Release Process
- Releases are automated through GitHub Actions
- Version bumps follow semantic versioning
- CHANGELOG.md is updated for each release

## License

By contributing to MRRA, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions about contributing, please:
1. Check this document and existing issues
2. Open a new issue with your question
3. Reach out to the maintainers

Thank you for contributing to MRRA! 🚀