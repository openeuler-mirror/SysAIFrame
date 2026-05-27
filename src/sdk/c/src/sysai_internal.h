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

#endif /* SYSAI_INTERNAL_H */
