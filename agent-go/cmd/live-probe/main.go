package main

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"log/slog"
	"os"
	"time"

	"github.com/apaichon/prompt-shop/agent-go/internal/liveprobe"
)

func main() {
	// SDK error logs can contain provider bodies or a request URL. Retain only
	// the structured status report below, even on failed connection attempts.
	log.SetOutput(io.Discard)
	slog.SetDefault(slog.New(slog.NewTextHandler(io.Discard, nil)))
	if os.Getenv("GO_ADK_LIVE_TEST") != "1" {
		emit(map[string]string{"status": "opt_in_required"})
		os.Exit(2)
	}
	s := liveprobe.Settings{Model: os.Getenv("GEMINI_MODEL"), Voice: os.Getenv("GEMINI_VOICE")}
	if s.Model == "" {
		s.Model = "gemini-3.8-live"
	}
	if s.Validate() != nil || os.Getenv("GOOGLE_API_KEY") == "" {
		emit(map[string]string{"status": "configuration_failed"})
		os.Exit(2)
	}
	var pcm []byte
	if p := os.Getenv("GO_ADK_SYNTHETIC_PCM"); p != "" {
		f, err := os.Open(p)
		if err != nil {
			emit(map[string]string{"status": "input_failed"})
			os.Exit(2)
		}
		pcm, err = io.ReadAll(io.LimitReader(f, 640001))
		_ = f.Close()
		if err != nil || len(pcm) == 0 || len(pcm) > 640000 || len(pcm)%2 != 0 {
			emit(map[string]string{"status": "input_failed"})
			os.Exit(2)
		}
	}
	// SDK websocket dialing does not honor context in all failure paths. Bound
	// the CLI process too. This is diagnostic isolation, not a runtime fix.
	ctx, cancel := context.WithTimeout(context.Background(), 55*time.Second)
	defer cancel()
	done := make(chan liveprobe.Report, 1)
	go func() { done <- liveprobe.Run(ctx, s, os.Getenv("GOOGLE_API_KEY"), pcm) }()
	select {
	case report := <-done:
		emit(report)
		if report.Status != "pass" || !report.Cleanup {
			os.Exit(1)
		}
	case <-time.After(60 * time.Second):
		emit(map[string]string{"status": "process_deadline"})
		os.Exit(1)
	}
}
func emit(v any) { _ = json.NewEncoder(os.Stdout).Encode(v) }
