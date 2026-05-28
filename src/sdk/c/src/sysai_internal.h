/**
 * SysAI C SDK - Internal declarations
 *
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

#ifndef SYSAI_INTERNAL_H
#define SYSAI_INTERNAL_H

#include "sysai.h"
#include <systemd/sd-bus.h>

/* Client structure */
struct sysai_client {
    sd_bus *bus;
    char *last_error;
    int last_error_code;
};

/* Message structure */
struct sysai_message {
    char *role;
    char *content;
};

/* Options structure */
struct sysai_options {
    char *model;
    double temperature;
    int max_tokens;
    double top_p;
    bool has_temperature;
    bool has_max_tokens;
    bool has_top_p;
};

/* Response structure */
struct sysai_response {
    char *id;
    char *model;
    char *content;
    char *finish_reason;
    int total_tokens;
};

/* Internal functions */
sysai_client_t *sysai_client_new_internal(bool use_session);

int sysai_build_request_dict(
    sd_bus_message *m,
    const sysai_message_t **messages,
    const sysai_options_t *options,
    bool stream
);

sysai_response_t *sysai_parse_response(sd_bus_message *m);

/* Helper functions from sysai_types.c */
char *extract_string_from_variant_dict(sd_bus_message *m, const char *key);
int extract_int_from_variant_dict(sd_bus_message *m, const char *key);

#endif /* SYSAI_INTERNAL_H */