#!/usr/bin/env python3
"""KARAR ARAMA - Bedesten (Adalet Bakanligi) uzerinden Yargitay/Danistay karar arama.

Kullanim:
  karar_arama.py sunucu            -> http://127.0.0.1:8790 adresinde arama sayfasi
  karar_arama.py ara "kelime" [--daire "3. Hukuk Dairesi"] [--esas 2025/4989] [--tur YARGITAYKARARI]
  karar_arama.py metin <documentId>
Yalnizca Python standart kutuphanesi kullanir (3.9+).
"""
import base64
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8790
API = "https://bedesten.adalet.gov.tr/emsal-karar/"
BASLIK = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json",
    "AdaletApplicationName": "UyapMevzuat",
    "Origin": "https://mevzuat.adalet.gov.tr",
    "Referer": "https://mevzuat.adalet.gov.tr/",
    "User-Agent": "Mozilla/5.0 (Macintosh) KararArama/1",
}
TURLER = {
    "YARGITAYKARARI": "Yargıtay",
    "DANISTAYKARAR": "Danıştay",
    "ISTINAFHUKUK": "İstinaf (Hukuk)",
    "YERELHUKUK": "Yerel Hukuk",
    "KYB": "Kanun Yararına Bozma",
}
BOSTA_KAPAN = 3 * 3600  # 3 saat istek gelmezse sunucu kapanir
ARALIK = 1.0  # Bedesten'e iki istek arasi en az bu kadar saniye

_kilit = threading.Lock()
_son_istek = [0.0]
_son_kullanim = [time.time()]
_metin_onbellek = {}


class BedestenHatasi(Exception):
    pass


def _gonder(uc, veri):
    govde = json.dumps({"data": veri, "applicationName": "UyapMevzuat", "paging": True}).encode()
    for deneme in range(4):
        with _kilit:
            bekle = _son_istek[0] + ARALIK - time.time()
            if bekle > 0:
                time.sleep(bekle)
            try:
                istek = urllib.request.Request(API + uc, govde, BASLIK)
                with urllib.request.urlopen(istek, timeout=40) as y:
                    j = json.load(y)
            except urllib.error.HTTPError as e:
                _son_istek[0] = time.time()
                if e.code == 429 and deneme < 3:
                    time.sleep(5 * (deneme + 1))
                    continue
                if e.code == 429:
                    raise BedestenHatasi("Bedesten çok sık istek nedeniyle geçici olarak yanıt vermiyor. Bir dakika sonra tekrar deneyin.")
                raise BedestenHatasi("Bedesten hata verdi: HTTP %s" % e.code)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                _son_istek[0] = time.time()
                raise BedestenHatasi("Bedesten'e ulaşılamadı: %s" % getattr(e, "reason", e))
            _son_istek[0] = time.time()
        meta = j.get("metadata") or {}
        if meta.get("FMTY") not in (None, "SUCCESS"):
            raise BedestenHatasi(meta.get("FMU") or meta.get("FMTE") or "Bedesten isteği reddetti.")
        return j.get("data") or {}
    raise BedestenHatasi("Bedesten yanıt vermedi.")


