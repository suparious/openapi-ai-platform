#!/bin/bash
# Script to pre-load models on Ollama instances
# This runs as part of the model-loader service

set -e

# Configuration
OLLAMA_HOST="${OLLAMA_HOST:-localhost:11434}"

# Models to load based on machine capabilities
if [[ "$HOSTNAME" == *"hades"* ]]; then
    # Large models for AMD GPU machine
    MODELS=(
        "llama3.1:70b"
        "mixtral:8x7b"
        "qwen2.5:32b"
        "llava:34b"
        "deepseek-coder:33b"
    )
else
    # Standard models for NVIDIA GPU machines
    MODELS=(
        "llama3.2"
        "llama3.2:1b"
        "codellama:13b"
        "llava:13b"
        "nomic-embed-text"
        "mxbai-embed-large"
    )
fi

# Function to pull a model
pull_model() {
    local model=$1
    echo "Pulling model: $model"
    
    if curl -X POST "$OLLAMA_HOST/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$model\"}" \
        --max-time 3600; then
        echo "Successfully pulled $model"
    else
        echo "Failed to pull $model"
        return 1
    fi
}

# Function to check if model exists
model_exists() {
    local model=$1
    curl -s "$OLLAMA_HOST/api/tags" | grep -q "\"$model\""
}

# Main execution
echo "Starting model loader for Ollama at $OLLAMA_HOST"
echo "Waiting for Ollama to be ready..."

# Wait for Ollama to be ready
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo "Ollama is ready"
        break
    fi
    echo "Waiting for Ollama... (attempt $((attempt + 1))/$max_attempts)"
    sleep 10
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "Ollama failed to start after $max_attempts attempts"
    exit 1
fi

# Pull models
echo "Loading models..."
for model in "${MODELS[@]}"; do
    if model_exists "$model"; then
        echo "Model $model already exists, skipping"
    else
        pull_model "$model"
    fi
done

echo "Model loading completed"
