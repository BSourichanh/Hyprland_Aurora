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

// Enveloppe temporelle fluide et continue à double variabilité :
// Brillance longue, nette et stable (11s à 14s) ET pause de repos variable (17s à 21s)
// Zéro saut discret, zéro clignotement haute fréquence
float computeEnvelope(float time) {
    float phase = time / 32.0 + 0.12 * sin(time * 0.025);
    float cycleProg = fract(phase);
    float activeRatio = 0.40 + 0.04 * cos(time * 0.015);

    if (cycleProg < activeRatio) {
        float u = cycleProg / activeRatio;
        float fadeIn = smoothstep(0.0, 0.10, u);
        float fadeOut = 1.0 - smoothstep(0.90, 1.0, u);
        return fadeIn * fadeOut;
    }
    return 0.0;
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

	// Enveloppe temporelle à durée active variable et pause de repos variable
	float envelope = computeEnvelope(g_Time);

	// Émission lumineuse confinée à l'intérieur du masque de la pupille
	float intensity = 0.65 * envelope * mask;

	// Alpha = 1.0 impératif pour écraser le FBO à chaque frame (empêche l'accumulation)
	gl_FragColor = vec4(pupilGlow * intensity, 1.0);
}
