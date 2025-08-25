#define _GNU_SOURCE
#include "camera_capture.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

void list_video_devices(void) {
    printf("=== Video Devices Detection ===\n");
    
    char device_path[32];
    for (int i = 0; i < 64; i++) {
        snprintf(device_path, sizeof(device_path), "/dev/video%d", i);
        
        int fd = open(device_path, O_RDWR);
        if (fd == -1) {
            continue;
        }
        
        struct v4l2_capability cap;
        if (ioctl(fd, VIDIOC_QUERYCAP, &cap) == 0) {
            printf("Device: %s\n", device_path);
            printf("  Driver: %s\n", cap.driver);
            printf("  Card: %s\n", cap.card);
            printf("  Bus: %s\n", cap.bus_info);
            
            if (cap.capabilities & V4L2_CAP_VIDEO_CAPTURE) {
                printf("  -> Video capture supported\n");
            }
            if (cap.capabilities & V4L2_CAP_STREAMING) {
                printf("  -> Streaming I/O supported\n");
            }
            printf("\n");
        }
        
        close(fd);
    }
}

void list_supported_formats(const char *device) {
    int fd = open(device, O_RDWR);
    if (fd == -1) {
        printf("Error: Cannot open device %s: %s\n", device, strerror(errno));
        return;
    }
    
    printf("=== Supported Formats for %s ===\n", device);
    
    struct v4l2_fmtdesc fmtdesc;
    memset(&fmtdesc, 0, sizeof(fmtdesc));
    fmtdesc.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    
    int index = 0;
    while (ioctl(fd, VIDIOC_ENUM_FMT, &fmtdesc) == 0) {
        printf("[%d]: '%c%c%c%c' (%s)\n",
               index,
               fmtdesc.pixelformat & 0xFF,
               (fmtdesc.pixelformat >> 8) & 0xFF,
               (fmtdesc.pixelformat >> 16) & 0xFF,
               (fmtdesc.pixelformat >> 24) & 0xFF,
               fmtdesc.description);
        
        struct v4l2_frmsizeenum framesize;
        memset(&framesize, 0, sizeof(framesize));
        framesize.pixel_format = fmtdesc.pixelformat;
        framesize.index = 0;
        
        if (ioctl(fd, VIDIOC_ENUM_FRAMESIZES, &framesize) == 0) {
            if (framesize.type == V4L2_FRMSIZE_TYPE_DISCRETE) {
                printf("  Sizes: ");
                do {
                    printf("%dx%d ", framesize.discrete.width, framesize.discrete.height);
                    framesize.index++;
                } while (ioctl(fd, VIDIOC_ENUM_FRAMESIZES, &framesize) == 0);
                printf("\n");
            } else if (framesize.type == V4L2_FRMSIZE_TYPE_STEPWISE) {
                printf("  Sizes: %dx%d - %dx%d (step %dx%d)\n",
                       framesize.stepwise.min_width, framesize.stepwise.min_height,
                       framesize.stepwise.max_width, framesize.stepwise.max_height,
                       framesize.stepwise.step_width, framesize.stepwise.step_height);
            }
        }
        
        fmtdesc.index = ++index;
    }
    
    close(fd);
}

void test_current_format(const char *device) {
    int fd = open(device, O_RDWR);
    if (fd == -1) {
        printf("Error: Cannot open device %s: %s\n", device, strerror(errno));
        return;
    }
    
    printf("=== Current Format for %s ===\n", device);
    
    struct v4l2_format fmt;
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    
    if (ioctl(fd, VIDIOC_G_FMT, &fmt) == 0) {
        printf("Resolution: %dx%d\n", fmt.fmt.pix.width, fmt.fmt.pix.height);
        printf("Pixel format: 0x%08X ('%c%c%c%c')\n", 
               fmt.fmt.pix.pixelformat,
               fmt.fmt.pix.pixelformat & 0xFF,
               (fmt.fmt.pix.pixelformat >> 8) & 0xFF,
               (fmt.fmt.pix.pixelformat >> 16) & 0xFF,
               (fmt.fmt.pix.pixelformat >> 24) & 0xFF);
        printf("Bytes per line: %d\n", fmt.fmt.pix.bytesperline);
        printf("Image size: %d bytes\n", fmt.fmt.pix.sizeimage);
        printf("Color space: %d\n", fmt.fmt.pix.colorspace);
    } else {
        printf("Error: Failed to get current format: %s\n", strerror(errno));
    }
    
    close(fd);
}

