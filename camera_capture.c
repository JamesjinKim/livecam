#define _GNU_SOURCE
#include "camera_capture.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/time.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <jpeglib.h>
#include <time.h>

static uint64_t get_timestamp_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}

static int xioctl(int fh, int request, void *arg) {
    int r;
    do {
        r = ioctl(fh, request, arg);
    } while (-1 == r && EINTR == errno);
    return r;
}

void print_v4l2_capabilities(int fd) {
    struct v4l2_capability cap;
    
    if (-1 == xioctl(fd, VIDIOC_QUERYCAP, &cap)) {
        printf("Error: Failed to query capabilities\n");
        return;
    }
    
    printf("=== V4L2 Device Capabilities ===\n");
    printf("Driver: %s\n", cap.driver);
    printf("Card: %s\n", cap.card);
    printf("Bus info: %s\n", cap.bus_info);
    printf("Version: %u.%u.%u\n", (cap.version >> 16) & 0xFF,
                                   (cap.version >> 8) & 0xFF,
                                   cap.version & 0xFF);
    printf("Capabilities: 0x%08X\n", cap.capabilities);
    
    if (cap.capabilities & V4L2_CAP_VIDEO_CAPTURE)
        printf("  - Video capture supported\n");
    if (cap.capabilities & V4L2_CAP_STREAMING)
        printf("  - Streaming I/O supported\n");
    printf("\n");
}

void print_camera_info(const camera_t *cam) {
    printf("=== Camera Information ===\n");
    printf("File descriptor: %d\n", cam->fd);
    printf("Resolution: %dx%d\n", cam->width, cam->height);
    printf("Pixel format: 0x%08X\n", cam->pixel_format);
    printf("Number of buffers: %d\n", cam->n_buffers);
    printf("Streaming: %s\n", cam->streaming ? "Yes" : "No");
    
    for (int i = 0; i < cam->n_buffers; i++) {
        printf("Buffer %d: start=%p, length=%zu\n", 
               i, cam->buffers[i].start, cam->buffers[i].length);
    }
    printf("\n");
}

void debug_frame_info(const frame_t *frame) {
    printf("=== Frame Information ===\n");
    printf("Data pointer: %p\n", frame->data);
    printf("Size: %zu bytes\n", frame->size);
    printf("Timestamp: %lu us\n", frame->timestamp);
    
    if (frame->data && frame->size > 0) {
        printf("First 16 bytes: ");
        for (int i = 0; i < 16 && i < (int)frame->size; i++) {
            printf("%02X ", frame->data[i]);
        }
        printf("\n");
    }
    printf("\n");
}

int camera_init(camera_t *cam, const char *device, int width, int height) {
    if (!cam || !device) {
        printf("Error: Invalid parameters\n");
        return -1;
    }
    
    memset(cam, 0, sizeof(camera_t));
    cam->width = width;
    cam->height = height;
    cam->pixel_format = V4L2_PIX_FMT_YUYV;
    
    printf("Opening device: %s\n", device);
    cam->fd = open(device, O_RDWR | O_NONBLOCK, 0);
    if (-1 == cam->fd) {
        printf("Error: Cannot open '%s': %s\n", device, strerror(errno));
        return -1;
    }
    
    printf("Device opened successfully (fd=%d)\n", cam->fd);
    print_v4l2_capabilities(cam->fd);
    
    struct v4l2_format fmt;
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width = width;
    fmt.fmt.pix.height = height;
    fmt.fmt.pix.pixelformat = cam->pixel_format;
    fmt.fmt.pix.field = V4L2_FIELD_INTERLACED;
    
    printf("Setting format: %dx%d, YUYV\n", width, height);
    if (-1 == xioctl(cam->fd, VIDIOC_S_FMT, &fmt)) {
        printf("Error: VIDIOC_S_FMT failed: %s\n", strerror(errno));
        close(cam->fd);
        return -1;
    }
    
    if (fmt.fmt.pix.pixelformat != cam->pixel_format) {
        printf("Warning: Libv4l didn't accept YUYV format. Format: 0x%08X\n",
               fmt.fmt.pix.pixelformat);
    }
    
    cam->width = fmt.fmt.pix.width;
    cam->height = fmt.fmt.pix.height;
    printf("Actual format set: %dx%d\n", cam->width, cam->height);
    
    struct v4l2_requestbuffers req;
    memset(&req, 0, sizeof(req));
    req.count = MAX_BUFFERS;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    
    printf("Requesting %d buffers for memory mapping\n", MAX_BUFFERS);
    if (-1 == xioctl(cam->fd, VIDIOC_REQBUFS, &req)) {
        if (EINVAL == errno) {
            printf("Error: %s does not support memory mapping\n", device);
        } else {
            printf("Error: VIDIOC_REQBUFS failed: %s\n", strerror(errno));
        }
        close(cam->fd);
        return -1;
    }
    
    if (req.count < 2) {
        printf("Error: Insufficient buffer memory on %s\n", device);
        close(cam->fd);
        return -1;
    }
    
    cam->n_buffers = req.count;
    printf("Allocated %d buffers\n", cam->n_buffers);
    
    for (int i = 0; i < cam->n_buffers; ++i) {
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index = i;
        
        if (-1 == xioctl(cam->fd, VIDIOC_QUERYBUF, &buf)) {
            printf("Error: VIDIOC_QUERYBUF failed for buffer %d: %s\n", 
                   i, strerror(errno));
            camera_cleanup(cam);
            return -1;
        }
        
        cam->buffers[i].length = buf.length;
        cam->buffers[i].start = mmap(NULL, buf.length,
                                    PROT_READ | PROT_WRITE,
                                    MAP_SHARED, cam->fd, buf.m.offset);
        
        if (MAP_FAILED == cam->buffers[i].start) {
            printf("Error: mmap failed for buffer %d: %s\n", i, strerror(errno));
            camera_cleanup(cam);
            return -1;
        }
        
        printf("Buffer %d mapped: start=%p, length=%zu\n", 
               i, cam->buffers[i].start, cam->buffers[i].length);
    }
    
    printf("Camera initialization completed successfully\n\n");
    return 0;
}

