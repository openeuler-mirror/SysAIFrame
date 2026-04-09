/**
 * SysAI C SDK - Public API
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

#ifndef SYSAI_H
#define SYSAI_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>

/* Version */
#define SYSAI_VERSION_MAJOR 0
#define SYSAI_VERSION_MINOR 1
#define SYSAI_VERSION_PATCH 0

/* Symbol visibility */
#if defined(_WIN32) || defined(__CYGWIN__)
  #ifdef SYSAI_BUILDING
    #define SYSAI_API __declspec(dllexport)
  #else
    #define SYSAI_API __declspec(dllimport)
  #endif
#else
  #if __GNUC__ >= 4
    #define SYSAI_API __attribute__((visibility("default")))
  #else
    #define SYSAI_API
  #endif
#endif

/* Error codes */
#define SYSAI_OK                0
#define SYSAI_ERR_CONNECTION   -1
#define SYSAI_ERR_SERVICE      -2
#define SYSAI_ERR_INVALID      -3
#define SYSAI_ERR_TIMEOUT      -4
#define SYSAI_ERR_MODEL        -5
#define SYSAI_ERR_SERVER       -6
#define SYSAI_ERR_PARSE       -7
#define SYSAI_ERR_MEMORY      -8

/* Opaque types */
typedef struct sysai_client sysai_client_t;
typedef struct sysai_message sysai_message_t;
typedef struct sysai_options sysai_options_t;
typedef struct sysai_response sysai_response_t;

/* Streaming callback */
typedef void (*sysai_stream_cb)(const char *content, int is_done, void *user_data);

/* ============================================================================
 * Client Management
 * ========================================================================= */

/**
 * Create a new SysAI client connected to system bus
 *
 * @return Client handle or NULL on error
 */
SYSAI_API sysai_client_t *sysai_client_new(void);

/**
 * Create a new SysAI client connected to session bus
 *
 * @return Client handle or NULL on error
 */
SYSAI_API sysai_client_t *sysai_client_new_session(void);

/**
 * Free a SysAI client
 *
 * @param client Client handle
 */
SYSAI_API void sysai_client_free(sysai_client_t *client);

/**
 * Get last error message
 *
 * @param client Client handle
 * @return Error message string or NULL
 */
SYSAI_API const char *sysai_last_error(sysai_client_t *client);

/**
 * Get last error code
 *
 * @param client Client handle
 * @return Error code
 */
SYSAI_API int sysai_last_error_code(sysai_client_t *client);

#endif /* SYSAI_H */
