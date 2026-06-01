/**
 * SysAI C SDK - Client implementation
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

#include "sysai.h"
#include "sysai_internal.h"
#include <systemd/sd-bus.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>

/* D-Bus constants */
#define SYSAI_BUS_NAME "org.ctyunos.AIGateway.Chat"
#define SYSAI_OBJECT_PATH "/org/ctyunos/AIGateway/Chat"
#define SYSAI_INTERFACE "org.ctyunos.AIGateway.Chat"

/* ============================================================================
 * Internal Helpers
 * ========================================================================= */

static void set_error(sysai_client_t *client, int code, const char *fmt, ...) {
    if (!client) return;

    free(client->last_error);
    client->last_error_code = code;

    va_list args;
    va_start(args, fmt);
    int size = vsnprintf(NULL, 0, fmt, args);
    va_end(args);

    if (size < 0) {
        client->last_error = NULL;
        return;
    }

    client->last_error = malloc(size + 1);
    if (!client->last_error) return;

    va_start(args, fmt);
    vsnprintf(client->last_error, size + 1, fmt, args);
    va_end(args);
}

/* ============================================================================
 * Client Management
 * ========================================================================= */

sysai_client_t *sysai_client_new(void) {
    return sysai_client_new_internal(false);
}

sysai_client_t *sysai_client_new_session(void) {
    return sysai_client_new_internal(true);
}

sysai_client_t *sysai_client_new_internal(bool use_session) {
    sysai_client_t *client = calloc(1, sizeof(sysai_client_t));
    if (!client) return NULL;

    int r;
    if (use_session) {
        r = sd_bus_open_user(&client->bus);
    } else {
        r = sd_bus_open_system(&client->bus);
    }

    if (r < 0) {
        set_error(client, SYSAI_ERR_CONNECTION,
                 "Failed to connect to D-Bus: %s", strerror(-r));
        free(client);
        return NULL;
    }

    return client;
}

void sysai_client_free(sysai_client_t *client) {
    if (!client) return;

    if (client->bus) {
        sd_bus_unref(client->bus);
    }
    free(client->last_error);
    free(client);
}

const char *sysai_last_error(sysai_client_t *client) {
    return client ? client->last_error : NULL;
}

int sysai_last_error_code(sysai_client_t *client) {
    return client ? client->last_error_code : SYSAI_ERR_CONNECTION;
}

/* ============================================================================
 * Message Construction
 * ========================================================================= */

sysai_message_t *sysai_message_new(const char *role, const char *content) {
    if (!role || !content) return NULL;

    sysai_message_t *msg = calloc(1, sizeof(sysai_message_t));
    if (!msg) return NULL;

    msg->role = strdup(role);
    msg->content = strdup(content);

    if (!msg->role || !msg->content) {
        free(msg->role);
        free(msg->content);
        free(msg);
        return NULL;
    }

    return msg;
}

void sysai_message_free(sysai_message_t *message) {
    if (!message) return;
    free(message->role);
    free(message->content);
    free(message);
}

const char *sysai_message_get_role(const sysai_message_t *message) {
    return message ? message->role : NULL;
}

const char *sysai_message_get_content(const sysai_message_t *message) {
    return message ? message->content : NULL;
}

/* ============================================================================
 * Request Options
 * ========================================================================= */

sysai_options_t *sysai_options_new(void) {
    sysai_options_t *opts = calloc(1, sizeof(sysai_options_t));
    return opts;
}

void sysai_options_set_model(sysai_options_t *opts, const char *model) {
    if (!opts) return;
    free(opts->model);
    opts->model = model ? strdup(model) : NULL;
}

void sysai_options_set_temperature(sysai_options_t *opts, double temperature) {
    if (!opts) return;
    opts->temperature = temperature;
    opts->has_temperature = true;
}

void sysai_options_set_max_tokens(sysai_options_t *opts, int max_tokens) {
    if (!opts) return;
    opts->max_tokens = max_tokens;
    opts->has_max_tokens = true;
}

void sysai_options_set_top_p(sysai_options_t *opts, double top_p) {
    if (!opts) return;
    opts->top_p = top_p;
    opts->has_top_p = true;
}

void sysai_options_free(sysai_options_t *opts) {
    if (!opts) return;
    free(opts->model);
    free(opts);
}

const char *sysai_options_get_model(const sysai_options_t *opts) {
    return opts ? opts->model : NULL;
}

double sysai_options_get_temperature(const sysai_options_t *opts, bool *has_value) {
    if (has_value) *has_value = opts ? opts->has_temperature : false;
    return opts ? opts->temperature : 0.0;
}

int sysai_options_get_max_tokens(const sysai_options_t *opts, bool *has_value) {
    if (has_value) *has_value = opts ? opts->has_max_tokens : false;
    return opts ? opts->max_tokens : 0;
}

double sysai_options_get_top_p(const sysai_options_t *opts, bool *has_value) {
    if (has_value) *has_value = opts ? opts->has_top_p : false;
    return opts ? opts->top_p : 0.0;
}

/* ============================================================================
 * Non-Streaming Chat
 * ========================================================================= */

