from cyberlab.lab.environment import validate_environment
from cyberlab.lab.workstation import validate_workstation

WORKSTATION_SETUP = '''
set -eu
name=$1
home=$2
shift 2
test "$(id -u student)" = 2000
test "$(id -g student)" = 2000
test ! -L /home/student
test -d /home/student
test ! -e "$home" && test ! -L "$home"
if getent passwd "$name" >/dev/null || getent group "$name" >/dev/null; then exit 125; fi
groupmod --new-name "$name" student
usermod --login "$name" --home "$home" --move-home student
printf '%s ALL=(ALL) NOPASSWD: ALL\\n' "$name" > /etc/sudoers.d/student
chmod 0440 /etc/sudoers.d/student
visudo -cf /etc/sudoers.d/student >/dev/null
exec runuser --user "$name" -- /bin/sh -c 'cd "$HOME"; exec "$@"' cyberlab-user "$@"
'''

def workstation_setup_command(node, command):
    validate_workstation(node)
    return ["/bin/sh", "-c", WORKSTATION_SETUP, "cyberlab-user-setup", node.user.name, node.user.home, *command]

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
