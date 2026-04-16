#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
Codex remote development checklist:

1. Install Codex on the Pi.
2. From the Pi, run the Codex app-server bound to loopback.
3. From your development machine, forward the remote port:
   ssh -L <LOCAL_PORT>:127.0.0.1:<REMOTE_PORT> <PI_USER>@<PI_HOST>
4. Connect from your local machine with:
   codex --remote http://127.0.0.1:<LOCAL_PORT>

Do not expose the app-server directly on a public interface without auth and TLS.
EOF
