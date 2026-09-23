varying vec4 v_TexCoord;

uniform sampler2D g_Texture0; // {"hidden":true}

// Pass-through pour l'éclat des yeux : élimine le flou gaussien baveux
// Alpha = 1.0 impératif pour écraser le FBO à chaque frame et empêcher l'accumulation
void main() {
	vec4 s = texSample2D(g_Texture0, v_TexCoord.xy);
	gl_FragColor = vec4(s.rgb, 1.0);
}
