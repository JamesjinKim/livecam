cmake_minimum_required(VERSION 3.16)
project(RaspberryPiCameraCapture CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Enable debug symbols and optimization
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -Wall -Wextra")
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -Wall -Wextra -DNDEBUG")

# Default to Release build
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")

# Find required packages
find_package(PkgConfig REQUIRED)

# Find libcamera
pkg_check_modules(LIBCAMERA REQUIRED IMPORTED_TARGET libcamera)
message(STATUS "libcamera version: ${LIBCAMERA_VERSION}")

# Find JPEG library
find_package(JPEG REQUIRED)
if(JPEG_FOUND)
    message(STATUS "JPEG library found: ${JPEG_LIBRARIES}")
endif()

# Find threading support
find_package(Threads REQUIRED)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})
include_directories(${JPEG_INCLUDE_DIR})

# Source files
set(CAMERA_SOURCES
    CameraCapture.cpp
    DebugUtils.cpp
)

# Executable targets
add_executable(test_camera
    TestCamera.cpp
    ${CAMERA_SOURCES}
)

add_executable(demo_test
    DemoTest.cpp
    ${CAMERA_SOURCES}
)

# Link libraries
target_link_libraries(test_camera
    PkgConfig::LIBCAMERA
    ${JPEG_LIBRARIES}
    Threads::Threads
)

target_link_libraries(demo_test
    PkgConfig::LIBCAMERA
    ${JPEG_LIBRARIES}
    Threads::Threads
)

# Compiler-specific options
target_compile_features(test_camera PRIVATE cxx_std_17)
target_compile_features(demo_test PRIVATE cxx_std_17)

# Installation (optional)
install(TARGETS test_camera demo_test
    RUNTIME DESTINATION bin
)

# Custom targets
add_custom_target(run_demo
    COMMAND ./demo_test
    DEPENDS demo_test
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Running demo tests"
)

add_custom_target(run_test
    COMMAND ./test_camera -v
    DEPENDS test_camera
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Running camera tests"
)

add_custom_target(capture_test
    COMMAND ./test_camera -t -f 5 -v
    DEPENDS test_camera
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Running capture tests"
)

# Print configuration summary
message(STATUS "")
message(STATUS "Configuration Summary:")
message(STATUS "  C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  libcamera: ${LIBCAMERA_VERSION}")
message(STATUS "  JPEG: ${JPEG_LIBRARIES}")
message(STATUS "")
message(STATUS "Build commands:")
message(STATUS "  mkdir build && cd build")
message(STATUS "  cmake ..")
message(STATUS "  make -j$(nproc)")
message(STATUS "")
message(STATUS "Run commands:")
message(STATUS "  make run_demo      # Test without camera")
message(STATUS "  make run_test      # Basic camera test")
message(STATUS "  make capture_test  # Capture test frames")
message(STATUS "")