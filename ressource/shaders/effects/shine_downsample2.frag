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

// Enveloppe temporelle non périodique à double variabilité :
// Durée active aléatoire (3.5s à 8.5s) ET pause de repos aléatoire (16s à 29s)
float computeEnvelope(float time) {
    const float T_step = 28.0;
    float k0 = floor(time / T_step);
    float totalEnv = 0.0;

    for (int i = -1; i <= 1; ++i) {
        float k = k0 + float(i);
        if (k < 0.0) {
            continue;
        }

        float tStart;
        float duration;

        if (k == 0.0) {
            // Cycle 0 immédiat au démarrage pour validation visuelle instantanée
            tStart = 0.5;
            duration = 5.0;
        } else {
            // Gigue temporelle pseudo-aléatoire rendant chaque pause de repos variable
            float hJit = hash11(k * 31.7 + 7.0);
            float jitter = (hJit - 0.5) * 12.0; // [-6.0s, +6.0s]
            tStart = k * T_step + jitter;

            // Durée d'illumination active aléatoire entre 3.5s et 8.5s
            float hDur = hash11(k * 17.3 + 1.0);
            duration = 3.5 + 5.0 * hDur;
        }

        float x = (time - tStart) / duration;
        if (x >= 0.0 && x <= 1.0) {
            float inWindow = step(0.0, x) * step(x, 1.0);
            float fadeIn = smoothstep(0.0, 0.20, x);
            float fadeOut = 1.0 - smoothstep(0.80, 1.0, x);
            totalEnv += fadeIn * fadeOut * inWindow;
        }
    }
    return clamp(totalEnv, 0.0, 1.0);
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
