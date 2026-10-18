// Package liveprobe exercises real ADK APIs without wiring an unqualified
// agent into the shopper gateway. Its tool never supplies catalog facts.
package liveprobe

import (
	"context"
	"encoding/binary"
	"errors"
	"iter"
	"regexp"
	"strings"
	"sync/atomic"
	"time"

	"google.golang.org/adk/v2/agent"
	"google.golang.org/adk/v2/agent/llmagent"
	"google.golang.org/adk/v2/model"
	"google.golang.org/adk/v2/model/gemini"
	"google.golang.org/adk/v2/runner"
	"google.golang.org/adk/v2/session"
	"google.golang.org/adk/v2/tool"
	"google.golang.org/adk/v2/tool/toolutils"
	"google.golang.org/genai"
)

const App = "prompt_shop_go_probe"
const ADKVersion = "v2.6.0"
const GenAIVersion = "v1.74.0"

var ErrConfig = errors.New("invalid probe configuration")
var ErrInput = errors.New("invalid synthetic PCM")

// Settings mirrors Python's server-owned configuration, including its explicit
// activity boundaries. A successful compile does not establish wire parity.
type Settings struct{ Model, Voice string }

func (s Settings) Validate() error {
	if !regexp.MustCompile(`^(models/)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`).MatchString(s.Model) {
		return ErrConfig
	}
	if s.Voice != "" && !regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_-]{0,63}$`).MatchString(s.Voice) {
		return ErrConfig
	}
	return nil
}

func (s Settings) RunConfig() agent.LiveRunConfig {
	cfg := agent.LiveRunConfig{
		ResponseModalities:       []genai.Modality{genai.ModalityAudio},
		InputAudioTranscription:  &genai.AudioTranscriptionConfig{},
		OutputAudioTranscription: &genai.AudioTranscriptionConfig{},
		RealtimeInputConfig: &genai.RealtimeInputConfig{
			AutomaticActivityDetection: &genai.AutomaticActivityDetection{Disabled: true},
		},
		SaveLiveBlob: false,
	}
	if s.Voice != "" {
		cfg.SpeechConfig = &genai.SpeechConfig{VoiceConfig: &genai.VoiceConfig{
			PrebuiltVoiceConfig: &genai.PrebuiltVoiceConfig{VoiceName: s.Voice},
		}}
	}
	return cfg
}

type ackTool struct{ calls *atomic.Int64 }

func (a *ackTool) Name() string { return "probe_ack" }
func (a *ackTool) Description() string {
	return "Acknowledge this compatibility test. It has no store information."
}
func (a *ackTool) IsLongRunning() bool { return false }
func (a *ackTool) Declaration() *genai.FunctionDeclaration {
	// Use the same supported Live parameter-schema subset as Python. Runtime
	// validation rejects additional fields independently of provider validation.
	return &genai.FunctionDeclaration{Name: a.Name(), Description: a.Description(),
		Behavior: genai.BehaviorBlocking,
		Parameters: &genai.Schema{Type: genai.TypeObject,
			Properties: map[string]*genai.Schema{"text": {Type: genai.TypeString}},
			Required:   []string{"text"}},
	}
}
func (a *ackTool) ProcessRequest(_ agent.Context, req *model.LLMRequest) error {
	return toolutils.PackTool(req, a)
}
func (a *ackTool) Run(ctx agent.Context, args any) (map[string]any, error) {
	if ctx.Err() != nil {
		return nil, ctx.Err()
	}
	m, ok := args.(map[string]any)
	if !ok || len(m) != 1 {
		return nil, ErrInput
	}
	text, ok := m["text"].(string)
	if !ok || len([]rune(text)) > 300 || strings.TrimSpace(text) == "" {
		return nil, ErrInput
	}
	if a.calls.Add(1) > 1 {
		return map[string]any{"acknowledged": false}, nil
	}
	return map[string]any{"acknowledged": true}, nil
}

// Start uses the real Gemini model implementation and ADK session/runner.
// Endpoint injection exists for local wire tests only; the CLI never exposes it.
func Start(ctx context.Context, settings Settings, cfg *genai.ClientConfig) (agent.LiveSession, iter.Seq2[*session.Event, error], *atomic.Int64, func(), error) {
	if settings.Validate() != nil || cfg == nil || cfg.APIKey == "" {
		return nil, nil, nil, nil, ErrConfig
	}
	m, err := gemini.NewModel(ctx, settings.Model, cfg)
	if err != nil {
		return nil, nil, nil, nil, err
	}
	calls := &atomic.Int64{}
	a, err := llmagent.New(llmagent.Config{Name: "go_compatibility_probe", Model: m,
		Instruction: "You are an English compatibility test agent. For each user request call probe_ack exactly once with the completed request as text. After acknowledgment, say one short English sentence. Never give store facts or make additional tool calls.",
		Tools:       []tool.Tool{&ackTool{calls: calls}},
	})
	if err != nil {
		return nil, nil, nil, nil, err
	}
	store := session.InMemoryService()
	_, err = store.Create(ctx, &session.CreateRequest{AppName: App, UserID: "probe", SessionID: "probe"})
	if err != nil {
		return nil, nil, nil, nil, err
	}
	cleanup := func() {
		c, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		_ = store.Delete(c, &session.DeleteRequest{AppName: App, UserID: "probe", SessionID: "probe"})
	}
	r, err := runner.New(runner.Config{AppName: App, Agent: a, SessionService: store})
	if err != nil {
		cleanup()
		return nil, nil, nil, nil, err
	}
	live, events, err := r.RunLive(ctx, "probe", "probe", settings.RunConfig())
	if err != nil {
		cleanup()
		return nil, nil, nil, nil, err
	}
	return live, events, calls, cleanup, nil
}

// Report is intentionally safe to retain as evidence. Error strings, captions,
// session identity, function arguments and raw audio are never copied into it.
type Report struct {
	CompatibilityPatches string `json:"compatibility_patches,omitempty"`
	ADK                  string `json:"adk"`
	GenAI                string `json:"genai"`
	Model                string `json:"model"`
	Voice                string `json:"voice,omitempty"`
	Input                string `json:"input"`
	Status               string `json:"status"`
	ToolCalls            int64  `json:"tool_calls"`
	InputTranscript      bool   `json:"input_transcript"`
	OutputTranscript     bool   `json:"output_transcript"`
	AudioBytes           int    `json:"audio_bytes"`
	NonzeroSamples       int    `json:"nonzero_pcm_samples"`
	Interrupted          bool   `json:"interrupted"`
	Complete             bool   `json:"turn_complete"`
	Cleanup              bool   `json:"iterator_cleanup"`
	ElapsedMS            int64  `json:"elapsed_ms"`
}

// Run sends either a public synthetic text prompt or caller-supplied synthetic
// 16 kHz mono PCM. A separate process deadline bounds SDK connection behavior.
func Run(ctx context.Context, s Settings, apiKey string, pcm []byte) Report {
	start := time.Now()
	report := Report{CompatibilityPatches: compatibilityPatches, ADK: ADKVersion, GenAI: GenAIVersion, Model: s.Model, Voice: s.Voice, Input: "text control", Status: "configuration_failed"}
	if len(pcm) > 0 {
		report.Input = "synthetic PCM with manual activity"
	}
	if s.Validate() != nil || apiKey == "" {
		return report
	}
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	live, events, calls, cleanup, err := Start(ctx, s, &genai.ClientConfig{APIKey: apiKey, Backend: genai.BackendGeminiAPI, HTTPOptions: genai.HTTPOptions{APIVersion: "v1alpha"}})
	if err != nil {
		return report
	}
	defer cleanup()
	type item struct {
		event *session.Event
		err   error
	}
	ch := make(chan item)
	done := make(chan struct{})
	go func() {
		defer close(done)
		defer close(ch)
		for e, err := range events {
			select {
			case ch <- item{e, err}:
			case <-ctx.Done():
				return
			}
			if err != nil {
				return
			}
		}
	}()
	report.Status = "stream_failed"
	if len(pcm) > 0 {
		err = SendPCM(ctx, live, pcm, true)
	} else {
		err = live.Send(agent.LiveRequest{Content: genai.NewContentFromText("Hello. Please acknowledge this test and say hello.", "user")})
	}
	if err == nil {
	consume:
		for {
			select {
			case <-ctx.Done():
				report.Status = "deadline"
				break consume
			case v, ok := <-ch:
				if !ok || v.err != nil || v.event == nil {

					break consume
				}
				e := v.event
				if e.ErrorCode != "" {
					break consume
				}
				if e.InputTranscription != nil && e.InputTranscription.Text != "" {
					report.InputTranscript = true
				}
				if e.OutputTranscription != nil && e.OutputTranscription.Text != "" {
					report.OutputTranscript = true
				}
				report.Interrupted = report.Interrupted || e.Interrupted
				if e.Content != nil {
					for _, p := range e.Content.Parts {
						if p != nil && p.InlineData != nil {
							b := p.InlineData
							if !strings.HasPrefix(b.MIMEType, "audio/pcm") || len(b.Data)%2 != 0 {
								report.Status = "invalid_audio"
								break consume
							}
							report.AudioBytes += len(b.Data)
							for i := 0; i+1 < len(b.Data); i += 2 {
								if binary.LittleEndian.Uint16(b.Data[i:i+2]) != 0 {
									report.NonzeroSamples++
								}
							}
						}
					}
				}
				if e.TurnComplete {
					report.Complete = true
					report.Status = "incomplete_evidence"
					if calls.Load() == 1 && report.NonzeroSamples > 0 && report.OutputTranscript && (len(pcm) == 0 || report.InputTranscript) {
						report.Status = "pass"
					}
					break consume
				}
			}
		}
	}
	_ = live.Close()
	cancel()
	select {
	case <-done:
		report.Cleanup = true
	case <-time.After(2 * time.Second):
		report.Status = "cleanup_timeout"
	}
	report.ToolCalls = calls.Load()
	report.ElapsedMS = time.Since(start).Milliseconds()
	return report
}

// SendPCM preserves Python's manual activity contract. Fixtures inspect these
// messages even when the pinned SDK omits the corresponding setup setting.
func SendPCM(ctx context.Context, live agent.LiveSession, pcm []byte, pace bool) error {
	if len(pcm) == 0 || len(pcm)%2 != 0 || len(pcm) > 32_000*20 {
		return ErrInput
	}
	if err := live.Send(agent.LiveRequest{RealtimeInput: &genai.ActivityStart{}}); err != nil {
		return err
	}
	for offset := 0; offset < len(pcm); offset += 640 {
		end := min(offset+640, len(pcm))
		b := append([]byte(nil), pcm[offset:end]...)
		if err := live.Send(agent.LiveRequest{RealtimeInput: &genai.Blob{MIMEType: "audio/pcm;rate=16000", Data: b}}); err != nil {
			return err
		}
		if pace {
			timer := time.NewTimer(20 * time.Millisecond)
			select {
			case <-ctx.Done():
				timer.Stop()
				return ctx.Err()
			case <-timer.C:
			}
		}
	}
	return live.Send(agent.LiveRequest{RealtimeInput: &genai.ActivityEnd{}})
}
