#!/usr/bin/env bash
set -e

echo "=== ChronicForge Build Script ==="
echo ""

# Verify we are in the project root
if [ ! -f "main.py" ] || [ ! -f "chronicforge.spec" ]; then
    echo "ERROR: Run this script from the ChronicForge project root."
    exit 1
fi

# Check system dependencies
if ! command -v ffmpeg &>/dev/null; then
    echo "WARNING: ffmpeg not found. Install with: sudo apt install ffmpeg"
    echo "         pydub audio playback will not work in the built app."
    echo ""
fi

if ! command -v upx &>/dev/null; then
    echo "INFO: upx not found. Install with: sudo apt install upx"
    echo "      Binary will still build; upx just reduces file size."
    echo ""
fi

# Install PyInstaller if not present
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install "pyinstaller>=6.0"
fi

# Remove previous dist output (--clean in pyinstaller handles build/, but not dist/)
echo "Cleaning previous dist output..."
rm -rf dist/ChronicForge/

# Build the application
echo "Building ChronicForge..."
pyinstaller --clean chronicforge.spec

echo ""
echo "=== Build Complete ==="
echo "Output: dist/ChronicForge/"
echo "Run with: ./dist/ChronicForge/ChronicForge"
echo ""
echo "To distribute: zip the entire dist/ChronicForge/ folder."
echo "  zip -r ChronicForge-linux-x86_64.zip dist/ChronicForge/"
echo ""
echo "Recipients must have ffmpeg installed: sudo apt install ffmpeg"
echo "API keys go in a .env file beside the ChronicForge executable."
