# Assets & Shaders du Thème Lucy (`ressource/`) 🌌

Ressources graphiques, shaders GLSL natifs et descripteurs de scène pour le fond d'écran animé **Lucy (Cyberpunk: Edgerunners)** sous Wallpaper Engine (Steam Workshop `3566437475`).

---

## 📁 Arborescence & Rôles des Fichiers

```
ressource/
├── lucy.png                 # Artwork maître 1920x1080 nettoyé (détourage subpixel cheveux & doigts)
├── lucy.tex                 # Conteneur binaire de texture Wallpaper Engine (TEXV0005 / FIF_PNG)
├── lucy_model.json          # Descripteur géométrique du modèle Lucy
├── lucy_material.json       # Descripteur du matériau principal et liaisons de textures
├── scene.json               # Configuration de la scène (passes de post-traitement, shine, bloom)
├── preview.gif              # Vignette animée officielle du Workshop
└── blackwall/               # Effet Blackwall natif GLSL (remplace les particules non supportées)
    ├── blackwall.frag       # Fragment shader optimisé (Fast-Path GPU, glyphes vectorisés)
    ├── blackwall.vert       # Vertex shader pour la projection 2D de la passe Blackwall
    ├── blackwall_mask.png   # Masque subpixel haute fidélité (isolation du gradient de fond)
    ├── blackwall_mask.tex   # Masque compilé en conteneur binaire TEXV0005
    ├── blackwall.json       # Liaisons des propriétés et passes de rendu
    └── effect.json          # Descripteur de l'effet pour le moteur Wallpaper Engine
```

---

## ⚡ Architecture & Performance du Shader Blackwall

### 1. Fast-Path GPU Zero-Overhead
Le shader [`blackwall.frag`](file:///home/user/Documents/antigravity/hyprland_project/ressource/blackwall/blackwall.frag) intègre une condition d'abandon précoce :
```glsl
if (mask <= 0.001) {
    gl_FragColor = orig;
    return;
}
```
Ce court-circuit évite le calcul lourd du réseau cybernétique et des flux de code sur **~65% des pixels de l'écran** (silhouette complète de Lucy), réduisant drastiquement la consommation GPU.

### 2. Vectorisation & Calculs sans Racine
- **Générateur de glyphes (`renderGlyph`)** : Traitement simultané sur 4 canaux vectoriels (`vec4`) au lieu de 4 appels scalaires successifs.
- **Distances euclidiennes** : Remplacement des fonctions `length(v)` par `dot(v, v)` pour éliminer les calculs de racines carrées superflues au niveau matériel.

---

## 🎭 Modélisation Analytique du Fond & Masque Subpixel

L'image d'origine ne disposait pas de canal alpha natif. L'arrière-plan d'origine suit un gradient linéaire vertical parfait :
$$\begin{aligned}
R_{bg}(y) &= y \times \frac{170}{1079} \\
G_{bg}(y) &= 0 \\
B_{bg}(y) &= y \times \frac{88}{1079}
\end{aligned}$$

L'algorithme de génération de masque (`scripts/wallpaper_tool.py mask`) applique :
- **Ensemencement universel** : Détection des pixels de fond piégés ($D \le 1.8$).
- **Propagation subpixel (BFS)** : Expansion douce avec seuil d'adhérence $D < 18.0$ et lissage `smoothstep`.
- **Préservation anatomique** : Préservation intégrale de la fente cou/dos et détourage net des fentes entre les doigts de la main.

---

## 🛠️ Compilation & Déploiement

Toutes les opérations sur ces ressources sont automatisées via le CLI :

```bash
# Régénérer le masque et recompiler le blackwall_mask.tex
./scripts/wallpaper_tool.py mask

# Déployer les shaders, textures et scene.json vers le Workshop Steam
./scripts/wallpaper_tool.py sync

# Redémarrer les instances Wallpaper Engine sur DP-1 et DP-2
./scripts/wallpaper_tool.py restart
```
