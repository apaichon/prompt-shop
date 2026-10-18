.PHONY: prepare test vet build

prepare:
	go run ./cmd/prepare-sdk

test: prepare
	GOWORK="$(CURDIR)/.sdk/go.work" go test -tags=sdkcompat -race ./... -count=1

vet: prepare
	GOWORK="$(CURDIR)/.sdk/go.work" go vet -tags=sdkcompat ./...

build: prepare
	GOWORK="$(CURDIR)/.sdk/go.work" go build -tags=sdkcompat -o ../tmp/go-live-probe-patched ./cmd/live-probe
