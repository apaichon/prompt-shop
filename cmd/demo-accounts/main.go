// Generate the local ten-account handout once. Never print passwords or hashes.
package main

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"github.com/apaichon/prompt-shop/internal/shopauth"
	"golang.org/x/crypto/bcrypt"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
func run() error {
	dir := "tmp/auth"
	if len(os.Args) == 2 {
		dir = os.Args[1]
	} else if len(os.Args) > 2 {
		return fmt.Errorf("usage: demo-accounts [private-directory]")
	}
	accountsFile := filepath.Join(dir, "accounts.json")
	credentialsFile := filepath.Join(dir, "credentials.txt")
	if _, err := os.Stat(accountsFile); err == nil {
		fmt.Println("Shopper accounts already exist; preserved")
		return nil
	} else if !os.IsNotExist(err) {
		return fmt.Errorf("cannot access account directory")
	}
	if _, err := os.Stat(credentialsFile); !os.IsNotExist(err) {
		return fmt.Errorf("credential handout exists or is inaccessible; preserved")
	}
	if err := os.MkdirAll(dir, 0700); err != nil {
		return fmt.Errorf("cannot create private account directory")
	}
	if err := os.Chmod(dir, 0700); err != nil {
		return fmt.Errorf("cannot protect account directory")
	}
	accounts := []shopauth.Account{}
	var handout strings.Builder
	handout.WriteString("Monti Store demo shopper accounts\nKeep this file private. demo01 is an administrator; demo02-demo10 are shoppers.\n\n")
	for i := 1; i <= 10; i++ {
		var raw [18]byte
		if _, err := rand.Read(raw[:]); err != nil {
			return fmt.Errorf("password generation failed")
		}
		password := base64.RawURLEncoding.EncodeToString(raw[:])
		hashed, err := bcrypt.GenerateFromPassword([]byte(password), 12)
		if err != nil {
			return fmt.Errorf("password hashing failed")
		}
		username := fmt.Sprintf("demo%02d", i)
		role := "shopper"
		if i == 1 {
			role = "admin"
		}
		accounts = append(accounts, shopauth.Account{Username: username, PasswordHash: string(hashed), Role: role})
		fmt.Fprintf(&handout, "%s  %s\n", username, password)
	}
	data, err := json.MarshalIndent(accounts, "", "  ")
	if err != nil {
		return err
	}
	// Exclusive creation never replaces existing credentials. Failure leaves a
	// private handout for operator recovery instead of silently rotating passwords.
	for _, f := range []struct {
		name string
		data []byte
	}{{credentialsFile, []byte(handout.String())}, {accountsFile, append(data, '\n')}} {
		file, err := os.OpenFile(f.name, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if err != nil {
			return fmt.Errorf("account files could not be created; existing files preserved")
		}
		_, err = file.Write(f.data)
		closeErr := file.Close()
		if err != nil || closeErr != nil {
			return fmt.Errorf("account file write failed")
		}
	}
	fmt.Println("Created ten shopper accounts and a private credential handout in", dir)
	return nil
}
