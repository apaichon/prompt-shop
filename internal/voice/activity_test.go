package voice

import (
	"encoding/binary"
	"errors"
	"testing"
)

func activityPCM(size, amplitude int) []byte {
	pcm := make([]byte, size)
	for i := 0; i < size; i += 2 {
		binary.LittleEndian.PutUint16(pcm[i:], uint16(amplitude))
	}
	return pcm
}
func TestInputActivityRejectsImpulseAndPreservesSustainedOnset(t *testing.T) {
	var a inputActivity
	for i := 0; i < 50; i++ {
		start, end, frames := a.push(activityPCM(640, 0))
		if start || end || len(frames) > 0 {
			t.Fatal("silence forwarded")
		}
	}
	start, _, frames := a.push(activityPCM(640, 2000))
	if start || len(frames) > 0 {
		t.Fatal("20ms noise became speech")
	}
	a.push(activityPCM(640, 0))
	for i := 0; i < 4; i++ {
		start, _, frames = a.push(activityPCM(640, 1000))
		if i < 3 && (start || len(frames) > 0) {
			t.Fatal("premature onset")
		}
	}
	if !start || len(frames) != 4 {
		t.Fatal("onset missing")
	}
	for _, pcm := range frames {
		if len(pcm) != 640 || binary.LittleEndian.Uint16(pcm) != 1000 {
			t.Fatal("first syllable lost")
		}
	}
	for i := 0; i < 17; i++ {
		_, end, frames := a.push(activityPCM(640, 0))
		if end || len(frames) != 1 {
			t.Fatal("premature end")
		}
	}
	_, end, frames := a.push(activityPCM(640, 0))
	if !end || len(frames) != 1 {
		t.Fatal("silence did not end")
	}
	_, _, frames = a.push(activityPCM(640, 0))
	if len(frames) > 0 {
		t.Fatal("idle silence leaked")
	}
}
func TestInputActivityBoundedForMaximumFramesAndReset(t *testing.T) {
	var a inputActivity
	start, _, frames := a.push(activityPCM(6400, 1000))
	if !start || len(frames) != 1 {
		t.Fatal("valid 200ms frame lost")
	}
	a.reset()
	start, _, frames = a.push(activityPCM(640, 1000))
	if start || len(frames) != 0 {
		t.Fatal("reset failed")
	}
}
func TestSessionEndReasonDoesNotExposeErrorPayload(t *testing.T) {
	if sessionEndReason(errors.New("secret transcript token")) != "transport_failure" {
		t.Fatal("unsafe logging")
	}
}
