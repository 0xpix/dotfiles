return {
  {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    config = function()
      local config = require("nvim-treesitter.configs")
      config.setup({
        auto_install = true,
        ensure_installed = {
          "astro",
          "bash",
          "c",
          "cpp",
          "css",
          "go",
          "gomod",
          "gosum",
          "html",
          "javascript",
          "json",
          "lua",
          "python",
          "scss",
          "tsx",
          "typescript",
          "yaml",
        },
        highlight = { enable = true },
        indent = { enable = false },
      })
    end
  }
}
