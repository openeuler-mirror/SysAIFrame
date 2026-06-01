/**
 * SysAI C SDK - Type conversion and parsing
 * 
 * Copyright (C) 2025 CTyunOS. All Rights Reserved.
 */

#include "sysai.h"
#include "sysai_internal.h"
#include <cjson/cJSON.h>
#include <systemd/sd-bus.h>
#include <string.h>
#include <stdlib.h>

/* ============================================================================
 * Request Building
 * ========================================================================= */

int sysai_build_request_dict(
    sd_bus_message *m,
    const sysai_message_t **messages,
    const sysai_options_t *options,
    bool stream
) {
    int r;
    
    /* Open a{sv} container */
    r = sd_bus_message_open_container(m, 'a', "{sv}");
    if (r < 0) return r;
    
    /* Add messages array */
    r = sd_bus_message_open_container(m, 'e', "sv");
    if (r < 0) return r;
    r = sd_bus_message_append(m, "s", "messages");
    if (r < 0) return r;
    
    /* Open variant for messages array */
    r = sd_bus_message_open_container(m, 'v', "av");
    if (r < 0) return r;
    r = sd_bus_message_open_container(m, 'a', "v");
    if (r < 0) return r;
    
    /* Add each message as a{sv} */
    for (size_t i = 0; messages[i]; i++) {
        r = sd_bus_message_open_container(m, 'v', "a{sv}");
        if (r < 0) return r;
        r = sd_bus_message_open_container(m, 'a', "{sv}");
        if (r < 0) return r;
        
        /* role */
        r = sd_bus_message_append(m, "{sv}", "role", "s", messages[i]->role);
        if (r < 0) return r;
        
        /* content */
        r = sd_bus_message_append(m, "{sv}", "content", "s", messages[i]->content);
        if (r < 0) return r;
        
        r = sd_bus_message_close_container(m);  /* a{sv} */
        if (r < 0) return r;
        r = sd_bus_message_close_container(m);  /* v */
        if (r < 0) return r;
    }
    
    r = sd_bus_message_close_container(m);  /* av */
    if (r < 0) return r;
    r = sd_bus_message_close_container(m);  /* v */
    if (r < 0) return r;
    r = sd_bus_message_close_container(m);  /* e */
    if (r < 0) return r;
    
    /* Add stream flag */
    r = sd_bus_message_append(m, "{sv}", "stream", "b", stream);
    if (r < 0) return r;
    
    /* Add optional parameters */
    if (options) {
        if (options->model) {
            r = sd_bus_message_append(m, "{sv}", "model", "s", options->model);
            if (r < 0) return r;
        }
        if (options->has_temperature) {
            r = sd_bus_message_append(m, "{sv}", "temperature", "d", options->temperature);
            if (r < 0) return r;
        }
        if (options->has_max_tokens) {
            r = sd_bus_message_append(m, "{sv}", "max_tokens", "x", (int64_t)options->max_tokens);
            if (r < 0) return r;
        }
        if (options->has_top_p) {
            r = sd_bus_message_append(m, "{sv}", "top_p", "d", options->top_p);
            if (r < 0) return r;
        }
    }
    
    /* Close a{sv} container */
    r = sd_bus_message_close_container(m);
    if (r < 0) return r;
    
    return 0;
}

/* ============================================================================
 * Response Parsing Helpers
 * ========================================================================= */

char *extract_string_from_variant_dict(sd_bus_message *m, const char *key) {
    int r;
    const char *k, *value;

    r = sd_bus_message_rewind(m, true);
    if (r < 0) return NULL;

    r = sd_bus_message_enter_container(m, 'a', "{sv}");
    if (r < 0) return NULL;

    while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
        r = sd_bus_message_read(m, "s", &k);
        if (r < 0) {
            sd_bus_message_exit_container(m);
            continue;
        }

        if (strcmp(k, key) == 0) {
            r = sd_bus_message_enter_container(m, 'v', "s");
            if (r >= 0) {
                r = sd_bus_message_read(m, "s", &value);
                if (r >= 0 && value && strlen(value) > 0) {
                    char *result = strdup(value);
                    sd_bus_message_exit_container(m);  /* v */
                    sd_bus_message_exit_container(m);  /* e */
                    sd_bus_message_exit_container(m);  /* a{sv} */
                    return result;
                }
                sd_bus_message_exit_container(m);  /* v */
            }
        }

        sd_bus_message_skip(m, "v");
        sd_bus_message_exit_container(m);  /* e */
    }

    sd_bus_message_exit_container(m);  /* a{sv} */
    return NULL;
}