int camera_start_streaming(camera_t *cam) {
    if (!cam || cam->fd == -1) {
        printf("Error: Camera not initialized\n");
        return -1;
    }
    
    if (cam->streaming) {
        printf("Warning: Camera already streaming\n");
        return 0;
    }
    
    printf("Queuing buffers and starting streaming\n");
    
    for (int i = 0; i < cam->n_buffers; ++i) {
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index = i;
        
        if (-1 == xioctl(cam->fd, VIDIOC_QBUF, &buf)) {
            printf("Error: VIDIOC_QBUF failed for buffer %d: %s\n", 
                   i, strerror(errno));
            return -1;
        }
        printf("Buffer %d queued\n", i);
    }
    
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (-1 == xioctl(cam->fd, VIDIOC_STREAMON, &type)) {
        printf("Error: VIDIOC_STREAMON failed: %s\n", strerror(errno));
        return -1;
    }
    
    cam->streaming = 1;
    printf("Streaming started successfully\n\n");
    return 0;
}

int camera_stop_streaming(camera_t *cam) {
    if (!cam || cam->fd == -1) {
        return -1;
    }
    
    if (!cam->streaming) {
        return 0;
    }
    
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (-1 == xioctl(cam->fd, VIDIOC_STREAMOFF, &type)) {
        printf("Error: VIDIOC_STREAMOFF failed: %s\n", strerror(errno));
        return -1;
    }
    
    cam->streaming = 0;
    printf("Streaming stopped\n");
    return 0;
}

int camera_capture_frame(camera_t *cam, frame_t *frame) {
    if (!cam || !frame || cam->fd == -1) {
        return -1;
    }
    
    if (!cam->streaming) {
        printf("Error: Camera not streaming\n");
        return -1;
    }
    
    struct v4l2_buffer buf;
    memset(&buf, 0, sizeof(buf));
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    
    if (-1 == xioctl(cam->fd, VIDIOC_DQBUF, &buf)) {
        switch (errno) {
        case EAGAIN:
            return 0;
        case EIO:
        default:
            printf("Error: VIDIOC_DQBUF failed: %s\n", strerror(errno));
            return -1;
        }
    }
    
    if (buf.index >= cam->n_buffers) {
        printf("Error: Buffer index out of range: %d\n", buf.index);
        return -1;
    }
    
    frame->data = (uint8_t *)cam->buffers[buf.index].start;
    frame->size = buf.bytesused;
    frame->timestamp = get_timestamp_us();
    
    if (-1 == xioctl(cam->fd, VIDIOC_QBUF, &buf)) {
        printf("Error: VIDIOC_QBUF failed: %s\n", strerror(errno));
        return -1;
    }
    
    return 1;
}

void camera_cleanup(camera_t *cam) {
    if (!cam) return;
    
    if (cam->streaming) {
        camera_stop_streaming(cam);
    }
    
    for (int i = 0; i < cam->n_buffers; ++i) {
        if (cam->buffers[i].start != MAP_FAILED && cam->buffers[i].start != NULL) {
            if (-1 == munmap(cam->buffers[i].start, cam->buffers[i].length)) {
                printf("Warning: munmap failed for buffer %d: %s\n", 
                       i, strerror(errno));
            }
            cam->buffers[i].start = NULL;
        }
    }
    
    if (cam->fd != -1) {
        if (-1 == close(cam->fd)) {
            printf("Warning: close failed: %s\n", strerror(errno));
        }
        cam->fd = -1;
    }
    
    printf("Camera cleanup completed\n");
}

