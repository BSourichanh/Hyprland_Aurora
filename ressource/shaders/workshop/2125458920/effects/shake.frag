#include "common.h"

varying vec4 v_TexCoord;

uniform sampler2D g_Texture0; // {"material":"framebuffer","hidden":true}
uniform float g_Time;

float hash11(float p) {
    p = frac(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return frac(p);
}

float hash21(vec2 p) {
    vec3 p3 = frac(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return frac((p3.x + p3.y) * p3.z);
}

void main() {
    vec2 uv = v_TexCoord.xy;

    // 1. Relic Malfunction Cycle : fréquence réduite et durée aléatoire entre 1.0s et 3.0s
    float cyclePeriod = 12.0; // Fréquence réduite (~5 fois par minute)
    float cycleIndex = floor(g_Time / cyclePeriod);
    float tLocal = mod(g_Time, cyclePeriod);
    
    float hDur = hash11(cycleIndex * 13.37 + 1.0);
    float hStart = hash11(cycleIndex * 29.71 + 5.0);
    
    float glitchDuration = 1.0 + 2.0 * hDur; // Durée aléatoire entre 1.0s et 3.0s
    float glitchStart = 0.5 + hStart * (cyclePeriod - glitchDuration - 1.0);
    
    float glitchProgress = (tLocal - glitchStart) / glitchDuration;
    float inGlitchWindow = step(0.0, glitchProgress) * step(glitchProgress, 1.0);
    
    // Attaque et relâchement doux sur les 1 à 3 secondes
    float envelope = smoothstep(0.0, 0.2, glitchProgress) * (1.0 - smoothstep(0.8, 1.0, glitchProgress)) * inGlitchWindow;
    
    // Micro-saccades uniquement actives pendant la fenêtre de glitch
    float microTwitch = step(0.88, hash11(floor(g_Time * 12.0) + cycleIndex)) * 0.45;
    float intensity = envelope * max(0.6, microTwitch);

    vec2 glitchUV = uv;
    float time = g_Time * 1.5;

    if (intensity > 0.005) {
        // --- NIVEAU 1: Tranches horizontales partielles (largeurs et positions variées) ---
        float sliceY = floor(uv.y * 42.0);
        float sliceSeed = sliceY + floor(time * 22.0) * 17.13;
        float sliceTrigger = hash11(sliceSeed);

        if (sliceTrigger > 0.65) {
            float xStart = hash11(sliceSeed * 2.31);
            float xLen   = hash11(sliceSeed * 5.73) * 0.45 + 0.12; // Largeur variable : 12% à 57%
            float xEnd   = xStart + xLen;

            bool inSegment = (uv.x >= xStart && uv.x <= xEnd) || 
                             (xEnd > 1.0 && uv.x <= fract(xEnd));

            if (inSegment) {
                float shift = (hash11(sliceSeed * 9.47) - 0.5) * 0.065 * intensity;
                glitchUV.x += shift;
            }
        }

        // --- NIVEAU 2: Blocs rectangulaires 2D (corruption de paquets de données) ---
        vec2 grid2D = vec2(14.0, 32.0);
        vec2 blockCell = floor(uv * grid2D);
        float blockSeed = hash21(blockCell + floor(time * 16.0) * 31.41);

        if (blockSeed > 0.84) {
            float blockShiftX = (hash21(blockCell * 3.1 + 1.7) - 0.5) * 0.045 * intensity;
            float blockShiftY = (hash21(blockCell * 7.9 + 4.3) - 0.5) * 0.012 * intensity;
            glitchUV += vec2(blockShiftX, blockShiftY);
        }

        // --- NIVEAU 3: Micro-lignes et micro-bandes courtes ---
        float fineLineY = floor(uv.y * 140.0);
        float fineSeed = fineLineY + floor(time * 30.0) * 11.87;
        if (hash11(fineSeed) > 0.88) {
            float xCenter = hash11(fineSeed * 3.7);
            float xHalfWidth = hash11(fineSeed * 7.1) * 0.15 + 0.03;
            if (abs(uv.x - xCenter) < xHalfWidth) {
                float microShift = (hash11(fineSeed * 13.9) - 0.5) * 0.025 * intensity;
                glitchUV += microShift;
            }
        }
    }

    // Échantillonnage direct et propre : couleurs originales 100% fidèles, sans frange ni flashs
    vec4 color = texSample2D(g_Texture0, glitchUV);

    gl_FragColor = color;
}
