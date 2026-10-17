# TASK-0019 welcome evidence

2026-10-17: npm test passes61/61; npm run check has0errors/warnings;
npm run build passes; npm run test:browser passes36/36.

Unit coverage includes output-only playback, denied output, both completion/drain
orders,25second timeout, send failure, empty audio and one-shot ownership.
Browser coverage includes failed/fresh/restored/backoffice login, unlock before
auth, no microphone/worklet, Play/Skip, Start voice, logout, navigation, hidden
page, focus/refresh no replay,320px layout and axe accessibility.

[native-welcome.json](native-welcome.json) records a real Gemini/ADK greeting
using candidate static assets and the existing authenticated local Go gateway.
It played28chunks/265920bytes, completed and closed one socket, said hi and Monti,
and requested no microphone.8196ms is total login/setup/playout, not first audio.
The deliberate failed login created no provider ticket. Transcripts, credentials,
cookies and raw audio are not retained.

The initial candidate interception run was blocked by Chromium local-network
permission before WebSocket handshake. The opt-in harness grants local-network
access only for candidate interception, consistent with the existing audio probe.
No autoplay bypass or microphone permission is used. Normal served-app verification
is repeated after integration without candidate interception or this permission.

This bounded check does not establish physical speaker acoustics, cloud readiness,
or full-system/classifier acceptance. No existing acceptance gate is changed.
