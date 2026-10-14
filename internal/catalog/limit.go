package catalog

import (
	"math"
	"sync"
	"time"
)

// Limiter is a per-key token bucket. A nil limiter allows every call.
type Limiter struct {
	mu      sync.Mutex
	rate    float64
	burst   float64
	now     func() time.Time
	buckets map[string]*bucket
}

type bucket struct {
	tokens  float64
	updated time.Time
}

func NewLimiter(perMinute, burst int) *Limiter {
	if perMinute < 1 {
		perMinute = 60
	}
	if burst < 1 {
		burst = 10
	}
	return &Limiter{
		rate:    float64(perMinute) / 60,
		burst:   float64(burst),
		now:     time.Now,
		buckets: map[string]*bucket{},
	}
}

func (l *Limiter) Allow(key string) bool {
	if l == nil {
		return true
	}
	if key == "" {
		key = "unknown"
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.now()
	b := l.buckets[key]
	if b == nil {
		if len(l.buckets) > 10000 {
			l.buckets = map[string]*bucket{}
		}
		l.buckets[key] = &bucket{tokens: l.burst - 1, updated: now}
		return true
	}
	elapsed := now.Sub(b.updated).Seconds()
	if elapsed > 0 {
		b.tokens = math.Min(l.burst, b.tokens+elapsed*l.rate)
		b.updated = now
	}
	if b.tokens < 1 {
		return false
	}
	b.tokens--
	return true
}