int extract_int_from_variant_dict(sd_bus_message *m, const char *key) {
    int r;
    const char *k;
    int64_t value;

    r = sd_bus_message_rewind(m, true);
    if (r < 0) return 0;

    r = sd_bus_message_enter_container(m, 'a', "{sv}");
    if (r < 0) return 0;

    while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
        r = sd_bus_message_read(m, "s", &k);
        if (r < 0) {
            sd_bus_message_exit_container(m);
            continue;
        }

        if (strcmp(k, key) == 0) {
            r = sd_bus_message_enter_container(m, 'v', "x");
            if (r >= 0) {
                r = sd_bus_message_read(m, "x", &value);
                if (r >= 0) {
                    sd_bus_message_exit_container(m);  /* v */
                    sd_bus_message_exit_container(m);  /* e */
                    sd_bus_message_exit_container(m);  /* a{sv} */
                    return (int)value;
                }
                sd_bus_message_exit_container(m);  /* v */
            }
        }

        sd_bus_message_skip(m, "v");
        sd_bus_message_exit_container(m);  /* e */
    }

    sd_bus_message_exit_container(m);  /* a{sv} */
    return 0;
}

/* Extract nested array from variant dict */
static sd_bus_message *extract_array_from_variant_dict(sd_bus_message *m, const char *key) {
    int r;
    const char *k;
    
    r = sd_bus_message_rewind(m, true);
    if (r < 0) return NULL;
    
    r = sd_bus_message_enter_container(m, 'a', "{sv}");
    if (r < 0) return NULL;
    
    while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
        r = sd_bus_message_read(m, "s", &k);
        if (r < 0) {
            sd_bus_message_exit_container(m);
            continue;
        }
        
        if (strcmp(k, key) == 0) {
            /* Found the key, return message positioned at variant */
            return m;
        }
        
        sd_bus_message_skip(m, "v");
        sd_bus_message_exit_container(m);
    }
    
    return NULL;
}

/* ============================================================================
 * Response Parsing
 * ========================================================================= */

sysai_response_t *sysai_parse_response(sd_bus_message *m) {
    if (!m) return NULL;
    
    sysai_response_t *resp = calloc(1, sizeof(sysai_response_t));
    if (!resp) return NULL;
    
    /* Extract basic fields */
    resp->id = extract_string_from_variant_dict(m, "id");
    resp->model = extract_string_from_variant_dict(m, "model");
    
    /* Extract content from choices[0].message.content */
    int r = sd_bus_message_rewind(m, true);
    if (r < 0) goto fallback;
    
    r = sd_bus_message_enter_container(m, 'a', "{sv}");
    if (r < 0) goto fallback;
    
    const char *key;
    bool found_choices = false;
    
    while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
        r = sd_bus_message_read(m, "s", &key);
        if (r < 0) {
            sd_bus_message_exit_container(m);
            continue;
        }
        
        if (strcmp(key, "choices") == 0) {
            found_choices = true;
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
                                
                                if (strcmp(choice_key, "message") == 0) {
                                    /* Enter message dict */
                                    r = sd_bus_message_enter_container(m, 'v', "a{sv}");
                                    if (r >= 0) {
                                        r = sd_bus_message_enter_container(m, 'a', "{sv}");
                                        if (r >= 0) {
                                            const char *msg_key;
                                            while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
                                                r = sd_bus_message_read(m, "s", &msg_key);
                                                if (r >= 0 && strcmp(msg_key, "content") == 0) {
                                                    const char *content;
                                                    r = sd_bus_message_enter_container(m, 'v', "s");
                                                    if (r >= 0) {
                                                        r = sd_bus_message_read(m, "s", &content);
                                                        if (r >= 0 && content) {
                                                            resp->content = strdup(content);
                                                        }
                                                        sd_bus_message_exit_container(m);
                                                    }
                                                } else {
                                                    sd_bus_message_skip(m, "v");
                                                }
                                                sd_bus_message_exit_container(m);
                                            }
                                        }
                                        sd_bus_message_exit_container(m);
                                    }
                                } else if (strcmp(choice_key, "finish_reason") == 0) {
                                    const char *finish;
                                    r = sd_bus_message_enter_container(m, 'v', "s");
                                    if (r >= 0) {
                                        r = sd_bus_message_read(m, "s", &finish);
                                        if (r >= 0 && finish && strlen(finish) > 0) {
                                            resp->finish_reason = strdup(finish);
                                        }
                                        sd_bus_message_exit_container(m);
                                    }
                                } else {
                                    sd_bus_message_skip(m, "v");
                                }
                                sd_bus_message_exit_container(m);
                            }
                        }
                    }
                }
            }
            break;
        } else if (strcmp(key, "usage") == 0) {
            /* Parse usage */
            r = sd_bus_message_enter_container(m, 'v', "a{sv}");
            if (r >= 0) {
                r = sd_bus_message_enter_container(m, 'a', "{sv}");
                if (r >= 0) {
                    const char *usage_key;
                    while (sd_bus_message_enter_container(m, 'e', "sv") > 0) {
                        r = sd_bus_message_read(m, "s", &usage_key);
                        if (r >= 0 && strcmp(usage_key, "total_tokens") == 0) {
                            int64_t tokens;
                            r = sd_bus_message_enter_container(m, 'v', "x");
                            if (r >= 0) {
                                r = sd_bus_message_read(m, "x", &tokens);
                                if (r >= 0) {
                                    resp->total_tokens = (int)tokens;
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
    
fallback:
    /* Set defaults if parsing failed */
    if (!resp->id) resp->id = strdup("");
    if (!resp->model) resp->model = strdup("");
    if (!resp->content) resp->content = strdup("");
    
    return resp;
}
