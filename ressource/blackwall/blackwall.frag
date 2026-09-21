#include "common.h"

uniform sampler2D g_Texture0; // {"hidden":true}
uniform sampler2D g_Texture1; // {"combo":"MASK"}
uniform float g_Time;

varying vec4 v_TexCoord;

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

// Procedural cyber glyph generator (hex, binary, runes)
float renderGlyph(vec2 cellUv, float seed) {
    if (cellUv.x < 0.12 || cellUv.x > 0.88 || cellUv.y < 0.12 || cellUv.y > 0.88) {
        return 0.0;
    }
    vec4 s4 = fract(seed * vec4(7.13, 13.37, 19.81, 29.43));
    float p1 = step(0.35, s4.x) * (step(cellUv.x, 0.32) + step(0.68, cellUv.x));
    float p2 = step(0.40, s4.y) * (step(cellUv.y, 0.32) + step(0.68, cellUv.y));
    vec2 centerOffset = abs(cellUv - 0.5);
    float p3 = step(0.30, s4.z) * step(centerOffset.x, 0.16);
    float p4 = step(0.30, s4.w) * step(centerOffset.y, 0.16);
    vec2 dCenter = cellUv - 0.5;
    float centerDot = step(0.65, fract(seed * 43.19)) * step(dot(dCenter, dCenter), 0.0484);
    return clamp(p1 + p2 + p3 + p4 + centerDot, 0.0, 1.0);
}

void main() {
    vec2 uv = v_TexCoord.xy;
    vec4 orig = texSample2D(g_Texture0, uv);
    float mask = texSample2D(g_Texture1, uv).r;

    // Fast-path GPU: le premier plan Lucy couvre ~65% de l'ecran, court-circuiter les calculs proceduraux
    if (mask <= 0.001) {
        gl_FragColor = orig;
        return;
    }

    // 1. Deep Obsidian / Blood-Red Void Gradient
    vec3 bgVoid = mix(vec3(0.02, 0.001, 0.006), vec3(0.18, 0.003, 0.035), 1.0 - uv.y);
    
    // Rogue AI low-frequency energy pulse
    float breath = sin(g_Time * 1.6) * 0.5 + 0.5;
    float pulse = sin(g_Time * 0.9 - uv.y * 3.5) * 0.5 + 0.5;
    bgVoid += vec3(0.12, 0.002, 0.02) * (breath * 0.6 + pulse * 0.4);

    // 2. Cyberspace Partition Grid (Blackwall Firewall Grid)
    vec2 gridCount = vec2(70.0, 40.0);
    vec2 gridUv = uv * gridCount;
    vec2 gridFract = fract(gridUv);
    float gridLine = max(step(0.92, gridFract.x), step(0.92, gridFract.y));
    float gridWave = sin(gridUv.y * 0.25 - g_Time * 2.5) * 0.5 + 0.5;
    vec3 gridColor = vec3(0.45, 0.015, 0.08) * gridLine * (0.35 + 0.65 * gridWave);

    // 3. LAYER A: Dense Micro Data Stream (Background depth layer)
    float colsA = 110.0;
    float colIdA = floor(uv.x * colsA);
    float colU_A = fract(uv.x * colsA);
    float seedA = hash11(colIdA * 17.41);
    float speedA = mix(0.5, 1.6, seedA);
    float yFlowA = uv.y + g_Time * speedA * 0.3 + seedA * 12.0;
    float rowsA = 55.0;
    float rowIdA = floor(yFlowA * rowsA);
    float cellV_A = fract(yFlowA * rowsA);
    float glyphA = renderGlyph(vec2(colU_A, cellV_A), hash21(vec2(colIdA, rowIdA)));
    float phaseA = fract(yFlowA * 0.09 + seedA * 2.0);
    float streamA = pow(max(0.0, 1.0 - phaseA), 3.0) * glyphA * 1.3;
    vec3 colorA = vec3(0.75, 0.01, 0.12) * streamA;

    // 4. LAYER B: Primary Blackwall Rogue AI Streams (Crisp foreground data)
    float colsB = 65.0;
    float colIdB = floor(uv.x * colsB);
    float colU_B = fract(uv.x * colsB);
    float seedB = hash11(colIdB * 31.89);
    float speedB = mix(0.4, 1.2, seedB);
    
    // Corrupted stream micro-jitter
    float jitterTrig = step(0.982, hash11(floor(g_Time * 14.0) + colIdB));
    float jitter = jitterTrig * (hash11(g_Time * 2.0 + colIdB) - 0.5) * 0.18;
    
    float yFlowB = uv.y + g_Time * speedB * 0.38 + seedB * 7.0 + jitter;
    float rowsB = 38.0;
    float rowIdB = floor(yFlowB * rowsB);
    float cellV_B = fract(yFlowB * rowsB);
    float glyphB = renderGlyph(vec2(colU_B, cellV_B), hash21(vec2(colIdB, rowIdB)));
    
    float phaseB = fract(yFlowB * 0.13 + seedB * 5.0);
    float tailB = pow(max(0.0, 1.0 - phaseB), 4.0);
    float headB = smoothstep(0.95, 1.0, 1.0 - phaseB);
    
    vec3 coreColor = vec3(1.0, 0.02, 0.22) * (glyphB * tailB * 2.6);
    // Cyan rogue AI packet spark heads (Netrunner Blackwall signature)
    float isCyan = step(0.80, seedB);
    vec3 sparkColor = mix(vec3(1.0, 0.45, 0.55), vec3(0.0, 0.95, 1.0), isCyan);
    vec3 spark = sparkColor * (glyphB * headB * 4.5);
    vec3 colorB = coreColor + spark;

    // 5. Ambient Cyber Scanlines & Flare
    float scanline = sin(uv.y * 540.0) * 0.035;
    vec3 blackwallBg = bgVoid + gridColor + colorA + colorB + vec3(scanline);

    // 6. Silhouette Atmosphere & Volumetric Red Back-Glow
    float rim = smoothstep(0.0, 0.35, mask) * smoothstep(1.0, 0.55, mask);
    vec3 rimGlow = vec3(1.0, 0.03, 0.20) * rim * (0.8 + 0.4 * breath);

    // Composite: background Blackwall + foreground Lucy with rim glow
    vec3 finalRgb = mix(orig.rgb + rimGlow, blackwallBg, mask);

    gl_FragColor = vec4(finalRgb, 1.0);
}
