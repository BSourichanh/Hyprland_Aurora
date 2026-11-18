-- Hyprland Configuration - Aurora Theme
-- Adapted for Hyprland 0.57.2 on Ubuntu 24.04 LTS

local source = debug.getinfo(1, "S").source
if source and source:sub(1, 1) == "@" then
    local dir = source:sub(2):match("^(.*[/\\])") or "./"
    package.path = dir .. "?.lua;" .. package.path
end

local home = os.getenv("HOME") or ""

-- ----------------- MONITORS -----------------
hl.monitor({ output = "DP-2", mode = "1920x1080@60", position = "0x0", scale = 1 })
hl.monitor({ output = "DP-1", mode = "1920x1080@60", position = "1920x0", scale = 1 })
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })

-- Workspaces écran principal (Gauche : DP-2) & secondaire (Droite : DP-1)
for i = 1, 5 do hl.workspace_rule({ workspace = tostring(i), monitor = "DP-2", default = (i == 1) or nil }) end
for i = 6, 10 do hl.workspace_rule({ workspace = tostring(i), monitor = "DP-1", default = (i == 6) or nil }) end

-- Workspaces temporaires de verrouillage (masquage hyprlock)
hl.workspace_rule({ workspace = "98", monitor = "DP-2", persistent = false })
hl.workspace_rule({ workspace = "99", monitor = "DP-1", persistent = false })

-- Workspace spécial déroulant (Scratchpad Terminal)
hl.workspace_rule({ workspace = "special:scratchpad" })
hl.on("workspace.created", function(ws)
    if ws and (ws.name == "special:scratchpad" or ws.name == "scratchpad" or ws.addressable_name == "special:scratchpad") and ws.is_empty then
        hl.exec_cmd("kitty --class scratchpad-term")
    end
end)

-- ----------------- ENVIRONMENT -----------------
local currentPath = os.getenv("PATH") or ""
local localBin = home .. "/.local/bin"
hl.env("PATH", currentPath ~= "" and (localBin .. ":" .. currentPath) or localBin)
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")
hl.env("TERMINAL", "kitty")

-- ----------------- DEFAULT APPS -----------------
local terminal    = "kitty"
local fileManager = "nautilus"
local menu        = home .. "/.config/hypr/scripts/wofi-toggle.sh"

hl.on("hyprland.start", function()
    hl.exec_cmd("xrandr --output DP-2 --primary --mode 1920x1080 --pos 0x0 --output DP-1 --mode 1920x1080 --right-of DP-2")
    hl.exec_cmd("swaybg -i " .. home .. "/.config/hypr/theme-summer/wallpaper.jpg")
    hl.exec_cmd(home .. "/.config/hypr/scripts/wallpaper_daemon.sh")
    hl.exec_cmd("waybar")
    hl.exec_cmd(home .. "/.config/waybar/scripts/spotify-card.py daemon &")
    hl.exec_cmd(localBin .. "/aurora-osd daemon &")
    hl.exec_cmd("hypridle")
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("systemctl --user start hyprpolkitagent.service || /usr/libexec/hyprpolkitagent")
    hl.exec_cmd("python3 " .. home .. "/.config/hypr/scripts/workspace-autocompact.py &")
end)

-- ----------------- INPUT & AURORA THEME STYLE -----------------
hl.config({
    input = {
        kb_layout    = "fr",
        kb_variant   = "",
        kb_model     = "pc105",
        follow_mouse = 0,
        touchpad     = { natural_scroll = true },
        sensitivity  = 0,
    },
    general = {
        gaps_in     = 4,
        gaps_out    = 8,
        border_size = 2,
        col = {
            active_border = { colors = { "rgba(00F0FFFF)", "rgba(7AA2F7FF)", "rgba(9778D0FF)", "rgba(00F0FFFF)" }, angle = 45 },
            inactive_border = "rgba(04404aaa)",
        },
        layout        = "dwindle",
        allow_tearing = false,
    },
    decoration = {
        rounding = 17,
        blur     = { enabled = true, size = 6, passes = 1, new_optimizations = true },
        shadow   = { enabled = true, range = 1, render_power = 3 },
    },
    animations = { enabled = true },
    dwindle    = { preserve_split = true },
    misc = {
        force_default_wallpaper    = 0,
        disable_hyprland_logo      = true,
        session_lock_xray          = true,
        session_lock_blur          = true,
        allow_session_lock_restore = true,
        mouse_move_enables_dpms    = true,
        key_press_enables_dpms     = true,
        bell_sound                 = "",
    },
    layers = { allow_new_top_layers_over_existing_fullscreen = true, layers_hog_keyboard_focus = true },
    render = { use_fp16 = 0 },
    ecosystem = { no_update_news = true, no_donation_nag = true },
    debug = { vfr = true },
    binds = { scroll_event_delay = 0, pass_mouse_when_bound = false },
})

