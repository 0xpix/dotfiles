return {
  {
    "catppuccin/nvim",
    lazy = true, -- keep installed but don't make it the default theme
    name = "catppuccin",
    priority = 50,

    config = function()
      require("catppuccin").setup({
        transparent_background = true,
      })
      -- Intentionally do not set a colorscheme here to avoid overriding the active theme.
      -- To use catppuccin manually, run: :colorscheme catppuccin-[latte|frappe|macchiato|mocha]
    end
  }
}
