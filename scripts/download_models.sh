#!/bin/bash
# Download MediaPipe models for analyzer
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="${SCRIPT_DIR}/../analyzer/models"
mkdir -p "${MODELS_DIR}"

download_model() {
    local name="$1"
    local url="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_${name}/float16/latest/pose_landmarker_${name}.task"
    local out="${MODELS_DIR}/pose_landmarker_${name}.task"

    if [ -f "$out" ]; then
        echo "Pose model '${name}' already exists, skipping."
        return
    fi

    echo "Downloading pose_landmarker_${name}.task ..."
    curl -L -o "$out" "$url"
    echo "Saved: $out"
}

download_hand_model() {
    local out="${MODELS_DIR}/hand_landmarker.task"
    if [ -f "$out" ]; then
        echo "Hand model already exists, skipping."
        return
    fi
    echo "Downloading hand_landmarker.task ..."
    curl -L -o "$out" \
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
    echo "Saved: $out"
}

# Download pose models (lite is always downloaded, full/heavy optional)
download_model "lite"
# download_model "full"
# download_model "heavy"

# Download hand model
download_hand_model

echo "Done. Models saved to ${MODELS_DIR}"
echo ""
echo "To switch pose model, edit config.yaml:"
echo "  analysis:"
echo "    pose_model: heavy   # or lite / full"
