package backoffice

import (
	"math"
	"sync"
	"time"
)

type bucket struct {
	tokens float64
	at     time.Time
}
type limiter struct {
	mu          sync.Mutex
	buckets     map[string]bucket
	rate, burst float64
}

func newLimiter(rate, burst float64) *limiter {
	return &limiter{buckets: map[string]bucket{}, rate: rate / 60, burst: burst}
}
func (l *limiter) allow(key string, now time.Time) (bool, int) {
	l.mu.Lock()
	defer l.mu.Unlock()
	b, exists := l.buckets[key]
	if !exists {
		if len(l.buckets) >= 10000 {
			for k, v := range l.buckets {
				if now.Sub(v.at) > 10*time.Minute {
					delete(l.buckets, k)
				}
			}
			if len(l.buckets) >= 10000 {
				return false, 60
			}
		}
		b = bucket{l.burst, now}
	}
	elapsed := math.Max(0, now.Sub(b.at).Seconds())
	b.tokens = math.Min(l.burst, b.tokens+elapsed*l.rate)
	b.at = now
	if b.tokens < 1 {
		l.buckets[key] = b
		return false, int(math.Ceil((1 - b.tokens) / l.rate))
	}
	b.tokens--
	l.buckets[key] = b
	return true, 0
}
