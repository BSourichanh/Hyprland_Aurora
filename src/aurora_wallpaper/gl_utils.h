#ifndef GL_UTILS_H
#define GL_UTILS_H

#include <stdbool.h>
#include <wayland-client.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>

extern const GLfloat quad_vertices[8];

const char *resolve_asset_path(const char *rel_path);
GLuint compile_shader(GLenum type, const char *src);
GLuint create_program(const char *vs_src, const char *fs_src);
GLuint load_texture(const char *path);
bool init_egl_context(struct wl_display *wl_display, EGLDisplay *out_display, EGLContext *out_context, EGLConfig *out_config);
bool create_shared_fbo(int width, int height, GLuint *out_fbo, GLuint *out_tex);

#endif /* GL_UTILS_H */
