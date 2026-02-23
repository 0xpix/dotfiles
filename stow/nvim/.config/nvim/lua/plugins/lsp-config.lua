return {
  {
    "williamboman/mason.nvim",
    lazy = false,
    config = function()
      require("mason").setup()
    end,
  },
  {
    "williamboman/mason-lspconfig.nvim",
    lazy = false,
    opts = {
      auto_install = true,
    },
  },
  {
    "neovim/nvim-lspconfig",
    lazy = false,
    config = function()
      local cmp_nvim_lsp = require("cmp_nvim_lsp")
      local capabilities = vim.tbl_deep_extend(
        "force",
        {},
        vim.lsp.protocol.make_client_capabilities(),
        cmp_nvim_lsp.default_capabilities()
      )

      local servers = {
        "lua_ls",
        "gopls",
        "ts_ls",
        "tailwindcss",
        "astro",
        "pyright",
        "clangd",
      }

      for _, server in ipairs(servers) do
        vim.lsp.config(server, {
          capabilities = capabilities,
        })
      end

      vim.lsp.enable(servers)

      vim.keymap.set("n", "K", vim.lsp.buf.hover, { desc = "Hover docs" })
      vim.keymap.set("n", "gd", vim.lsp.buf.definition, { desc = "Go to definition" })
      vim.keymap.set("n", "gD", vim.lsp.buf.declaration, { desc = "Go to declaration" })
      vim.keymap.set("n", "gr", vim.lsp.buf.references, { desc = "Go to references" })
      vim.keymap.set("n", "gT", vim.lsp.buf.type_definition, { desc = "Go to type definition" })
      vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, { desc = "Code action" })
      vim.keymap.set("n", "<leader>rn", vim.lsp.buf.rename, { desc = "Rename symbol" })
      vim.keymap.set("n", "<leader>d", vim.diagnostic.open_float, { desc = "Show diagnostic" })
      vim.keymap.set("n", "[d", vim.diagnostic.goto_prev, { desc = "Prev diagnostic" })
      vim.keymap.set("n", "]d", vim.diagnostic.goto_next, { desc = "Next diagnostic" })
    end,
  },
}