sysai_response_t *sysai_chat(
    sysai_client_t *client,
    const sysai_message_t **messages,
    const sysai_options_t *options
) {
    if (!client || !messages) {
        if (client) set_error(client, SYSAI_ERR_INVALID, "Invalid parameters");
        return NULL;
    }

    sd_bus_error error = SD_BUS_ERROR_NULL;
    sd_bus_message *m = NULL, *reply = NULL;
    int r;

    /* Create method call */
    r = sd_bus_message_new_method_call(
        client->bus,
        &m,
        SYSAI_BUS_NAME,
        SYSAI_OBJECT_PATH,
        SYSAI_INTERFACE,
        "ChatCompletion"
    );

    if (r < 0) {
        set_error(client, SYSAI_ERR_CONNECTION, "Failed to create method call: %s", strerror(-r));
        goto cleanup;
    }

    /* Build request dictionary */
    r = sysai_build_request_dict(m, messages, options, false);
    if (r < 0) {
        set_error(client, SYSAI_ERR_INVALID, "Failed to build request: %s", strerror(-r));
        goto cleanup;
    }

    /* Call method */
    r = sd_bus_call(client->bus, m, 120000000, &error, &reply);  /* 120 second timeout */
    if (r < 0) {
        if (sd_bus_error_has_name(&error, SD_BUS_ERROR_SERVICE_UNKNOWN)) {
            set_error(client, SYSAI_ERR_SERVICE, "Service not available");
        } else if (sd_bus_error_has_name(&error, SD_BUS_ERROR_TIMEOUT)) {
            set_error(client, SYSAI_ERR_TIMEOUT, "Request timeout");
        } else {
            set_error(client, SYSAI_ERR_SERVER, "D-Bus call failed: %s", error.message);
        }
        goto cleanup;
    }

    /* Parse response */
    sysai_response_t *response = sysai_parse_response(reply);
    if (!response) {
        set_error(client, SYSAI_ERR_PARSE, "Failed to parse response");
        goto cleanup;
    }

    sd_bus_error_free(&error);
    sd_bus_message_unref(m);
    sd_bus_message_unref(reply);
    return response;

cleanup:
    sd_bus_error_free(&error);
    sd_bus_message_unref(m);
    sd_bus_message_unref(reply);
    return NULL;
}

/* Response construction */
sysai_response_t *sysai_response_new(
    const char *id,
    const char *model,
    const char *content,
    const char *finish_reason,
    int total_tokens
) {
    sysai_response_t *resp = calloc(1, sizeof(sysai_response_t));
    if (!resp) return NULL;

    resp->id = strdup(id ? id : "");
    resp->model = strdup(model ? model : "");
    resp->content = strdup(content ? content : "");
    resp->finish_reason = finish_reason ? strdup(finish_reason) : NULL;
    resp->total_tokens = total_tokens;

    if (!resp->id || !resp->model || !resp->content) {
        sysai_response_free(resp);
        return NULL;
    }
    if (finish_reason && !resp->finish_reason) {
        sysai_response_free(resp);
        return NULL;
    }

    return resp;
}

/* Response accessors */
const char *sysai_response_get_content(const sysai_response_t *resp) {
    return resp ? resp->content : NULL;
}

const char *sysai_response_get_model(const sysai_response_t *resp) {
    return resp ? resp->model : NULL;
}

const char *sysai_response_get_id(const sysai_response_t *resp) {
    return resp ? resp->id : NULL;
}

int sysai_response_get_total_tokens(const sysai_response_t *resp) {
    return resp ? resp->total_tokens : 0;
}

const char *sysai_response_get_finish_reason(const sysai_response_t *resp) {
    return resp ? resp->finish_reason : NULL;
}

void sysai_response_free(sysai_response_t *resp) {
    if (!resp) return;
    free(resp->id);
    free(resp->model);
    free(resp->content);
    free(resp->finish_reason);
    free(resp);
}

/* ============================================================================
 * Model Management
 * ========================================================================= */

char **sysai_list_models(sysai_client_t *client) {
    if (!client) return NULL;

    sd_bus_error error = SD_BUS_ERROR_NULL;
    sd_bus_message *reply = NULL;
    char **models = NULL;
    int r;

    r = sd_bus_call_method(
        client->bus,
        SYSAI_BUS_NAME,
        SYSAI_OBJECT_PATH,
        SYSAI_INTERFACE,
        "GetChatModels",
        &error,
        &reply,
        ""
    );

    if (r < 0) {
        set_error(client, SYSAI_ERR_SERVER, "Failed to list models: %s",
                 error.message ? error.message : strerror(-r));
        goto cleanup;
    }

    /* Parse array of strings */
    r = sd_bus_message_enter_container(reply, 'a', "s");
    if (r < 0) goto cleanup;

    /* Count models */
    size_t count = 0;
    const char *model;
    while (sd_bus_message_read(reply, "s", &model) > 0) {
        count++;
    }

    /* Rewind */
    sd_bus_message_rewind(reply, true);
    sd_bus_message_enter_container(reply, 'a', "s");

    /* Allocate array */
    models = calloc(count + 1, sizeof(char *));
    if (!models) goto cleanup;

    /* Copy strings */
    size_t i = 0;
    while (sd_bus_message_read(reply, "s", &model) > 0 && i < count) {
        models[i] = strdup(model);
        if (!models[i]) {
            sysai_free_models(models);
            models = NULL;
            goto cleanup;
        }
        i++;
    }

cleanup:
    sd_bus_error_free(&error);
    sd_bus_message_unref(reply);
    return models;
}

void sysai_free_models(char **models) {
    if (!models) return;
    for (size_t i = 0; models[i]; i++) {
        free(models[i]);
    }
    free(models);
}