#!/bin/bash

# ARC Python Package Release Script
set -e

echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

echo "🔍 Running tests..."
if find tests/ -name "test_*.py" -o -name "*_test.py" | grep -q .; then
    python -m pytest tests/ || { echo "❌ Tests failed!"; exit 1; }
    echo "✅ All tests passed!"
else
    echo "⚠️  No test files found - skipping test phase"
    echo "   Consider adding test files (test_*.py) in the tests/ directory"
fi

echo "🏗️  Building package..."
python -m build

echo "✅ Build complete! Files created:"
ls -la dist/

echo ""
echo "📤 Ready to upload!"
echo "For TestPyPI: twine upload --repository testpypi dist/*"
echo "For PyPI:     twine upload dist/*"
echo ""
echo "🔄 Don't forget to:"
echo "  1. Update version in pyproject.toml and setup.py"
echo "  2. Update CHANGELOG.md"
echo "  3. Commit and tag the release"
echo "  4. git tag v$(python -c 'import tomllib; print(tomllib.load(open(\"pyproject.toml\", \"rb\"))[\"project\"][\"version\"])')"
