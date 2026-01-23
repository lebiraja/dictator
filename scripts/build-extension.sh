#!/bin/bash
#
# Build script for Dictator GNOME Extension
# Creates a zip file for submission to extensions.gnome.org
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EXTENSION_DIR="$PROJECT_DIR/extension"
BUILD_DIR="$PROJECT_DIR/build"
DIST_DIR="$PROJECT_DIR/dist"

# Get version from metadata.json
VERSION=$(grep -oP '"version":\s*\K\d+' "$EXTENSION_DIR/metadata.json")
UUID=$(grep -oP '"uuid":\s*"\K[^"]+' "$EXTENSION_DIR/metadata.json")

echo "Building Dictator Extension v$VERSION"
echo "UUID: $UUID"
echo ""

# Create build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$DIST_DIR"

# Copy extension files
echo "Copying extension files..."
cp "$EXTENSION_DIR/extension.js" "$BUILD_DIR/"
cp "$EXTENSION_DIR/metadata.json" "$BUILD_DIR/"
cp "$EXTENSION_DIR/stylesheet.css" "$BUILD_DIR/"

# Copy and compile schemas
echo "Compiling schemas..."
mkdir -p "$BUILD_DIR/schemas"
cp "$EXTENSION_DIR/schemas/"*.xml "$BUILD_DIR/schemas/"
glib-compile-schemas "$BUILD_DIR/schemas/"

# Create zip file
ZIP_NAME="$UUID.v$VERSION.shell-extension.zip"
echo "Creating $ZIP_NAME..."
cd "$BUILD_DIR"
zip -r "$DIST_DIR/$ZIP_NAME" ./*

# Cleanup
rm -rf "$BUILD_DIR"

echo ""
echo "✓ Extension built successfully!"
echo ""
echo "Output: $DIST_DIR/$ZIP_NAME"
echo ""
echo "To install locally for testing:"
echo "  gnome-extensions install $DIST_DIR/$ZIP_NAME"
echo ""
echo "To submit to extensions.gnome.org:"
echo "  1. Go to https://extensions.gnome.org/upload/"
echo "  2. Log in with your GNOME account"
echo "  3. Upload $DIST_DIR/$ZIP_NAME"
echo "  4. Fill in the description and screenshots"
echo ""
echo "IMPORTANT: Users will also need to install the backend service."
echo "See README.md for full installation instructions."
echo ""
