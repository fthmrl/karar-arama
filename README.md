<p align="center"><img src="simge.png" width="128" alt="Karar Arama simgesi"></p>

<h1 align="center">Karar Arama</h1>

<p align="center"><b>Yargıtay, Danıştay, istinaf ve yerel mahkeme kararlarını Adalet Bakanlığı'nın Bedesten arşivinden arayan; hem tarayıcıda çalışan bir arama sayfası hem de Claude gibi yapay zekâ asistanları için bir MCP sunucusu olan, ücretsiz ve açık kaynak araç.</b></p>

---

## Neden?

Adalet Bakanlığı'nın [mevzuat.adalet.gov.tr](https://mevzuat.adalet.gov.tr) sitesindeki karar araması arka planda **Bedesten** adlı bir servis kullanır. Bu servis yaklaşık 10 milyon Yargıtay kararını, Danıştay, istinaf ve yerel mahkeme kararlarını tam metinleriyle sunar.

**Karar Arama** bu servise doğrudan bağlanır:

- **Tarayıcıda:** sade bir arama sayfası. Kararı açar, aradığınız kelimeleri işaretler, künyeyi tek tıkla kopyalar.
- **Yapay zekâ asistanında:** MCP sunucusu olarak. Claude'a "3. HD'nin 2025'ten beri kira tespitinde verdiği kararları bul ve özetle" diyebilirsiniz.

Başkasının sunucusu, aracı bir hizmet ya da ek paket yoktur: istekler bilgisayarınızdan doğrudan Bakanlığın sunucusuna gider.

## Özellikler

- **Kelime araması.** Tam ifade için çift tırnak kullanın: `"kira tespit"`.
- **Filtreler:** kaynak (Yargıtay, Danıştay, İstinaf Hukuk, Yerel Hukuk, Kanun Yararına Bozma), daire, esas no, karar no, karar tarihi aralığı.
- **Sıralama:** en yeni ya da en eski karar önce.
- **Okuma:** kararın tam metni, aranan kelimeler vurgulanmış. ↑/↓ tuşlarıyla kararlar arasında gezinme.
- **Künye kopyalama:** `Yargıtay 3. HD 2026/546 E., 2026/3879 K., 17.06.2026 T.`
- **Yazdır / PDF:** yalnızca karar metni yazdırılır.
- **Komut satırı:** `karar ara …` ve `karar metin …`.
- **MCP sunucusu:** `karar_ara` ve `karar_metni` araçları.

## Kurulum (macOS)

> Gereksinim: macOS'teki hazır Python 3 (`/usr/bin/python3`). Başka hiçbir paket gerekmez.

```bash
git clone https://github.com/fthmrl/karar-arama.git
```

```bash
cd karar-arama && ./kur.sh
```

Kurulum betiği:

1. Dosyaları `~/Library/Application Support/KararArama` klasörüne kopyalar.
2. **Uygulamalar** klasörüne **Karar Arama** uygulamasını ekler. Açınca arama sayfası tarayıcıda `http://127.0.0.1:8790` adresinde açılır.
3. `~/.local/bin/karar` komutunu oluşturur.
4. MCP sunucusunu **Claude Code** (`~/.claude.json`) ve **Claude masaüstü uygulamasına** (`claude_desktop_config.json`) kaydeder. Değiştirmeden önce dosyanın yedeğini `….karar-arama-yedek` adıyla alır. Bu adımı istemezseniz `MCP_KAYDETME=1 ./kur.sh` ile kurun.

Kaydın etkin olması için Claude'u yeniden başlatın.

## MCP sunucusu

`karar_mcp.py` yalnızca Python standart kütüphanesini kullanan bir stdio MCP sunucusudur (Python 3.9+). macOS dışında Windows ve Linux'ta da çalışır.

| Araç | Ne yapar |
|---|---|
| `karar_ara` | Kelime, kaynak, daire, esas/karar no, tarih aralığı ve sıralamayla arar; her sonuç için belge numarası ve künye döner. |
| `karar_metni` | Belge numarasıyla kararın tam metnini düz yazı olarak getirir. |

Başka bir MCP istemcisine elle eklemek için:

```json
{
  "mcpServers": {
    "karar-arama": {
      "command": "python3",
      "args": ["/tam/yol/karar-arama/karar_mcp.py"]
    }
  }
}
```

Claude Code komut satırı kuruluysa:

```bash
claude mcp add karar-arama -s user -- python3 /tam/yol/karar-arama/karar_mcp.py
```

## Komut satırı

```bash
karar ara '"kira tespit"' --daire "3. Hukuk Dairesi" --bas 01.01.2025 --sira eski
```

```bash
karar ara --esas 2025/4989 --daire "8. Hukuk Dairesi"
```

```bash
karar metin 1237139100
```

Seçenekler: `--tur` (YARGITAYKARARI, DANISTAYKARAR, ISTINAFHUKUK, YERELHUKUK, KYB), `--daire`, `--esas`, `--karar`, `--bas`, `--bit`, `--sira` (yeni, eski, ilgi), `--sayfa`, `--adet`.

## Bilinmesi gerekenler

- **Bedesten resmî olarak yayımlanmış bir API değildir.** Bakanlığın kendi sitesinin arka planda kullandığı servistir; haber verilmeden değişebilir.
- **Hız sınırı sıkıdır.** Araç istekleri en az bir saniye arayla gönderir ve "çok fazla istek" (429) yanıtında bekleyip yeniden dener. Toplu indirme için uygun değildir; lütfen servisi yormayın.
- Daire adı tam yazılmalıdır: `3. Hukuk Dairesi`, `12. Ceza Dairesi`, `Hukuk Genel Kurulu`, Danıştay için `4. Daire`.
- Arama sunucusu yalnızca bilgisayarınızın içinden (`127.0.0.1`) erişilebilir ve 3 saat kullanılmazsa kendiliğinden kapanır.

## Gizlilik

- Hesap, kayıt, reklam ya da kullanım istatistiği yoktur.
- Aramalarınız yalnızca `bedesten.adalet.gov.tr` adresine gönderilir; başka hiçbir yere veri gitmez.

## Lisans

MIT
