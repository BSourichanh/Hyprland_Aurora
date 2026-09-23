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
	// Sécurité spatiale : confinement absolu au rectangle englobant des yeux de Lucy
	float inEyeRegion = step(0.35, v_TexCoord.x) * step(v_TexCoord.x, 0.65) *
	                    step(0.24, v_TexCoord.y) * step(v_TexCoord.y, 0.45);

#if MASK
	float mask = texSample2D(g_Texture1, v_TexCoord.zw).r * inEyeRegion;
#else
	float mask = inEyeRegion;
#endif

	vec4 sample = texSample2D(g_Texture0, v_TexCoord.xy);
	
	// Classification stricte des pixels appartenant à l'intérieur de l'iris et la pupille
	float isIris = 0.0;
	vec3 pupilColor = vec3(0.0);
	
	// Anneau externe Cyan : dominance de bleu et vert sur le rouge
	if (sample.b > sample.r + 0.10 && sample.g > sample.r + 0.06 && sample.b > 0.45) {
		pupilColor = vec3(0.0, 0.94, 1.0); // Cyan néon vibrant (#00f0ff)
		isIris = 1.0;
	}
	// Anneau interne Magenta : dominance de rouge et bleu sur le vert
	else if (sample.r > sample.g + 0.16 && sample.b > sample.g + 0.02 && sample.r > 0.45) {
		pupilColor = vec3(0.96, 0.15, 0.65); // Magenta néon vibrant (#e0287d)
		isIris = 1.0;
	}
	// Reflet spéculaire blanc au coeur de la pupille
	else if (sample.r > 0.75 && sample.g > 0.75 && sample.b > 0.75) {
		pupilColor = vec3(0.70, 0.90, 1.0); // Blanc glacé cyan
		isIris = 1.0;
	}
	// Centre sombre de la pupille (violet profond cyber)
	else if (sample.r < 0.40 && sample.g < 0.35 && sample.b < 0.45 && sample.r > 0.12 && sample.b > 0.15) {
		pupilColor = vec3(0.35, 0.10, 0.45);
		isIris = 1.0;
	}

	// Modulation temporelle : cycle de 30s, durée aléatoire 3s à 10s
	float cyclePeriod = 30.0;
	float cycleIndex = floor(g_Time / cyclePeriod);
	float tLocal = mod(g_Time, cyclePeriod);
	float hDur = hash11(cycleIndex * 13.37 + 1.0);
	float hStart = hash11(cycleIndex * 29.71 + 5.0);
	float duration = 3.0 + 7.0 * hDur; // Aléatoire entre 3.0s et 10.0s
	// Cycle 0 démarre à t=0.8s pour une visibilité immédiate après relance
	float tStart = (cycleIndex == 0.0) ? 0.8 : (0.5 + hStart * max(0.1, cyclePeriod - duration - 1.0));
	float xProg = (tLocal - tStart) / duration;
	float inWindow = step(0.0, xProg) * step(xProg, 1.0);
	// Montée douce et retour fluide à l'état neutre
	float envelope = sin(clamp(xProg, 0.0, 1.0) * 3.14159265) * inWindow;

	// Émission lumineuse strictement confinée à l'intérieur de la pupille (zéro bavure, zéro boule)
	float intensity = 0.55 * envelope * mask * isIris;
	gl_FragColor = vec4(pupilColor * intensity, intensity);
}
