#!/usr/bin/env bash
# Build script for Render (or any Linux host). Run from the repository root.
#   1. builds the Vue site into djangoProject/spa/
#   2. installs Python packages, collects static files, migrates the database
#   3. loads the demo catalog the first time, and creates an admin login if
#      DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD are set
set -o errexit -o pipefail

# --- Node.js: Vite 8 needs Node 20.19+ or 22.12+. Use a portable Node 24 if the host's is older.
node_ok() {
  command -v node >/dev/null 2>&1 && node -e '
    const [a,b]=process.versions.node.split(".").map(Number);
    process.exit((a===20&&b>=19)||(a===22&&b>=12)||a>=23?0:1)'
}
if ! node_ok; then
  echo "Installing a portable Node.js 24 for the build..."
  NODE_DIR="$HOME/.cache/node24"
  mkdir -p "$NODE_DIR"
  FILE=$(curl -fsSL https://nodejs.org/dist/latest-v24.x/SHASUMS256.txt | awk '/linux-x64.tar.xz$/ {print $2}')
  curl -fsSL "https://nodejs.org/dist/latest-v24.x/$FILE" | tar -xJ -C "$NODE_DIR" --strip-components=1
  export PATH="$NODE_DIR/bin:$PATH"
fi
echo "Node $(node --version)"

(cd frontend && npm ci && npm run build)

cd djangoProject
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py seed_demo --if-empty
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py createsuperuser --no-input || echo "Admin user already exists."
fi
