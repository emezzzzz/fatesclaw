#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[verify-audio] %s\n' "$*"
}

log "Playback devices"
aplay -l || true

log "Capture devices"
arecord -l || true

if [ "${FATESCLAW_AUDIO_PLAYBACK_TEST:-0}" = "1" ]; then
  device="${AUDIO_PLAYBACK_DEVICE:-default}"
  wav="${AUDIO_TEST_WAV:-/usr/share/sounds/alsa/Front_Center.wav}"
  log "Playback test on $device using $wav"
  aplay -D "$device" "$wav"
fi

if [ "${FATESCLAW_AUDIO_CAPTURE_TEST:-0}" = "1" ]; then
  device="${AUDIO_CAPTURE_DEVICE:-default}"
  seconds="${AUDIO_CAPTURE_SECONDS:-3}"
  out="${AUDIO_CAPTURE_OUTPUT:-/tmp/fatesclaw-capture.wav}"
  log "Capture test on $device for ${seconds}s"
  arecord -D "$device" -f cd -d "$seconds" "$out"
  log "Captured to $out"
fi
