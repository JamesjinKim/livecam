#define _GNU_SOURCE
#include "camera_capture.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int create_demo_frame(frame_t *frame, int width, int height) {
    size_t frame_size = width * height * 2; // YUYV format
    frame->data = malloc(frame_size);
    if (!frame->data) {
        return -1;
    }
    
    frame->size = frame_size;
    frame->timestamp = 1234567890;
    
    // Create simple gradient pattern in YUYV format
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x += 2) {
            int pos = (y * width + x) * 2;
            
            // Y values (brightness)
            uint8_t y0 = (uint8_t)((x * 255) / width);
            uint8_t y1 = (uint8_t)(((x+1) * 255) / width);
            
            // U and V values (color)
            uint8_t u = (uint8_t)((y * 255) / height);
            uint8_t v = (uint8_t)(255 - (y * 255) / height);
            
            frame->data[pos] = y0;      // Y0
            frame->data[pos + 1] = u;   // U
            frame->data[pos + 2] = y1;  // Y1
            frame->data[pos + 3] = v;   // V
        }
    }
    
    return 0;
}

int demo_test_jpeg_compression() {
    printf("=== JPEG Compression Demo Test ===\n");
    
    int width = 640;
    int height = 480;
    int quality = 85;
    
    frame_t demo_frame;
    if (create_demo_frame(&demo_frame, width, height) != 0) {
        printf("Error: Failed to create demo frame\n");
        return -1;
    }
    
    printf("Created demo frame: %dx%d, %zu bytes\n", 
           width, height, demo_frame.size);
    
    uint8_t *jpeg_data = NULL;
    size_t jpeg_size = 0;
    
    printf("Compressing to JPEG (quality %d)...\n", quality);
    int ret = compress_yuyv_to_jpeg(demo_frame.data, width, height, 
                                   &jpeg_data, &jpeg_size, quality);
    
    if (ret == 0) {
        printf("JPEG compression successful!\n");
        printf("  Original size: %zu bytes\n", demo_frame.size);
        printf("  JPEG size: %zu bytes\n", jpeg_size);
        printf("  Compression ratio: %.1f%%\n", 
               100.0 * jpeg_size / demo_frame.size);
        
        // Save JPEG file
        frame_t jpeg_frame = {
            .data = jpeg_data,
            .size = jpeg_size,
            .timestamp = demo_frame.timestamp
        };
        
        if (create_output_directory("./demo") == 0) {
            ret = save_frame_to_file(&jpeg_frame, "./demo/demo_frame.jpg");
            if (ret == 0) {
                printf("  Saved demo JPEG: ./demo/demo_frame.jpg\n");
            }
        }
        
        free(jpeg_data);
    } else {
        printf("Error: JPEG compression failed\n");
        free(demo_frame.data);
        return -1;
    }
    
    free(demo_frame.data);
    printf("JPEG compression test completed successfully\n\n");
    return 0;
}

int demo_test_file_operations() {
    printf("=== File Operations Demo Test ===\n");
    
    frame_t demo_frame;
    if (create_demo_frame(&demo_frame, 320, 240) != 0) {
        printf("Error: Failed to create demo frame\n");
        return -1;
    }
    
    printf("Testing directory creation...\n");
    if (create_output_directory("./demo/test_dir") != 0) {
        printf("Error: Failed to create directory\n");
        free(demo_frame.data);
        return -1;
    }
    
    printf("Testing file save...\n");
    if (save_frame_to_file(&demo_frame, "./demo/test_dir/raw_frame.yuv") != 0) {
        printf("Error: Failed to save file\n");
        free(demo_frame.data);
        return -1;
    }
    
    printf("File operations test completed successfully\n\n");
    free(demo_frame.data);
    return 0;
}

int demo_test_debug_functions() {
    printf("=== Debug Functions Demo Test ===\n");
    
    frame_t demo_frame;
    if (create_demo_frame(&demo_frame, 160, 120) != 0) {
        printf("Error: Failed to create demo frame\n");
        return -1;
    }
    
    debug_frame_info(&demo_frame);
    
    printf("Debug functions test completed successfully\n\n");
    free(demo_frame.data);
    return 0;
}

void print_demo_usage(const char *prog_name) {
    printf("Usage: %s [test_name]\n", prog_name);
    printf("Available tests:\n");
    printf("  jpeg      - JPEG compression test\n");
    printf("  file      - File operations test\n");
    printf("  debug     - Debug functions test\n");
    printf("  all       - Run all tests (default)\n");
}

int main(int argc, char *argv[]) {
    const char *test_name = "all";
    
    if (argc > 1) {
        if (strcmp(argv[1], "--help") == 0) {
            print_demo_usage(argv[0]);
            return 0;
        }
        test_name = argv[1];
    }
    
    printf("C Components Demo Test\n");
    printf("=====================\n");
    printf("This demo tests the core functionality without requiring a physical camera.\n\n");
    
    int ret = 0;
    
    if (strcmp(test_name, "jpeg") == 0 || strcmp(test_name, "all") == 0) {
        ret |= demo_test_jpeg_compression();
    }
    
    if (strcmp(test_name, "file") == 0 || strcmp(test_name, "all") == 0) {
        ret |= demo_test_file_operations();
    }
    
    if (strcmp(test_name, "debug") == 0 || strcmp(test_name, "all") == 0) {
        ret |= demo_test_debug_functions();
    }
    
    if (ret == 0) {
        printf("🎉 All demo tests passed successfully!\n");
        printf("\nNext steps:\n");
        printf("1. Connect a camera module to test actual capture\n");
        printf("2. Run 'make capture-test' when camera is connected\n");
        printf("3. Check ./demo/ directory for generated files\n");
    } else {
        printf("❌ Some tests failed\n");
    }
    
    return ret;
}