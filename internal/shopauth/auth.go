// Package shopauth provides the bounded, single-process demo shopper login.
package shopauth

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/url"
	"os"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/gofiber/fiber/v2"
	"golang.org/x/crypto/bcrypt"
)

const cookieName = "__Host-shop-session"

var usernamePattern = regexp.MustCompile(`^[a-z][a-z0-9._-]{2,31}$`)

type Account struct {
	Username     string `json:"username"`
	PasswordHash string `json:"password_hash"`
	Role         string `json:"role"`
}
type Config struct {
	Origin   string
	Accounts []Account
	Now      func() time.Time
	OnLogin  func(context.Context, string, string, Session) error
	OnLogout func(context.Context, string) error
}
type Session struct {
	Role      string    `json:"role"`
	Username  string    `json:"username"`
	ExpiresAt time.Time `json:"expires_at"`
	CSRF      string    `json:"csrf_token"`
}
type attempt struct {
	Count int
	Until time.Time
}
type Auth struct {
	cfg         Config
	accounts    map[string]string
	roles       map[string]string
	dummyHash   string
	mu          sync.Mutex
	sessions    map[string]Session
	attempts    map[string]attempt
	comparisons chan struct{}
}

func decode(data []byte, target any) error {
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(target); err != nil {
		return err
	}
	if d.Decode(new(any)) != io.EOF {
		return errors.New("unexpected input")
	}
	return nil
}
func LoadAccounts(path string) ([]Account, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, errors.New("shopper account file unavailable")
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, 16385))
	if err != nil || len(data) > 16384 {
		return nil, errors.New("invalid shopper account file")
	}
	var accounts []Account
	if decode(data, &accounts) != nil {
		return nil, errors.New("invalid shopper account file")
	}
	return accounts, nil
}
func New(cfg Config) (*Auth, error) {
	u, err := url.Parse(cfg.Origin)
	if err != nil || u.Host == "" || u.User != nil || u.Path != "" || u.RawQuery != "" || u.Fragment != "" || (u.Scheme != "https" && !(u.Scheme == "http" && (u.Hostname() == "localhost" || u.Hostname() == "127.0.0.1" || u.Hostname() == "::1"))) {
		return nil, errors.New("invalid shopper origin")
	}
	if len(cfg.Accounts) != 10 {
		return nil, errors.New("exactly ten shopper accounts required")
	}
	if cfg.Now == nil {
		cfg.Now = time.Now
	}
	a := &Auth{cfg: cfg, accounts: map[string]string{}, roles: map[string]string{}, sessions: map[string]Session{}, attempts: map[string]attempt{}, comparisons: make(chan struct{}, 2)}
	for _, account := range cfg.Accounts {
		cost, err := bcrypt.Cost([]byte(account.PasswordHash))
		if !usernamePattern.MatchString(account.Username) || a.accounts[account.Username] != "" || err != nil || cost != 12 || (account.Role != "admin" && account.Role != "shopper") {
			return nil, errors.New("invalid shopper accounts; unique usernames and bcrypt cost12 required")
		}
		a.accounts[account.Username] = account.PasswordHash
		a.roles[account.Username] = account.Role
		a.dummyHash = account.PasswordHash
	}
	return a, nil
}
func failure(c *fiber.Ctx, status int, code string) error {
	return c.Status(status).JSON(fiber.Map{"error": fiber.Map{"code": code, "message": "Sign in to continue.", "retryable": status == 429 || status >= 500}, "request_id": c.GetRespHeader("X-Request-ID")})
}
func hash(raw string) string { s := sha256.Sum256([]byte(raw)); return hex.EncodeToString(s[:]) }
func token() (string, error) {
	var b [32]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b[:]), nil
}
func (a *Auth) lookup(key string) (Session, bool) {
	a.mu.Lock()
	defer a.mu.Unlock()
	s, ok := a.sessions[key]
	if ok && !a.cfg.Now().Before(s.ExpiresAt) {
		delete(a.sessions, key)
		ok = false
	}
	return s, ok
}
func (a *Auth) key(c *fiber.Ctx) string {
	raw := c.Cookies(cookieName)
	if len(raw) != 43 {
		return ""
	}
	return hash(raw)
}

