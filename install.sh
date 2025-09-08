#!/bin/bash
# Smart Security System - Installation Script
# Raspberry Pi 5 + OV5647 Camera Modules Setup

echo "🚀 Smart Security System - Installation Starting..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    print_warning "This script is optimized for Raspberry Pi. Continuing anyway..."
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update
if [ $? -ne 0 ]; then
    print_error "Failed to update package list"
    exit 1
fi

# Install system dependencies
print_status "Installing system dependencies..."
sudo apt install -y rpicam-apps ffmpeg python3-pip python3-venv
if [ $? -ne 0 ]; then
    print_error "Failed to install system packages"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oP 'Python \K[0-9]+\.[0-9]+')
if [[ $(echo "$python_version >= 3.11" | bc -l 2>/dev/null || echo "0") -eq 1 ]]; then
    print_success "Python $python_version detected (✓ >= 3.11)"
else
    print_warning "Python $python_version detected. Python 3.11+ recommended."
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
    # Try system-wide installation first
    pip3 install -r requirements.txt --break-system-packages 2>/dev/null || \
    pip3 install -r requirements.txt
else
    print_error "pip3 not found. Please install python3-pip"
    exit 1
fi

if [ $? -ne 0 ]; then
    print_error "Failed to install Python dependencies"
    exit 1
fi

# Check camera modules
print_status "Checking camera modules..."
if command -v rpicam-hello &> /dev/null; then
    camera_count=$(rpicam-hello --list-cameras 2>/dev/null | grep -c "Available cameras" || echo "0")
    if [ "$camera_count" -gt 0 ]; then
        print_success "Camera modules detected"
        rpicam-hello --list-cameras 2>/dev/null || true
    else
        print_warning "No camera modules detected. Please check connections."
    fi
else
    print_error "rpicam-hello not found. Camera support may not work."
fi

# Check user permissions
print_status "Checking user permissions..."
if groups $USER | grep -q video; then
    print_success "User has video group permissions"
else
    print_warning "Adding user to video group..."
    sudo usermod -a -G video $USER
    print_warning "Please log out and log back in for permissions to take effect"
fi

# Create videos directory structure
print_status "Creating video storage directories..."
mkdir -p videos/motion_events/cam0
mkdir -p videos/motion_events/cam1
chmod 755 videos/motion_events/cam0 videos/motion_events/cam1

# Set executable permissions
print_status "Setting executable permissions..."
chmod +x *.sh 2>/dev/null || true

# Installation complete
print_success "Installation completed successfully!"
echo ""
echo "🎯 Next Steps:"
echo "1. Reboot system: sudo reboot"
echo "2. Test camera: rpicam-hello --camera 0 --timeout 2000"
echo "3. Start system: python3 integrated_controller.py"
echo "4. Access web UI: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
print_status "For more information, see README.md"