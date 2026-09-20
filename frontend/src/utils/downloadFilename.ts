/** Supports RFC 5987 Unicode filenames and older quoted filename headers. */
export function downloadFilename(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const encoded = header.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  if (encoded) {
    try { return decodeURIComponent(encoded[1].trim()); } catch { /* Try the legacy value. */ }
  }
  const plain = header.match(/filename\s*=\s*(?:"([^"]+)"|([^;]+))/i);
  return plain?.[1] || plain?.[2]?.trim() || fallback;
}
