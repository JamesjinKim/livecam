# Modern C++ Makefile for Raspberry Pi Camera Capture
# Uses libcamera, C++17, and modern build practices

CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O3 -g
INCLUDES = -I. -I/usr/include
LDFLAGS = -L/usr/lib/aarch64-linux-gnu

# Package config for libcamera
LIBCAMERA_CFLAGS = $(shell pkg-config --cflags libcamera)
LIBCAMERA_LIBS = $(shell pkg-config --libs libcamera)

# JPEG library
JPEG_LIBS = -ljpeg

# Threading
THREAD_LIBS = -lpthread

# All libraries
LIBS = $(LIBCAMERA_LIBS) $(JPEG_LIBS) $(THREAD_LIBS)

# Source files
COMMON_SOURCES = CameraCapture.cpp DebugUtils.cpp
TEST_SOURCES = TestCamera.cpp
DEMO_SOURCES = DemoTest.cpp

# Object files
COMMON_OBJECTS = $(COMMON_SOURCES:.cpp=.o)
TEST_OBJECTS = $(TEST_SOURCES:.cpp=.o)
DEMO_OBJECTS = $(DEMO_SOURCES:.cpp=.o)

# Target executables
TEST_TARGET = test_camera
DEMO_TARGET = demo_test

# Default target
all: $(TEST_TARGET) $(DEMO_TARGET)

# Test camera executable
$(TEST_TARGET): $(COMMON_OBJECTS) $(TEST_OBJECTS)
	@echo "Linking $(TEST_TARGET)..."
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $^ $(LIBS)
	@echo "Built $(TEST_TARGET) successfully"

# Demo test executable  
$(DEMO_TARGET): $(COMMON_OBJECTS) $(DEMO_OBJECTS)
	@echo "Linking $(DEMO_TARGET)..."
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $^ $(LIBS)
	@echo "Built $(DEMO_TARGET) successfully"

# Compile source files to object files
%.o: %.cpp CameraCapture.hpp
	@echo "Compiling $<..."
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(LIBCAMERA_CFLAGS) -c $< -o $@

# Installation target (requires sudo)
install: all
	@echo "Installing executables to /usr/local/bin..."
	sudo cp $(TEST_TARGET) /usr/local/bin/
	sudo cp $(DEMO_TARGET) /usr/local/bin/
	@echo "Installation complete"

# Uninstall target (requires sudo)
uninstall:
	@echo "Removing installed executables..."
	sudo rm -f /usr/local/bin/$(TEST_TARGET)
	sudo rm -f /usr/local/bin/$(DEMO_TARGET)
	@echo "Uninstall complete"

# Check dependencies
check-deps:
	@echo "Checking dependencies..."
	@command -v g++ >/dev/null 2>&1 || { echo "g++ is not installed. Install with: sudo apt install build-essential"; exit 1; }
	@pkg-config --exists libcamera || { echo "libcamera is not installed. Install with: sudo apt install libcamera-dev"; exit 1; }
	@pkg-config --exists libjpeg || { echo "libjpeg-dev is not installed. Install with: sudo apt install libjpeg-dev"; exit 1; }
	@echo "libcamera version: $$(pkg-config --modversion libcamera)"
	@echo "All dependencies satisfied"

# Quick test (without camera)
demo: $(DEMO_TARGET)
	@echo "Running demo tests..."
	./$(DEMO_TARGET)

# Camera test (requires camera)
test: $(TEST_TARGET)
	@echo "Running basic camera test..."
	./$(TEST_TARGET) -v

# Capture test frames
capture-test: $(TEST_TARGET)
	@echo "Capturing test frames..."
	./$(TEST_TARGET) -t -f 5 -v

# Performance benchmark
benchmark: $(TEST_TARGET)
	@echo "Running performance benchmark..."
	./$(TEST_TARGET) -b

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -f *.o
	rm -f $(TEST_TARGET) $(DEMO_TARGET)
	rm -rf captures/ demo/
	@echo "Clean complete"

# Create output directories
dirs:
	@mkdir -p captures demo

# Build with CMake (alternative)
cmake-build:
	@echo "Building with CMake..."
	mkdir -p build
	cd build && cmake .. && make -j$$(nproc)
	@echo "CMake build complete. Executables in build/ directory"

# Clean CMake build
cmake-clean:
	@echo "Cleaning CMake build..."
	rm -rf build/
	@echo "CMake clean complete"

# Help target
help:
	@echo "Raspberry Pi Camera Capture - C++ Build System"
	@echo "=============================================="
	@echo ""
	@echo "Targets:"
	@echo "  all           - Build all executables (default)"
	@echo "  test_camera   - Build camera test executable"
	@echo "  demo_test     - Build demo test executable"
	@echo "  install       - Install to /usr/local/bin (requires sudo)"
	@echo "  uninstall     - Remove from /usr/local/bin (requires sudo)"
	@echo "  check-deps    - Check build dependencies"
	@echo "  demo          - Run demo tests (no camera needed)"
	@echo "  test          - Run basic camera test"
	@echo "  capture-test  - Capture test frames"
	@echo "  benchmark     - Run performance benchmark"
	@echo "  dirs          - Create output directories"
	@echo "  cmake-build   - Build using CMake"
	@echo "  cmake-clean   - Clean CMake build"
	@echo "  clean         - Remove build artifacts"
	@echo "  help          - Show this help message"
	@echo ""
	@echo "Dependencies:"
	@echo "  - g++ with C++17 support"
	@echo "  - libcamera-dev"
	@echo "  - libjpeg-dev"
	@echo "  - pkg-config"
	@echo ""
	@echo "Install dependencies:"
	@echo "  sudo apt update"
	@echo "  sudo apt install build-essential libcamera-dev libjpeg-dev pkg-config"
	@echo ""
	@echo "Usage examples:"
	@echo "  make                    # Build all"
	@echo "  make demo              # Test without camera"
	@echo "  make test              # Basic camera test"  
	@echo "  make capture-test      # Capture 5 frames"
	@echo "  make benchmark         # Performance test"
	@echo "  make cmake-build       # Alternative CMake build"

# Specify phony targets
.PHONY: all install uninstall check-deps demo test capture-test benchmark clean dirs cmake-build cmake-clean help

# Default goal
.DEFAULT_GOAL := all