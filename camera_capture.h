#ifndef CAMERA_CAPTURE_H
#define CAMERA_CAPTURE_H

#include <stdint.h>
#include <stddef.h>
#include <time.h>
#include <linux/videodev2.h>

#define MAX_BUFFERS 4
#define DEFAULT_WIDTH 1920
#define DEFAULT_HEIGHT 1080
#define DEFAULT_DEVICE "/dev/video0"

typedef struct {
    void *start;
    size_t length;
} buffer_t;

typedef struct {
    int fd;
    int width;
    int height;
    uint32_t pixel_format;
    buffer_t buffers[MAX_BUFFERS];
    int n_buffers;
    int streaming;
} camera_t;

typedef struct {
    uint8_t *data;
    size_t size;
    uint64_t timestamp;
} frame_t;

/* Function declarations */
int camera_init(camera_t *cam, const char *device, int width, int height);
int camera_start_streaming(camera_t *cam);
int camera_stop_streaming(camera_t *cam);
int camera_capture_frame(camera_t *cam, frame_t *frame);
void camera_cleanup(camera_t *cam);

/* JPEG compression */
int compress_yuyv_to_jpeg(const uint8_t *yuyv_data, int width, int height, 
                         uint8_t **jpeg_data, size_t *jpeg_size, int quality);

/* File operations */
int save_frame_to_file(const frame_t *frame, const char *filename);
int create_output_directory(const char *path);

/* Debugging utilities */
void print_camera_info(const camera_t *cam);
void print_v4l2_capabilities(int fd);
void debug_frame_info(const frame_t *frame);

#endif