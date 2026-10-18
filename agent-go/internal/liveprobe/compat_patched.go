//go:build sdkcompat

package liveprobe

// The wire tests must also prove the setup change. The tag alone cannot make
// an unpatched SDK pass the compatibility gate.
const compatibilityPatches = "adk-realtime-input-v1,adk-gemini3-live-input-v1,genai-live-write-lock-v1"