-- ----------------- AURORA THEME ANIMATIONS -----------------
hl.curve("linear",       { type = "bezier", points = { {0.0, 0.0},  {1.0, 1.0}  } })
hl.curve("md3_standard", { type = "bezier", points = { {0.2, 0.0},  {0, 1.0}    } })
hl.curve("md3_decel",    { type = "bezier", points = { {0.05, 0.7}, {0.1, 1}    } })
hl.curve("overshot",     { type = "bezier", points = { {0.05, 0.9}, {0.1, 1.05} } })

hl.animation({ leaf = "windows",          enabled = true, speed = 3,  bezier = "overshot",  style = "popin 80%" })
hl.animation({ leaf = "windowsOut",       enabled = true, speed = 3,  bezier = "default",   style = "popin 80%" })
hl.animation({ leaf = "border",           enabled = true, speed = 10, bezier = "default" })
-- hl.animation({ leaf = "borderangle", enabled = true, speed = 50, bezier = "linear", style = "loop" }) -- Désactivé pour VFR et zéro charge idle
hl.animation({ leaf = "fade",             enabled = true, speed = 3,  bezier = "default" })
hl.animation({ leaf = "workspaces",       enabled = true, speed = 4,  bezier = "md3_decel", style = "slidefade 20%" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 3,  bezier = "md3_decel", style = "slidevert" })
hl.animation({ leaf = "layersIn",         enabled = true, speed = 3,  bezier = "md3_decel", style = "popin 92%" })
hl.animation({ leaf = "layersOut",        enabled = true, speed = 2,  bezier = "md3_decel", style = "fade" })

-- ----------------- LAYER & WINDOW RULES -----------------
hl.layer_rule({ name = "waybar_blur",             match = { namespace = "waybar" },                     blur = true, ignore_alpha = 0.1 })
hl.layer_rule({ name = "wofi_blur",               match = { namespace = "wofi" },                       blur = true, ignore_alpha = 0.1 })
hl.layer_rule({ name = "aurora_osd_blur",         match = { namespace = "aurora-osd" },                 blur = true, ignore_alpha = 0.1 })
hl.layer_rule({ name = "swaync_blur",             match = { namespace = "swaync-control-center" },      blur = true, ignore_alpha = 0.1, animation = "slide right" })
hl.layer_rule({ name = "swaync_notif_blur",       match = { namespace = "swaync-notification-window" }, blur = true, ignore_alpha = 0.1, animation = "slide right" })
hl.layer_rule({ name = "selection_noanim",        match = { namespace = "selection" },                  no_anim = true })
hl.layer_rule({ name = "hyprpicker_noanim",       match = { namespace = "hyprpicker" },                 no_anim = true })
hl.layer_rule({ name = "aurora_wallpaper_noanim", match = { namespace = "aurora-wallpaper" },           no_anim = true })

