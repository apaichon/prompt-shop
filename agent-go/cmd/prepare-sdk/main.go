// Command prepare-sdk builds isolated, checksum-verified SDK compatibility
// copies. It never writes to the Go module cache or the production app module.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type sdk struct{ Module, Version, Sum, Source, SourceSHA, ExtraSource, ExtraSHA, Patch, Target string }

var sdks = []sdk{
	{"google.golang.org/adk/v2", "v2.6.0", "h1:ZgMfKWzzB1H3qQ/6JV3pGkm7rcfNZFRMkgvOLBtmJTk=", "internal/llminternal/base_flow.go", "7834d5f978837bfebba0751e0afba637fccbd95217824eb1c7539e9a30949934", "internal/llminternal/googlellm/live_connection.go", "5ccd141cc9f068ee76f29ba8be0c36c82a535113487457843217dc7044751a15", "adk-v2.6.0-realtime-input.patch,adk-v2.6.0-gemini3-live-input.patch", "adk-v2.6.0-compat3"},
	{"google.golang.org/genai", "v1.74.0", "h1:n7lBIax9PkdrmfxsNilfFPOwo1ahelozeZj2Ady0lgw=", "live.go", "8a493f6fddf3ec17a9ec1503da2873925d4f4080dd0c2fdb4f51211efd17f6a6", "", "", "genai-v1.74.0-live-write-lock.patch", "genai-v1.74.0-compat3"},
}

