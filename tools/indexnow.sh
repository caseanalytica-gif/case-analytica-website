#!/bin/sh
# Tell Bing and the other IndexNow engines that pages changed.
# Run after a push is live, with the changed paths or full URLs:
#   sh tools/indexnow.sh articles/new-slug.html sitemap.xml
# No arguments submits every URL in the live sitemap.
# 200 or 202 means accepted. This speeds up crawling; it doesn't affect ranking.
KEY=295a80b0bac54428a001d9578de1549f
HOST=www.caseanalytica.com

if [ $# -eq 0 ]; then
  set -- $(curl -s "https://$HOST/sitemap.xml" | grep -o '<loc>[^<]*' | sed 's/<loc>//')
fi

python3 - "$KEY" "$HOST" "$@" <<'EOF' | curl -s -o /dev/null -w 'IndexNow %{http_code}\n' \
  -X POST https://api.indexnow.org/IndexNow \
  -H 'Content-Type: application/json; charset=utf-8' --data @-
import json, sys
key, host, *paths = sys.argv[1:]
urls = [p if p.startswith("http") else f"https://{host}/{p.lstrip('/')}" for p in paths]
print(json.dumps({"host": host, "key": key,
                  "keyLocation": f"https://{host}/{key}.txt", "urlList": urls}))
EOF
