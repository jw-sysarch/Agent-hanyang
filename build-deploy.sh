#!/bin/sh
set -eu

IMAGE_PREFIX="${IMAGE_PREFIX:-hai}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
PUSH="${PUSH:-false}"

build_image() {
  name="$1"
  dockerfile="$2"
  context="$3"
  image="${IMAGE_PREFIX}/${name}:${TAG}"

  echo "build: $image"
  docker build -f "$dockerfile" -t "$image" "$context"

  if [ "$PUSH" = "true" ]; then
    echo "push: $image"
    docker push "$image"
  fi
}

build_image "frontend" "frontend/Dockerfile" "frontend"
build_image "adk-agent" "Dockerfile" "."
build_image "mcp-gmail" "mcps/gmail/Dockerfile" "."
build_image "mcp-google-docs" "mcps/google_docs/Dockerfile" "."
build_image "mcp-google-sheets" "mcps/google_sheets/Dockerfile" "."
build_image "mcp-google-calendar" "mcps/google_calendar/Dockerfile" "."
build_image "mcp-everytime" "mcps/everytime/Dockerfile" "."
build_image "mcp-naver-clova" "mcps/naver_clova/Dockerfile" "."
build_image "mcp-kakao-map" "mcps/kakao_map/Dockerfile" "."

echo "deploy tag: $TAG"
TAG="$TAG" ./deploy.sh
