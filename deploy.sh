#!/bin/sh
set -eu

STACK_NAME="${STACK_NAME:-hai}"
IMAGE_PREFIX="${IMAGE_PREFIX:-hai}"
TAG="${TAG:-latest}"

WITH_REGISTRY_AUTH="${WITH_REGISTRY_AUTH:-false}"

update_service() {
  service="$1"
  image="$2"

  full_service="${STACK_NAME}_${service}"

  if ! docker service inspect "$full_service" >/dev/null 2>&1; then
    echo "skip: service not found: $full_service"
    return 0
  fi

  echo "deploy: $full_service -> $image"

  if [ "$WITH_REGISTRY_AUTH" = "true" ]; then
    docker service update --with-registry-auth --image "$image" "$full_service"
  else
    docker service update --image "$image" "$full_service"
  fi
}

update_service "frontend" "${IMAGE_PREFIX}/frontend:${TAG}"
update_service "adk-agent" "${IMAGE_PREFIX}/adk-agent:${TAG}"
update_service "mcp-gmail" "${IMAGE_PREFIX}/mcp-gmail:${TAG}"
update_service "mcp-google-docs" "${IMAGE_PREFIX}/mcp-google-docs:${TAG}"
update_service "mcp-google-sheets" "${IMAGE_PREFIX}/mcp-google-sheets:${TAG}"
update_service "mcp-google-calendar" "${IMAGE_PREFIX}/mcp-google-calendar:${TAG}"
update_service "mcp-everytime" "${IMAGE_PREFIX}/mcp-everytime:${TAG}"
update_service "mcp-naver-clova" "${IMAGE_PREFIX}/mcp-naver-clova:${TAG}"
update_service "mcp-kakao-map" "${IMAGE_PREFIX}/mcp-kakao-map:${TAG}"

echo "done"
