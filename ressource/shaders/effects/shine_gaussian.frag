varying vec4 v_TexCoord;

uniform sampler2D g_Texture0; // {"hidden":true}

// Pass-through pour l'éclat des yeux : élimine le flou gaussien 13-tap
// qui transformait l'iris en boule lumineuse sphérique baveuse
void main() {
	gl_FragColor = texSample2D(g_Texture0, v_TexCoord.xy);
}
