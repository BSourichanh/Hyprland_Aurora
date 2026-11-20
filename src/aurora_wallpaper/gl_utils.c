#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <libgen.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "gl_utils.h"

#define STB_IMAGE_IMPLEMENTATION
#ifdef __GNUC__
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"
#endif
#include "stb_image.h"
#ifdef __GNUC__
#pragma GCC diagnostic pop
#endif

const GLfloat quad_vertices[8] = { -1.0f, -1.0f, 1.0f, -1.0f, -1.0f, 1.0f, 1.0f, 1.0f };

static bool try_asset_candidate(char *buf, size_t buf_sz, const char *base, const char *mid, const char *rel) {
    if (!base || !base[0] || !rel || !rel[0]) return false;
    int n = mid ? snprintf(buf, buf_sz, "%s/%s/%s", base, mid, rel)
                : snprintf(buf, buf_sz, "%s/%s", base, rel);
    return n > 0 && (size_t)n < buf_sz && access(buf, R_OK) == 0;
}

const char *resolve_asset_path(const char *rel_path) {
    static char full_path[1024];
    if (!rel_path || !rel_path[0]) return "";
    if (access(rel_path, R_OK) == 0) return rel_path;

    const char *stripped = (strncmp(rel_path, "ressource/", 10) == 0) ? (rel_path + 10) : NULL;

    char exe_path[1024];
    ssize_t len = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);
    if (len > 0 && (size_t)len < sizeof(exe_path) - 1) {
        exe_path[len] = '\0';
        char *dir = dirname(exe_path);
        if (try_asset_candidate(full_path, sizeof(full_path), dir, "../..", rel_path)) return full_path;
        if (try_asset_candidate(full_path, sizeof(full_path), dir, "..", rel_path)) return full_path;
        if (try_asset_candidate(full_path, sizeof(full_path), dir, "../share/aurora-wallpaper", rel_path)) return full_path;
        if (stripped && try_asset_candidate(full_path, sizeof(full_path), dir, "../share/aurora-wallpaper", stripped)) return full_path;
        if (try_asset_candidate(full_path, sizeof(full_path), dir, NULL, rel_path)) return full_path;
    }

    const char *custom_res = getenv("AURORA_RES_DIR");
    if (try_asset_candidate(full_path, sizeof(full_path), custom_res, NULL, rel_path)) return full_path;
    if (stripped && try_asset_candidate(full_path, sizeof(full_path), custom_res, NULL, stripped)) return full_path;

    const char *xdg_data = getenv("XDG_DATA_HOME");
    if (try_asset_candidate(full_path, sizeof(full_path), xdg_data, "aurora-wallpaper", rel_path)) return full_path;
    if (stripped && try_asset_candidate(full_path, sizeof(full_path), xdg_data, "aurora-wallpaper", stripped)) return full_path;

    const char *home = getenv("HOME");
    if (try_asset_candidate(full_path, sizeof(full_path), home, ".local/share/aurora-wallpaper", rel_path)) return full_path;
    if (stripped && try_asset_candidate(full_path, sizeof(full_path), home, ".local/share/aurora-wallpaper", stripped)) return full_path;

    return rel_path;
}

