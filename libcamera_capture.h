#ifndef LIBCAMERA_CAPTURE_H
#define LIBCAMERA_CAPTURE_H

#include <stdint.h>
#include <stddef.h>
#include <time.h>

#define DEFAULT_WIDTH 1920
#define DEFAULT_HEIGHT 1080

typedef struct {
    uint8_t *data;
    size_t size;
    uint64_t timestamp;
    int width;
    int height;
} libcamera_frame_t;

typedef struct {
    void *camera_mgr;
    void *camera;
    void *config;
    int streaming;
    int width;
    int height;
} libcamera_t;

/* Function declarations */
int libcamera_init(libcamera_t *cam, int width, int height);
int libcamera_start_streaming(libcamera_t *cam);
int libcamera_stop_streaming(libcamera_t *cam);
int libcamera_capture_frame(libcamera_t *cam, libcamera_frame_t *frame);
void libcamera_cleanup(libcamera_t *cam);

/* JPEG compression for YUV420 */
int compress_yuv420_to_jpeg(const uint8_t *yuv_data, int width, int height, 
                           uint8_t **jpeg_data, size_t *jpeg_size, int quality);

#endif