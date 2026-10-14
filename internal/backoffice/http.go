package backoffice

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"io"
	"mime"
	"net/url"
	"strconv"
	"time"

	"github.com/gofiber/fiber/v2"
	"golang.org/x/crypto/bcrypt"
)

type Config struct {
	Origin, PasswordHash string
	Now                  func() time.Time
	Random               io.Reader
}
type API struct {
	repo                   Repository
	cfg                    Config
	loginLimit, writeLimit *limiter
	compareSlots           chan struct{}
}

func New(repo Repository, cfg Config) (*API, error) {
	u, err := url.Parse(cfg.Origin)
	if err != nil || u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Path != "" || (u.Scheme != "https" && !(u.Scheme == "http" && (u.Hostname() == "localhost" || u.Hostname() == "127.0.0.1" || u.Hostname() == "::1"))) {
		return nil, errors.New("invalid backoffice origin")
	}
	cost, err := bcrypt.Cost([]byte(cfg.PasswordHash))
	if err != nil || cost != 12 {
		return nil, errors.New("invalid maintainer password hash: cost 12 required")
	}
	if cfg.Now == nil {
		cfg.Now = time.Now
	}
	if cfg.Random == nil {
		cfg.Random = rand.Reader
	}
	return &API{repo: repo, cfg: cfg, loginLimit: newLimiter(5, 2), writeLimit: newLimiter(20, 2), compareSlots: make(chan struct{}, 2)}, nil
}
func (a *API) Register(r fiber.Router) {
	r.Post("/api/backoffice/session", a.login)
	r.Get("/api/backoffice/session", a.protect(false, func(c *fiber.Ctx, s Session, hash string, ctx context.Context) error { return c.JSON(s) }))
	r.Delete("/api/backoffice/session", a.protect(true, a.logout))
	r.Get("/api/backoffice/products", a.protect(false, a.list))
	r.Get("/api/backoffice/shelves", a.protect(false, a.shelves))
	r.Post("/api/backoffice/products", a.protect(true, a.mutate("create")))
	r.Put("/api/backoffice/products/:id", a.protect(true, a.mutate("save")))
	r.Post("/api/backoffice/products/:id/publish", a.protect(true, a.mutate("publish")))
	r.Post("/api/backoffice/products/:id/archive", a.protect(true, a.mutate("archive")))
}
func fail(c *fiber.Ctx, err error) error {
	f := &fault{503, "DEPENDENCY_UNAVAILABLE", "The catalog is temporarily unavailable. Please try again."}
	var known *fault
	if errors.As(err, &known) {
		f = known
	}
	return c.Status(f.status).JSON(fiber.Map{"error": fiber.Map{"code": f.code, "message": f.message, "retryable": f.status == 503 || f.status == 429}, "request_id": c.GetRespHeader("X-Request-ID")})
}
func limited(c *fiber.Ctx, seconds int) error {
	c.Set("Retry-After", strconv.Itoa(seconds))
	return fail(c, &fault{429, "RATE_LIMITED", "Please wait before trying again."})
}
func tokenHash(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}
func (a *API) token() (string, error) {
	var value [32]byte
	if _, err := io.ReadFull(a.cfg.Random, value[:]); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(value[:]), nil
}
func (a *API) setCookie(c *fiber.Ctx, raw string, expires time.Time, clear bool) {
	maxAge := 8 * 60 * 60
	if clear {
		maxAge = -1
		expires = time.Unix(1, 0)
	}
	c.Cookie(&fiber.Cookie{Name: cookieName, Value: raw, Path: "/", Secure: true, HTTPOnly: true, SameSite: "Strict", Expires: expires, MaxAge: maxAge})
}
func (a *API) login(c *fiber.Ctx) error {
	ctx, cancel := context.WithTimeout(c.UserContext(), 1500*time.Millisecond)
	defer cancel()
	if c.Get("Origin") != a.cfg.Origin {
		return fail(c, &fault{403, "FORBIDDEN", "Use the approved store portal."})
	}
	if ok, seconds := a.loginLimit.allow(c.Context().RemoteIP().String(), a.cfg.Now()); !ok {
		return limited(c, seconds)
	}
	// Bound bcrypt CPU as well as per-IP admission; never queue unbounded comparisons.
	select {
	case a.compareSlots <- struct{}{}:
		defer func() { <-a.compareSlots }()
	default:
		return limited(c, 1)
	}
	var body struct {
		Password *string `json:"password"`
	}
	if len(c.Body()) > 1024 || decode(c.Body(), &body) != nil || body.Password == nil {
		return fail(c, &fault{400, "INVALID_REQUEST", "Enter your maintainer password."})
	}
	password := *body.Password
	if len(password) < 16 || len(password) > 72 || bcrypt.CompareHashAndPassword([]byte(a.cfg.PasswordHash), []byte(password)) != nil {
		return fail(c, errAuth)
	}
	raw, err := a.token()
	if err != nil {
		return fail(c, err)
	}
	csrf, err := a.token()
	if err != nil {
		return fail(c, err)
	}
	now := a.cfg.Now().UTC()
	s := Session{ExpiresAt: now.Add(8 * time.Hour), CSRFToken: csrf}
	oldHash := ""
	old := c.Cookies(cookieName)
	if tokenPattern.MatchString(old) {
		oldHash = tokenHash(old)
	}
	if err = a.repo.Rotate(ctx, oldHash, tokenHash(raw), s, now); err != nil {
		return fail(c, err)
	}
	a.setCookie(c, raw, s.ExpiresAt, false)
	return c.JSON(s)
}