GLuint compile_shader_parts(GLenum type, const char *const *parts, GLsizei count) {
    if (!parts || count <= 0) return 0;
    GLuint s = glCreateShader(type);
    if (!s) return 0;

    glShaderSource(s, count, parts, NULL);
    glCompileShader(s);

    GLint ok = 0;
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

GLuint compile_shader(GLenum type, const char *src) {
    if (!src) return 0;
    return compile_shader_parts(type, &src, 1);
}

GLuint create_program_parts(const char *const *vs_parts, GLsizei vs_count,
                            const char *const *fs_parts, GLsizei fs_count) {
    GLuint vs = compile_shader_parts(GL_VERTEX_SHADER, vs_parts, vs_count);
    if (!vs) return 0;

    GLuint fs = compile_shader_parts(GL_FRAGMENT_SHADER, fs_parts, fs_count);
    if (!fs) { glDeleteShader(vs); return 0; }

    GLuint p = glCreateProgram();
    if (!p) { glDeleteShader(vs); glDeleteShader(fs); return 0; }
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glBindAttribLocation(p, 0, "a_Position");
    glLinkProgram(p);

    glDeleteShader(vs);
    glDeleteShader(fs);

    GLint ok = 0;
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

GLuint create_program(const char *vs_src, const char *fs_src) {
    if (!vs_src || !fs_src) return 0;
    return create_program_parts(&vs_src, 1, &fs_src, 1);
}

static void set_linear_clamp_params(void) {
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

GLuint load_texture(const char *path) {
    if (!path || !path[0]) return 0;
    int w, h, channels;
    stbi_set_flip_vertically_on_load(0);
    unsigned char *data = stbi_load(path, &w, &h, &channels, 4);
    if (!data) {
        fprintf(stderr, "Erreur : Impossible de charger l'image : %s\n", path);
        return 0;
    }

    GLuint tex = 0;
    glGenTextures(1, &tex);
    if (!tex) {
        stbi_image_free(data);
        return 0;
    }
    glBindTexture(GL_TEXTURE_2D, tex);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data);
    set_linear_clamp_params();

    stbi_image_free(data);
    printf("✓ Texture chargée [%s] : %dx%d\n", path, w, h);
    return tex;
}

bool init_egl_context(struct wl_display *wl_display, EGLDisplay *out_display, EGLContext *out_context, EGLConfig *out_config) {
    EGLDisplay dpy = eglGetDisplay((EGLNativeDisplayType)wl_display);
    if (dpy == EGL_NO_DISPLAY) return false;

    EGLint major, minor;
    if (!eglInitialize(dpy, &major, &minor)) return false;
    if (!eglBindAPI(EGL_OPENGL_ES_API)) return false;

    EGLint num_configs = 0;
    EGLint alphas[2] = { 0, 8 };
    bool cfg_ok = false;
    for (int i = 0; i < 2 && !cfg_ok; ++i) {
        EGLint attribs[] = {
            EGL_SURFACE_TYPE, EGL_WINDOW_BIT, EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8,
            EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, alphas[i], EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_NONE
        };
        cfg_ok = eglChooseConfig(dpy, attribs, out_config, 1, &num_configs) && num_configs >= 1;
    }
    if (!cfg_ok) return false;

    static const EGLint context_attribs[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };

    EGLContext ctx = eglCreateContext(dpy, *out_config, EGL_NO_CONTEXT, context_attribs);
    if (ctx == EGL_NO_CONTEXT) return false;

    *out_display = dpy;
    *out_context = ctx;
    return true;
}

static bool try_create_fbo_format(int width, int height, GLenum fmt, GLuint *out_fbo, GLuint *out_tex) {
    GLuint fbo = 0, tex = 0;
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glGenTextures(1, &tex);
    glBindTexture(GL_TEXTURE_2D, tex);
    glTexImage2D(GL_TEXTURE_2D, 0, (GLint)fmt, width, height, 0, fmt, GL_UNSIGNED_BYTE, NULL);
    set_linear_clamp_params();
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex, 0);
    GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glBindTexture(GL_TEXTURE_2D, 0);
    if (status != GL_FRAMEBUFFER_COMPLETE || fbo == 0 || tex == 0) {
        if (tex) glDeleteTextures(1, &tex);
        if (fbo) glDeleteFramebuffers(1, &fbo);
        return false;
    }
    *out_fbo = fbo;
    *out_tex = tex;
    return true;
}

bool create_shared_fbo(int width, int height, GLuint *out_fbo, GLuint *out_tex) {
    if (!out_fbo || !out_tex || width <= 0 || height <= 0) return false;
    *out_fbo = 0;
    *out_tex = 0;
    if (try_create_fbo_format(width, height, GL_RGB, out_fbo, out_tex)) return true;
    return try_create_fbo_format(width, height, GL_RGBA, out_fbo, out_tex);
}

uint64_t aurora_get_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)(ts.tv_nsec / 1000000L);
}