def _no(deger):
    m = re.fullmatch(r"\s*(\d{4})\s*[/\-. ]\s*(\d+)\s*", deger or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _tarih(deger, son=False):
    m = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*", deger or "") or re.fullmatch(r"\s*(\d{4})-(\d{2})-(\d{2})\s*", deger or "")
    if not m:
        return None
    a, b, c = m.groups()
    y, ay, g = (a, b, c) if len(a) == 4 else (c, b, a)
    return "%s-%02d-%02dT%s" % (y, int(ay), int(g), "23:59:59.999Z" if son else "00:00:00.000Z")


def ara(kelime="", daire="", tur="YARGITAYKARARI", esas="", karar="", bas="", bit="", sayfa=1, adet=20, sira="yeni"):
    veri = {"pageSize": max(1, min(int(adet), 100)), "pageNumber": max(1, int(sayfa)),
            "itemTypeList": [tur if tur in TURLER else "YARGITAYKARARI"]}
    if kelime.strip():
        veri["phrase"] = kelime.strip()
    if daire.strip():
        veri["birimAdi"] = daire.strip()
    e, k = _no(esas), _no(karar)
    if esas.strip() and not e:
        raise BedestenHatasi("Esas no 2025/4989 biçiminde olmalı.")
    if karar.strip() and not k:
        raise BedestenHatasi("Karar no 2026/6208 biçiminde olmalı.")
    if e:
        veri["esasNoYil"], veri["esasNoSira"] = e
    if k:
        veri["kararNoYil"], veri["kararNoSira"] = k
    tb, ts = _tarih(bas), _tarih(bit, son=True)
    if bas.strip() and not tb or bit.strip() and not ts:
        raise BedestenHatasi("Tarih 01.01.2025 biçiminde olmalı.")
    if tb or ts:  # Bedesten tarih filtresini yalnızca iki uç birlikte verilince uyguluyor
        veri["kararTarihiStart"] = tb or "1900-01-01T00:00:00.000Z"
        veri["kararTarihiEnd"] = ts or "2100-12-31T23:59:59.999Z"
    if sira in ("yeni", "eski"):
        veri["sortFields"] = ["KARAR_TARIHI"]
        veri["sortDirection"] = "DESC" if sira == "yeni" else "ASC"  # kucuk harf yok sayiliyor
    if not any(x in veri for x in ("phrase", "esasNoYil", "kararNoYil")):
        raise BedestenHatasi("Aranacak kelime ya da esas/karar no girin.")
    d = _gonder("searchDocuments", veri)
    sonuc = []
    for x in d.get("emsalKararList") or []:
        sonuc.append({
            "id": x.get("documentId"),
            "daire": x.get("birimAdi") or "",
            "esas": x.get("esasNo") or "",
            "karar": x.get("kararNo") or "",
            "tarih": x.get("kararTarihiStr") or "",
            "tur": (x.get("itemType") or {}).get("name") or tur,
        })
    return {"toplam": d.get("total") or 0, "sayfa": veri["pageNumber"], "adet": veri["pageSize"], "sonuclar": sonuc}


def _duz_metin(h):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", h)
    h = re.sub(r"(?i)<br\s*/?>", "\n", h)
    h = re.sub(r"(?i)</(p|div|tr|li|h\d)>", "\n", h)
    h = re.sub(r"<[^>]+>", "", h)
    h = html.unescape(h).replace("\xa0", " ")
    satirlar = [re.sub(r"[ \t]+", " ", s).strip() for s in h.split("\n")]
    metin = "\n".join(satirlar)
    return re.sub(r"\n{3,}", "\n\n", metin).strip()


def metin(belge_id):
    belge_id = str(belge_id).strip()
    if not re.fullmatch(r"\d{1,20}", belge_id):
        raise BedestenHatasi("Geçersiz belge numarası.")
    if belge_id in _metin_onbellek:
        return _metin_onbellek[belge_id]
    d = _gonder("getDocumentContent", {"documentId": belge_id})
    ham = base64.b64decode(d.get("content") or "")
    tip = d.get("mimeType") or ""
    if "pdf" in tip:
        sonuc = {"id": belge_id, "metin": "", "pdf": base64.b64encode(ham).decode()}
    else:
        sonuc = {"id": belge_id, "metin": _duz_metin(ham.decode("utf-8", "replace"))}
    if len(_metin_onbellek) > 500:
        _metin_onbellek.clear()
    _metin_onbellek[belge_id] = sonuc
    return sonuc


def kunye(daire, esas, karar, tarih, tur="YARGITAYKARARI"):
    kisa = (daire.replace("Hukuk Dairesi", "HD").replace("Ceza Dairesi", "CD")
            .replace("Hukuk Genel Kurulu", "HGK").replace("Ceza Genel Kurulu", "CGK"))
    kurum = {"YARGITAYKARARI": "Yargıtay", "DANISTAYKARAR": "Danıştay", "KYB": "Yargıtay"}.get(tur, "")
    parca = [p for p in (kurum, kisa) if p]
    s = " ".join(parca) + " %s E., %s K." % (esas, karar)
    return s + (", %s T." % tarih if tarih else "")


# ---------------------------------------------------------------- sunucu
class Isleyici(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _yaz(self, kod, govde, tip="application/json; charset=utf-8"):
        if isinstance(govde, (dict, list)):
            govde = json.dumps(govde, ensure_ascii=False).encode()
        self.send_response(kod)
        self.send_header("Content-Type", tip)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def do_GET(self):
        _son_kullanim[0] = time.time()
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), "rb") as f:
                    return self._yaz(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/ara":
                return self._yaz(200, ara(q.get("q", ""), q.get("daire", ""), q.get("tur", "YARGITAYKARARI"),
                                          q.get("esas", ""), q.get("karar", ""), q.get("bas", ""), q.get("bit", ""),
                                          q.get("sayfa", "1"), q.get("adet", "20"), q.get("sira", "yeni")))
            if u.path == "/api/karar":
                return self._yaz(200, metin(q.get("id", "")))
            if u.path == "/api/durum":
                return self._yaz(200, {"tamam": True, "uygulama": "karar-arama", "surum": 1})
            return self._yaz(404, {"hata": "Bulunamadı"})
        except BedestenHatasi as e:
            return self._yaz(502, {"hata": str(e)})
        except Exception as e:  # beklenmeyen
            return self._yaz(500, {"hata": "Beklenmeyen hata: %s" % e})


def sunucu():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Isleyici)

    def bekci():
        while True:
            time.sleep(60)
            if time.time() - _son_kullanim[0] > BOSTA_KAPAN:
                srv.shutdown()
                return
    threading.Thread(target=bekci, daemon=True).start()
    print("Karar Arama: http://127.0.0.1:%d" % PORT, flush=True)
    srv.serve_forever()


