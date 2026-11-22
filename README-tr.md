# lcwaikiki-mcp

**LC Waikiki** (lcw.com) için resmî olmayan, salt okunur MCP sunucusu — Türkiye'nin en büyük moda perakendecisi (1.300+ mağaza, 1988'den beri): ürün arama, ürün detayı, kategori dizini, kategori ürünleri ve fiyat istatistikleri.

mcp-name: io.github.mohammad-abbasi-sh/lcwaikiki-mcp

## Araçlar

| Araç | Ne yapar |
| --- | --- |
| `lcwaikiki_search_products` | Türkçe anahtar kelimeyle ürün arar (`elbise`, `kot pantolon`, `kaban`). Sayfa (sayfa başına 100 ürün), sıralama: `default`, `price_asc`, `price_desc`, `newest`, `discount`, `best_sellers`, `most_reviewed`, `most_favorited`. |
| `lcwaikiki_get_product` | Bir ürünün tüm detayı (URL veya `-o-<id>` içeren yol): ad, marka, renk, bedenler, kumaş, TRY fiyat, stok durumu, kargo, puan ortalaması, yorum sayısı ve en yeni 5 yorum. |
| `lcwaikiki_list_categories` | Tam kategori dizini: 6 departman (KADIN, ERKEK, ÇOCUK, BEBEK, EV \| YAŞAM, Fırsat Alanı), gruplar ve 185 kategori; URL ve ağaç id'leriyle. |
| `lcwaikiki_category_products` | Bir kategorinin ürünleri (örn. `/kadin-giyim-t-10`); sayfalama ve aramadaki sıralamalarla. |
| `lcwaikiki_price_stats` | Bir arama için fiyat istatistikleri (ilk 100 sonuç): TRY olarak min / medyan / ortalama / maks, indirimli ürün payı, ortalama indirim, ortalama puan, en çok geçen markalar. |
| `lcwaikiki_health` | Erişilebilirlik kontrolü (ana sayfa + bir arama). |

## Kurulum

Python 3.10+ gerekir. Paket PyPI'da yayımlanır (yayıncı kurulumu bekleniyor — aşağıya bakın); yayına girince:

```bash
uvx lcwaikiki-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lcwaikiki": {
      "command": "uvx",
      "args": ["lcwaikiki-mcp"]
    }
  }
}
```

Giriş gerekmez, API anahtarı gerekmez. Salt okunur: sunucu yalnızca herkese açık sayfaları çeker.

## Yapay zekâ ajanları için

- Arama Türkçedir: Türkçe anahtar kelime kullanın (`elbise`, `dress` değil). Sonuçlarda `exact_match` alanı vardır — site bir şey bulamazsa `exact_match: false` ile genel yedek ürünler döner; sonuçları eşleşme saymadan önce bu alana bakın.
- Fiyatlar canlıdır ve kampanyalarla değişir; `old_price_try` sitenin gösterdiği eski fiyattır, `discount_pct` ondan hesaplanır. Satın almadan önce fiyatı ve stok durumunu lcw.com'da doğrulayın.
- Ürün URL'si her zaman `-o-<id>` ile biter (örn. `...-elbise-haki-o-5657836`) — `lcwaikiki_get_product` bu kimliği ister.
- Kategori id'leri `lcwaikiki_list_categories` aracından alınır (örn. Kadın Giyim `/kadin-giyim-t-10`).
- Her yanıt `fetched_at` (UTC) ve `source` içerir.

## Nasıl çalışır

- Arama listeleri sitenin kendi herkese açık ürün listesi AJAX uç noktasından gelir (`/tr/ajax/ProductList/ProductListPageData`, sayfa başına 100 ürün).
- Kategori listeleri sunucuda oluşturulan kategori sayfasından ayrıştırılır: AJAX uç noktası kategoriler için durumsuz istekte yalnızca genel 52 ürünlük yedek döner; oturumlu istek Akamai'de takılır.
- Detay sayfaları schema.org `Product` JSON-LD bloğundan ve sayfadaki `Option()` çağrısındaki kumaş bilgisinden ayrıştırılır.
- Aktarım Chrome TLS taklidi kullanır (curl-cffi): düz istekler HTTP 403 ile reddedilir (Akamai). İstekler ~0,8 sn arayla yapılır; 403/429'da başka parmak iziyle bir kez yeniden denenir.

## Uyarılar

- LC Waikiki sık kampanya yapar: sabah görülen fiyat aynı gün değişebilir. Sunucu her zaman çekildiği andaki değeri döner.
- Yorum metinleri filtrelenmemiş kullanıcı içeriğidir (Türkçe).
- Kaydedilen sayfalardaki sitenin kendi Firebase web anahtarı, yayımlanmadan önce test verilerinden temizlendi.

## Lisans

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — kişisel ve ticari olmayan kullanım için ücretsizdir; ticari kullanım ayrı lisans gerektirir.

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
