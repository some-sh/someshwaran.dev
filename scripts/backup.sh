#!/usr/bin/env bash
# Downloads a backup of every resume from a running instance into a dated JSON
# file, and checks that what it got is really a backup.
#
#   APP_URL=https://someshwarandev.fastapicloud.dev \
#   APP_ADMIN_API_KEY=... \
#   ./scripts/backup.sh [output-dir]        # default: current directory
#
# Restore with the admin UI ("Restore from file…" on the Resumes page) or:
#   curl -X POST "$APP_URL/api/admin/import" -H "Authorization: Bearer $APP_ADMIN_API_KEY" \
#        -H "Content-Type: application/json" --data @backup-file.json
#
# The backup contains every draft as well as the published resume, so keep it
# somewhere private (not in a public repository or a public CI artifact).
set -euo pipefail

: "${APP_URL:?Set APP_URL, e.g. https://someshwarandev.fastapicloud.dev}"
: "${APP_ADMIN_API_KEY:?Set APP_ADMIN_API_KEY}"

out_dir="${1:-.}"
mkdir -p "$out_dir"
out_file="$out_dir/someshwaran-backup-$(date -u +%Y-%m-%dT%H%M%SZ).json"
tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

# The key goes to curl on stdin as a config file, not on the command line, so it
# never shows up in the process list or shell history.
printf 'header = "Authorization: Bearer %s"\n' "$APP_ADMIN_API_KEY" |
  curl --fail --silent --show-error --max-time 60 -K - \
    -o "$tmp_file" "${APP_URL%/}/api/admin/export"

# Refuse to keep something that is not a backup (an HTML error page, an empty file).
count="$(python3 - "$tmp_file" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
assert data.get("format") == "someshwaran.dev/resume-backup", "not a backup file"
print(len(data["resumes"]))
PY
)"

(umask 077 && cp "$tmp_file" "$out_file")
echo "Saved $count resume(s) to $out_file"
