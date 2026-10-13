package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/apaichon/prompt-shop/internal/platform/database"
	"github.com/apaichon/prompt-shop/internal/platform/importer"
	"github.com/apaichon/prompt-shop/migrations"
)

func main() { os.Exit(run()) }
func run() int {
	file := flag.String("file", "", "JSON import path (operator-only)")
	migrate := flag.Bool("migrate", false, "apply checked migrations before import; allowed without -file")
	flag.Parse()
	fail := func(code, msg string) int {
		_ = json.NewEncoder(os.Stderr).Encode(map[string]any{"errors": []importer.RowError{{Collection: "batch", Index: 0, Code: code, Message: msg}}})
		return 1
	}
	if *file == "" && !*migrate {
		return fail("USAGE", "use -file and/or -migrate")
	}
	url := os.Getenv("OPERATOR_DATABASE_URL")
	if url == "" {
		return fail("CONFIGURATION", "OPERATOR_DATABASE_URL is required")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	pool, err := database.Open(ctx, url, 1)
	if err != nil {
		return fail("CONFIGURATION", "invalid operator database configuration")
	}
	defer pool.Close()
	if *migrate {
		if err = migrations.Apply(ctx, pool); err != nil {
			return fail("MIGRATION_FAILED", "migration failed; inspect database availability and schema using operator tools")
		}
	}
	if *file == "" {
		fmt.Println(`{"status":"migrated"}`)
		return 0
	}
	f, err := os.Open(*file)
	if err != nil {
		return fail("READ_FAILED", "cannot open import file")
	}
	defer f.Close()
	result, err := importer.Import(ctx, pool, f)
	if err != nil {
		var validation *importer.ValidationError
		if errors.As(err, &validation) {
			_ = json.NewEncoder(os.Stderr).Encode(validation)
			return 1
		}
		return fail("IMPORT_FAILED", "database import failed; no partial changes committed")
	}
	_ = json.NewEncoder(os.Stdout).Encode(result)
	return 0
}
