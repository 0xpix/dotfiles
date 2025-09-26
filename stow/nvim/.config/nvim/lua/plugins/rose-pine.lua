return {
  {
    "rose-pine/neovim",
    name = "rose-pine",
    lazy = false,
    priority = 1000,
    config = function()
      -- Track the last applied mode to avoid duplicate work/notifications
      local last_applied_mode = nil

      -- Notification control (default silent; set `vim.g.omarchy_theme_notify = 1` to enable)
      if vim.g.omarchy_theme_notify == nil then
        vim.g.omarchy_theme_notify = 0
      end
      local function notify(msg)
        if vim.g.omarchy_theme_notify == 1 then
          pcall(vim.notify, msg, vim.log.levels.INFO)
        end
      end

      -- Determine desired mode from Omarchy marker
      local function desired_mode_from_omarchy()
        local light_marker = vim.fn.expand("~/.config/omarchy/current/theme/light.mode")
        local stat = vim.loop.fs_stat(light_marker)
        local want_light = stat ~= nil and stat.type == "file"
        return want_light and "light" or "dark"
      end

      -- Apply rose-pine for a given mode ("light"/"dark") once
      local function apply_mode(mode)
        if mode == last_applied_mode then
          return
        end
        last_applied_mode = mode
        if mode == "light" then
          if vim.o.background ~= "light" then
            vim.o.background = "light"
          end
          vim.cmd.colorscheme("rose-pine-dawn")
          -- Extra contrast tweaks specifically for Dawn (light)
          vim.api.nvim_set_hl(0, "Normal", { fg = "#2a273f", bg = "#faf4ed" })
          vim.api.nvim_set_hl(0, "NormalFloat", { fg = "#2a273f", bg = "#f2e9e1" })
          vim.api.nvim_set_hl(0, "LineNr", { fg = "#6e6a86" })
          vim.api.nvim_set_hl(0, "Comment", { fg = "#6e6a86", italic = true })
          vim.api.nvim_set_hl(0, "CursorLine", { bg = "#f2e9e1" })
          vim.api.nvim_set_hl(0, "Pmenu", { fg = "#2a273f", bg = "#f2e9e1" })
          vim.api.nvim_set_hl(0, "PmenuSel", { fg = "#faf4ed", bg = "#907aa9" })
          vim.api.nvim_set_hl(0, "Visual", { bg = "#e6d7ca" })
          vim.api.nvim_set_hl(0, "Search", { fg = "#faf4ed", bg = "#286983", bold = true })
          vim.api.nvim_set_hl(0, "IncSearch", { fg = "#faf4ed", bg = "#b4637a", bold = true })
          vim.cmd([[redraw!]])
          notify("Rose Pine Dawn (light) applied")
        else
          if vim.o.background ~= "dark" then
            vim.o.background = "dark"
          end
          vim.cmd.colorscheme("rose-pine-moon")
          -- Make Moon (dark) explicitly dark to avoid looking similar to Dawn
          vim.api.nvim_set_hl(0, "Normal", { fg = "#e0def4", bg = "#232136" })
          vim.api.nvim_set_hl(0, "NormalFloat", { fg = "#e0def4", bg = "#2a273f" })
          vim.api.nvim_set_hl(0, "LineNr", { fg = "#6e6a86" })
          vim.api.nvim_set_hl(0, "Comment", { fg = "#6e6a86", italic = true })
          vim.api.nvim_set_hl(0, "CursorLine", { bg = "#2a273f" })
          vim.api.nvim_set_hl(0, "Pmenu", { fg = "#e0def4", bg = "#2a273f" })
          vim.api.nvim_set_hl(0, "PmenuSel", { fg = "#232136", bg = "#907aa9" })
          vim.api.nvim_set_hl(0, "Visual", { bg = "#393552" })
          vim.api.nvim_set_hl(0, "Search", { fg = "#232136", bg = "#9ccfd8", bold = true })
          vim.api.nvim_set_hl(0, "IncSearch", { fg = "#232136", bg = "#ea9a97", bold = true })
          vim.cmd([[redraw!]])
          notify("Rose Pine Moon (dark) applied")
        end
      end

      -- default: enabled (set to 0 to disable)
      if vim.g.omarchy_auto_background == nil then
        vim.g.omarchy_auto_background = 1
      end

  -- (Removed) stale set_background_from_omarchy call

      local rp = require("rose-pine")
      rp.setup({
        --- Use transparent background if your terminal supports it
        enable = { terminal = true, legacy_highlights = false },
        variant = "auto", -- auto/moon/dawn; we'll call :set background to switch
        dark_variant = "moon",
        dim_inactive_windows = false,
        extend_background_behind_borders = true,
        highlight_groups = {
          Normal = { fg = "text", bg = "base" },
          NormalNC = { fg = "text", bg = "base" },
          NormalFloat = { fg = "text", bg = "surface" },
          FloatBorder = { fg = "muted", bg = "surface" },
          Visual = { bg = "highlight_high" },
          CursorLine = { bg = "highlight_low" },
          LineNr = { fg = "muted" },
          Comment = { fg = "muted", italic = true },
          Search = { fg = "base", bg = "pine", bold = true },
          IncSearch = { fg = "base", bg = "rose", bold = true },
          StatusLine = { fg = "subtle", bg = "overlay" },
          StatusLineNC = { fg = "muted", bg = "overlay" },
          VertSplit = { fg = "overlay", bg = "none" },
          WinSeparator = { fg = "overlay" },
          Pmenu = { fg = "text", bg = "surface" },
          PmenuSel = { fg = "base", bg = "iris" },
          PmenuSbar = { bg = "overlay" },
          PmenuThumb = { bg = "muted" },
        },
      })

      -- Ensure we follow background option for light/dark.
      -- On startup, sync with Omarchy if enabled; otherwise apply current background
      if vim.g.omarchy_auto_background ~= 0 then
        apply_mode(desired_mode_from_omarchy())
      else
        apply_mode(vim.o.background)
      end

      -- Optional: auto-switch when background changes during session
      local aug = vim.api.nvim_create_augroup("RosePineAutoSwitch", { clear = true })
      -- Re-sync background from Omarchy marker when focus returns to Neovim
      vim.api.nvim_create_autocmd({"VimEnter", "FocusGained"}, {
        group = aug,
        callback = function()
          if vim.g.omarchy_auto_background ~= 0 then
            apply_mode(desired_mode_from_omarchy())
          end
        end,
      })
      vim.api.nvim_create_autocmd("OptionSet", {
        group = aug,
        pattern = "background",
        callback = function()
          -- If user manually changes background, apply that mode
          apply_mode(vim.o.background)
        end,
      })

      -- Live watch Omarchy theme directory to auto-apply changes without restart/focus change
      local uv = vim.loop
      local current_dir = vim.fn.expand("~/.config/omarchy/current")
      local watch_path = vim.fn.expand("~/.config/omarchy/current/theme")
      local watcher -- watches the theme directory
      local parent_watcher -- watches the parent directory to catch symlink changes
      -- Coalesce file events into a single apply using a timer
      local change_timer
      do
        local ok, t = pcall(uv.new_timer)
        if ok then change_timer = t end
      end
      local function schedule_apply()
        if not change_timer then
          if vim.g.omarchy_auto_background ~= 0 then
            apply_mode(desired_mode_from_omarchy())
          end
          return
        end
        change_timer:stop()
        change_timer:start(500, 0, function()
          vim.schedule(function()
            if vim.g.omarchy_auto_background ~= 0 then
              apply_mode(desired_mode_from_omarchy())
            end
          end)
        end)
      end
      local function start_watcher()
        local st = uv.fs_stat(watch_path)
        if not st or st.type ~= "directory" then
          return
        end
        local ok, fs_ev = pcall(uv.new_fs_event)
        if not ok or not fs_ev then
          return
        end
        watcher = fs_ev
        watcher:start(watch_path, {}, function(err, _fname, _status)
          if err then return end
          schedule_apply()
        end)
      end
      local function restart_watcher()
        if watcher then
          pcall(function() watcher:stop() end)
          pcall(function() watcher:close() end)
          watcher = nil
        end
        -- Recompute path (in case symlink target changed) and reattach
        watch_path = vim.fn.expand("~/.config/omarchy/current/theme")
        pcall(start_watcher)
      end
      -- Start watcher now and keep it clean on exit
      pcall(start_watcher)
      -- Also watch the parent dir to catch when 'theme' symlink flips
      do
        local stp = uv.fs_stat(current_dir)
        if stp and stp.type == "directory" then
          local ok, fs_ev = pcall(uv.new_fs_event)
          if ok and fs_ev then
            parent_watcher = fs_ev
            parent_watcher:start(current_dir, {}, function(err, _fname, _status)
              if err then return end
              vim.schedule(function()
                restart_watcher()
                schedule_apply()
              end)
            end)
          end
        end
      end
      vim.api.nvim_create_autocmd("VimLeavePre", {
        group = aug,
        callback = function()
          if watcher then
            pcall(function() watcher:stop() end)
            pcall(function() watcher:close() end)
          end
          if parent_watcher then
            pcall(function() parent_watcher:stop() end)
            pcall(function() parent_watcher:close() end)
          end
          if change_timer then
            pcall(function() change_timer:stop() end)
            pcall(function() change_timer:close() end)
          end
        end,
      })

      -- Optional command to toggle light/dark quickly
      vim.api.nvim_create_user_command("ToggleBackground", function()
        if vim.o.background == "light" then
          vim.o.background = "dark"
        else
          vim.o.background = "light"
        end
      end, { desc = "Toggle between light and dark backgrounds (Dawn/Moon)" })

      -- Optional: toggle Omarchy auto background
      vim.api.nvim_create_user_command("OmarchyAutoBackgroundToggle", function()
        vim.g.omarchy_auto_background = (vim.g.omarchy_auto_background == 1) and 0 or 1
        pcall(vim.notify, "Omarchy auto background: " .. (vim.g.omarchy_auto_background == 1 and "ON" or "OFF"))
      end, { desc = "Enable/disable auto background sync from Omarchy theme" })
    end,
  },
}
