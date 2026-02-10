# bash completion for brain CLI
# Source this file: source brain.bash
# Or copy to /etc/bash_completion.d/brain

_brain() {
    local cur prev commands hook_subcommands export_options
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    commands="write guard check list audit stats export hook tutorial help"
    hook_subcommands="install uninstall status"
    export_options="--format --output"

    case "$prev" in
        brain)
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            return 0
            ;;
        hook)
            COMPREPLY=($(compgen -W "$hook_subcommands" -- "$cur"))
            return 0
            ;;
        export)
            COMPREPLY=($(compgen -W "$export_options" -- "$cur"))
            return 0
            ;;
        --format)
            COMPREPLY=($(compgen -W "md json" -- "$cur"))
            return 0
            ;;
        --output|-f)
            COMPREPLY=($(compgen -f -- "$cur"))
            return 0
            ;;
        write)
            COMPREPLY=($(compgen -W "-f" -- "$cur"))
            return 0
            ;;
        audit)
            COMPREPLY=($(compgen -W "--json" -- "$cur"))
            return 0
            ;;
    esac

    COMPREPLY=($(compgen -W "$commands" -- "$cur"))
    return 0
}

complete -F _brain brain
