#compdef brain
# zsh completion for brain CLI
# Copy to a directory in $fpath, or source directly

_brain() {
    local -a commands
    commands=(
        'write:Add a new lesson'
        'guard:Check command against lessons'
        'check:Search lessons by keyword'
        'list:List all lessons'
        'audit:Show compliance report'
        'stats:Quick stats summary'
        'export:Export lessons'
        'hook:Manage Claude Code hook'
        'tutorial:Interactive walkthrough'
        'help:Show help'
    )

    local -a hook_commands
    hook_commands=(
        'install:Install brain guard hook'
        'uninstall:Remove brain guard hook'
        'status:Check hook status'
    )

    _arguments -C \
        '1: :->command' \
        '*:: :->args'

    case "$state" in
        command)
            _describe -t commands 'brain commands' commands
            ;;
        args)
            case "$words[1]" in
                hook)
                    _describe -t hook_commands 'hook commands' hook_commands
                    ;;
                write)
                    _arguments '-f[Load from YAML file]:file:_files -g "*.yaml *.yml"'
                    ;;
                guard)
                    _message 'command to check'
                    ;;
                check)
                    _message 'keyword to search'
                    ;;
                audit)
                    _arguments '--json[Output as JSON]'
                    ;;
                export)
                    _arguments \
                        '--format[Output format]:format:(md json)' \
                        '--output[Output file]:file:_files'
                    ;;
            esac
            ;;
    esac
}

_brain "$@"
