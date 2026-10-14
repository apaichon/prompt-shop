// Reads a maintainer password from standard input; never prints the password.
package main

import (
	"fmt"
	"golang.org/x/crypto/bcrypt"
	"io"
	"os"
	"strings"
	"unicode/utf8"
)

func main() {
	raw, err := io.ReadAll(io.LimitReader(os.Stdin, 74))
	password := strings.TrimSuffix(strings.TrimSuffix(string(raw), "\n"), "\r")
	if err != nil || len(password) < 16 || len(password) > 72 || !utf8.ValidString(password) {
		fmt.Fprintln(os.Stderr, "password must be 16–72 UTF-8 bytes")
		os.Exit(1)
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(password), 12)
	if err != nil {
		fmt.Fprintln(os.Stderr, "hash generation failed")
		os.Exit(1)
	}
	fmt.Println(string(hash))
}
