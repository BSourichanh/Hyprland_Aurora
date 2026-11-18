-- hyprviz configuration (migrated to Hyprland 0.57.2 Lua API)

hl.config({
    decoration = {
        fullscreen_opacity = 1,
        inactive_opacity = 1,
        dim_inactive = false,
        blur = {
            xray = false,
            ignore_opacity = false,
        },
    },
    general = {
        float_gaps = 1,
        gaps_workspaces = 1,
        resize_on_border = true,
        extend_border_grab_area = 20,
        snap = {
            window_gap = 11,
            enabled = true,
        },
    },
    xwayland = {
        force_zero_scaling = true,
    },
})
