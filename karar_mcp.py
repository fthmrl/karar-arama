#!/usr/bin/env python3
"""KARAR ARAMA MCP sunucusu (stdio).

Bedesten (Adalet Bakanligi) uzerinden Yargitay, Danistay, istinaf ve yerel mahkeme
kararlarini arar ve tam metnini getirir. Yalnizca Python standart kutuphanesi kullanir
(3.9+); `mcp` paketi gerekmez.

Claude Code'a eklemek icin:
  claude mcp add karar-arama -s user -- python3 /tam/yol/karar_mcp.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from karar_arama import TURLER, BedestenHatasi, ara, kunye, metin  # noqa: E402

SURUM = "1.0.0"
PROTOKOLLER = ("2025-06-18", "2025-03-26", "2024-11-05")

ARACLAR = [
    {
        "name": "karar_ara",
        "title": "Karar ara",
        "description": (
            "Bedesten (Adalet Bakanlığı) karar arşivinde arama yapar. Yargıtay, Danıştay, istinaf "
            "ve yerel mahkeme kararlarını kelimeyle, daireyle, esas/karar numarasıyla ve tarih "
            "aralığıyla süzer. Her sonuç için belge numarası (id) ve künye döner; tam metin için "
            "karar_metni aracını bu id ile çağırın. Tam ifade için kelimeyi çift tırnak içine "
            "alın: \"kira tespit\". En az bir kelime ya da esas/karar no gerekir."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kelime": {"type": "string", "description": "Aranacak kelimeler. Tam ifade için çift tırnak: \"kira tespit\""},
                "kaynak": {"type": "string", "enum": list(TURLER), "default": "YARGITAYKARARI",
                           "description": "YARGITAYKARARI, DANISTAYKARAR, ISTINAFHUKUK, YERELHUKUK ya da KYB"},
                "daire": {"type": "string", "description": "Tam daire adı: \"3. Hukuk Dairesi\", \"12. Ceza Dairesi\", \"Hukuk Genel Kurulu\", Danıştay için \"4. Daire\""},
                "esas_no": {"type": "string", "description": "Esas numarası, 2025/4989 biçiminde"},
                "karar_no": {"type": "string", "description": "Karar numarası, 2026/6208 biçiminde"},
                "baslangic_tarihi": {"type": "string", "description": "Karar tarihi alt sınırı, GG.AA.YYYY"},
                "bitis_tarihi": {"type": "string", "description": "Karar tarihi üst sınırı, GG.AA.YYYY"},
                "siralama": {"type": "string", "enum": ["yeni", "eski", "ilgi"], "default": "yeni",
                             "description": "yeni: en yeni karar önce, eski: en eski önce, ilgi: Bedesten'in kendi sırası"},
                "sayfa": {"type": "integer", "minimum": 1, "default": 1},
                "adet": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "karar_metni",
        "title": "Karar metni",
        "description": "karar_ara sonucundaki belge numarasıyla (id) kararın tam metnini düz yazı olarak getirir.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "karar_ara'nın döndürdüğü belge numarası"}},
            "required": ["id"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
]


def _karar_ara(a):
    r = ara(a.get("kelime", ""), a.get("daire", ""), a.get("kaynak", "YARGITAYKARARI"),
            a.get("esas_no", ""), a.get("karar_no", ""), a.get("baslangic_tarihi", ""),
            a.get("bitis_tarihi", ""), a.get("sayfa", 1), a.get("adet", 20), a.get("siralama", "yeni"))
    satirlar = ["Toplam %s karar, sayfa %s (sayfa başına %s)." % (format(r["toplam"], ",").replace(",", "."), r["sayfa"], r["adet"])]
    for x in r["sonuclar"]:
        satirlar.append("id %s | %s" % (x["id"], kunye(x["daire"], x["esas"], x["karar"], x["tarih"], x["tur"])))
    if not r["sonuclar"]:
        satirlar.append("Sonuç bulunamadı.")
    return "\n".join(satirlar)


def _karar_metni(a):
    r = metin(a.get("id", ""))
    return r["metin"] or "Bu karar Bedesten'de PDF olarak duruyor; düz metni yok."


def _cevap(kimlik, sonuc=None, hata=None):
    m = {"jsonrpc": "2.0", "id": kimlik}
    if hata is not None:
        m["error"] = hata
    else:
        m["result"] = sonuc
    sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def isle(m):
    yontem, kimlik, p = m.get("method"), m.get("id"), m.get("params") or {}
    if kimlik is None:  # bildirim (notifications/initialized vb.)
        return
    if yontem == "initialize":
        istenen = p.get("protocolVersion")
        return _cevap(kimlik, {
            "protocolVersion": istenen if istenen in PROTOKOLLER else PROTOKOLLER[0],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "karar-arama", "title": "Karar Arama (Bedesten)", "version": SURUM},
            "instructions": "Türk mahkeme kararlarını Bedesten'den arar. Önce karar_ara ile id bulun, sonra karar_metni ile tam metni alın. Bedesten'in hız sınırı sıkıdır; gereksiz toplu istekten kaçının.",
        })
    if yontem == "ping":
        return _cevap(kimlik, {})
    if yontem == "tools/list":
        return _cevap(kimlik, {"tools": ARACLAR})
    if yontem == "tools/call":
        ad, arg = p.get("name"), p.get("arguments") or {}
        islev = {"karar_ara": _karar_ara, "karar_metni": _karar_metni}.get(ad)
        if not islev:
            return _cevap(kimlik, hata={"code": -32602, "message": "Bilinmeyen araç: %s" % ad})
        try:
            return _cevap(kimlik, {"content": [{"type": "text", "text": islev(arg)}], "isError": False})
        except (BedestenHatasi, ValueError, TypeError) as e:
            return _cevap(kimlik, {"content": [{"type": "text", "text": "HATA: %s" % e}], "isError": True})
    return _cevap(kimlik, hata={"code": -32601, "message": "Desteklenmeyen yöntem: %s" % yontem})


def main():
    for satir in sys.stdin:
        satir = satir.strip()
        if not satir:
            continue
        try:
            m = json.loads(satir)
        except ValueError:
            _cevap(None, hata={"code": -32700, "message": "JSON çözümlenemedi"})
            continue
        for tek in (m if isinstance(m, list) else [m]):
            try:
                isle(tek)
            except Exception as e:  # sunucu dusmesin
                print("karar-arama: %r" % e, file=sys.stderr)
                if isinstance(tek, dict) and tek.get("id") is not None:
                    _cevap(tek["id"], hata={"code": -32603, "message": str(e)})


if __name__ == "__main__":
    main()
