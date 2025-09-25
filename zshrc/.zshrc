# --- fast & safe defaults ---
setopt prompt_subst
DISABLE_AUTO_UPDATE="true"
DISABLE_MAGIC_FUNCTIONS="true"
DISABLE_COMPFIX="true"

# Guard: only run in zsh
[ -n "$ZSH_VERSION" ] || return

# --- completion ---
autoload -Uz compinit
compinit -C

# --- Oh My Zsh (plugins only) ---
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME=""  # theme disabled; Starship handles prompt

plugins=(
  git
  zsh-autosuggestions
  zsh-syntax-highlighting  # keep this last among plugins for best behavior
  zsh-vi-mode
  zoxide
)
source "$ZSH/oh-my-zsh.sh"

# --- Starship prompt ---
eval "$(starship init zsh)"

# --- uv integration (no conda) ---
# Add uv completion and ensure ~/.local/bin (typical uv install path) is on PATH
export PATH="$HOME/.local/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
  eval "$(uv generate-shell-completion zsh)"
fi

# --- key bindings ---
globalias() {
  if [[ $LBUFFER =~ '[a-zA-Z0-9]+$' ]]; then
    zle _expand_alias
    zle expand-word
  fi
  zle self-insert
}
zle -N globalias
bindkey " " globalias
bindkey "^[[Z" magic-space
bindkey -M isearch " " magic-space

# --- SSH agent (lazy) ---
_load_ssh_agent() {
  if [ -z "$SSH_AUTH_SOCK" ]; then
    eval "$(ssh-agent -s)" > /dev/null
    ssh-add ~/.ssh/id_github_sign_and_auth 2>/dev/null
  fi
}
autoload -U add-zsh-hook
add-zsh-hook precmd _load_ssh_agent

# --- PATH extras ---
export VOLTA_HOME="$HOME/.volta"
export PATH="$VOLTA_HOME/bin:$PATH"
# (remove the wrong user path)
# export PATH="$PATH:/home/scott/.turso"   # <- deleted

# --- autosuggestions tweaks ---
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE="fg=#663399,standout"
ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE="20"
ZSH_AUTOSUGGEST_USE_ASYNC=1

# --- history & mode ---
HISTFILE=~/.histfile
HISTSIZE=1000
SAVEHIST=1000
bindkey -e

# --- aliases ---
[ -f ~/.zsh_aliases ] && source ~/.zsh_aliases
