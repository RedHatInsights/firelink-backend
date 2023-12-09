#!/bin/bash

# Get the first 7 characters of the current git commit SHA
GIT_SHA=$(git rev-parse --short=7 HEAD)

if [ -z "$GIT_SHA" ]; then
    echo "Error: Git commit hash not found."
    exit 1
fi

# Define the image name
IMAGE_NAME="firelink-backend:$GIT_SHA"

# Log in to registries
docker login -u="$QUAY_USER" -p="$QUAY_TOKEN" quay.io
docker login -u="$RH_REGISTRY_USER" -p="$RH_REGISTRY_TOKEN" registry.redhat.io

# Build the Docker image
echo "Building Docker image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" .

# Tag the image for Quay
QUAY_IMAGE="quay.io/cloudservices/$IMAGE_NAME"
echo "Tagging image for Quay: $QUAY_IMAGE"
docker tag "$IMAGE_NAME" "$QUAY_IMAGE"

# Push the image to Quay
echo "Pushing image to Quay: $QUAY_IMAGE"
docker push "$QUAY_IMAGE"

echo "Image successfully pushed to Quay: $QUAY_IMAGE"
