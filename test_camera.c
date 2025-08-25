#define _GNU_SOURCE
#include "camera_capture.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>

static volatile int running = 1;

static void sigint_handler(int sig) {
    printf("\nReceived signal %d, stopping...\n", sig);
    running = 0;
}

void print_usage(const char *prog_name) {
    printf("Usage: %s [options]\n", prog_name);
    printf("Options:\n");
    printf("  -d <device>    Camera device (default: /dev/video0)\n");
    printf("  -w <width>     Frame width (default: 1920)\n");
    printf("  -h <height>    Frame height (default: 1080)\n");
    printf("  -f <frames>    Number of frames to capture (default: 10)\n");
    printf("  -o <output>    Output directory (default: ./frames)\n");
    printf("  -q <quality>   JPEG quality 1-100 (default: 85)\n");
    printf("  -v             Verbose output\n");
    printf("  -t             Test mode (capture and save frames)\n");
    printf("  --help         Show this help message\n");
    printf("\nExamples:\n");
    printf("  %s -t -f 5              # Capture 5 test frames\n", prog_name);
    printf("  %s -d /dev/video0 -v    # Verbose camera info\n", prog_name);
    printf("  %s -w 640 -h 480 -q 70  # Lower resolution, lower quality\n", prog_name);
}

int test_camera_basic(const char *device, int width, int height, int verbose) {
    camera_t cam;
    int ret;
    
    printf("=== Basic Camera Test ===\n");
    printf("Device: %s\n", device);
    printf("Resolution: %dx%d\n", width, height);
    printf("\n");
    
    ret = camera_init(&cam, device, width, height);
    if (ret != 0) {
        printf("Camera initialization failed!\n");
        return ret;
    }
    
    if (verbose) {
        print_camera_info(&cam);
    }
    
    ret = camera_start_streaming(&cam);
    if (ret != 0) {
        printf("Failed to start streaming!\n");
        camera_cleanup(&cam);
        return ret;
    }
    
    printf("Camera test successful - streaming started\n");
    
    camera_stop_streaming(&cam);
    camera_cleanup(&cam);
    
    printf("Camera test completed successfully\n");
    return 0;
}

int test_frame_capture(const char *device, int width, int height, 
                      int num_frames, const char *output_dir, 
                      int jpeg_quality, int verbose) {
    camera_t cam;
    frame_t frame;
    int ret, captured = 0;
    
    printf("=== Frame Capture Test ===\n");
    printf("Device: %s\n", device);
    printf("Resolution: %dx%d\n", width, height);
    printf("Frames to capture: %d\n", num_frames);
    printf("Output directory: %s\n", output_dir);
    printf("JPEG quality: %d\n", jpeg_quality);
    printf("\n");
    
    ret = create_output_directory(output_dir);
    if (ret != 0) {
        return ret;
    }
    
    ret = camera_init(&cam, device, width, height);
    if (ret != 0) {
        printf("Camera initialization failed!\n");
        return ret;
    }
    
    if (verbose) {
        print_camera_info(&cam);
    }
    
    ret = camera_start_streaming(&cam);
    if (ret != 0) {
        printf("Failed to start streaming!\n");
        camera_cleanup(&cam);
        return ret;
    }
    
    printf("Starting frame capture...\n");
    
    signal(SIGINT, sigint_handler);
    
    while (running && captured < num_frames) {
        ret = camera_capture_frame(&cam, &frame);
        if (ret < 0) {
            printf("Error capturing frame\n");
            break;
        } else if (ret == 0) {
            usleep(1000);
            continue;
        }
        
        captured++;
        printf("Captured frame %d/%d (size: %zu bytes)\n", 
               captured, num_frames, frame.size);
        
        if (verbose) {
            debug_frame_info(&frame);
        }
        
        char raw_filename[256];
        char jpeg_filename[256];
        snprintf(raw_filename, sizeof(raw_filename), 
                "%s/frame_%03d_raw.yuv", output_dir, captured);
        snprintf(jpeg_filename, sizeof(jpeg_filename), 
                "%s/frame_%03d.jpg", output_dir, captured);
        
        frame_t raw_frame = frame;
        ret = save_frame_to_file(&raw_frame, raw_filename);
        if (ret != 0) {
            printf("Warning: Failed to save raw frame %d\n", captured);
        }
        
        uint8_t *jpeg_data = NULL;
        size_t jpeg_size = 0;
        ret = compress_yuyv_to_jpeg(frame.data, cam.width, cam.height, 
                                   &jpeg_data, &jpeg_size, jpeg_quality);
        if (ret == 0) {
            frame_t jpeg_frame = {
                .data = jpeg_data,
                .size = jpeg_size,
                .timestamp = frame.timestamp
            };
            ret = save_frame_to_file(&jpeg_frame, jpeg_filename);
            if (ret == 0) {
                printf("  -> Saved as JPEG: %s (%zu bytes, %.1f%% compression)\n", 
                       jpeg_filename, jpeg_size, 
                       100.0 * jpeg_size / frame.size);
            }
            free(jpeg_data);
        } else {
            printf("Warning: JPEG compression failed for frame %d\n", captured);
        }
        
        printf("\n");
    }
    
    camera_stop_streaming(&cam);
    camera_cleanup(&cam);
    
    printf("Frame capture test completed\n");
    printf("Total frames captured: %d\n", captured);
    return 0;
}

