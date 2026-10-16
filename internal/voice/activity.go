package voice

// Both sides count mono 16kHz PCM16 bytes, not network-arrival wall time.
// 80ms onset rejects brief impulses; 350ms silence ends sustained speech.
const onsetBytes = 2560
const silenceBytes = 11200

type inputActivity struct {
	active         bool
	onset, silence int
	pending        [][]byte
}

func (a *inputActivity) reset() { *a = inputActivity{} }
func (a *inputActivity) push(pcm []byte) (started, ended bool, frames [][]byte) {
	speech := voiced(pcm)
	if a.active {
		if speech {
			a.silence = 0
		} else {
			a.silence += len(pcm)
		}
		ended = a.silence >= silenceBytes
		if ended {
			a.reset()
		}
		return false, ended, [][]byte{pcm}
	}
	if !speech {
		a.reset()
		return false, false, nil
	}
	// Keep the onset (at most 80ms plus one bounded input frame) so that
	// activity_start precedes its PCM and the first syllable isn't discarded.
	a.pending = append(a.pending, append([]byte(nil), pcm...))
	a.onset += len(pcm)
	if a.onset < onsetBytes {
		return false, false, nil
	}
	frames = a.pending
	a.pending = nil
	a.onset = 0
	a.active = true
	return true, false, frames
}