hl.window_rule({ name = "float-steam",         match = { class = "steam" },                                float = true })
hl.window_rule({ name = "float-pavucontrol",   match = { class = "pavucontrol" },                          float = true, center = true, size = "800 500" })
hl.window_rule({ name = "float-file-roller",   match = { class = "^(file-roller|org.gnome.FileRoller)$" }, float = true, center = true })
hl.window_rule({ name = "float-blueman",       match = { class = "^(blueman-manager)$" },                  float = true, center = true })
hl.window_rule({ name = "float-image-viewers", match = { class = "^(imv|viewnior|loupe)$" },               float = true, center = true })
hl.window_rule({ name = "float-xdg-portal",    match = { class = "^(xdg-desktop-portal-.*)$" },            float = true, center = true })
hl.window_rule({ name = "float-nm-editor",     match = { class = "^(nm-connection-editor)$" },             float = true, center = true })
hl.window_rule({ name = "float-open-file",     match = { title = "^(Open File)(.*)$" },                    float = true })
hl.window_rule({ name = "float-open-folder",   match = { title = "^(Open Folder)(.*)$" },                  float = true })
hl.window_rule({ name = "float-save-as",       match = { title = "^(Save As)(.*)$" },                      float = true })
hl.window_rule({ name = "float-confirmation",  match = { title = "^(Confirmation)(.*)$" },                 float = true })
hl.window_rule({
    name             = "spotify-card",
    match            = { class = "^(spotify-card)$" },
    float            = true,
    pin              = true,
    move             = "600 44",
    border_size      = 0,
    no_initial_focus = true,
    animation        = "slide top",
})
hl.window_rule({
    name      = "scratchpad-term",
    match     = { class = "^(scratchpad-term)$" },
    float     = true,
    size      = "1100 650",
    center            = true,
    focus_on_activate = true,
    animation         = "slide top",
})
hl.window_rule({
    name             = "paros-companion",
    match            = { class = "^(Paros)$" },
    float            = true,
    pin              = true,
    border_size      = 0,
    no_shadow        = true,
    no_blur          = true,
    rounding         = 0,
    tag              = "+hyprglass_disabled",
    no_initial_focus = true,
    no_anim          = true,
})

-- ----------------- PLUGINS -----------------
hl.plugin.load(home .. "/.config/hypr/plugins/Hyprspace.so")
hl.plugin.load(home .. "/.config/hypr/plugins/hyprglass.so")

if hl.plugin.overview then
    hl.config({
        plugin = {
            overview = {
                centerAligned       = true,
                drawActiveWorkspace = true,
                showNewWorkspace    = true,
                exitOnClick         = true,
                exitOnSwitch        = true,
                affectStrut         = false,
                overrideGaps        = false,
            },
        },
    })
end

if hl.plugin.hyprglass then
    local hg = hl.plugin.hyprglass
    hg.config({
        enabled              = true,
        manage_window_blur   = true,
        default_theme        = "dark",
        default_preset       = "clear",
        tint_color           = 0x8899aa22,
        glass_opacity        = 0.50,
        blur_iterations      = 1,
        chromatic_aberration = 0.0,
        brightness           = 0.9,
        dark  = { blur_iterations = 1, chromatic_aberration = 0.0, brightness = 0.82 },
        light = { adaptive_boost = 0.5 },
        layers = { enabled = true },
    })
    hg.layer("hyprlock", { preset = "clear" })
end

-- ----------------- KEYBINDINGS -----------------
local mainMod = "SUPER"
local osd     = localBin .. "/aurora-osd"
local scripts = home .. "/.config/hypr/scripts"

-- Audio, OSD & Media (Volume wheel, touches multimédia, Verr. Maj)
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd(osd .. " volume-up"),   { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd(osd .. " volume-down"), { locked = true, repeating = true })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd(osd .. " volume-mute"), { locked = true })
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd(osd .. " mic-mute"),    { locked = true })
hl.bind("Caps_Lock",            hl.dsp.exec_cmd(osd .. " caps-lock"),   { release = true, locked = true })
hl.bind("CAPS + Caps_Lock",     hl.dsp.exec_cmd(osd .. " caps-lock"),   { release = true, locked = true })
hl.bind("XF86AudioPlay",        hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPause",       hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioNext",        hl.dsp.exec_cmd("playerctl next"),       { locked = true })
hl.bind("XF86AudioPrev",        hl.dsp.exec_cmd("playerctl previous"),   { locked = true })

-- Hyprspace Overview (Mission Control)
if hl.plugin.overview then
    hl.bind(mainMod .. " + TAB", hl.plugin.overview.toggle)
else
    hl.bind(mainMod .. " + TAB", function()
        if hl.plugin.overview then
            hl.plugin.overview.toggle()
        end
    end)
end

-- Applications
hl.bind(mainMod .. " + Return", hl.dsp.exec_cmd(terminal))
hl.bind(mainMod .. " + Q",      hl.dsp.exec_cmd(terminal))

