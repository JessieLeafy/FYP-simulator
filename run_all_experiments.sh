#!/usr/bin/env bash
# Run all 5 experiments sequentially with the real Ollama backend.
set -euo pipefail

cd "$(dirname "$0")"
PYTHON=".venv/bin/python"
LOG_DIR="outputs/experiments/run_all_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

run_exp() {
    local name=$1
    local cfg=$2
    echo ""
    echo "=========================================="
    echo "  EXPERIMENT: $name"
    echo "  $(date)"
    echo "=========================================="
    $PYTHON experiments/run.py \
        --config "$cfg" \
        --experiment "$name" \
        --experiment_output "outputs/experiments" \
        2>&1 | tee "$LOG_DIR/${name}.log"
    echo "  ✓ $name complete at $(date)"
}

echo "Starting all experiments at $(date)" | tee "$LOG_DIR/master.log"

run_exp concession      experiments/configs/exp_concession.yaml     2>&1 | tee -a "$LOG_DIR/master.log"
run_exp anchoring       experiments/configs/exp_anchoring.yaml      2>&1 | tee -a "$LOG_DIR/master.log"
run_exp deadline        experiments/configs/exp_deadline.yaml       2>&1 | tee -a "$LOG_DIR/master.log"
run_exp market_dynamics experiments/configs/exp_market_dynamics.yaml 2>&1 | tee -a "$LOG_DIR/master.log"
run_exp shock_response  experiments/configs/exp_shock_response.yaml 2>&1 | tee -a "$LOG_DIR/master.log"

echo ""
echo "All experiments complete at $(date)" | tee -a "$LOG_DIR/master.log"
echo "Logs: $LOG_DIR"
