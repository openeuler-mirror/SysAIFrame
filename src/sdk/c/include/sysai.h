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
#define SYSAI_ERR_PARSE        -7
#define SYSAI_ERR_MEMORY       -8

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

/* ============================================================================
 * Message Construction
 * ========================================================================= */

/**
 * Create a new message
 *
 * @param role Message role ("user", "system", "assistant")
 * @param content Message content
 * @return Message handle or NULL on error
 */
SYSAI_API sysai_message_t *sysai_message_new(const char *role, const char *content);

/**
 * Get message role
 *
 * @param message Message handle
 * @return Role string
 */
SYSAI_API const char *sysai_message_get_role(const sysai_message_t *message);

/**
 * Get message content
 *
 * @param message Message handle
 * @return Content string
 */
SYSAI_API const char *sysai_message_get_content(const sysai_message_t *message);

/**
 * Free a message
 *
 * @param message Message handle
 */
SYSAI_API void sysai_message_free(sysai_message_t *message);

/* ============================================================================
 * Request Options
 * ========================================================================= */

/**
 * Create new request options
 *
 * @return Options handle or NULL on error
 */
SYSAI_API sysai_options_t *sysai_options_new(void);

/**
 * Set model name
 *
 * @param opts Options handle
 * @param model Model name
 */
SYSAI_API void sysai_options_set_model(sysai_options_t *opts, const char *model);

/**
 * Set temperature
 *
 * @param opts Options handle
 * @param temperature Temperature value (0.0 to 2.0)
 */
SYSAI_API void sysai_options_set_temperature(sysai_options_t *opts, double temperature);

/**
 * Set max tokens
 *
 * @param opts Options handle
 * @param max_tokens Maximum tokens to generate
 */
SYSAI_API void sysai_options_set_max_tokens(sysai_options_t *opts, int max_tokens);

/**
 * Set top_p
 *
 * @param opts Options handle
 * @param top_p Top-p value (0.0 to 1.0)
 */
SYSAI_API void sysai_options_set_top_p(sysai_options_t *opts, double top_p);

/**
 * Get model name
 *
 * @param opts Options handle
 * @return Model name or NULL
 */
SYSAI_API const char *sysai_options_get_model(const sysai_options_t *opts);

/**
 * Get temperature
 *
 * @param opts Options handle
 * @param has_value Output: whether temperature was set
 * @return Temperature value (0.0 if not set)
 */
SYSAI_API double sysai_options_get_temperature(const sysai_options_t *opts, bool *has_value);

/**
 * Get max tokens
 *
 * @param opts Options handle
 * @param has_value Output: whether max_tokens was set
 * @return Max tokens value (0 if not set)
 */
SYSAI_API int sysai_options_get_max_tokens(const sysai_options_t *opts, bool *has_value);

/**
 * Get top_p
 *
 * @param opts Options handle
 * @param has_value Output: whether top_p was set
 * @return Top-p value (0.0 if not set)
 */
SYSAI_API double sysai_options_get_top_p(const sysai_options_t *opts, bool *has_value);

/**
 * Free options
 *
 * @param opts Options handle
 */
SYSAI_API void sysai_options_free(sysai_options_t *opts);

/* ============================================================================
 * Chat Completion
 * ========================================================================= */

/**
 * Send a chat completion request (non-streaming)
 *
 * @param client Client handle
 * @param messages NULL-terminated array of messages
 * @param options Request options (can be NULL)
 * @return Response handle or NULL on error
 */
SYSAI_API sysai_response_t *sysai_chat(
    sysai_client_t *client,
    const sysai_message_t **messages,
    const sysai_options_t *options
);

/**
 * Send a chat completion request with streaming
 *
 * @param client Client handle
 * @param messages NULL-terminated array of messages
 * @param options Request options (can be NULL)
 * @param callback Callback for receiving chunks
 * @param user_data User data passed to callback
 * @return SYSAI_OK on success, error code on failure
 */
SYSAI_API int sysai_chat_stream(
    sysai_client_t *client,
    const sysai_message_t **messages,
    const sysai_options_t *options,
    sysai_stream_cb callback,
    void *user_data
);

/* ============================================================================
 * Response Access
 * ========================================================================= */

/**
 * Create a new response (for testing / manual construction)
 *
 * @param id Response ID (can be "")
 * @param model Model name (can be "")
 * @param content Response content (can be "")
 * @param finish_reason Finish reason (can be NULL)
 * @param total_tokens Total tokens used
 * @return Response handle or NULL on error
 */
SYSAI_API sysai_response_t *sysai_response_new(
    const char *id,
    const char *model,
    const char *content,
    const char *finish_reason,
    int total_tokens
);

/**
 * Get response content
 *
 * @param resp Response handle
 * @return Content string
 */
SYSAI_API const char *sysai_response_get_content(const sysai_response_t *resp);

/**
 * Get response model
 *
 * @param resp Response handle
 * @return Model name
 */
SYSAI_API const char *sysai_response_get_model(const sysai_response_t *resp);

/**
 * Get response ID
 *
 * @param resp Response handle
 * @return Response ID
 */
SYSAI_API const char *sysai_response_get_id(const sysai_response_t *resp);

/**
 * Get total tokens used
 *
 * @param resp Response handle
 * @return Total tokens
 */
SYSAI_API int sysai_response_get_total_tokens(const sysai_response_t *resp);

/**
 * Get finish reason
 *
 * @param resp Response handle
 * @return Finish reason or NULL
 */
SYSAI_API const char *sysai_response_get_finish_reason(const sysai_response_t *resp);

/**
 * Free response
 *
 * @param resp Response handle
 */
SYSAI_API void sysai_response_free(sysai_response_t *resp);

/* ============================================================================
 * Model Management
 * ========================================================================= */

/**
 * List available models
 *
 * @param client Client handle
 * @return NULL-terminated array of model names, or NULL on error
 */
SYSAI_API char **sysai_list_models(sysai_client_t *client);

/**
 * Free models array
 *
 * @param models Models array from sysai_list_models
 */
SYSAI_API void sysai_free_models(char **models);

#ifdef __cplusplus
}
#endif

#endif /* SYSAI_H */