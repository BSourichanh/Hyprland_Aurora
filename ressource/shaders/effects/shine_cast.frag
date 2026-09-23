varying vec4 v_TexCoord01;
varying vec4 v_TexCoord23;
varying vec4 v_TexCoord45;

uniform sampler2D g_Texture0; // {"hidden":true}

uniform float g_Length;
uniform float g_Intensity;
uniform vec3 g_ColorRays;

// Pass-through pour l'éclat des yeux : élimine la diffusion de rayons en étoile
// Alpha = 1.0 impératif pour écraser le FBO à chaque frame et empêcher l'accumulation
void main() {
	vec4 s = texSample2D(g_Texture0, v_TexCoord01.xy);
	gl_FragColor = vec4(s.rgb, 1.0);
}
