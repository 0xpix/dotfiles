-- Jump between markdown headers (only in markdown buffers)
vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    vim.keymap.set("n", "gj", [[/^##\+ .*<CR>]], { buffer = true, silent = true })
    vim.keymap.set("n", "gk", [[?^##\+ .*<CR>]], { buffer = true, silent = true })
  end,
})

-- Exit insert mode without hitting Esc
vim.keymap.set("i", "jj", "<Esc><Esc>", { desc = "Esc" })

-- Make Y behave like C or D
vim.keymap.set("n", "Y", "y$")

-- Select all
vim.keymap.set("n", "==", "gg<S-v>G")

-- Keep window centered when going up/down
vim.keymap.set("n", "J", "mzJ`z")
vim.keymap.set("n", "<C-d>", "<C-d>zz")
vim.keymap.set("n", "<C-u>", "<C-u>zz")
vim.keymap.set("n", "n", "nzzzv")
vim.keymap.set("n", "N", "Nzzzv")

-- Paste without overwriting register
vim.keymap.set("v", "p", '"_dP')

-- Copy text to " register
vim.keymap.set("n", "<leader>y", "\"+y", { desc = "Yank into \" register" })
vim.keymap.set("v", "<leader>y", "\"+y", { desc = "Yank into \" register" })
vim.keymap.set("n", "<leader>Y", "\"+Y", { desc = "Yank into \" register" })

-- Delete text to " register
vim.keymap.set("n", "<leader>d", "\"_d", { desc = "Delete into \" register" })
vim.keymap.set("v", "<leader>d", "\"_d", { desc = "Delete into \" register" })

-- Get out Q
vim.keymap.set("n", "Q", "<nop>")

-- close buffer
vim.keymap.set("n", "<leader>q", "<cmd>bd<CR>", { desc = "Close Buffer" })

-- Close buffer without closing split
vim.keymap.set("n", "<leader>w", "<cmd>bp|bd #<CR>", { desc = "Close Buffer; Retain Split" })

-- Navigate between quickfix items
vim.keymap.set("n", "<leader>h", "<cmd>cnext<CR>zz", { desc = "Forward qfixlist" })
vim.keymap.set("n", "<leader>;", "<cmd>cprev<CR>zz", { desc = "Backward qfixlist" })

-- Navigate between location list items
vim.keymap.set("n", "<leader>k", "<cmd>lnext<CR>zz", { desc = "Forward location list" })
vim.keymap.set("n", "<leader>j", "<cmd>lprev<CR>zz", { desc = "Backward location list" })

-- Replace word under cursor across entire buffer
vim.keymap.set("n", "<leader>s", [[:%s/\<<C-r><C-w>\>/<C-r><C-w>/gI<Left><Left><Left>]],
  { desc = "Replace word under cursor" })

-- Make current file executable
vim.keymap.set("n", "<leader>x", "<cmd>!chmod +x %<CR>", { silent = true, desc = "Make current file executable" })

-- Jump to plugin management
vim.keymap.set("n", "<leader>vpp", "<cmd>e ~/.config/nvim/lua/plugins/<CR>", { desc = "Jump to plugins directory" })

-- Copy file paths
vim.keymap.set("n", "<leader>cf", "<cmd>let @+ = expand(\"%\")<CR>", { desc = "Copy File Name" })
vim.keymap.set("n", "<leader>cp", "<cmd>let @+ = expand(\"%:p\")<CR>", { desc = "Copy File Path" })

vim.keymap.set("n", "<leader><leader>", function()
  local ft = vim.bo.filetype
  if ft == "lua" or ft == "vim" then
    vim.cmd("so")
    vim.notify("Sourced " .. vim.fn.expand("%:t"), vim.log.levels.INFO)
  else
    vim.notify("Cannot source a " .. ft .. " file", vim.log.levels.WARN)
  end
end, { desc = "Source current file" })

-- Dismiss Noice Message
vim.keymap.set("n", "<leader>nd", "<cmd>NoiceDismiss<CR>", { desc = "Dismiss Noice Message" })

-- Navigate vim panes
vim.keymap.set("n", "<C-k>", ":wincmd k<CR>", { silent = true, desc = "Move to pane above" })
vim.keymap.set("n", "<C-j>", ":wincmd j<CR>", { silent = true, desc = "Move to pane below" })
vim.keymap.set("n", "<C-h>", ":wincmd h<CR>", { silent = true, desc = "Move to left pane" })
vim.keymap.set("n", "<C-l>", ":wincmd l<CR>", { silent = true, desc = "Move to right pane" })

-- Clear search highlighting
vim.keymap.set("n", "<Esc>", "<cmd>nohlsearch<CR>", { desc = "Clear search highlight" })

-- Resize with arrows
vim.keymap.set("n", "<C-S-Down>", ":resize +2<CR>", { desc = "Resize Horizontal Split Down" })
vim.keymap.set("n", "<C-S-Up>", ":resize -2<CR>", { desc = "Resize Horizontal Split Up" })
vim.keymap.set("n", "<C-Left>", ":vertical resize -2<CR>", { desc = "Resize Vertical Split Down" })
vim.keymap.set("n", "<C-Right>", ":vertical resize +2<CR>", { desc = "Resize Vertical Split Up" })

-- Visual --
-- Stay in indent mode
vim.keymap.set("v", "<", "<gv")
vim.keymap.set("v", ">", ">gv")

vim.keymap.set({ "n", "o", "x" }, "<s-h>", "^", { desc = "Jump to beginning of line" })
vim.keymap.set({ "n", "o", "x" }, "<s-l>", "g_", { desc = "Jump to end of line" })

-- Move block
vim.keymap.set("v", "J", ":m '>+1<CR>gv=gv", { desc = "Move Block Down" })
vim.keymap.set("v", "K", ":m '<-2<CR>gv=gv", { desc = "Move Block Up" })

-- Search for highlighted text in buffer
vim.keymap.set("v", "//", 'y/<C-R>"<CR>', { desc = "Search for highlighted text" })

-- Exit terminal mode shortcut
vim.keymap.set("t", "<C-t>", "<C-\\><C-n>")

-- Autocommands
vim.api.nvim_create_augroup("custom_buffer", { clear = true })

-- start terminal in insert mode
vim.api.nvim_create_autocmd("TermOpen", {
  desc = "Auto enter insert mode when opening a terminal",
  group = "custom_buffer",
  pattern = "*",
  callback = function()
    -- Wait briefly just in case we immediately switch out of the buffer (e.g. Neotest)
    vim.defer_fn(function()
      if vim.bo[0].buftype == 'terminal' then
        vim.cmd([[startinsert]])
      end
    end, 100)
  end,
})

-- highlight yanks
vim.api.nvim_create_autocmd("TextYankPost", {
  group    = "custom_buffer",
  pattern  = "*",
  callback = function() vim.highlight.on_yank { timeout = 200 } end
})
