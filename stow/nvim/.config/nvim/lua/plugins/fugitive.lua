return {
  "tpope/vim-fugitive",
  config = function()
    vim.keymap.set("n", "<leader>gs", vim.cmd.Git, { desc = "Git status" })
    vim.keymap.set("n", "<leader>gp", function() vim.cmd.Git("push") end, { desc = "Git push" })
    vim.keymap.set("n", "<leader>gP", function() vim.cmd.Git({ "pull", "--rebase" }) end, { desc = "Git pull --rebase" })
    vim.keymap.set("n", "gu", "<cmd>diffget //2<CR>", { desc = "Diffget ours" })
    vim.keymap.set("n", "gh", "<cmd>diffget //3<CR>", { desc = "Diffget theirs" })
  end,
}