int compress_yuyv_to_jpeg(const uint8_t *yuyv_data, int width, int height, 
                         uint8_t **jpeg_data, size_t *jpeg_size, int quality) {
    if (!yuyv_data || !jpeg_data || !jpeg_size || quality < 1 || quality > 100) {
        printf("Error: Invalid parameters for JPEG compression\n");
        return -1;
    }
    
    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr jerr;
    JSAMPROW row_pointer[1];
    int row_stride;
    
    cinfo.err = jpeg_std_error(&jerr);
    jpeg_create_compress(&cinfo);
    
    unsigned long mem_size = 0;
    unsigned char *mem_buffer = NULL;
    jpeg_mem_dest(&cinfo, &mem_buffer, &mem_size);
    
    cinfo.image_width = width;
    cinfo.image_height = height;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;
    
    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, quality, TRUE);
    
    jpeg_start_compress(&cinfo, TRUE);
    
    row_stride = width * 3;
    uint8_t *rgb_buffer = malloc(row_stride);
    if (!rgb_buffer) {
        printf("Error: Memory allocation failed for RGB buffer\n");
        jpeg_destroy_compress(&cinfo);
        return -1;
    }
    
    while (cinfo.next_scanline < cinfo.image_height) {
        int y = cinfo.next_scanline;
        const uint8_t *yuyv_row = yuyv_data + y * width * 2;
        
        for (int x = 0; x < width; x += 2) {
            int y0 = yuyv_row[x * 2];
            int u = yuyv_row[x * 2 + 1];
            int y1 = yuyv_row[x * 2 + 2];
            int v = yuyv_row[x * 2 + 3];
            
            int c0 = y0 - 16;
            int c1 = y1 - 16;
            int d = u - 128;
            int e = v - 128;
            
            int r0 = (298 * c0 + 409 * e + 128) >> 8;
            int g0 = (298 * c0 - 100 * d - 208 * e + 128) >> 8;
            int b0 = (298 * c0 + 516 * d + 128) >> 8;
            
            int r1 = (298 * c1 + 409 * e + 128) >> 8;
            int g1 = (298 * c1 - 100 * d - 208 * e + 128) >> 8;
            int b1 = (298 * c1 + 516 * d + 128) >> 8;
            
            rgb_buffer[x * 3] = (r0 < 0) ? 0 : (r0 > 255) ? 255 : r0;
            rgb_buffer[x * 3 + 1] = (g0 < 0) ? 0 : (g0 > 255) ? 255 : g0;
            rgb_buffer[x * 3 + 2] = (b0 < 0) ? 0 : (b0 > 255) ? 255 : b0;
            
            if (x + 1 < width) {
                rgb_buffer[(x + 1) * 3] = (r1 < 0) ? 0 : (r1 > 255) ? 255 : r1;
                rgb_buffer[(x + 1) * 3 + 1] = (g1 < 0) ? 0 : (g1 > 255) ? 255 : g1;
                rgb_buffer[(x + 1) * 3 + 2] = (b1 < 0) ? 0 : (b1 > 255) ? 255 : b1;
            }
        }
        
        row_pointer[0] = rgb_buffer;
        jpeg_write_scanlines(&cinfo, row_pointer, 1);
    }
    
    free(rgb_buffer);
    jpeg_finish_compress(&cinfo);
    
    *jpeg_data = malloc(mem_size);
    if (!*jpeg_data) {
        printf("Error: Memory allocation failed for JPEG data\n");
        free(mem_buffer);
        jpeg_destroy_compress(&cinfo);
        return -1;
    }
    
    memcpy(*jpeg_data, mem_buffer, mem_size);
    *jpeg_size = mem_size;
    
    free(mem_buffer);
    jpeg_destroy_compress(&cinfo);
    
    return 0;
}

int create_output_directory(const char *path) {
    if (!path) return -1;
    
    struct stat st = {0};
    if (stat(path, &st) == -1) {
        if (mkdir(path, 0755) == -1) {
            printf("Error: Failed to create directory '%s': %s\n", 
                   path, strerror(errno));
            return -1;
        }
        printf("Created directory: %s\n", path);
    }
    return 0;
}

int save_frame_to_file(const frame_t *frame, const char *filename) {
    if (!frame || !filename || !frame->data) {
        return -1;
    }
    
    FILE *fp = fopen(filename, "wb");
    if (!fp) {
        printf("Error: Cannot open file '%s': %s\n", filename, strerror(errno));
        return -1;
    }
    
    size_t written = fwrite(frame->data, 1, frame->size, fp);
    fclose(fp);
    
    if (written != frame->size) {
        printf("Error: Only wrote %zu of %zu bytes to '%s'\n", 
               written, frame->size, filename);
        return -1;
    }
    
    printf("Saved frame to '%s' (%zu bytes)\n", filename, frame->size);
    return 0;
}