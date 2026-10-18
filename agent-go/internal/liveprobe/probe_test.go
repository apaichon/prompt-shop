package liveprobe

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"google.golang.org/adk/v2/agent"
	"google.golang.org/genai"
)

func TestSettings(t *testing.T) {
	tests := []struct {
		name  string
		s     Settings
		valid bool
	}{
		{"configured", Settings{"gemini-3.8-live", "Aoede"}, true},
		{"default_voice", Settings{"gemini-3.8-live", ""}, true},
		{"model_prefix", Settings{"models/gemini-3.8-live", "Aoede"}, true},
		{"missing_model", Settings{}, false},
		{"url_model", Settings{"https://provider.invalid/model", ""}, false},
		{"bad_voice", Settings{"gemini-3.8-live", "../../voice"}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if (tt.s.Validate() == nil) != tt.valid {
				t.Fatal("configuration validity mismatch")
			}
		})
	}
}

func object(v any) map[string]any { m, _ := v.(map[string]any); return m }
func path(m map[string]any, keys ...string) any {
	var v any = m
	for _, k := range keys {
		v = object(v)[k]
	}
	return v
}

type wire struct {
	Model                  string `json:"model"`
	Voice                  string `json:"voice"`
	Audio                  bool   `json:"audio_requested"`
	InputTranscription     bool   `json:"input_transcription_requested"`
	OutputTranscription    bool   `json:"output_transcription_requested"`
	ManualSettingForwarded bool   `json:"manual_activity_setting_forwarded"`
	AckTool                bool   `json:"blocking_ack_tool_declared"`
	ActivityStart          bool   `json:"activity_start_sent"`
	ActivityEnd            bool   `json:"activity_end_sent"`
	PCMBytes               int    `json:"input_pcm_bytes"`
	FunctionResponse       bool   `json:"function_response_received"`
	ModernAudio            bool   `json:"modern_audio_field"`
	LegacyMedia            bool   `json:"legacy_media_chunks"`
	ModernText             bool   `json:"modern_text_field"`
}

