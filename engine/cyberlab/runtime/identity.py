from cyberlab.lab.environment import validate_environment

IDENTITY_CHECK = '''
matched=0
while IFS=: read -r account password account_uid account_gid gecos account_home account_shell; do
    if [ "$account" = "$1" ] && [ "$account_uid" = "$2" ] && [ "$account_gid" = "$3" ] && [ "$account_home" = "$4" ] && [ "$account_shell" = "$5" ]; then
        matched=1
    fi
done < /etc/passwd
if [ "$matched" != 1 ] || [ "$(/bin/id -un)" != "$1" ] || [ "$(/bin/id -u)" != "$2" ] || [ "$(/bin/id -g)" != "$3" ] || [ ! -x "$5" ] || [ "$HOME" != "$4" ] || [ "$PWD" != "$4" ]; then
    exit 125
fi
shift 5
exec "$@"
'''

def identity_command(node, command):
    validate_environment(node.hostname, node.user)
    user = node.user
    return [
        "/bin/sh", "-c", IDENTITY_CHECK, "cyberlab-identity",
        user.name, str(user.uid), str(user.gid), user.home, user.shell, *command,
    ]