void test_controls(const char *device) {
    int fd = open(device, O_RDWR);
    if (fd == -1) {
        printf("Error: Cannot open device %s: %s\n", device, strerror(errno));
        return;
    }
    
    printf("=== Controls for %s ===\n", device);
    
    struct v4l2_queryctrl queryctrl;
    memset(&queryctrl, 0, sizeof(queryctrl));
    
    for (queryctrl.id = V4L2_CID_BASE;
         queryctrl.id < V4L2_CID_LASTP1;
         queryctrl.id++) {
        
        if (0 == ioctl(fd, VIDIOC_QUERYCTRL, &queryctrl)) {
            if (queryctrl.flags & V4L2_CTRL_FLAG_DISABLED) {
                continue;
            }
            
            printf("Control: %s\n", queryctrl.name);
            printf("  ID: 0x%08X\n", queryctrl.id);
            printf("  Type: %d\n", queryctrl.type);
            printf("  Min: %d, Max: %d, Step: %d, Default: %d\n",
                   queryctrl.minimum, queryctrl.maximum,
                   queryctrl.step, queryctrl.default_value);
            
            struct v4l2_control control;
            control.id = queryctrl.id;
            if (0 == ioctl(fd, VIDIOC_G_CTRL, &control)) {
                printf("  Current value: %d\n", control.value);
            }
            printf("\n");
        } else {
            if (errno == EINVAL) {
                continue;
            }
            break;
        }
    }
    
    close(fd);
}

void memory_usage_analysis(void) {
    printf("=== Memory Usage Analysis ===\n");
    
    FILE *fp = fopen("/proc/meminfo", "r");
    if (!fp) {
        printf("Error: Cannot read /proc/meminfo\n");
        return;
    }
    
    char line[256];
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "MemTotal:", 9) == 0 ||
            strncmp(line, "MemFree:", 8) == 0 ||
            strncmp(line, "MemAvailable:", 13) == 0 ||
            strncmp(line, "Buffers:", 8) == 0 ||
            strncmp(line, "Cached:", 7) == 0 ||
            strncmp(line, "CmaTotal:", 9) == 0 ||
            strncmp(line, "CmaFree:", 8) == 0) {
            printf("%s", line);
        }
    }
    
    fclose(fp);
    printf("\n");
}

void dma_info_analysis(void) {
    printf("=== DMA Information ===\n");
    
    FILE *fp = fopen("/proc/dma", "r");
    if (fp) {
        char line[256];
        while (fgets(line, sizeof(line), fp)) {
            printf("%s", line);
        }
        fclose(fp);
    } else {
        printf("DMA info not available in /proc/dma\n");
    }
    
    fp = fopen("/sys/kernel/debug/dma_buf/bufinfo", "r");
    if (fp) {
        printf("\nDMA Buffer Info:\n");
        char line[256];
        int lines = 0;
        while (fgets(line, sizeof(line), fp) && lines++ < 20) {
            printf("%s", line);
        }
        fclose(fp);
    } else {
        printf("DMA buffer info not available\n");
    }
    
    printf("\n");
}

int main(int argc, char *argv[]) {
    const char *device = DEFAULT_DEVICE;
    
    if (argc > 1) {
        if (strcmp(argv[1], "--help") == 0) {
            printf("Usage: %s [device]\n", argv[0]);
            printf("Debug utility for camera capture system\n");
            printf("Default device: %s\n", DEFAULT_DEVICE);
            printf("\nFunctions:\n");
            printf("  - List all video devices\n");
            printf("  - Show supported formats\n");
            printf("  - Display current format\n");
            printf("  - List camera controls\n");
            printf("  - Memory usage analysis\n");
            printf("  - DMA information\n");
            return 0;
        }
        device = argv[1];
    }
    
    printf("Camera Debug Utility\n");
    printf("====================\n");
    printf("Target device: %s\n\n", device);
    
    list_video_devices();
    list_supported_formats(device);
    test_current_format(device);
    test_controls(device);
    memory_usage_analysis();
    dma_info_analysis();
    
    return 0;
}