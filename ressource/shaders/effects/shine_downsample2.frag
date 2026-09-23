// [COMBO] {"material":"ui_editor_properties_noise","combo":"NOISE","type":"options","default":1}

varying vec4 v_TexCoord;

uniform sampler2D g_Texture0; // {"hidden":true}
uniform sampler2D g_Texture1; // {"label":"ui_editor_properties_opacity_mask","mode":"opacitymask","combo":"MASK","paintdefaultcolor":"0 0 0 1"}

uniform float g_Threshold; // {"material":"raythreshold","label":"ui_editor_properties_ray_threshold","default":0.5,"range":[0, 1]}
uniform float g_Time;

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
	
	// Rehaussement chromatique continu et stable (zéro scintillement par seuil discret)
	// Détecte naturellement la dominance spectrale de chaque pixel de l'iris
	float cyanDominance = clamp((sample.b - sample.r) * 2.5, 0.0, 1.0) * clamp((sample.g - sample.r) * 2.5, 0.0, 1.0);
	float magentaDominance = clamp((sample.r - sample.g) * 2.5, 0.0, 1.0) * clamp((sample.b - sample.g) * 2.5, 0.0, 1.0);
	
	vec3 cyberCyan = vec3(0.0, 0.94, 1.0);       // Cyan néon électrique (#00f0ff)
	vec3 cyberMagenta = vec3(0.96, 0.15, 0.65);   // Magenta néon fuchsia (#e0287d)
	
	vec3 pupilGlow = sample.rgb;
	pupilGlow = mix(pupilGlow, cyberCyan, cyanDominance * 0.9);
	pupilGlow = mix(pupilGlow, cyberMagenta, magentaDominance * 0.9);

	// Modulation temporelle avec plateau stable et retour à la normale garanti
	float cyclePeriod = 22.0;
	float cycleIndex = floor(g_Time / cyclePeriod);
	float tLocal = mod(g_Time, cyclePeriod);
	float hDur = hash11(cycleIndex * 13.37 + 1.0);
	float hStart = hash11(cycleIndex * 29.71 + 5.0);
	
	// Durée d'illumination active entre 3.5s et 6.5s
	float duration = 3.5 + 3.0 * hDur;
	// Cycle 0 démarre à t=0.5s pour une vérification immédiate après relance
	float tStart = (cycleIndex == 0.0) ? 0.5 : (0.5 + hStart * max(0.1, cyclePeriod - duration - 1.0));
	float xProg = (tLocal - tStart) / duration;
	
	// Enveloppe avec plateau : montée douce (0.2), maintien stable (0.2 à 0.8), descente fluide (0.8 à 1.0)
	float inWindow = step(0.0, xProg) * step(xProg, 1.0);
	float fadeIn = smoothstep(0.0, 0.20, clamp(xProg, 0.0, 1.0));
	float fadeOut = 1.0 - smoothstep(0.80, 1.0, clamp(xProg, 0.0, 1.0));
	float envelope = fadeIn * fadeOut * inWindow;

	// Émission lumineuse strictement limitée au masque de la pupille
	// Facteur 0.65 pour une illumination intense mais contrôlée
	float intensity = 0.65 * envelope * mask;

	// Alpha = 1.0 impératif pour écraser le FBO à chaque frame (empêche l'accumulation sous blending normal)
	gl_FragColor = vec4(pupilGlow * intensity, 1.0);
}