// fixture runs a real WebSocket endpoint only on an ephemeral loopback listener.
// It examines actual ADK/GenAI serialization; no application request builder is
// substituted. Server errors are reported through channels, not ignored.
func fixture(t *testing.T) (string, <-chan wire, <-chan error) {
	t.Helper()
	captured := make(chan wire, 1)
	failures := make(chan error, 1)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		upgrader := websocket.Upgrader{}
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			failures <- errors.New("upgrade failed")
			return
		}
		defer conn.Close()
		_ = conn.SetReadDeadline(time.Now().Add(8 * time.Second))
		_ = conn.SetWriteDeadline(time.Now().Add(8 * time.Second))
		var request map[string]any
		if conn.ReadJSON(&request) != nil {
			failures <- errors.New("setup read failed")
			return
		}
		setup := object(request["setup"])
		got := wire{}
		got.Model, _ = setup["model"].(string)
		got.Voice, _ = path(setup, "generationConfig", "speechConfig", "voiceConfig", "prebuiltVoiceConfig", "voiceName").(string)
		modes, _ := path(setup, "generationConfig", "responseModalities").([]any)
		got.Audio = len(modes) == 1 && modes[0] == "AUDIO"
		_, got.InputTranscription = setup["inputAudioTranscription"]
		_, got.OutputTranscription = setup["outputAudioTranscription"]
		disabled, _ := path(setup, "realtimeInputConfig", "automaticActivityDetection", "disabled").(bool)
		got.ManualSettingForwarded = disabled
		tools, _ := setup["tools"].([]any)
		for _, tool := range tools {
			decls, _ := object(tool)["functionDeclarations"].([]any)
			for _, d := range decls {
				v := object(d)
				if v["name"] == "probe_ack" && v["behavior"] == "BLOCKING" {
					got.AckTool = true
				}
			}
		}
		if conn.WriteJSON(map[string]any{"setupComplete": map[string]any{}}) != nil {
			failures <- errors.New("setup response failed")
			return
		}
		started := false
		for {
			var msg map[string]any
			if conn.ReadJSON(&msg) != nil {
				failures <- errors.New("input read failed")
				return
			}
			real := object(msg["realtimeInput"])
			if _, ok := real["activityStart"]; ok {
				got.ActivityStart = true
			}
			if _, ok := real["activityEnd"]; ok {
				got.ActivityEnd = true
			}
			media := object(real["audio"])
			if data, ok := media["data"].(string); ok {
				got.ModernAudio = true
				b, _ := base64.StdEncoding.DecodeString(data)
				got.PCMBytes += len(b)
			}
			if chunks, ok := real["mediaChunks"].([]any); ok {
				got.LegacyMedia = true
				for _, c := range chunks {
					data, _ := object(c)["data"].(string)
					b, _ := base64.StdEncoding.DecodeString(data)
					got.PCMBytes += len(b)
				}
			}
			if _, ok := msg["toolResponse"]; ok {
				got.FunctionResponse = true
				break
			}
			_, text := msg["clientContent"]
			if value, ok := real["text"].(string); ok && value != "" {
				text = true
				got.ModernText = true
			}
			// Do not ask for a tool until all manual PCM frames arrive.
			if !started && (text || got.ActivityEnd) {
				started = true
				if conn.WriteJSON(map[string]any{"toolCall": map[string]any{"functionCalls": []any{map[string]any{"id": "fixture-call", "name": "probe_ack", "args": map[string]any{"text": "fixture request"}}}}}) != nil {
					failures <- errors.New("tool request failed")
					return
				}
			}
		}
		audio := base64.StdEncoding.EncodeToString([]byte{1, 0, 2, 0, 3, 0, 4, 0})
		if conn.WriteJSON(map[string]any{"serverContent": map[string]any{"interrupted": true}}) != nil {
			failures <- errors.New("interrupt event failed")
			return
		}
		// A single event contains all output branches, as real Live events can.
		err = conn.WriteJSON(map[string]any{"serverContent": map[string]any{
			"inputTranscription":  map[string]any{"text": "fixture input", "finished": true},
			"outputTranscription": map[string]any{"text": "fixture output", "finished": true},
			"modelTurn":           map[string]any{"role": "model", "parts": []any{map[string]any{"inlineData": map[string]any{"mimeType": "audio/pcm;rate=24000", "data": audio}}}},
			"turnComplete":        true,
		}})
		if err != nil {
			failures <- errors.New("model response failed")
			return
		}
		captured <- got
		// Wait for explicit client teardown, avoiding an accidental reconnect.
		_, _, _ = conn.ReadMessage()
	}))
	t.Cleanup(srv.Close)
	return "ws" + strings.TrimPrefix(srv.URL, "http"), captured, failures
}