# ---------------------------------------------------------------- komut satiri
def _arg(liste, ad, varsayilan=""):
    if ad in liste:
        i = liste.index(ad)
        if i + 1 < len(liste):
            deger = liste[i + 1]
            del liste[i:i + 2]
            return deger
    return varsayilan


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "yardim"):
        print(__doc__)
        return 0
    komut, kalan = argv[0], argv[1:]
    try:
        if komut == "sunucu":
            sunucu()
        elif komut == "ara":
            daire, esas, karar = _arg(kalan, "--daire"), _arg(kalan, "--esas"), _arg(kalan, "--karar")
            tur, bas, bit = _arg(kalan, "--tur", "YARGITAYKARARI"), _arg(kalan, "--bas"), _arg(kalan, "--bit")
            sayfa, adet, sira = _arg(kalan, "--sayfa", "1"), _arg(kalan, "--adet", "20"), _arg(kalan, "--sira", "yeni")
            r = ara(" ".join(kalan), daire, tur, esas, karar, bas, bit, sayfa, adet, sira)
            print("Toplam %s karar (sayfa %s)" % (format(r["toplam"], ",").replace(",", "."), r["sayfa"]))
            for x in r["sonuclar"]:
                print("%-12s %s" % (x["id"], kunye(x["daire"], x["esas"], x["karar"], x["tarih"], x["tur"])))
        elif komut == "metin":
            r = metin(kalan[0] if kalan else "")
            print(r["metin"] or "(Karar PDF olarak geldi, metin yok.)")
        else:
            print("Bilinmeyen komut: %s\n%s" % (komut, __doc__))
            return 2
    except BedestenHatasi as e:
        print("HATA: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
