# pi notice — for debian's interactive login shells (/etc/profile.d/pi.sh
# is a copy of this file). Until a credential is saved, it says how to pick one.
case $- in
  *i*)
    if [ "$(id -un)" = debian ]; then
      if grep -q '"type"' /home/debian/.pi/agent/auth.json 2>/dev/null; then
        printf '\n\033[1;33m%s\033[0m\n\n' "The agent is one command away: type pi"
      else
        printf '\n\033[1;33m%s\033[0m\n\n' "pi has no model yet: run pi, then /login <provider> and /model"
      fi
    fi
    ;;
esac
