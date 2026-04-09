/**
 * SysAI C SDK - Streaming support
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

#include "sysai.h"
#include "sysai_internal.h"
#include <cjson/cJSON.h>
#include <systemd/sd-bus.h>
#include <string.h>
#include <stdlib.h>

#define SYSAI_BUS_NAME "org.ctyunos.AIGateway.Chat"
#define SYSAI_OBJECT_PATH "/org/ctyunos/AIGateway/Chat"
#define SYSAI_INTERFACE "org.ctyunos.AIGateway.Chat"

/* Stream context */
typedef struct {
    sysai_client_t *client;
    char *request_id;
    char *model;
    sysai_stream_cb callback;
    void *user_data;
    bool done;
    sd_bus_slot *chunk_slot;
    sd_bus_slot *done_slot;
} stream_context_t;

/* Parse content from chunk's choices[0].delta.content */
static char *extract_chunk_content(sd_bus_message *m) {
    int r;
    const char *key;
    char *content = NULL;

    /* Enter a{sv} container */
    r = sd_bus_message_enter_container(m, 'a', "{sv}");
    if (r < 0) return NULL;

    /* Look for "choices" key */
    while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
        r = sd_bus_message_read(m, "s", &key);
        if (r < 0) {
            sd_bus_message_exit_container(m);
            continue;
        }

        if (strcmp(key, "choices") == 0) {
            /* Enter variant containing array */
            r = sd_bus_message_enter_container(m, 'v', "av");
            if (r >= 0) {
                /* Enter array of variants */
                r = sd_bus_message_enter_container(m, 'a', "v");
                if (r >= 0) {
                    /* Get first choice */
                    r = sd_bus_message_enter_container(m, 'v', "a{sv}");
                    if (r >= 0) {
                        r = sd_bus_message_enter_container(m, 'a', "{sv}");
                        if (r >= 0) {
                            /* Parse choice dict */
                            const char *choice_key;
                            while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
                                r = sd_bus_message_read(m, "s", &choice_key);
                                if (r < 0) {
                                    sd_bus_message_exit_container(m);
                                    continue;
                                }

                                if (strcmp(choice_key, "delta") == 0) {
                                    /* Enter delta dict */
                                    r = sd_bus_message_enter_container(m, 'v', "a{sv}");
                                    if (r >= 0) {
                                        r = sd_bus_message_enter_container(m, 'a', "{sv}");
                                        if (r >= 0) {
                                            const char *delta_key;
                                            while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
                                                r = sd_bus_message_read(m, "s", &delta_key);
                                                if (r >= 0 && strcmp(delta_key, "content") == 0) {
                                                    const char *content_str;
                                                    r = sd_bus_message_enter_container(m, 'v', "s");
                                                    if (r >= 0) {
                                                        r = sd_bus_message_read(m, "s", &content_str);
                                                        if (r >= 0 && content_str && strlen(content_str) > 0) {
                                                            content = strdup(content_str);
                                                        }
                                                        sd_bus_message_exit_container(m);
                                                    }
                                                } else {
                                                    sd_bus_message_skip(m, "v");
                                                }
                                                sd_bus_message_exit_container(m);
                                            }
                                            sd_bus_message_exit_container(m);
                                        }
                                        sd_bus_message_exit_container(m);
                                    }
                                } else {
                                    sd_bus_message_skip(m, "v");
                                }
                                sd_bus_message_exit_container(m);
                            }
                            sd_bus_message_exit_container(m);
                        }
                        sd_bus_message_exit_container(m);
                    }
                    sd_bus_message_exit_container(m);
                }
                sd_bus_message_exit_container(m);
            }
            break;
        } else {
            sd_bus_message_skip(m, "v");
        }
        sd_bus_message_exit_container(m);
    }

    sd_bus_message_exit_container(m);
    return content;
}

/* Signal handlers */
static int on_stream_chunk(sd_bus_message *m, void *userdata, sd_bus_error *ret_error) {
    stream_context_t *ctx = userdata;
    const char *request_id;
    int r;

    /* Read request_id */
    r = sd_bus_message_read(m, "s", &request_id);
    if (r < 0) return 0;

    /* Filter by request_id */
    if (strcmp(request_id, ctx->request_id) != 0) {
        return 0;
    }

    /* Extract content from chunk */
    char *content = extract_chunk_content(m);

    /* Call callback with content */
    if (ctx->callback && content) {
        ctx->callback(content, 0, ctx->user_data);
        free(content);
    }

    return 0;
}

