# OpenClaw Provider Examples

Provider secrets belong in environment variables or ignored local env files.
Never place real API keys in OpenClaw examples, docs, service files, or shell
history snippets committed to git.

## NVIDIA Example

Template:

```bash
cp examples/openclaw/providers/nvidia.example.env config/openclaw.env
```

Edit the local ignored file:

```text
NVIDIA_API_KEY=<YOUR_NVIDIA_API_KEY>
OPENCLAW_DEFAULT_PROVIDER=nvidia
OPENCLAW_DEFAULT_MODEL=<NVIDIA_MODEL_NAME>
```

The model value is intentionally a placeholder. Choose a model supported by your
OpenClaw provider adapter and NVIDIA account.

## Other Providers

The same pattern applies to other providers:

- Keep keys in env vars.
- Keep local env files ignored.
- Prefer loopback services and SSH tunnels.
- Do not commit generated provider config containing credentials.
