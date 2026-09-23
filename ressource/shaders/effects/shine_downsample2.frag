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
	// Sécurité spatiale : strict confinement aux coordonnées des yeux de Lucy
	float inEyeRegion = step(0.35, v_TexCoord.x) * step(v_TexCoord.x, 0.65) *
	                    step(0.24, v_TexCoord.y) * step(v_TexCoord.y, 0.45);

#if MASK
	float mask = texSample2D(g_Texture1, v_TexCoord.zw).r * inEyeRegion;
#else
	float mask = inEyeRegion;
#endif
	vec4 sample = texSample2D(g_Texture0, v_TexCoord.xy);
	
#if NOISE
	float noiseSample = texSample2D(g_Texture2, v_NoiseTexCoord.xy).r * texSample2D(g_Texture2, v_NoiseTexCoord.zw).r;
	noiseSample = mix(sample.a, sample.a * noiseSample, g_NoiseAmount);
#endif
	
	sample.rgb *= sample.a;
	sample.a = 1.0;

	// Extraction et saturation des teintes cybernétiques de la pupille (Cyan / Magenta)
	vec3 pupilColor = sample.rgb;
	// Anneau externe Cyan : dominance de bleu et vert sur le rouge
	if (pupilColor.b > pupilColor.r + 0.12 && pupilColor.g > pupilColor.r + 0.08) {
		pupilColor = vec3(0.0, 0.94, 1.0); // Cyan néon vibrant (#00f0ff)
	}
	// Anneau interne Magenta : dominance de rouge et bleu sur le vert
	else if (pupilColor.r > pupilColor.g + 0.18 && pupilColor.b > pupilColor.g + 0.04) {
		pupilColor = vec3(0.96, 0.15, 0.65); // Magenta néon vibrant (#e0287d)
	}
	// Reflet spéculaire blanc : adouci en blanc glacé pour préserver la chromaticité
	else if (pupilColor.r > 0.75 && pupilColor.g > 0.75 && pupilColor.b > 0.75) {
		pupilColor = vec3(0.65, 0.88, 1.0);
	}
	// Centre de la pupille sombre : lueur violette cybernétique profonde
	else if (pupilColor.r < 0.4 && pupilColor.g < 0.35 && pupilColor.b < 0.45) {
		pupilColor = vec3(0.35, 0.10, 0.45);
	}
	
	gl_FragColor = vec4(pupilColor, 1.0) * mask * step(g_Threshold, dot(vec3(0.11, 0.59, 0.3), sample.rgb));

#if NOISE
	gl_FragColor.a *= noiseSample;
#endif

	// Modulation temporelle : fréquence espacée (cycle de 30s) et durée aléatoire entre 3.0s et 10.0s
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
	float envelope = sin(clamp(xProg, 0.0, 1.0) * 3.14159265) * inWindow;
	gl_FragColor *= envelope;
}
