// [COMBO] {"material":"ui_editor_properties_noise","combo":"NOISE","type":"options","default":1}

varying vec4 v_TexCoord;

uniform sampler2D g_Texture0; // {"hidden":true}
uniform sampler2D g_Texture1; // {"label":"ui_editor_properties_opacity_mask","mode":"opacitymask","combo":"MASK","paintdefaultcolor":"0 0 0 1"}

uniform float g_Threshold; // {"material":"raythreshold","label":"ui_editor_properties_ray_threshold","default":0.5,"range":[0, 1]}
uniform float g_Time;

#if NOISE == 1
varying vec4 v_NoiseTexCoord;

uniform sampler2D g_Texture2; // {"label":"ui_editor_properties_albedo","default":"util/clouds_256"}
uniform float g_NoiseAmount; // {"material":"noiseamount","label":"ui_editor_properties_noise_amount","default":0.4,"range":[0.01, 1]}
#endif

float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

void main() {
#if MASK
	float mask = texSample2D(g_Texture1, v_TexCoord.zw).r;
#else
	float mask = 1.0;
#endif

	vec4 sample = texSample2D(g_Texture0, v_TexCoord.xy);
	
	// Extraction et saturation des teintes cybernétiques de la pupille (Cyan / Magenta)
	vec3 pupilColor = sample.rgb;
	// Anneau externe Cyan : dominance de bleu et vert sur le rouge
	if (sample.b > sample.r + 0.08 && sample.g > sample.r + 0.04) {
		pupilColor = vec3(0.0, 0.94, 1.0); // Cyan néon (#00f0ff)
	}
	// Anneau interne Magenta : dominance de rouge et bleu sur le vert
	else if (sample.r > sample.g + 0.12 && sample.b > sample.g) {
		pupilColor = vec3(0.96, 0.15, 0.65); // Magenta néon (#e0287d)
	}
	// Reflet spéculaire blanc
	else if (sample.r > 0.70 && sample.g > 0.70 && sample.b > 0.70) {
		pupilColor = vec3(0.70, 0.90, 1.0); // Blanc glacé cyan
	}
	// Centre sombre de la pupille
	else {
		pupilColor = vec3(0.35, 0.10, 0.45); // Violet sombre cyber
	}

	// Modulation temporelle : cycle de 30s, durée aléatoire 3s à 10s
	float cyclePeriod = 30.0;
	float cycleIndex = floor(g_Time / cyclePeriod);
	float tLocal = mod(g_Time, cyclePeriod);
	float hDur = hash11(cycleIndex * 13.37 + 1.0);
	float hStart = hash11(cycleIndex * 29.71 + 5.0);
	float duration = 3.0 + 7.0 * hDur; // Aléatoire entre 3.0s et 10.0s
	// Cycle 0 démarre à t=0.5s pour une visibilité immédiate au lancement
	float tStart = (cycleIndex == 0.0) ? 0.5 : (0.5 + hStart * max(0.1, cyclePeriod - duration - 1.0));
	float xProg = (tLocal - tStart) / duration;
	float inWindow = step(0.0, xProg) * step(xProg, 1.0);
	// Montée douce et retour fluide à l'état neutre
	float envelope = sin(clamp(xProg, 0.0, 1.0) * 3.14159265) * inWindow;

	// Émission lumineuse strictement limitée aux pixels du masque de la pupille
	// Facteur 0.85 pour une illumination nette, franche et visible sans délaver les couleurs
	float intensity = 0.85 * envelope * mask;
	gl_FragColor = vec4(pupilColor * intensity, intensity);
}
