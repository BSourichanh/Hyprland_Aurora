#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <wayland-client.h>
#include <wayland-egl.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>

#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "shader.h"
#include "gl_utils.h"

static struct App app;

static uint32_t min_u32(uint32_t a, uint32_t b) {
    return (a < b) ? a : b;
}

static void sig_handler(int sig) {
    (void)sig;
    app.running = 0;
}

static void destroy_output_surface(struct Output *out) {
    if (!out) return;
    out->configured = false;
    out->swap_interval_set = false;
    if (out->egl_surface != EGL_NO_SURFACE) {
        if (app.egl_display != EGL_NO_DISPLAY &&
            eglGetCurrentSurface(EGL_DRAW) == out->egl_surface) {
            eglMakeCurrent(app.egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        }
        eglDestroySurface(app.egl_display, out->egl_surface);
        out->egl_surface = EGL_NO_SURFACE;
    }
    if (out->egl_window) {
        wl_egl_window_destroy(out->egl_window);
        out->egl_window = NULL;
    }
    if (out->layer_surface) {
        zwlr_layer_surface_v1_destroy(out->layer_surface);
        out->layer_surface = NULL;
    }
    if (out->wl_surface) {
        wl_surface_destroy(out->wl_surface);
        out->wl_surface = NULL;
    }
}

static void layer_surface_configure(void *data, struct zwlr_layer_surface_v1 *layer_surface,
                                    uint32_t serial, uint32_t width, uint32_t height) {
    struct Output *out = data;
    zwlr_layer_surface_v1_ack_configure(layer_surface, serial);
    if (!out) return;

    if (width > 0) out->width = (int32_t)width;
    if (height > 0) out->height = (int32_t)height;
    if (out->width <= 0) out->width = 1920;
    if (out->height <= 0) out->height = 1080;

    if (out->wl_surface && app.compositor) {
        struct wl_region *reg = wl_compositor_create_region(app.compositor);
        if (reg) {
            wl_region_add(reg, 0, 0, out->width, out->height);
            wl_surface_set_opaque_region(out->wl_surface, reg);
            wl_region_destroy(reg);
        }
    }

    if (!out->egl_window) {
        out->egl_window = wl_egl_window_create(out->wl_surface, out->width, out->height);
        if (!out->egl_window) {
            fprintf(stderr, "Erreur : wl_egl_window_create échoué [id=%u].\n", out->id);
            return;
        }
        out->egl_surface = eglCreateWindowSurface(app.egl_display, app.egl_config,
                                                  (EGLNativeWindowType)out->egl_window, NULL);
        if (out->egl_surface == EGL_NO_SURFACE) {
            fprintf(stderr, "Erreur : eglCreateWindowSurface échoué [id=%u].\n", out->id);
            wl_egl_window_destroy(out->egl_window);
            out->egl_window = NULL;
            return;
        }
        out->swap_interval_set = false;
        printf("✓ Écran configuré [%dx%d]\n", out->width, out->height);
    } else {
        wl_egl_window_resize(out->egl_window, out->width, out->height, 0, 0);
    }
    out->configured = true;
}

static void layer_surface_closed(void *data, struct zwlr_layer_surface_v1 *layer_surface) {
    (void)layer_surface;
    struct Output *out = data;
    if (out) {
        printf("ℹ Surface d'affichage fermée [id=%u]\n", out->id);
        destroy_output_surface(out);
    }
}

static const struct zwlr_layer_surface_v1_listener layer_surface_listener = {
    .configure = layer_surface_configure,
    .closed = layer_surface_closed,
};

static void setup_output_surface(struct Output *out) {
    if (!out || out->layer_surface || !app.compositor || !app.layer_shell) return;

    out->wl_surface = wl_compositor_create_surface(app.compositor);
    if (!out->wl_surface) {
        fprintf(stderr, "Erreur : wl_compositor_create_surface échoué [id=%u].\n", out->id);
        return;
    }

    out->layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        app.layer_shell,
        out->wl_surface,
        out->wl_output,
        ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM,
        "aurora-wallpaper"
    );
    if (!out->layer_surface) {
        fprintf(stderr, "Erreur : zwlr_layer_shell_v1_get_layer_surface échoué [id=%u].\n", out->id);
        wl_surface_destroy(out->wl_surface);
        out->wl_surface = NULL;
        return;
    }

    zwlr_layer_surface_v1_set_size(out->layer_surface, 0, 0);
    zwlr_layer_surface_v1_set_anchor(out->layer_surface,
        ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT | ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);
    zwlr_layer_surface_v1_set_exclusive_zone(out->layer_surface, -1);
    zwlr_layer_surface_v1_set_keyboard_interactivity(out->layer_surface, 0);

    zwlr_layer_surface_v1_add_listener(out->layer_surface, &layer_surface_listener, out);
    wl_surface_commit(out->wl_surface);
}

