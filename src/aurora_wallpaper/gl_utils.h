#ifndef GL_UTILS_H
#define GL_UTILS_H

#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <wayland-client.h>
#include <wayland-egl.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>

struct zwlr_layer_surface_v1;
struct zwlr_layer_shell_v1;

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
    bool swap_interval_set;
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
    int32_t fbo_width, fbo_height;
    GLuint tex_lucy, tex_mask;
    GLuint prog_lucy, prog_blit;
    GLint loc_lucy_time, loc_lucy_tex, loc_mask_tex, loc_blit_tex;
    GLint loc_lucy_params;
    GLuint quad_vbo;

    volatile sig_atomic_t running;
    uint64_t start_time_ms;
    uint64_t last_lock_check_ms;
    bool cached_locked;
    char lock_flag_path[1024];
    char lock_inst_path[1024];
};

extern const GLfloat quad_vertices[8];

uint64_t aurora_get_time_ms(void);
void aurora_init_lock_paths(struct App *app);
bool aurora_is_session_locked(struct App *app);
struct Output *aurora_first_configured_output(const struct App *app);
void aurora_compute_fbo_size(const struct App *app, int32_t *out_w, int32_t *out_h);
void aurora_render_frame(struct App *app);

const char *resolve_asset_path(const char *rel_path);
GLuint compile_shader(GLenum type, const char *src);
GLuint compile_shader_parts(GLenum type, const char *const *parts, GLsizei count);
GLuint create_program(const char *vs_src, const char *fs_src);
GLuint create_program_parts(const char *const *vs_parts, GLsizei vs_count,
                            const char *const *fs_parts, GLsizei fs_count);
GLuint load_texture(const char *path);
bool init_egl_context(struct wl_display *wl_display, EGLDisplay *out_display, EGLContext *out_context, EGLConfig *out_config);
bool create_shared_fbo(int width, int height, GLuint *out_fbo, GLuint *out_tex);

#endif /* GL_UTILS_H */