-- Scratchpad Terminal déroulant (Special Workspace, touche physique code:49 = ²)
hl.bind(mainMod .. " + code:49",         hl.dsp.workspace.toggle_special("scratchpad"))
hl.bind(mainMod .. " + F12",             hl.dsp.workspace.toggle_special("scratchpad"))
hl.bind(mainMod .. " + SHIFT + code:49", hl.dsp.window.move({ workspace = "special:scratchpad" }))
hl.bind(mainMod .. " + SHIFT + F12",     hl.dsp.window.move({ workspace = "special:scratchpad" }))
hl.bind(mainMod .. " + C",               hl.dsp.window.close())
hl.bind(mainMod .. " + SHIFT + M",       hl.dsp.exit())
hl.bind(mainMod .. " + L",               hl.dsp.exec_cmd(home .. "/.config/hypr/lock.sh"))
hl.bind(mainMod .. " + S",               hl.dsp.exec_cmd(scripts .. "/power-menu.sh"))
hl.bind(mainMod .. " + E",               hl.dsp.exec_cmd(fileManager))
hl.bind(mainMod .. " + V",               hl.dsp.window.float({ action = "toggle" }))
hl.bind(mainMod .. " + F",               hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" }))
hl.bind(mainMod .. " + R",               hl.dsp.exec_cmd(menu))
hl.bind(mainMod .. " + N",               hl.dsp.exec_cmd("swaync-client -t -sw"))
hl.bind(mainMod .. " + SHIFT + R",       hl.dsp.exec_cmd(scripts .. "/reload.sh"))
hl.bind(mainMod .. " + P",               hl.dsp.window.pseudo())
hl.bind(mainMod .. " + J",               hl.dsp.layout("togglesplit"))

-- Raccourci d'arrêt d'urgence MCP (Hypruse panic switch)
hl.bind(mainMod .. " + SHIFT + BackSpace", hl.dsp.exec_cmd("hypruse stop"))

-- Captures d'écran (Print Screen / Impr écran)
hl.bind("Print",                   hl.dsp.exec_cmd(scripts .. "/screenshot.sh area"))
hl.bind("SHIFT + Print",           hl.dsp.exec_cmd(scripts .. "/screenshot.sh screen"))
hl.bind("CTRL + Print",            hl.dsp.exec_cmd(scripts .. "/screenshot.sh full"))
hl.bind(mainMod .. " + Print",     hl.dsp.exec_cmd(scripts .. "/screenshot.sh window"))
hl.bind(mainMod .. " + SHIFT + S", hl.dsp.exec_cmd(scripts .. "/screenshot.sh area"))

-- Focus Navigation
hl.bind(mainMod .. " + left",  hl.dsp.focus({ direction = "left" }))
hl.bind(mainMod .. " + right", hl.dsp.focus({ direction = "right" }))
hl.bind(mainMod .. " + up",    hl.dsp.focus({ direction = "up" }))
hl.bind(mainMod .. " + down",  hl.dsp.focus({ direction = "down" }))

-- Workspaces & Move window to workspace (AZERTY 1-10)
local wsKeys = { "ampersand", "eacute", "quotedbl", "apostrophe", "parenleft", "minus", "egrave", "underscore", "ccedilla", "agrave" }
for i, key in ipairs(wsKeys) do
    hl.bind(mainMod .. " + " .. key,           hl.dsp.focus({ workspace = i }))
    hl.bind(mainMod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }))
end

-- Mouse bindings
hl.bind(mainMod .. " + mouse:272",          hl.dsp.window.drag(),   { mouse = true })
hl.bind(mainMod .. " + mouse:273",          hl.dsp.window.resize(), { mouse = true })
hl.bind(mainMod .. " + mouse_down",         hl.dsp.focus({ workspace = "e+1" }))
hl.bind(mainMod .. " + mouse_up",           hl.dsp.focus({ workspace = "e-1" }))
hl.bind(mainMod .. " + SHIFT + mouse_down", hl.dsp.window.move({ workspace = "e+1" }))
hl.bind(mainMod .. " + SHIFT + mouse_up",   hl.dsp.window.move({ workspace = "e-1" }))

-- Source for hyprviz
require("hyprviz")
