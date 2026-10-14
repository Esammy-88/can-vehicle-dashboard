#!/usr/bin/env bash
# Create (or remove) a Linux SocketCAN virtual interface for the simulator.
#
#   ./scripts/setup_vcan.sh            # create vcan0 if missing
#   ./scripts/setup_vcan.sh vcan1      # use another name
#   ./scripts/setup_vcan.sh --remove   # delete vcan0
#
# Not needed on Windows/macOS: the backend falls back to a software CAN bus.
set -euo pipefail

remove=false
iface=vcan0
for arg in "$@"; do
    case "$arg" in
        --remove) remove=true ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        *) iface="$arg" ;;
    esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "SocketCAN is Linux-only. Run the backend with CAN_MODE=virtual instead." >&2
    exit 1
fi

sudo_cmd=""
[[ $EUID -ne 0 ]] && sudo_cmd="sudo"

if $remove; then
    if ip link show "$iface" &>/dev/null; then
        $sudo_cmd ip link delete "$iface"
        echo "Removed $iface"
    else
        echo "$iface does not exist; nothing to remove"
    fi
    exit 0
fi

if ip link show "$iface" &>/dev/null; then
    echo "$iface already exists"
else
    $sudo_cmd modprobe can
    $sudo_cmd modprobe vcan
    $sudo_cmd ip link add dev "$iface" type vcan
    echo "Created $iface"
fi

$sudo_cmd ip link set up "$iface"
ip -details link show "$iface"
