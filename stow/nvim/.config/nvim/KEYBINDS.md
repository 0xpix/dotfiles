# Neovim Keybinds Cheatsheet

> Leader key: `Space`

## General

| Key | Description |
|-----|-------------|
| `jj` | Exit insert mode |
| `Y` | Yank to end of line |
| `==` | Select all |
| `Q` | Disabled |
| `Esc` | Clear search highlight |
| `Space Space` | Source current file (lua/vim only) |
| `Space x` | Make file executable |
| `Space s` | Replace word under cursor |
| `Space q` | Close buffer |
| `Space w` | Close buffer, keep split |
| `Space nd` | Dismiss Noice message |
| `Space vpp` | Jump to plugins directory |
| `Space ?` | Show buffer local keymaps |
| `Ctrl+t` | Exit terminal mode |

## Yank / Delete Registers

| Key | Mode | Description |
|-----|------|-------------|
| `Space y` | n/v | Yank into system clipboard |
| `Space Y` | n | Yank line into system clipboard |
| `Space d` | n/v | Delete into blackhole register |
| `p` | v | Paste without overwriting register |

## Copy File Info

| Key | Description |
|-----|-------------|
| `Space cf` | Copy file name to clipboard |
| `Space cp` | Copy file path to clipboard |

## Navigation / Motion

| Key | Description |
|-----|-------------|
| `J` | Join lines, keep cursor position |
| `Ctrl+d` | Half-page down + center |
| `Ctrl+u` | Half-page up + center |
| `n` | Next search result + center |
| `N` | Prev search result + center |
| `Shift+H` | Jump to beginning of line |
| `Shift+L` | Jump to end of line |
| `gj` | Next markdown header (md only) |
| `gk` | Prev markdown header (md only) |

## Window / Pane Management

| Key | Description |
|-----|-------------|
| `Ctrl+k` | Move to pane above |
| `Ctrl+j` | Move to pane below |
| `Ctrl+h` | Move to left pane |
| `Ctrl+l` | Move to right pane |
| `Ctrl+Shift+Down` | Resize split down |
| `Ctrl+Shift+Up` | Resize split up |
| `Ctrl+Left` | Resize vertical split left |
| `Ctrl+Right` | Resize vertical split right |

## Quickfix / Location List

| Key | Description |
|-----|-------------|
| `Space h` | Next quickfix item |
| `Space ;` | Prev quickfix item |
| `Space k` | Next location list item |
| `Space j` | Prev location list item |

## Visual Mode

| Key | Description |
|-----|-------------|
| `<` | Indent left, stay in visual |
| `>` | Indent right, stay in visual |
| `J` | Move block down |
| `K` | Move block up |
| `//` | Search for highlighted text |

## Telescope (Search)

| Key | Description |
|-----|-------------|
| `Space ff` | Find files |
| `Space fg` | Live grep |
| `Space fc` | Live grep code (excl spec/test) |
| `Space fb` | Find buffers |
| `Space fh` | Find help tags |
| `Space fs` | Find LSP symbols |
| `Space fi` | Git status |
| `Space fo` | Find old files |
| `Space fw` | Find word under cursor |
| `Space fk` | Find keymaps |
| `Space /` | Fuzzy search in current buffer |

### Inside Telescope Picker

| Key | Mode | Description |
|-----|------|-------------|
| `Ctrl+j` | i | Cycle history next |
| `Ctrl+k` | i | Cycle history prev |
| `Ctrl+w` | n/i | Send to quickfix list |
| `Ctrl+D` | i | Delete buffer |
| `Ctrl+s` | i | Cycle previewers next |
| `Ctrl+a` | i | Cycle previewers prev |
| `Enter` | i | Select (multi-select aware) |

## Harpoon

| Key | Description |
|-----|-------------|
| `Space a` | Add file to Harpoon |
| `Ctrl+e` | Toggle Harpoon menu |
| `Space 1-4` | Jump to Harpoon file 1-4 |
| `Tab` | Next Harpoon file |
| `Shift+Tab` | Prev Harpoon file |
| `Space hc` | Clear Harpoon list |

## LSP

| Key | Description |
|-----|-------------|
| `K` | Hover docs |
| `gd` | Go to definition |
| `gD` | Go to declaration |
| `gr` | Go to references |
| `gT` | Go to type definition |
| `Space ca` | Code action |
| `Space rn` | Rename symbol |
| `Space dd` | Show diagnostic float |
| `[d` | Prev diagnostic |
| `]d` | Next diagnostic |

## Completion (nvim-cmp)

| Key | Description |
|-----|-------------|
| `Ctrl+Space` | Trigger completion |
| `Ctrl+e` | Abort completion |
| `Ctrl+b` | Scroll docs up |
| `Ctrl+f` | Scroll docs down |
| `Enter` | Confirm completion |
| `Tab` | Next item / expand snippet |
| `Shift+Tab` | Prev item / jump snippet back |

## Git

| Key | Description |
|-----|-------------|
| `Space gs` | Git status (Fugitive) |
| `Space gp` | Git push |
| `Space gP` | Git pull --rebase |
| `gu` | Diffget ours |
| `gh` | Diffget theirs |
| `Space gc` | Search git commits |
| `Space gb` | Search git commits for buffer |

## File Management

| Key | Description |
|-----|-------------|
| `-` | Open Oil float (parent dir) |
| `Space f` | Format buffer (Conform) |

## Buffer Management (Snacks)

| Key | Description |
|-----|-------------|
| `Space bd` | Delete buffer |
| `Space ba` | Delete all buffers |
| `Space bo` | Delete other buffers |
| `Space bz` | Toggle Zen Mode |