void aurora_init_lock_paths(struct App *app) {
    const char *xdg = getenv("XDG_RUNTIME_DIR");
    char runtime_base[768];
    int n_base = (xdg && xdg[0])
        ? snprintf(runtime_base, sizeof(runtime_base), "%s", xdg)
        : snprintf(runtime_base, sizeof(runtime_base), "/run/user/%u", (unsigned)getuid());

    if (n_base <= 0 || (size_t)n_base >= sizeof(runtime_base)) {
        app->lock_flag_path[0] = '\0';
        app->lock_inst_path[0] = '\0';
        return;
    }
    int n1 = snprintf(app->lock_flag_path, sizeof(app->lock_flag_path), "%s/aurora/hypr_locked", runtime_base);
    int n2 = snprintf(app->lock_inst_path, sizeof(app->lock_inst_path), "%s/aurora/hypr_lock_instance.lock", runtime_base);
    if (n1 <= 0 || (size_t)n1 >= sizeof(app->lock_flag_path)) app->lock_flag_path[0] = '\0';
    if (n2 <= 0 || (size_t)n2 >= sizeof(app->lock_inst_path)) app->lock_inst_path[0] = '\0';
}

static bool is_lock_instance_held(const char *inst_path) {
    if (!inst_path || !inst_path[0]) return false;
    struct stat st;
    if (lstat(inst_path, &st) != 0 || !S_ISREG(st.st_mode) || st.st_uid != getuid()) return false;
    int fd = open(inst_path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW);
    if (fd < 0) return false;

    bool held = false;
    if (flock(fd, LOCK_EX | LOCK_NB) == -1) {
        if (errno == EWOULDBLOCK || errno == EAGAIN) held = true;
    } else {
        flock(fd, LOCK_UN);
    }
    close(fd);
    return held;
}

bool aurora_is_session_locked(struct App *app) {
    if (!app) return false;
    uint64_t now_ms = aurora_get_time_ms();
    if (app->last_lock_check_ms != 0 && now_ms >= app->last_lock_check_ms &&
        (now_ms - app->last_lock_check_ms) < 250ULL) {
        return app->cached_locked;
    }
    bool locked = (app->lock_flag_path[0] && access(app->lock_flag_path, F_OK) == 0 &&
                   is_lock_instance_held(app->lock_inst_path));
    if (!locked) {
        /* Compatibilité transitoire live avec /tmp/hypr_locked (jamais utilisé comme mutex) */
        struct stat st;
        if (lstat("/tmp/hypr_locked", &st) == 0 && S_ISREG(st.st_mode) && st.st_uid == getuid() &&
            (lstat("/tmp/hypr_lock_instance.lock", &st) != 0 ||
             is_lock_instance_held("/tmp/hypr_lock_instance.lock"))) {
            locked = true;
        }
    }
    app->last_lock_check_ms = now_ms ? now_ms : 1ULL;
    app->cached_locked = locked;
    return locked;
}

struct Output *aurora_first_configured_output(const struct App *app) {
    for (struct Output *o = app->outputs; o; o = o->next) {
        if (o->configured && o->egl_surface != EGL_NO_SURFACE) return o;
    }
    return NULL;
}

void aurora_compute_fbo_size(const struct App *app, int32_t *out_w, int32_t *out_h) {
    int32_t max_w = 0, max_h = 0;
    for (struct Output *o = app->outputs; o; o = o->next) {
        if (o->configured && o->width > 0 && o->height > 0) {
            if (o->width > max_w) max_w = o->width;
            if (o->height > max_h) max_h = o->height;
        }
    }
    *out_w = (max_w > 0) ? max_w : 1920;
    *out_h = (max_h > 0) ? max_h : 1080;
}

static float aurora_fractf(float x) { return x - floorf(x); }