static void registry_global(void *data, struct wl_registry *registry,
                            uint32_t name, const char *interface, uint32_t version) {
    (void)data;
    if (strcmp(interface, "wl_compositor") == 0) {
        app.compositor = wl_registry_bind(registry, name, &wl_compositor_interface, min_u32(version, 4));
    } else if (strcmp(interface, "zwlr_layer_shell_v1") == 0) {
        app.layer_shell = wl_registry_bind(registry, name, &zwlr_layer_shell_v1_interface, min_u32(version, 1));
    } else if (strcmp(interface, "wl_output") == 0) {
        struct Output *out = calloc(1, sizeof(struct Output));
        if (!out) return;
        out->id = name;
        out->wl_output = wl_registry_bind(registry, name, &wl_output_interface, min_u32(version, 2));
        if (!out->wl_output) {
            free(out);
            return;
        }
        out->egl_surface = EGL_NO_SURFACE;
        out->width = 1920;
        out->height = 1080;
        out->next = app.outputs;
        app.outputs = out;

        if (app.running) {
            printf("✓ Détection hotplug écran [id=%u], initialisation...\n", name);
            setup_output_surface(out);
        }
    }
}

static void registry_global_remove(void *data, struct wl_registry *registry, uint32_t name) {
    (void)data;
    (void)registry;
    struct Output **curr = &app.outputs;
    while (*curr) {
        if ((*curr)->id == name) {
            struct Output *to_del = *curr;
            *curr = to_del->next;
            destroy_output_surface(to_del);
            if (to_del->wl_output) {
                wl_output_destroy(to_del->wl_output);
                to_del->wl_output = NULL;
            }
            free(to_del);
            printf("✓ Écran déconnecté [id=%u]\n", name);
            return;
        }
        curr = &(*curr)->next;
    }
}

