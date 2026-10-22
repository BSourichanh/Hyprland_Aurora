#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>
#include <sys/time.h>
#include <libgen.h>
#include <poll.h>

static const char *resolve_asset_path(const char *rel_path) {
    static char full_path[1024];
    // Check if directly accessible
    if (access(rel_path, R_OK) == 0) return rel_path;

    char exe_path[1024];
    ssize_t len = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);
    if (len > 0) {
        exe_path[len] = '\0';
        char *dir = dirname(exe_path);
        snprintf(full_path, sizeof(full_path), "%s/../../%s", dir, rel_path);
        if (access(full_path, R_OK) == 0) return full_path;
        snprintf(full_path, sizeof(full_path), "%s/%s", dir, rel_path);
        if (access(full_path, R_OK) == 0) return full_path;
    }
    snprintf(full_path, sizeof(full_path), "/home/user/Documents/antigravity/hyprland_project/%s", rel_path);
    return full_path;
}

#include <wayland-client.h>
#include <wayland-egl.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "shader.h"

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

    GLuint fbo;
    GLuint fbo_texture;
    GLuint tex_lucy;
    GLuint tex_mask;

    GLuint prog_lucy;
    GLuint prog_blit;
    GLint loc_lucy_time;
    GLint loc_lucy_tex;
    GLint loc_mask_tex;
    GLint loc_blit_tex;

    bool running;
    uint64_t start_time_ms;
};

static struct App app;

static uint64_t get_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)ts.tv_nsec / 1000000ULL;
}

static void sig_handler(int sig) {
    (void)sig;
    app.running = false;
}

static GLuint compile_shader(GLenum type, const char *src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, NULL);
    glCompileShader(s);

    GLint ok;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[1024];
        glGetShaderInfoLog(s, sizeof(log), NULL, log);
        fprintf(stderr, "Shader compile error:\n%s\n", log);
        glDeleteShader(s);
        return 0;
    }
    return s;
}

static GLuint create_program(const char *vs_src, const char *fs_src) {
    GLuint vs = compile_shader(GL_VERTEX_SHADER, vs_src);
    GLuint fs = compile_shader(GL_FRAGMENT_SHADER, fs_src);
    if (!vs || !fs) return 0;

    GLuint p = glCreateProgram();
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glBindAttribLocation(p, 0, "a_Position");
    glLinkProgram(p);

    glDeleteShader(vs);
    glDeleteShader(fs);

    GLint ok;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[1024];
        glGetProgramInfoLog(p, sizeof(log), NULL, log);
        fprintf(stderr, "Program link error:\n%s\n", log);
        glDeleteProgram(p);
        return 0;
    }
    return p;
}

static GLuint load_texture(const char *path) {
    int w, h, channels;
    stbi_set_flip_vertically_on_load(0);
    unsigned char *data = stbi_load(path, &w, &h, &channels, 4);
    if (!data) {
        fprintf(stderr, "Erreur : Impossible de charger l'image : %s\n", path);
        return 0;
    }

    GLuint tex;
    glGenTextures(1, &tex);
    glBindTexture(GL_TEXTURE_2D, tex);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    stbi_image_free(data);
    printf("✓ Texture chargée [%s] : %dx%d\n", path, w, h);
    return tex;
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
    (void)data;
    (void)layer_surface;
}

static const struct zwlr_layer_surface_v1_listener layer_surface_listener = {
    .configure = layer_surface_configure,
    .closed = layer_surface_closed,
};

static void setup_output_surface(struct Output *out) {
    out->wl_surface = wl_compositor_create_surface(app.compositor);
    out->layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        app.layer_shell, out->wl_surface, out->wl_output,
        ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM, "aurora-wallpaper");

    zwlr_layer_surface_v1_set_size(out->layer_surface, out->width, out->height);
    zwlr_layer_surface_v1_set_anchor(out->layer_surface,
        ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT | ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);
    zwlr_layer_surface_v1_set_exclusive_zone(out->layer_surface, -1);
    zwlr_layer_surface_v1_add_listener(out->layer_surface, &layer_surface_listener, out);
    wl_surface_commit(out->wl_surface);
}

static void registry_global(void *data, struct wl_registry *registry,
                            uint32_t name, const char *interface, uint32_t version) {
    (void)data;
    (void)version;
    if (strcmp(interface, wl_compositor_interface.name) == 0) {
        app.compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 4);
    } else if (strcmp(interface, zwlr_layer_shell_v1_interface.name) == 0) {
        app.layer_shell = wl_registry_bind(registry, name, &zwlr_layer_shell_v1_interface, 1);
    } else if (strcmp(interface, wl_output_interface.name) == 0) {
        struct Output *out = calloc(1, sizeof(struct Output));
        out->id = name;
        out->width = 1920;
        out->height = 1080;
        out->wl_output = wl_registry_bind(registry, name, &wl_output_interface, 2);
        out->next = app.outputs;
        app.outputs = out;
        if (app.compositor && app.layer_shell && app.running) {
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
            if (to_del->egl_surface) eglDestroySurface(app.egl_display, to_del->egl_surface);
            if (to_del->egl_window) wl_egl_window_destroy(to_del->egl_window);
            if (to_del->layer_surface) zwlr_layer_surface_v1_destroy(to_del->layer_surface);
            if (to_del->wl_surface) wl_surface_destroy(to_del->wl_surface);
            if (to_del->wl_output) wl_output_destroy(to_del->wl_output);
            free(to_del);
            printf("ℹ Écran déconnecté [%u]\n", name);
            break;
        }
        curr = &(*curr)->next;
    }
}

static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_global_remove,
};

