#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>
#include <poll.h>

#include <wayland-client.h>
#include <wayland-egl.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>

#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "shader.h"
#include "gl_utils.h"

struct Output {
    uint32_t id;
    struct wl_output *wl_output;
    struct wl_surface *wl_surface;
    struct zwlr_layer_surface_v1 *layer_surface;
    struct wl_egl_window *egl_window;
    EGLSurface egl_surface;
    int32_t width;
    int32_t height;
    bool configured;
    struct Output *next;
};

struct App {
    struct wl_display *display;
    struct wl_registry *registry;
    struct wl_compositor *compositor;
    struct zwlr_layer_shell_v1 *layer_shell;
    struct Output *outputs;

    EGLDisplay egl_display;
    EGLContext egl_context;
    EGLConfig egl_config;

    GLuint fbo, fbo_texture;
    GLuint tex_lucy, tex_mask;
    GLuint prog_lucy, prog_blit;
    GLint loc_lucy_time, loc_lucy_tex, loc_mask_tex, loc_blit_tex;

    bool running;
    uint64_t start_time_ms;
};

static struct App app;

static uint64_t get_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static void sig_handler(int sig) {
    (void)sig;
    app.running = false;
}

static void destroy_output_surface(struct Output *out) {
    if (!out) return;
    out->configured = false;
    if (out->egl_surface) {
        if (eglGetCurrentSurface(EGL_DRAW) == out->egl_surface) {
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

    if (width > 0) out->width = width;
    if (height > 0) out->height = height;

    if (!out->egl_window) {
        out->egl_window = wl_egl_window_create(out->wl_surface, out->width, out->height);
        out->egl_surface = eglCreateWindowSurface(app.egl_display, app.egl_config,
                                                 (EGLNativeWindowType)out->egl_window, NULL);
        eglSwapInterval(app.egl_display, 0);
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
    if (out->layer_surface) return;

    out->wl_surface = wl_compositor_create_surface(app.compositor);
    out->layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        app.layer_shell,
        out->wl_surface,
        out->wl_output,
        ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM,
        "aurora-wallpaper"
    );

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
    (void)version;
    if (strcmp(interface, "wl_compositor") == 0) {
        app.compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 4);
    } else if (strcmp(interface, "zwlr_layer_shell_v1") == 0) {
        app.layer_shell = wl_registry_bind(registry, name, &zwlr_layer_shell_v1_interface, 1);
    } else if (strcmp(interface, "wl_output") == 0) {
        struct Output *out = calloc(1, sizeof(struct Output));
        out->id = name;
        out->wl_output = wl_registry_bind(registry, name, &wl_output_interface, 2);
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

static void render_frame(void) {
    float t = (float)(get_time_ms() - app.start_time_ms) / 1000.0f;

    struct Output *active_out = NULL;
    for (struct Output *o = app.outputs; o; o = o->next) {
        if (o->configured && o->egl_surface) {
            active_out = o;
            break;
        }
    }
    if (!active_out) return;

    eglMakeCurrent(app.egl_display, active_out->egl_surface, active_out->egl_surface, app.egl_context);

    // ÉTAPE 1 : Rendu dans le FBO partagé (calculé 1 seule fois)
    glBindFramebuffer(GL_FRAMEBUFFER, app.fbo);
    glViewport(0, 0, 1920, 1080);
    glUseProgram(app.prog_lucy);
    glUniform1f(app.loc_lucy_time, t);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, app.tex_lucy);
    glUniform1i(app.loc_lucy_tex, 0);

    glActiveTexture(GL_TEXTURE1);
    glBindTexture(GL_TEXTURE_2D, app.tex_mask);
    glUniform1i(app.loc_mask_tex, 1);

    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, quad_vertices);
    glEnableVertexAttribArray(0);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

    // ÉTAPE 2 : Blit FBO vers tous les écrans connectés
    for (struct Output *out = app.outputs; out; out = out->next) {
        if (!out->configured || !out->egl_surface) continue;

        eglMakeCurrent(app.egl_display, out->egl_surface, out->egl_surface, app.egl_context);
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glViewport(0, 0, out->width, out->height);

        glUseProgram(app.prog_blit);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, app.fbo_texture);
        glUniform1i(app.loc_blit_tex, 0);

        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, quad_vertices);
        glEnableVertexAttribArray(0);
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

        eglSwapBuffers(app.egl_display, out->egl_surface);
    }
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

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

    for (struct Output *out = app.outputs; out; out = out->next) {
        setup_output_surface(out);
    }
    wl_display_roundtrip(app.display);

    struct Output *first = app.outputs;
    while (first && (!first->configured || !first->egl_surface)) first = first->next;
    if (!first) {
        fprintf(stderr, "Erreur : Aucun écran configuré.\n");
        return 1;
    }

    eglMakeCurrent(app.egl_display, first->egl_surface, first->egl_surface, app.egl_context);

    app.prog_lucy = create_program(vertex_shader_source, fragment_shader_lucy);
    app.prog_blit = create_program(vertex_shader_blit, fragment_shader_blit);
    if (!app.prog_lucy || !app.prog_blit) {
        fprintf(stderr, "Erreur : Échec compilation shaders.\n");
        return 1;
    }

    app.loc_lucy_time = glGetUniformLocation(app.prog_lucy, "u_Time");
    app.loc_lucy_tex  = glGetUniformLocation(app.prog_lucy, "u_LucyTexture");
    app.loc_mask_tex  = glGetUniformLocation(app.prog_lucy, "u_MaskTexture");
    app.loc_blit_tex  = glGetUniformLocation(app.prog_blit, "u_Texture");

    app.tex_lucy = load_texture(resolve_asset_path("ressource/lucy.png"));
    app.tex_mask = load_texture(resolve_asset_path("ressource/blackwall/blackwall_mask.png"));
    if (!app.tex_lucy || !app.tex_mask) {
        fprintf(stderr, "Erreur : Impossible de charger les assets Lucy.\n");
        return 1;
    }

    if (!create_shared_fbo(1920, 1080, &app.fbo, &app.fbo_texture)) {
        fprintf(stderr, "Erreur : FBO invalide.\n");
        return 1;
    }

    printf("✓ FBO partagé initialisé (1920x1080)\n");
    printf("✓ Moteur prêt. Cadence cible : 30 FPS fixes (33.3 ms / trame).\n");

    app.running = true;
    app.start_time_ms = get_time_ms();
    const uint64_t frame_duration_us = 33333;

    while (app.running) {
        if (wl_display_get_error(app.display)) {
            break;
        }

        uint64_t t0 = get_time_ms();

        while (wl_display_prepare_read(app.display) != 0) {
            if (wl_display_dispatch_pending(app.display) < 0) {
                app.running = false;
                break;
            }
        }
        if (!app.running) break;

        wl_display_flush(app.display);

        struct pollfd pfd = { wl_display_get_fd(app.display), POLLIN, 0 };
        poll(&pfd, 1, 0);

        if (pfd.revents & POLLIN) {
            if (wl_display_read_events(app.display) != 0) {
                break;
            }
        } else {
            wl_display_cancel_read(app.display);
        }

        if (wl_display_dispatch_pending(app.display) < 0 || wl_display_get_error(app.display)) {
            break;
        }

        render_frame();
        wl_display_flush(app.display);

        uint64_t elapsed_us = (get_time_ms() - t0) * 1000;
        if (elapsed_us < frame_duration_us) {
            usleep(frame_duration_us - elapsed_us);
        }
    }

    printf("\nArrêt propre du moteur Aurora...\n");

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
