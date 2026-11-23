#!/bin/bash
# KARAR ARAMA kurulumu: dosyalari ~/Library/Application Support/KararArama'ya kopyalar,
# /Applications/Karar Arama.app baslaticisini ve ~/.local/bin/karar komutunu olusturur,
# karar-arama MCP sunucusunu Claude Code'a ve Claude masaustu uygulamasina kaydeder.
# MCP kaydi istenmiyorsa: MCP_KAYDETME=1 ./kur.sh
set -euo pipefail
KAYNAK="$(cd "$(dirname "$0")" && pwd)"
HEDEF="$HOME/Library/Application Support/KararArama"
APP="/Applications/Karar Arama.app"
PY=/usr/bin/python3

mkdir -p "$HEDEF"
cp "$KAYNAK/karar_arama.py" "$KAYNAK/karar_mcp.py" "$KAYNAK/index.html" "$HEDEF/"

# Calisan eski sunucuyu kapat (yeni surum yuklensin)
pkill -f "KararArama/karar_arama.py sunucu" 2>/dev/null || true

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Karar Arama</string>
  <key>CFBundleDisplayName</key><string>Karar Arama</string>
  <key>CFBundleIdentifier</key><string>com.fthmrl.kararArama</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>1</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>baslat</string>
  <key>CFBundleIconFile</key><string>simge</string>
  <key>LSUIElement</key><true/>
</dict></plist>
PLIST
cat > "$APP/Contents/MacOS/baslat" <<EOF
#!/bin/bash
URL=http://127.0.0.1:8790/
if ! /usr/bin/curl -s -m 2 "\${URL}api/durum" | grep -q karar-arama; then
  nohup $PY "$HEDEF/karar_arama.py" sunucu >/dev/null 2>&1 &
  for i in \$(seq 1 40); do /usr/bin/curl -s -m 1 "\${URL}api/durum" | grep -q karar-arama && break; sleep 0.25; done
fi
/usr/bin/open "\$URL"
EOF
chmod +x "$APP/Contents/MacOS/baslat"
[ -f "$KAYNAK/simge.icns" ] && cp "$KAYNAK/simge.icns" "$APP/Contents/Resources/simge.icns"
/usr/bin/codesign --force -s - "$APP" >/dev/null 2>&1 || true

mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/karar" <<EOF
#!/bin/bash
exec $PY "$HEDEF/karar_arama.py" "\$@"
EOF
chmod +x "$HOME/.local/bin/karar"
echo "Kuruldu: $APP  ve  ~/.local/bin/karar"

# MCP kaydi: Claude Code (~/.claude.json) ve Claude masaustu (claude_desktop_config.json)
if [ "${MCP_KAYDETME:-0}" != "1" ]; then
  "$PY" -I - "$PY" "$HEDEF/karar_mcp.py" <<'PYEOF'
import json, os, shutil, sys, tempfile
py, betik = sys.argv[1], sys.argv[2]
kayit = {"type": "stdio", "command": py, "args": [betik], "env": {}}
dosyalar = [os.path.expanduser("~/.claude.json"),
            os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")]
for yol in dosyalar:
    if not os.path.exists(yol):
        continue
    with open(yol, encoding="utf-8") as f:
        d = json.load(f)
    sunucular = d.setdefault("mcpServers", {})
    yeni = dict(kayit) if yol.endswith(".claude.json") else {"command": py, "args": [betik]}
    if sunucular.get("karar-arama") == yeni:
        print("MCP zaten kayitli:", yol)
        continue
    shutil.copy2(yol, yol + ".karar-arama-yedek")
    sunucular["karar-arama"] = yeni
    fd, gecici = tempfile.mkstemp(dir=os.path.dirname(yol))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(gecici, yol)
    print("MCP kaydedildi:", yol)
PYEOF
fi
