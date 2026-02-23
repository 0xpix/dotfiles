return {
  "folke/noice.nvim",
  event = "VeryLazy",
  dependencies = {
    "MunifTanjim/nui.nvim",
    "rcarriga/nvim-notify",
  },
  config = function()
    local notify = require("notify")
    notify.setup({
      stages = "fade",
      timeout = 2500,
      render = "wrapped-compact",
    })

    vim.notify = notify

    require("noice").setup({
      cmdline = {
        enabled = true,
        view = "cmdline_popup",
      },
      popupmenu = {
        enabled = true,
        backend = "nui",
      },
      lsp = {
        progress = { enabled = true },
        signature = { enabled = false },
      },
      messages = { enabled = true },
      notify = { enabled = true },
      views = {
        cmdline_popup = {
          position = {
            row = "40%",
            col = "50%",
          },
          size = {
            width = 60,
            height = "auto",
          },
          border = {
            style = "rounded",
            padding = { 0, 1 },
          },
          win_options = {
            winhighlight = "NormalFloat:NormalFloat,FloatBorder:FloatBorder",
          },
        },
      },
      presets = {
        bottom_search = false,
        command_palette = true,
        long_message_to_split = true,
      },
    })
  end,
}
