return {
  "ThePrimeagen/harpoon",
  branch = "harpoon2",
  dependencies = { "nvim-lua/plenary.nvim" },
  config = function()
    local harpoon = require("harpoon")
    harpoon:setup()

    vim.keymap.set("n", "<leader>a", function() harpoon:list():add() end, { desc = "Harpoon add file" })
    vim.keymap.set("n", "<C-e>", function() harpoon.ui:toggle_quick_menu(harpoon:list()) end, { desc = "Harpoon menu" })

    vim.keymap.set("n", "<C-1>", function() harpoon:list():select(1) end, { desc = "Harpoon file 1" })
    vim.keymap.set("n", "<C-2>", function() harpoon:list():select(2) end, { desc = "Harpoon file 2" })
    vim.keymap.set("n", "<C-3>", function() harpoon:list():select(3) end, { desc = "Harpoon file 3" })
    vim.keymap.set("n", "<C-4>", function() harpoon:list():select(4) end, { desc = "Harpoon file 4" })

    vim.keymap.set("n", "<S-Tab>", function() harpoon:list():prev() end, { desc = "Harpoon prev" })
    vim.keymap.set("n", "<Tab>", function() harpoon:list():next() end, { desc = "Harpoon next" })
  end,
}