type handler func(*fiber.Ctx, Session, string, context.Context) error

func (a *API) protect(write bool, next handler) fiber.Handler {
	return func(c *fiber.Ctx) error {
		ctx, cancel := context.WithTimeout(c.UserContext(), 1500*time.Millisecond)
		defer cancel()
		raw := c.Cookies(cookieName)
		if !tokenPattern.MatchString(raw) {
			return fail(c, errAuth)
		}
		hash := tokenHash(raw)
		s, err := a.repo.Session(ctx, hash, a.cfg.Now())
		if err != nil {
			return fail(c, err)
		}
		if write {
			csrf := c.Get("X-CSRF-Token")
			if c.Get("Origin") != a.cfg.Origin || len(csrf) != len(s.CSRFToken) || subtle.ConstantTimeCompare([]byte(csrf), []byte(s.CSRFToken)) != 1 {
				return fail(c, &fault{403, "FORBIDDEN", "The session could not verify this change. Reload and try again."})
			}
			if ok, seconds := a.writeLimit.allow(hash, a.cfg.Now()); !ok {
				return limited(c, seconds)
			}
		}
		return next(c, s, hash, ctx)
	}
}
func (a *API) logout(c *fiber.Ctx, _ Session, hash string, ctx context.Context) error {
	if err := a.repo.Revoke(ctx, hash); err != nil {
		return fail(c, err)
	}
	a.setCookie(c, "", time.Time{}, true)
	return c.SendStatus(204)
}
func (a *API) list(c *fiber.Ctx, _ Session, _ string, ctx context.Context) error {
	bad := false
	seen := map[string]bool{}
	c.Context().QueryArgs().VisitAll(func(k, v []byte) {
		key := string(k)
		if (key != "q" && key != "state" && key != "cursor") || seen[key] {
			bad = true
		}
		seen[key] = true
	})
	if bad {
		return fail(c, invalid())
	}
	f, err := parseFilter(c.Query("q"), c.Query("state"), c.Query("cursor"))
	if err != nil {
		return fail(c, err)
	}
	p, err := a.repo.List(ctx, f)
	if err != nil {
		return fail(c, err)
	}
	return c.JSON(p)
}
func (a *API) shelves(c *fiber.Ctx, _ Session, _ string, ctx context.Context) error {
	items, err := a.repo.Shelves(ctx)
	if err != nil {
		return fail(c, err)
	}
	return c.JSON(fiber.Map{"items": items})
}
func (a *API) mutate(action string) handler {
	return func(c *fiber.Ctx, _ Session, hash string, ctx context.Context) error {
		mediaType, _, mediaErr := mime.ParseMediaType(c.Get("Content-Type"))
		if mediaErr != nil || mediaType != "application/json" {
			return fail(c, &fault{400, "INVALID_REQUEST", "Use a JSON request."})
		}
		var in Input
		if err := decode(c.Body(), &in); err != nil {
			return fail(c, err)
		}
		if _, err := validate(in, action); err != nil {
			return fail(c, err)
		}
		id := c.Params("id")
		if action != "create" && !idPattern.MatchString(id) {
			return fail(c, invalid())
		}
		product, err := a.repo.Mutate(ctx, hash, a.cfg.Now(), id, in, action)
		if err != nil {
			return fail(c, err)
		}
		status := 200
		if action == "create" {
			status = 201
		}
		return c.Status(status).JSON(product)
	}
}
