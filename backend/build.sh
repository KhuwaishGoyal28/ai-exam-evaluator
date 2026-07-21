#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build.sh — Render build script
# Runs during the "Build" phase on Render.
#
# What it does:
#   1. Installs Python dependencies (backend)
#   2. Installs Node.js + npm dependencies (frontend)
#   3. Builds the React/Vite app  →  frontend/dist/
#   4. Copies the built files     →  backend/static/
#      FastAPI then serves them at /
# ─────────────────────────────────────────────────────────────────────────────
set -e   # exit immediately on any error

echo "▶  Step 1/4 — Installing Python dependencies"
pip install -r requirements.txt

echo "▶  Step 2/4 — Installing Node.js dependencies"
cd ../frontend
npm install

echo "▶  Step 3/4 — Building React frontend"
npm run build           # outputs to frontend/dist/

echo "▶  Step 4/4 — Copying built files to backend/static"
cd ../backend
rm -rf static           # clean any previous build
cp -r ../frontend/dist static

echo "✅  Build complete — static/ is ready"