func TestPinnedSDKWireCharacterization(t *testing.T) {
	for _, manual := range []bool{false, true} {
		name := "text"
		if manual {
			name = "manual_pcm"
		}
		t.Run(name, func(t *testing.T) {
			endpoint, captured, failures := fixture(t)
			ctx, cancel := context.WithTimeout(t.Context(), 8*time.Second)
			defer cancel()
			live, events, calls, cleanup, err := Start(ctx, Settings{"gemini-3.8-live", "Aoede"}, &genai.ClientConfig{APIKey: "fixture-only", Backend: genai.BackendGeminiAPI, HTTPOptions: genai.HTTPOptions{APIVersion: "v1alpha", BaseURL: endpoint}})
			if err != nil {
				t.Fatal(err)
			}
			defer cleanup()
			defer live.Close()
			if manual {
				err = SendPCM(ctx, live, []byte{1, 0, 2, 0, 3, 0, 4, 0}, false)
			} else {
				err = live.Send(agent.LiveRequest{Content: genai.NewContentFromText("fixture request", "user")})
			}
			if err != nil {
				t.Fatal(err)
			}
			var input, output, complete, interrupted bool
			var audio int
			for e, err := range events {
				if err != nil {
					t.Fatal("SDK fixture stream failed")
				}
				if e.InputTranscription != nil {
					input = true
				}
				if e.OutputTranscription != nil {
					output = true
				}
				interrupted = interrupted || e.Interrupted
				if e.Content != nil {
					for _, p := range e.Content.Parts {
						if p.InlineData != nil {
							audio += len(p.InlineData.Data)
						}
					}
				}
				if e.TurnComplete {
					complete = true
					break
				}
			}
			if !input || !output || !complete || !interrupted || audio != 8 || calls.Load() != 1 {
				t.Fatalf("output parity failed input=%v output=%v complete=%v interrupted=%v bytes=%d calls=%d", input, output, complete, interrupted, audio, calls.Load())
			}
			var got wire
			select {
			case got = <-captured:
			case err := <-failures:
				t.Fatal(err)
			case <-ctx.Done():
				t.Fatal("wire capture timed out")
			}
			if got.Model != "models/gemini-3.8-live" || got.Voice != "Aoede" || !got.Audio || !got.InputTranscription || !got.OutputTranscription || !got.AckTool || !got.FunctionResponse {
				t.Fatalf("required baseline wire fields missing: %+v", got)
			}
			if manual && (!got.ActivityStart || !got.ActivityEnd || got.PCMBytes != 8) {
				t.Fatalf("manual input not transmitted: %+v", got)
			}
			if got.ManualSettingForwarded != (compatibilityPatches != "") {
				t.Fatal("SDK wire does not match selected compatibility build")
			}
			if compatibilityPatches != "" && manual && (!got.ModernAudio || got.LegacyMedia) {
				t.Fatal("Gemini 3 Live audio used legacy media wire")
			}
			if compatibilityPatches != "" && !manual && !got.ModernText {
				t.Fatal("Gemini 3 Live text used legacy content wire")
			}
			safe, _ := json.Marshal(got)
			t.Logf("characterization=%s", safe)
			if compatibilityPatches == "" {
				t.Log("CUTOVER GATE: NO-GO; manual activity configuration omitted")
			}

		})
	}
}

func TestCancellationClosesProviderAndIterator(t *testing.T) {
	setup := make(chan struct{})
	closed := make(chan struct{})
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		up := websocket.Upgrader{}
		c, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer c.Close()
		_ = c.SetReadDeadline(time.Now().Add(5 * time.Second))
		var msg any
		if c.ReadJSON(&msg) != nil {
			return
		}
		if c.WriteJSON(map[string]any{"setupComplete": map[string]any{}}) != nil {
			return
		}
		close(setup)
		_, _, _ = c.ReadMessage()
		close(closed)
	}))
	defer srv.Close()
	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()
	live, events, _, cleanup, err := Start(ctx, Settings{"gemini-3.8-live", ""}, &genai.ClientConfig{APIKey: "fixture-only", Backend: genai.BackendGeminiAPI, HTTPOptions: genai.HTTPOptions{APIVersion: "v1alpha", BaseURL: "ws" + strings.TrimPrefix(srv.URL, "http")}})
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()
	done := make(chan struct{})
	go func() {
		defer close(done)
		for range events {
		}
	}()
	select {
	case <-setup:
	case <-ctx.Done():
		t.Fatal("SDK never connected")
	}
	cancel()
	_ = live.Close()
	for _, ch := range []<-chan struct{}{done, closed} {
		select {
		case <-ch:
		case <-time.After(2 * time.Second):
			t.Fatal("SDK teardown exceeded bound")
		}
	}
}

func TestMissingCredentialsNeverStartsRunner(t *testing.T) {
	_, _, _, _, err := Start(t.Context(), Settings{"gemini-3.8-live", ""}, &genai.ClientConfig{})
	if !errors.Is(err, ErrConfig) {
		t.Fatal("expected configuration error")
	}
}

type dummyContext struct{ agent.Context }

func (dummyContext) Err() error { return nil }

func TestAcknowledgmentToolRejectsUnknownFields(t *testing.T) {
	a := &ackTool{calls: &atomic.Int64{}}
	_, err := a.Run(dummyContext{}, map[string]any{"text": "hello", "product_id": "invented"})
	if !errors.Is(err, ErrInput) || a.calls.Load() != 0 {
		t.Fatal("unknown tool field accepted")
	}
}
