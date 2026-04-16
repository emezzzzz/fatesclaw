# Codex Remote Development

Use this flow when the Pi owns the hardware workspace and the development
machine connects remotely.

## Pi Side

Install Codex on the Pi, clone the repository, and start the Codex app-server on
loopback only.

```bash
cd <PROJECT_PATH>
codex app-server --host 127.0.0.1 --port <REMOTE_PORT>
```

## Developer Machine

Forward the port over SSH:

```bash
ssh -L <LOCAL_PORT>:127.0.0.1:<REMOTE_PORT> <PI_USER>@<PI_HOST>
```

Connect:

```bash
codex --remote http://127.0.0.1:<LOCAL_PORT>
```

## Security

Do not bind the app-server to a public interface unless you have proper
authentication, TLS, firewalling, and a reason to do so. The loopback plus SSH
tunnel model is the default recommendation.
