#!/usr/bin/env bash
# deploy.sh — Promote dev to production
# Usage: ./deploy.sh seo|ziwei|game|all
# Example: ./deploy.sh seo    # Deploy SEO site dev → release
#          ./deploy.sh all    # Deploy all sites

set -euo pipefail

SITE=${1:-}

if [ -z "$SITE" ] || [ "$SITE" = "help" ]; then
  echo "Usage: $0 {seo|ziwei|game|textools|all}"
  echo ""
  echo "  seo      → /home/ubuntu/seo-tools"
  echo "  ziwei    → /home/ubuntu/ziwei-api (static root)"
  echo "  game     → /home/ubuntu/ziwei-games"
  echo "  textools → /home/ubuntu/textools"
  echo "  all      → Deploy all 4 sites"
  exit 1
fi

deploy_site() {
  local name="$1"
  local dir="$2"
  local ver_file="$dir/versions/.version"

  if [ ! -d "$dir/versions/dev" ]; then
    echo "  ⚠️  $name: no dev/ directory found, skipping"
    return
  fi

  # Determine next version number
  local next_ver=1
  for v in "$dir/versions"/v*; do
    if [ -d "$v" ]; then
      local num="${v##*v}"
      if [ "$num" -ge "$next_ver" ]; then
        next_ver=$((num + 1))
      fi
    fi
  done

  local ver_name="v${next_ver}"
  echo "  📦 $name: deploying dev → $ver_name"

  # Copy dev to new version directory
  cp -a "$dir/versions/dev" "$dir/versions/$ver_name"

  # Update release symlink
  ln -sfn "$dir/versions/$ver_name" "$dir/release"
  echo "$ver_name" > "$ver_file"

  echo "  ✅ $name: $ver_name is now live"
}

case "$SITE" in
  seo)
    deploy_site "seo.textools.site" "/home/ubuntu/seo-tools"
    ;;
  ziwei)
    deploy_site "ziweiapi.site" "/home/ubuntu/ziwei-api"
    ;;
  game)
    deploy_site "game.ziweiapi.site" "/home/ubuntu/ziwei-games"
    ;;
  textools)
    deploy_site "textools.site" "/home/ubuntu/textools"
    ;;
  all)
    deploy_site "seo.textools.site" "/home/ubuntu/seo-tools"
    deploy_site "ziweiapi.site" "/home/ubuntu/ziwei-api"
    deploy_site "game.ziweiapi.site" "/home/ubuntu/ziwei-games"
    deploy_site "textools.site" "/home/ubuntu/textools"
    ;;
esac

echo ""
echo "🎉 Done! No nginx reload needed — symlink is live."
