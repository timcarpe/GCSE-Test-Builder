#!/bin/bash
# Creates a fancy DMG installer for GCSE Toolkit

set -e

APP_NAME="GCSE Test Builder"
DMG_NAME="GCSE Test Builder"
SOURCE_APP="dist/${APP_NAME}.app"
DMG_PATH="dist/${DMG_NAME}.dmg"
VOLUME_NAME="${APP_NAME}"
ICON_PATH="build_resources/logo.icns"

# Window size
WINDOW_WIDTH=500
WINDOW_HEIGHT=350

# Icon positions
APP_ICON_X=125
APP_ICON_Y=170
APPS_ICON_X=375
APPS_ICON_Y=170

# Temporary DMG for setup
TEMP_DMG="dist/${DMG_NAME}_temp.dmg"

echo "🔧 Creating fancy DMG for ${APP_NAME}..."

# Clean up old files
rm -f "${DMG_PATH}" "${TEMP_DMG}"

# Create a temporary folder for DMG contents
DMG_TEMP_DIR=$(mktemp -d)
echo "📁 Staging in ${DMG_TEMP_DIR}"

# Copy app to temp folder
cp -R "${SOURCE_APP}" "${DMG_TEMP_DIR}/"

# Create Applications symlink
ln -s /Applications "${DMG_TEMP_DIR}/Applications"

# Calculate size needed (add 20MB buffer)
SIZE_KB=$(du -sk "${DMG_TEMP_DIR}" | cut -f1)
SIZE_KB=$((SIZE_KB + 20480))

echo "📦 Creating temporary DMG (${SIZE_KB}KB)..."

# Create temporary read-write DMG
hdiutil create -srcfolder "${DMG_TEMP_DIR}" -volname "${VOLUME_NAME}" -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" -format UDRW -size ${SIZE_KB}k "${TEMP_DMG}"

# Mount the DMG
echo "🔗 Mounting DMG for customization..."
MOUNT_DIR="/Volumes/${VOLUME_NAME}"
hdiutil attach "${TEMP_DMG}" -mountpoint "${MOUNT_DIR}"

# Apply custom view settings using AppleScript
echo "🎨 Applying Finder view settings..."
osascript <<EOF
tell application "Finder"
    tell disk "${VOLUME_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {100, 100, $((100 + WINDOW_WIDTH)), $((100 + WINDOW_HEIGHT))}
        
        set theViewOptions to icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 100
        
        set position of item "${APP_NAME}.app" of container window to {${APP_ICON_X}, ${APP_ICON_Y}}
        set position of item "Applications" of container window to {${APPS_ICON_X}, ${APPS_ICON_Y}}
        
        update without registering applications
        close
    end tell
end tell
EOF

# Wait for Finder to finish
sync
sleep 5

# Set custom volume icon if available
if [ -f "${ICON_PATH}" ]; then
    echo "🖼️ Setting volume icon..."
    cp "${ICON_PATH}" "${MOUNT_DIR}/.VolumeIcon.icns"
    SetFile -c icnC "${MOUNT_DIR}/.VolumeIcon.icns" 2>/dev/null || true
    SetFile -a C "${MOUNT_DIR}" 2>/dev/null || true
fi

# Unmount
echo "⏏️ Unmounting..."
hdiutil detach "${MOUNT_DIR}"

# Convert to compressed DMG
echo "📀 Creating final compressed DMG..."
hdiutil convert "${TEMP_DMG}" -format UDZO -imagekey zlib-level=9 -o "${DMG_PATH}"

# Clean up
rm -f "${TEMP_DMG}"
rm -rf "${DMG_TEMP_DIR}"

# Verify
if [ -f "${DMG_PATH}" ]; then
    SIZE=$(du -h "${DMG_PATH}" | cut -f1)
    echo ""
    echo "✅ DMG created successfully!"
    echo "   📍 Location: ${DMG_PATH}"
    echo "   📊 Size: ${SIZE}"
else
    echo "❌ Failed to create DMG"
    exit 1
fi