func main() {
	if err := prepare(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
func prepare() error {
	root, err := os.Getwd()
	if err != nil {
		return err
	}
	mod, err := os.ReadFile(filepath.Join(root, "go.mod"))
	if err != nil || !strings.HasPrefix(string(mod), "module github.com/apaichon/prompt-shop/agent-go\n") {
		return errors.New("run from agent-go module root")
	}
	if err := os.MkdirAll(filepath.Join(root, ".sdk"), 0700); err != nil {
		return err
	}
	verify := exec.Command("go", "mod", "verify")
	verify.Env = append(os.Environ(), "GOWORK=off")
	if err := verify.Run(); err != nil {
		return errors.New("module cache verification failed")
	}
	entries := []map[string]string{}
	for _, s := range sdks {
		output, err := exec.Command("go", "mod", "download", "-json", s.Module+"@"+s.Version).Output()
		if err != nil {
			return fmt.Errorf("download %s: %w", s.Module, err)
		}
		var m struct{ Path, Version, Dir, Sum string }
		if json.Unmarshal(output, &m) != nil || m.Path != s.Module || m.Version != s.Version || m.Sum != s.Sum {
			return fmt.Errorf("module identity mismatch: %s", s.Module)
		}
		if hashFile(filepath.Join(m.Dir, s.Source)) != s.SourceSHA {
			return fmt.Errorf("SDK source differs from pinned patch base: %s", s.Module)
		}
		if s.ExtraSource != "" && hashFile(filepath.Join(m.Dir, s.ExtraSource)) != s.ExtraSHA {
			return fmt.Errorf("SDK input source differs from patch base: %s", s.Module)
		}
		patches := strings.Split(s.Patch, ",")
		patchHash := sha256.New()
		for _, name := range patches {
			content, err := os.ReadFile(filepath.Join(root, "compat", name))
			if err != nil {
				return errors.New("missing patch")
			}
			patchHash.Write([]byte(name))
			patchHash.Write(content)
		}
		patchSHA := hex.EncodeToString(patchHash.Sum(nil))
		target := filepath.Join(root, ".sdk", s.Target)
		marker := filepath.Join(target, ".prompt-shop-compat.json")
		meta := map[string]string{"module": s.Module, "version": s.Version, "sum": s.Sum, "original_source_sha256": s.SourceSHA, "patch_sha256": patchSHA, "patches": s.Patch}
		if s.ExtraSource != "" {
			meta["original_extra_source_sha256"] = s.ExtraSHA
		}
		if _, err := os.Stat(target); err == nil {
			raw, err := os.ReadFile(marker)
			var old map[string]string
			if err != nil || json.Unmarshal(raw, &old) != nil || old["patch_sha256"] != patchSHA || old["sum"] != s.Sum || old["patched_source_sha256"] != hashFile(filepath.Join(target, s.Source)) {
				return errors.New("existing SDK copy changed; inspect it before preparing a fresh workspace")
			}
			if s.ExtraSource != "" && old["patched_extra_source_sha256"] != hashFile(filepath.Join(target, s.ExtraSource)) {
				return errors.New("existing SDK input source changed")
			}
			tree, err := hashTree(target)
			if err != nil || tree != old["patched_tree_sha256"] {
				return errors.New("existing SDK tree changed")
			}
			entries = append(entries, old)
			continue
		}
		stage, err := os.MkdirTemp(filepath.Join(root, ".sdk"), "stage-")
		if err != nil {
			return err
		}
		err = func() error {
			if err := copyTree(m.Dir, stage); err != nil {
				return err
			}
			for _, name := range patches {
				cmd := exec.Command("patch", "-p1", "-F0", "-t", "-i", filepath.Join(root, "compat", name))
				cmd.Dir = stage
				if err := cmd.Run(); err != nil {
					return fmt.Errorf("exact SDK patch failed: %s", s.Module)
				}
			}
			meta["patched_source_sha256"] = hashFile(filepath.Join(stage, s.Source))
			if meta["patched_source_sha256"] == "" || meta["patched_source_sha256"] == s.SourceSHA {
				return errors.New("patch did not change expected source")
			}
			if s.ExtraSource != "" {
				meta["patched_extra_source_sha256"] = hashFile(filepath.Join(stage, s.ExtraSource))
				if meta["patched_extra_source_sha256"] == s.ExtraSHA || meta["patched_extra_source_sha256"] == "" {
					return errors.New("input compatibility patch did not apply")
				}
			}
			tree, err := hashTree(stage)
			if err != nil {
				return err
			}
			meta["patched_tree_sha256"] = tree
			raw, _ := json.MarshalIndent(meta, "", "  ")
			if err := os.WriteFile(filepath.Join(stage, ".prompt-shop-compat.json"), append(raw, '\n'), 0600); err != nil {
				return err
			}
			return os.Rename(stage, target)
		}()
		if err != nil {
			_ = os.RemoveAll(stage)
			return err
		}
		entries = append(entries, meta)
	}
	work := "go 1.26.6\n\ntoolchain go1.26.9\n\nuse (\n    ..\n    ./adk-v2.6.0-compat3\n    ./genai-v1.74.0-compat3\n)\n"
	if err := os.WriteFile(filepath.Join(root, ".sdk", "go.work"), []byte(work), 0600); err != nil {
		return err
	}
	raw, _ := json.MarshalIndent(entries, "", "  ")
	if err := os.WriteFile(filepath.Join(root, ".sdk", "manifest.json"), append(raw, '\n'), 0600); err != nil {
		return err
	}
	fmt.Println("Prepared checksum-verified SDK compatibility workspace: .sdk/go.work")
	return nil
}
func hashFile(p string) string {
	b, err := os.ReadFile(p)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}
func hashTree(root string) (string, error) {
	h := sha256.New()
	err := filepath.WalkDir(root, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		if d.Type()&os.ModeSymlink != 0 {
			return errors.New("unexpected SDK tree symlink")
		}
		rel, err := filepath.Rel(root, p)
		if err != nil {
			return err
		}
		if rel == ".prompt-shop-compat.json" {
			return nil
		}
		data, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		h.Write([]byte(filepath.ToSlash(rel)))
		h.Write([]byte{0})
		h.Write(data)
		h.Write([]byte{0})
		return nil
	})
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
func copyTree(source, target string) error {
	return filepath.WalkDir(source, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(source, p)
		if err != nil {
			return err
		}
		dest := filepath.Join(target, rel)
		if d.Type()&os.ModeSymlink != 0 {
			return errors.New("unexpected symlink in SDK module")
		}
		if d.IsDir() {
			return os.MkdirAll(dest, 0700)
		}
		data, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		return os.WriteFile(dest, data, 0600)
	})
}