static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_global_remove,
};

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sig_handler;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
    signal(SIGPIPE, SIG_IGN);

    memset(&app, 0, sizeof(app));
    app.egl_display = EGL_NO_DISPLAY;
    app.egl_context = EGL_NO_CONTEXT;
    app.loc_lucy_time = -1;
    app.loc_lucy_params = -1;
    app.loc_lucy_tex = -1;
    app.loc_mask_tex = -1;
    app.loc_blit_tex = -1;
    aurora_init_lock_paths(&app);

    printf("=========================================================\n");
    printf("   Aurora Wallpaper Engine — Micro-Moteur Natif Wayland  \n");
    printf("   (Single-Pass GLSL + Rendu FBO Mutualisé Multi-Écrans) \n");
    printf("=========================================================\n");

    app.display = wl_display_connect(NULL);
    if (!app.display) {
        fprintf(stderr, "Erreur critique : Connexion Wayland impossible.\n");
        return 1;
    }

    app.registry = wl_display_get_registry(app.display);
    wl_registry_add_listener(app.registry, &registry_listener, NULL);
    wl_display_roundtrip(app.display);

    if (!app.compositor || !app.layer_shell) {
        fprintf(stderr, "Erreur : wl_compositor ou zwlr_layer_shell_v1 introuvable.\n");
        return 1;
    }

    if (!init_egl_context(app.display, &app.egl_display, &app.egl_context, &app.egl_config)) {
        fprintf(stderr, "Erreur : Initialisation EGL échouée.\n");
        return 1;
    }

    for (struct Output *out = app.outputs; out; out = out->next) setup_output_surface(out);
    wl_display_roundtrip(app.display);

    struct Output *first = aurora_first_configured_output(&app);
    if (!first) {
        fprintf(stderr, "Erreur : Aucun écran configuré.\n");
        return 1;
    }

    if (!eglMakeCurrent(app.egl_display, first->egl_surface, first->egl_surface, app.egl_context)) {
        fprintf(stderr, "Erreur : eglMakeCurrent échoué.\n");
        return 1;
    }
    eglSwapInterval(app.egl_display, 0);
    first->swap_interval_set = true;

    app.prog_lucy = create_program_parts(&vertex_shader_source, 1,
                                         fragment_shader_lucy_parts, FRAGMENT_SHADER_LUCY_PARTS_COUNT);
    app.prog_blit = create_program(vertex_shader_blit, fragment_shader_blit);
    if (!app.prog_lucy || !app.prog_blit) {
        fprintf(stderr, "Erreur : Échec compilation shaders.\n");
        return 1;
    }

    app.loc_lucy_time   = glGetUniformLocation(app.prog_lucy, "u_Time");
    app.loc_lucy_params = glGetUniformLocation(app.prog_lucy, "u_TimeParams");
    app.loc_lucy_tex    = glGetUniformLocation(app.prog_lucy, "u_LucyTexture");
    app.loc_mask_tex    = glGetUniformLocation(app.prog_lucy, "u_MaskTexture");
    app.loc_blit_tex    = glGetUniformLocation(app.prog_blit, "u_Texture");

    glGenBuffers(1, &app.quad_vbo);
    if (app.quad_vbo != 0) {
        glBindBuffer(GL_ARRAY_BUFFER, app.quad_vbo);
        glBufferData(GL_ARRAY_BUFFER, sizeof(quad_vertices), quad_vertices, GL_STATIC_DRAW);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
    }

    app.tex_lucy = load_texture(resolve_asset_path("ressource/lucy.png"));
    app.tex_mask = load_texture(resolve_asset_path("ressource/blackwall/blackwall_mask.png"));
    if (!app.tex_lucy || !app.tex_mask) {
        fprintf(stderr, "Erreur : Impossible de charger les assets Lucy.\n");
        return 1;
    }

    aurora_compute_fbo_size(&app, &app.fbo_width, &app.fbo_height);
    if (!create_shared_fbo(app.fbo_width, app.fbo_height, &app.fbo, &app.fbo_texture)) {
        fprintf(stderr, "Erreur : FBO invalide.\n");
        return 1;
    }

    printf("✓ FBO partagé initialisé (%dx%d)\n", app.fbo_width, app.fbo_height);
    printf("✓ Moteur prêt. Cadence cible : 30 FPS fixes (33.3 ms / trame).\n");

    app.running = 1;
    app.start_time_ms = aurora_get_time_ms();
    uint64_t last_render_ms = 0;
    bool first_frame = true;

    while (app.running) {
        if (wl_display_get_error(app.display)) break;

        uint64_t now_ms = aurora_get_time_ms();
        uint64_t target_ms = aurora_is_session_locked(&app) ? 16ULL : 33ULL;

        if (first_frame || (now_ms - last_render_ms) >= target_ms) {
            last_render_ms = now_ms;
            first_frame = false;
            if (aurora_first_configured_output(&app) != NULL) {
                aurora_render_frame(&app);
                wl_display_flush(app.display);
            }
            now_ms = aurora_get_time_ms();
        }

        uint64_t elapsed_ms = now_ms - last_render_ms;
        int timeout_ms = (elapsed_ms < target_ms) ? (int)(target_ms - elapsed_ms) : 0;

        while (wl_display_prepare_read(app.display) != 0) {
            if (wl_display_dispatch_pending(app.display) < 0) {
                app.running = 0;
                break;
            }
        }
        if (!app.running) break;

        if (wl_display_flush(app.display) < 0 && errno != EAGAIN) {
            wl_display_cancel_read(app.display);
            break;
        }

        struct pollfd pfd = { wl_display_get_fd(app.display), POLLIN, 0 };
        int ret = poll(&pfd, 1, timeout_ms);
        if (ret < 0) {
            wl_display_cancel_read(app.display);
            if (errno == EINTR) continue;
            break;
        }

        if (ret > 0 && (pfd.revents & POLLIN)) {
            if (wl_display_read_events(app.display) != 0) break;
        } else {
            wl_display_cancel_read(app.display);
        }

        if ((pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) && !(pfd.revents & POLLIN)) break;

        if (wl_display_dispatch_pending(app.display) < 0 || wl_display_get_error(app.display)) break;
    }

    printf("\nArrêt propre du moteur Aurora...\n");

    if (app.quad_vbo != 0) {
        glDeleteBuffers(1, &app.quad_vbo);
        app.quad_vbo = 0;
    }
    glDeleteFramebuffers(1, &app.fbo);
    glDeleteTextures(1, &app.fbo_texture);
    glDeleteTextures(1, &app.tex_lucy);
    glDeleteTextures(1, &app.tex_mask);
    glDeleteProgram(app.prog_lucy);
    glDeleteProgram(app.prog_blit);

    struct Output *out = app.outputs;
    while (out) {
        struct Output *next = out->next;
        destroy_output_surface(out);
        if (out->wl_output) wl_output_destroy(out->wl_output);
        free(out);
        out = next;
    }

    eglDestroyContext(app.egl_display, app.egl_context);
    eglTerminate(app.egl_display);

    zwlr_layer_shell_v1_destroy(app.layer_shell);
    wl_compositor_destroy(app.compositor);
    wl_registry_destroy(app.registry);
    wl_display_disconnect(app.display);

    printf("✓ Arrêt complet validé.\n");
    return 0;
}
