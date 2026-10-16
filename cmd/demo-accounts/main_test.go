package main

import (
	"github.com/apaichon/prompt-shop/internal/shopauth"
	"golang.org/x/crypto/bcrypt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestProvisionIsPrivateAndPreservesPasswords(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "auth")
	old := os.Args
	os.Args = []string{"demo-accounts", dir}
	defer func() { os.Args = old }()
	if e := run(); e != nil {
		t.Fatal(e)
	}
	accounts, e := shopauth.LoadAccounts(filepath.Join(dir, "accounts.json"))
	if e != nil {
		t.Fatal(e)
	}
	if _, e = shopauth.New(shopauth.Config{Origin: "http://localhost:8080", Accounts: accounts}); e != nil {
		t.Fatal(e)
	}
	handout, e := os.ReadFile(filepath.Join(dir, "credentials.txt"))
	if e != nil {
		t.Fatal(e)
	}
	passwords := map[string]bool{}
	for _, a := range accounts {
		var password string
		for _, line := range strings.Split(string(handout), "\n") {
			if strings.HasPrefix(line, a.Username+"  ") {
				password = strings.Fields(line)[1]
			}
		}
		if len(password) != 24 || passwords[password] || bcrypt.CompareHashAndPassword([]byte(a.PasswordHash), []byte(password)) != nil {
			t.Fatal("bad generated credential")
		}
		passwords[password] = true
	}
	for _, name := range []string{"accounts.json", "credentials.txt"} {
		info, _ := os.Stat(filepath.Join(dir, name))
		if info.Mode().Perm() != 0600 {
			t.Fatal("file permissions")
		}
	}
	info, _ := os.Stat(dir)
	if info.Mode().Perm() != 0700 {
		t.Fatal("directory permissions")
	}
	if e = run(); e != nil {
		t.Fatal(e)
	}
	after, _ := os.ReadFile(filepath.Join(dir, "credentials.txt"))
	if string(after) != string(handout) {
		t.Fatal("credentials rotated")
	}
}