static bool init_egl(void) {
    app.egl_display = eglGetDisplay((EGLNativeDisplayType)app.display);
    if (app.egl_display == EGL_NO_DISPLAY) return false;

    EGLint major, minor;
    if (!eglInitialize(app.egl_display, &major, &minor)) return false;

    if (!eglBindAPI(EGL_OPENGL_ES_API)) return false;

    static const EGLint config_attribs[] = {
        EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
        EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 8,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_NONE
    };

    EGLint num_configs;
    if (!eglChooseConfig(app.egl_display, config_attribs, &app.egl_config, 1, &num_configs) || num_configs < 1) {
        return false;
    }

    static const EGLint context_attribs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 2,
        EGL_NONE
    };

    app.egl_context = eglCreateContext(app.egl_display, app.egl_config, EGL_NO_CONTEXT, context_attribs);
    return app.egl_context != EGL_NO_CONTEXT;
}

static const GLfloat quad_vertices[] = {
    -1.0f, -1.0f,
     1.0f, -1.0f,
    -1.0f,  1.0f,
     1.0f,  1.0f,
};

static void render_frame(void) {
    float t = (float)(get_time_ms() - app.start_time_ms) / 1000.0f;

    // Trouver au moins une surface configurée pour rendre actif le contexte
    struct Output *active_out = NULL;
    for (struct Output *o = app.outputs; o; o = o->next) {
        if (o->configured && o->egl_surface) {
            active_out = o;
            break;
        }
    }
    if (!active_out) return;

    eglMakeCurrent(app.egl_display, active_out->egl_surface, active_out->egl_surface, app.egl_context);

    // =========================================================================
    // ÉTAPE 1 : CALCUL DU SHADER UNIFIÉ DANS LE FBO PARTAGÉ (EXÉCUTÉ 1 SEULE FOIS)
    // =========================================================================
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

    // =========================================================================
    // ÉTAPE 2 : COPIE (BLIT) ULTRA-RAPIDE VERS TOUS LES ÉCRANS CONNECTÉS
    // =========================================================================
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

    if (!init_egl()) {
        fprintf(stderr, "Erreur : Initialisation EGL échouée.\n");
        return 1;
    }

    // Création des surfaces Wayland sur chaque écran détecté
    for (struct Output *out = app.outputs; out; out = out->next) {
        setup_output_surface(out);
    }
    wl_display_roundtrip(app.display);

    // Initialisation OpenGL
    struct Output *first = app.outputs;
    while (first && (!first->configured || !first->egl_surface)) first = first->next;
    if (!first) {
        fprintf(stderr, "Erreur : Aucun écran configuré.\n");
        return 1;
    }

    eglMakeCurrent(app.egl_display, first->egl_surface, first->egl_surface, app.egl_context);

    // Compilation des Shaders
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

    // Chargement des Textures Lucy
    app.tex_lucy = load_texture(resolve_asset_path("ressource/lucy.png"));
    app.tex_mask = load_texture(resolve_asset_path("ressource/blackwall/blackwall_mask.png"));
    if (!app.tex_lucy || !app.tex_mask) {
        fprintf(stderr, "Erreur : Impossible de charger les assets Lucy.\n");
        return 1;
    }

    // Création du Framebuffer Partagé FBO (1920x1080)
    glGenFramebuffers(1, &app.fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, app.fbo);

    glGenTextures(1, &app.fbo_texture);
    glBindTexture(GL_TEXTURE_2D, app.fbo_texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 1920, 1080, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, app.fbo_texture, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        fprintf(stderr, "Erreur : FBO invalide.\n");
        return 1;
    }
    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    printf("✓ FBO partagé initialisé (1920x1080)\n");
    printf("✓ Moteur prêt. Cadence cible : 30 FPS fixes (33.3 ms / trame).\n");

    app.running = true;
    app.start_time_ms = get_time_ms();

    // Boucle de rendu cadencée à 30 FPS (33.3 ms par trame)
    const uint64_t frame_duration_us = 33333; // 30 FPS

    while (app.running) {
        uint64_t t0 = get_time_ms();

        while (wl_display_prepare_read(app.display) != 0) {
            wl_display_dispatch_pending(app.display);
        }
        wl_display_flush(app.display);

        struct pollfd pfd = { wl_display_get_fd(app.display), POLLIN, 0 };
        poll(&pfd, 1, 0);

        if (pfd.revents & POLLIN) {
            wl_display_read_events(app.display);
        } else {
            wl_display_cancel_read(app.display);
        }
        wl_display_dispatch_pending(app.display);

        render_frame();

        wl_display_flush(app.display);

        uint64_t elapsed_us = (get_time_ms() - t0) * 1000;
        if (elapsed_us < frame_duration_us) {
            usleep(frame_duration_us - elapsed_us);
        }
    }

    printf("\nArrêt propre du moteur Aurora...\n");

    // Nettoyage des ressources
    glDeleteFramebuffers(1, &app.fbo);
    glDeleteTextures(1, &app.fbo_texture);
    glDeleteTextures(1, &app.tex_lucy);
    glDeleteTextures(1, &app.tex_mask);
    glDeleteProgram(app.prog_lucy);
    glDeleteProgram(app.prog_blit);

    struct Output *out = app.outputs;
    while (out) {
        struct Output *next = out->next;
        if (out->egl_surface) eglDestroySurface(app.egl_display, out->egl_surface);
        if (out->egl_window) wl_egl_window_destroy(out->egl_window);
        if (out->layer_surface) zwlr_layer_surface_v1_destroy(out->layer_surface);
        if (out->wl_surface) wl_surface_destroy(out->wl_surface);
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
