#include "common.h"

varying vec4 v_TexCoord;

uniform sampler2D g_Texture0; // {"material":"framebuffer","hidden":true}
uniform float g_Time;

// ============================================================================
// CONFIGURATION DU GLITCH (CONSTANTES NOMMÉES)
// ============================================================================
const float TIME_SCALE      = 1.5;
const float CYCLE_PERIOD    = 3.8;
const float TICK1_START     = 3.20;
const float TICK1_END       = 3.30;
const float TICK2_START     = 3.35;
const float TICK2_END       = 3.43;
const float TICK2_WEIGHT    = 0.70;
const float TWITCH_RATE     = 10.0;
const float TWITCH_THRESH   = 0.982;
const float TWITCH_WEIGHT   = 0.45;

// Géométrie des tranches
const float MACRO_FREQ      = 14.4; // 1080.0 / 75.0 (tranches de 75px de période)
const float MACRO_MIN_H     = 50.0; // Hauteur minimale 50px
const float MACRO_VAR_H     = 25.0; // Plage de variation 50px à 75px
const float WIDTH_BASE      = 0.25; // Largeur minimale (25%)
const float WIDTH_RANGE     = 0.25; // Plage variable (25% à 50%)

// ============================================================================
// FONCTIONS DE HACHAGE & HELPERS
// ============================================================================
float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

float hash21(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// Vérification d'intervalle horizontal avec bouclage torique (DRY)
bool isInsideSpan(float x, float xStart, float xWidth) {
    float xEnd = xStart + xWidth;
    return (x >= xStart && x <= xEnd) || (xEnd > 1.0 && x <= fract(xEnd));
}

// ============================================================================
// MAIN SHADER PIPELINE
// ============================================================================
void main() {
    vec2 uv = v_TexCoord.xy;
    float time = g_Time * TIME_SCALE;

    // 1. Rythme posé : secousse nette et brève toutes les ~3.8s (calme absolu 90% du temps)
    float cycle = mod(time, CYCLE_PERIOD);

    // Double-tic sec et instantané (pas de glissement mou)
    float tick1 = step(TICK1_START, cycle) * (1.0 - step(TICK1_END, cycle)); // Choc principal franc (100ms)
    float tick2 = step(TICK2_START, cycle) * (1.0 - step(TICK2_END, cycle)) * TICK2_WEIGHT; // Réplique secondaire (80ms)
    float twitch = step(TWITCH_THRESH, hash11(floor(time * TWITCH_RATE))) * TWITCH_WEIGHT; // Micro-saccade rare
    float intensity = max(max(tick1, tick2), twitch);

    // -------------------------------------------------------------------------
    // FAST-PATH EARLY EXIT (Optimisation GPU 90% du temps)
    // -------------------------------------------------------------------------
    if (intensity <= 0.005) {
        gl_FragColor = texSample2D(g_Texture0, uv);
        return;
    }

    vec2 glitchUV = uv;
    float frameSeed = floor(time * 20.0) * 23.41;

    // =========================================================================
    // A. GRANDES TRANCHES ÉPAISSES (Hauteur exacte 50px à 75px, largeur 25%-50%)
    // =========================================================================
    float macroY = uv.y * MACRO_FREQ;
    float macroIndex = floor(macroY);
    float macroSeed = macroIndex + frameSeed;
    float macroHeight = hash11(macroSeed * 3.77) * MACRO_VAR_H + MACRO_MIN_H; // 50px à 75px
    float localY = fract(macroY) * 75.0; // Optimisation ALU : fract au lieu de mod

    if (hash11(macroSeed) > 0.65 && localY <= macroHeight) {
        float xStart = hash11(macroSeed * 2.17);
        float xWidth = hash11(macroSeed * 5.43) * WIDTH_RANGE + WIDTH_BASE;

        if (isInsideSpan(uv.x, xStart, xWidth)) {
            float macroShift = (hash11(macroSeed * 9.13) - 0.5) * 0.075 * intensity;
            glitchUV.x += macroShift;
        }
    }

    // =========================================================================
    // B. TRANCHES MOYENNES (Hauteur ~25-45px, largeur variable 25%-50%)
    // =========================================================================
    float midY = floor(uv.y * 30.0);
    float midSeed = midY + frameSeed * 1.47;
    if (hash11(midSeed) > 0.60) {
        float xStart = hash11(midSeed * 1.83);
        float xWidth = hash11(midSeed * 4.61) * WIDTH_RANGE + WIDTH_BASE;

        if (isInsideSpan(uv.x, xStart, xWidth)) {
            float midShift = (hash11(midSeed * 7.77) - 0.5) * 0.050 * intensity;
            glitchUV.x += midShift;
        }
    }

    // =========================================================================
    // C. TRANCHES FINES (Hauteur ~10-18px, largeur variable 25%-50%)
    // =========================================================================
    float fineY = floor(uv.y * 65.0);
    float fineSeed = fineY + frameSeed * 2.19;
    if (hash11(fineSeed) > 0.72) {
        float xStart = hash11(fineSeed * 3.11);
        float xWidth = hash11(fineSeed * 6.29) * WIDTH_RANGE + WIDTH_BASE;

        if (isInsideSpan(uv.x, xStart, xWidth)) {
            float fineShift = (hash11(fineSeed * 11.23) - 0.5) * 0.035 * intensity;
            glitchUV.x += fineShift;
        }
    }

    // =========================================================================
    // D. BLOCS RECTANGULAIRES 2D (Pavés francs de tailles variables)
    // =========================================================================
    // 1. Gros blocs francs (grille 8x16 : 67.5px de haut, décrochages massifs localisés)
    vec2 macroCell = floor(uv * vec2(8.0, 16.0));
    float macroBlockSeed = hash21(macroCell + frameSeed);
    if (macroBlockSeed > 0.88) {
        vec2 bShift = (vec2(hash21(macroCell * 2.7 + 1.1), hash21(macroCell * 6.1 + 3.7)) - 0.5) 
                      * vec2(0.060, 0.015) * intensity;
        glitchUV += bShift;
    }

    // 2. Blocs moyens (grille 18x28, détails nets)
    vec2 midCell = floor(uv * vec2(18.0, 28.0));
    float midBlockSeed = hash21(midCell + frameSeed * 1.33);
    if (midBlockSeed > 0.87) {
        vec2 bShift = (vec2(hash21(midCell * 3.9 + 1.4), hash21(midCell * 8.3 + 4.7)) - 0.5) 
                      * vec2(0.040, 0.008) * intensity;
        glitchUV += bShift;
    }

    // Échantillonnage direct 100% fidèle : couleurs d'origine pures, zéro flash, zéro flou
    gl_FragColor = texSample2D(g_Texture0, glitchUV);
}
