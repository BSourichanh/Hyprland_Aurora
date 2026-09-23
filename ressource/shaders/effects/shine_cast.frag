varying vec4 v_TexCoord01;
varying vec4 v_TexCoord23;
varying vec4 v_TexCoord45;

uniform sampler2D g_Texture0; // {"hidden":true}

uniform float g_Length;
uniform float g_Intensity;
uniform vec3 g_ColorRays;

// Pass-through pour l'éclat des yeux : élimine la diffusion de rayons en étoile
// qui produisait une boule de lumière diffuse hors de la pupille
void main() {
	gl_FragColor = texSample2D(g_Texture0, v_TexCoord01.xy);
}