static float aurora_hash11(float p) {
    p = aurora_fractf(p * 0.1031f);
    p *= p + 33.33f;
    p *= p + p;
    return aurora_fractf(p);
}

static void draw_fullscreen_quad(GLuint quad_vbo) {
    const void *vtx_ptr = (quad_vbo != 0) ? (const void *)0 : (const void *)quad_vertices;
    glBindBuffer(GL_ARRAY_BUFFER, quad_vbo);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, vtx_ptr);
    glEnableVertexAttribArray(0);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    if (quad_vbo != 0) glBindBuffer(GL_ARRAY_BUFFER, 0);
}

void aurora_render_frame(struct App *app) {
    struct Output *active_out = aurora_first_configured_output(app);
    if (!active_out) return;

    if (!eglMakeCurrent(app->egl_display, active_out->egl_surface,
                        active_out->egl_surface, app->egl_context)) return;

    int32_t req_w = 0, req_h = 0;
    aurora_compute_fbo_size(app, &req_w, &req_h);
    if (req_w != app->fbo_width || req_h != app->fbo_height) {
        GLuint new_fbo = 0, new_tex = 0;
        if (create_shared_fbo(req_w, req_h, &new_fbo, &new_tex)) {
            if (app->fbo) glDeleteFramebuffers(1, &app->fbo);
            if (app->fbo_texture) glDeleteTextures(1, &app->fbo_texture);
            app->fbo = new_fbo;
            app->fbo_texture = new_tex;
            app->fbo_width = req_w;
            app->fbo_height = req_h;
        }
    }

    float t = (float)(fmod((double)(aurora_get_time_ms() - app->start_time_ms) / 1000.0, 3600.0));
    float breath_offset = sinf(t) * 0.01f;
    float bg_breath = sinf(t * 1.6f) * 0.5f + 0.5f;
    float g_time = t * 1.5f;
    float cycle = fmodf(g_time, 3.8f);
    float tick1 = (cycle >= 3.20f && cycle < 3.30f) ? 1.0f : 0.0f;
    float tick2 = (cycle >= 3.35f && cycle < 3.43f) ? 0.70f : 0.0f;
    float twitch = (aurora_hash11(fmodf(floorf(g_time * 10.0f), 1000.0f)) >= 0.982f) ? 0.45f : 0.0f;
    float glitch_intensity = tick1 > tick2 ? tick1 : tick2;
    if (twitch > glitch_intensity) glitch_intensity = twitch;
    float frame_seed = fmodf(floorf(g_time * 20.0f) * 23.41f, 1000.0f);

    glBindFramebuffer(GL_FRAMEBUFFER, app->fbo);
    glViewport(0, 0, app->fbo_width, app->fbo_height);
    glUseProgram(app->prog_lucy);
    glUniform1f(app->loc_lucy_time, t);
    if (app->loc_lucy_params >= 0) {
        glUniform4f(app->loc_lucy_params, breath_offset, bg_breath, glitch_intensity, frame_seed);
    }

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, app->tex_lucy);
    glUniform1i(app->loc_lucy_tex, 0);

    glActiveTexture(GL_TEXTURE1);
    glBindTexture(GL_TEXTURE_2D, app->tex_mask);
    glUniform1i(app->loc_mask_tex, 1);

    draw_fullscreen_quad(app->quad_vbo);

    for (struct Output *out = app->outputs; out; out = out->next) {
        if (!out->configured || out->egl_surface == EGL_NO_SURFACE) continue;
        if (!eglMakeCurrent(app->egl_display, out->egl_surface,
                            out->egl_surface, app->egl_context)) continue;
        if (!out->swap_interval_set) {
            eglSwapInterval(app->egl_display, 0);
            out->swap_interval_set = true;
        }

        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glViewport(0, 0, out->width, out->height);

        glUseProgram(app->prog_blit);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, app->fbo_texture);
        glUniform1i(app->loc_blit_tex, 0);

        draw_fullscreen_quad(app->quad_vbo);

        eglSwapBuffers(app->egl_display, out->egl_surface);
    }
}
