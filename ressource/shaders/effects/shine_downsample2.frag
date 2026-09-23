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
	
#if NOISE
	float noiseSample = texSample2D(g_Texture2, v_NoiseTexCoord.xy).r * texSample2D(g_Texture2, v_NoiseTexCoord.zw).r;
	noiseSample = mix(sample.a, sample.a * noiseSample, g_NoiseAmount);
#endif
	
	sample.rgb *= sample.a;
	sample.a = 1.0;
	
	gl_FragColor = sample * mask * step(g_Threshold, dot(vec3(0.11, 0.59, 0.3), sample.rgb));

#if NOISE
	gl_FragColor.a *= noiseSample;
#endif

	// Modulation temporelle : fréquence réduite et durée aléatoire entre 1.0s et 5.0s
	float cyclePeriod = 13.0;
	float cycleIndex = floor(g_Time / cyclePeriod);
	float tLocal = mod(g_Time, cyclePeriod);
	float hDur = hash11(cycleIndex * 13.37 + 1.0);
	float hStart = hash11(cycleIndex * 29.71 + 5.0);
	float duration = 1.0 + 4.0 * hDur; // Aléatoire entre 1.0s et 5.0s
	// Cycle 0 démarre à t=0.8s pour une visibilité immédiate après relance
	float tStart = (cycleIndex == 0.0) ? 0.8 : (0.5 + hStart * max(0.1, cyclePeriod - duration - 1.0));
	float xProg = (tLocal - tStart) / duration;
	float inWindow = step(0.0, xProg) * step(xProg, 1.0);
	float envelope = sin(clamp(xProg, 0.0, 1.0) * 3.14159265) * inWindow;
	gl_FragColor *= envelope;
}