static int on_stream_done(sd_bus_message *m, void *userdata, sd_bus_error *ret_error) {
    stream_context_t *ctx = userdata;
    const char *request_id;
    int r;

    /* Read request_id */
    r = sd_bus_message_read(m, "s", &request_id);
    if (r < 0) return 0;

    /* Filter by request_id */
    if (strcmp(request_id, ctx->request_id) != 0) {
        return 0;
    }

    /* Mark as done */
    ctx->done = true;

    /* Call callback with is_done=1 */
    if (ctx->callback) {
        ctx->callback(NULL, 1, ctx->user_data);
    }

    return 0;
}

int sysai_chat_stream(
    sysai_client_t *client,
    const sysai_message_t **messages,
    const sysai_options_t *options,
    sysai_stream_cb callback,
    void *user_data
) {
    if (!client || !messages || !callback) {
        return SYSAI_ERR_INVALID;
    }

    sd_bus_error error = SD_BUS_ERROR_NULL;
    sd_bus_message *m = NULL, *reply = NULL;
    stream_context_t ctx = {0};
    int r;

    ctx.client = client;
    ctx.callback = callback;
    ctx.user_data = user_data;

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
        return SYSAI_ERR_CONNECTION;
    }

    /* Build request with stream=true */
    r = sysai_build_request_dict(m, messages, options, true);
    if (r < 0) {
        sd_bus_message_unref(m);
        return SYSAI_ERR_INVALID;
    }

    /* Call method to get initial response */
    r = sd_bus_call(client->bus, m, 30000000, &error, &reply);
    if (r < 0) {
        sd_bus_error_free(&error);
        sd_bus_message_unref(m);
        return SYSAI_ERR_SERVER;
    }

    /* Extract request_id from response */
    ctx.request_id = extract_string_from_variant_dict(reply, "id");
    ctx.model = extract_string_from_variant_dict(reply, "model");

    if (!ctx.request_id) {
        sd_bus_message_unref(m);
        sd_bus_message_unref(reply);
        return SYSAI_ERR_PARSE;
    }

    /* Build match rules for signals */
    char match_chunk[256];
    char match_done[256];
    snprintf(match_chunk, sizeof(match_chunk),
             "type='signal',interface='%s',member='StreamChunk',arg0='%s'",
             SYSAI_INTERFACE, ctx.request_id);
    snprintf(match_done, sizeof(match_done),
             "type='signal',interface='%s',member='StreamDone',arg0='%s'",
             SYSAI_INTERFACE, ctx.request_id);

    /* Add match rules */
    r = sd_bus_add_match(client->bus, &ctx.chunk_slot, match_chunk, on_stream_chunk, &ctx);
    if (r < 0) {
        free(ctx.request_id);
        free(ctx.model);
        sd_bus_message_unref(m);
        sd_bus_message_unref(reply);
        return SYSAI_ERR_CONNECTION;
    }

    r = sd_bus_add_match(client->bus, &ctx.done_slot, match_done, on_stream_done, &ctx);
    if (r < 0) {
        sd_bus_slot_unref(ctx.chunk_slot);
        free(ctx.request_id);
        free(ctx.model);
        sd_bus_message_unref(m);
        sd_bus_message_unref(reply);
        return SYSAI_ERR_CONNECTION;
    }

    /* Process messages until stream is done */
    while (!ctx.done) {
        r = sd_bus_process(client->bus, NULL);
        if (r < 0) break;

        if (r == 0) {
            r = sd_bus_wait(client->bus, 60000000);  /* 60 second timeout */
            if (r < 0) break;
        }
    }

    /* Cleanup */
    sd_bus_slot_unref(ctx.chunk_slot);
    sd_bus_slot_unref(ctx.done_slot);
    free(ctx.request_id);
    free(ctx.model);
    sd_bus_message_unref(m);
    sd_bus_message_unref(reply);

    return ctx.done ? SYSAI_OK : SYSAI_ERR_TIMEOUT;
}
