# All base references are supplied as name@sha256:digest by deploy/build.py.
ARG GO_IMAGE
ARG NODE_IMAGE
ARG RUNTIME_IMAGE
FROM ${GO_IMAGE} AS backend
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY cmd/ cmd/
COPY internal/ internal/
COPY migrations/ migrations/
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -ldflags="-s -w" -o /out/server ./cmd/server \
 && CGO_ENABLED=0 go build -mod=readonly -trimpath -ldflags="-s -w" -o /out/import ./cmd/import

FROM ${NODE_IMAGE} AS portal
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run check && npm run build && test -s build/index.html

FROM ${RUNTIME_IMAGE} AS runtime
WORKDIR /app
COPY --from=backend /out/server /out/import /app/
COPY --from=portal /src/web/build/ /app/web/build/
COPY data/demo-store.json /app/data/demo-store.json
ENV PORT=8080 READINESS_MODE=full STATIC_DIR=/app/web/build
USER 65532:65532
EXPOSE 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/server"]