// Validator captures only a hash, never a pooled Fiber context. Gateway checks it
// again throughout voice so logout in another tab revokes existing connections.
func (a *Auth) Validator(c *fiber.Ctx) func() bool {
	key := a.key(c)
	return func() bool { _, ok := a.lookup(key); return ok }
}
func (a *Auth) Register(r fiber.Router) {
	r.Get("/api/auth/session", func(c *fiber.Ctx) error {
		s, ok := a.lookup(a.key(c))
		if !ok {
			return failure(c, 401, "AUTH_REQUIRED")
		}
		return c.JSON(fiber.Map{"enabled": true, "username": s.Username, "role": s.Role, "expires_at": s.ExpiresAt, "csrf_token": s.CSRF})
	})
	r.Post("/api/auth/session", a.login)
	r.Delete("/api/auth/session", a.Logout)
	r.Use(func(c *fiber.Ctx) error {
		path := c.Path()
		if path == "/api" || strings.HasPrefix(path, "/api/") || path == "/ws/voice" {
			if _, ok := a.lookup(a.key(c)); !ok {
				return failure(c, 401, "AUTH_REQUIRED")
			}
		}
		return c.Next()
	})
}
func Disabled(r fiber.Router) {
	r.Get("/api/auth/session", func(c *fiber.Ctx) error { return c.JSON(fiber.Map{"enabled": false}) })
}
func (a *Auth) allow(ip string) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	now := a.cfg.Now()
	for k, v := range a.attempts {
		if !now.Before(v.Until) {
			delete(a.attempts, k)
		}
	}
	v, ok := a.attempts[ip]
	if !ok {
		if len(a.attempts) >= 1024 {
			return false
		}
		v = attempt{Until: now.Add(time.Minute)}
	}
	if v.Count >= 10 {
		return false
	}
	v.Count++
	a.attempts[ip] = v
	return true
}
func (a *Auth) cookie(c *fiber.Ctx, raw string, expires time.Time) {
	age := 8 * 60 * 60
	if raw == "" {
		age = -1
		expires = time.Unix(1, 0)
	}
	c.Cookie(&fiber.Cookie{Name: cookieName, Value: raw, HTTPOnly: true, Secure: true, SameSite: "Strict", Path: "/", MaxAge: age, Expires: expires})
}
func (a *Auth) login(c *fiber.Ctx) error {
	if c.Get("Origin") != a.cfg.Origin {
		return failure(c, 403, "FORBIDDEN")
	}
	if !a.allow(c.Context().RemoteIP().String()) {
		c.Set("Retry-After", "60")
		return failure(c, 429, "RATE_LIMITED")
	}
	select {
	case a.comparisons <- struct{}{}:
		defer func() { <-a.comparisons }()
	default:
		c.Set("Retry-After", "1")
		return failure(c, 429, "RATE_LIMITED")
	}
	var body struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if len(c.Body()) > 1024 || decode(c.Body(), &body) != nil || len(body.Password) > 72 || len(body.Password) < 1 {
		return failure(c, 400, "INVALID_REQUEST")
	}
	username := strings.ToLower(strings.TrimSpace(body.Username))
	passwordHash, exists := a.accounts[username]
	if !exists {
		passwordHash = a.dummyHash
	}
	matched := bcrypt.CompareHashAndPassword([]byte(passwordHash), []byte(body.Password)) == nil
	if !exists || !matched {
		return failure(c, 401, "INVALID_CREDENTIALS")
	}
	raw, err := token()
	if err != nil {
		return failure(c, 503, "DEPENDENCY_UNAVAILABLE")
	}
	csrf, err := token()
	if err != nil {
		return failure(c, 503, "DEPENDENCY_UNAVAILABLE")
	}
	now := a.cfg.Now()
	s := Session{Role: a.roles[username], Username: username, ExpiresAt: now.Add(8 * time.Hour), CSRF: csrf}
	a.mu.Lock()
	for k, v := range a.sessions {
		if !now.Before(v.ExpiresAt) {
			delete(a.sessions, k)
		}
	}
	if len(a.sessions) >= 200 {
		a.mu.Unlock()
		return failure(c, 429, "RATE_LIMITED")
	}
	if a.cfg.OnLogin != nil {
		ctx, cancel := context.WithTimeout(c.UserContext(), 1500*time.Millisecond)
		err = a.cfg.OnLogin(ctx, a.key(c), hash(raw), s)
		cancel()
		if err != nil {
			a.mu.Unlock()
			return failure(c, 503, "DEPENDENCY_UNAVAILABLE")
		}
	}
	delete(a.sessions, a.key(c))
	a.sessions[hash(raw)] = s
	a.mu.Unlock()
	a.cookie(c, raw, s.ExpiresAt)
	return c.JSON(fiber.Map{"enabled": true, "username": s.Username, "role": s.Role, "expires_at": s.ExpiresAt, "csrf_token": s.CSRF})
}
func (a *Auth) Logout(c *fiber.Ctx) error {
	key := a.key(c)
	s, ok := a.lookup(key)
	if !ok {
		return failure(c, 401, "AUTH_REQUIRED")
	}
	csrf := c.Get("X-CSRF-Token")
	if c.Get("Origin") != a.cfg.Origin || len(csrf) != len(s.CSRF) || subtle.ConstantTimeCompare([]byte(csrf), []byte(s.CSRF)) != 1 {
		return failure(c, 403, "FORBIDDEN")
	}
	a.mu.Lock()
	if a.cfg.OnLogout != nil {
		ctx, cancel := context.WithTimeout(c.UserContext(), 1500*time.Millisecond)
		err := a.cfg.OnLogout(ctx, key)
		cancel()
		if err != nil {
			a.mu.Unlock()
			return failure(c, 503, "DEPENDENCY_UNAVAILABLE")
		}
	}
	delete(a.sessions, key)
	a.mu.Unlock()
	a.cookie(c, "", time.Time{})
	return c.SendStatus(204)
}

// AdminSession never accepts the legacy maintainer cookie when shared login is enabled.
func (a *Auth) AdminSession(c *fiber.Ctx) (Session, string, bool) {
	key := a.key(c)
	s, ok := a.lookup(key)
	return s, key, ok && s.Role == "admin"
}