int benchmark_performance(const char *device, int width, int height) {
    camera_t cam;
    frame_t frame;
    int ret, frames = 0;
    time_t start_time, end_time;
    
    printf("=== Performance Benchmark ===\n");
    printf("Device: %s\n", device);
    printf("Resolution: %dx%d\n", width, height);
    printf("Duration: 10 seconds\n");
    printf("\n");
    
    ret = camera_init(&cam, device, width, height);
    if (ret != 0) {
        printf("Camera initialization failed!\n");
        return ret;
    }
    
    ret = camera_start_streaming(&cam);
    if (ret != 0) {
        printf("Failed to start streaming!\n");
        camera_cleanup(&cam);
        return ret;
    }
    
    printf("Starting benchmark...\n");
    start_time = time(NULL);
    signal(SIGINT, sigint_handler);
    
    while (running && (time(NULL) - start_time) < 10) {
        ret = camera_capture_frame(&cam, &frame);
        if (ret > 0) {
            frames++;
            if (frames % 30 == 0) {
                printf("Captured %d frames (%.1f fps)\n", 
                       frames, (float)frames / (time(NULL) - start_time));
            }
        } else if (ret < 0) {
            break;
        }
        usleep(1000);
    }
    
    end_time = time(NULL);
    double duration = difftime(end_time, start_time);
    
    camera_stop_streaming(&cam);
    camera_cleanup(&cam);
    
    printf("\n=== Benchmark Results ===\n");
    printf("Duration: %.1f seconds\n", duration);
    printf("Frames captured: %d\n", frames);
    printf("Average FPS: %.2f\n", frames / duration);
    printf("Frame size: ~%zu bytes\n", frame.size);
    printf("Data rate: %.2f MB/s\n", (frames * frame.size) / (duration * 1024 * 1024));
    
    return 0;
}

int main(int argc, char *argv[]) {
    const char *device = DEFAULT_DEVICE;
    int width = DEFAULT_WIDTH;
    int height = DEFAULT_HEIGHT;
    int num_frames = 10;
    const char *output_dir = "./frames";
    int jpeg_quality = 85;
    int verbose = 0;
    int test_mode = 0;
    int benchmark = 0;
    
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-d") == 0 && i + 1 < argc) {
            device = argv[++i];
        } else if (strcmp(argv[i], "-w") == 0 && i + 1 < argc) {
            width = atoi(argv[++i]);
        } else if (strcmp(argv[i], "-h") == 0 && i + 1 < argc) {
            height = atoi(argv[++i]);
        } else if (strcmp(argv[i], "-f") == 0 && i + 1 < argc) {
            num_frames = atoi(argv[++i]);
        } else if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) {
            output_dir = argv[++i];
        } else if (strcmp(argv[i], "-q") == 0 && i + 1 < argc) {
            jpeg_quality = atoi(argv[++i]);
        } else if (strcmp(argv[i], "-v") == 0) {
            verbose = 1;
        } else if (strcmp(argv[i], "-t") == 0) {
            test_mode = 1;
        } else if (strcmp(argv[i], "-b") == 0) {
            benchmark = 1;
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            printf("Unknown option: %s\n", argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }
    
    if (jpeg_quality < 1 || jpeg_quality > 100) {
        printf("Error: JPEG quality must be between 1 and 100\n");
        return 1;
    }
    
    if (width <= 0 || height <= 0) {
        printf("Error: Invalid resolution %dx%d\n", width, height);
        return 1;
    }
    
    printf("Raspberry Pi Camera Capture Test\n");
    printf("================================\n");
    
    if (benchmark) {
        return benchmark_performance(device, width, height);
    } else if (test_mode) {
        return test_frame_capture(device, width, height, num_frames, 
                                 output_dir, jpeg_quality, verbose);
    } else {
        return test_camera_basic(device, width, height, verbose);
    }
}