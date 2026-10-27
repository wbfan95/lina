const zhPinyinCollator = new Intl.Collator("zh-Hans-CN-u-co-pinyin", {
  numeric: true,
  sensitivity: "base",
});

export function compareText(a: string, b: string) {
  return zhPinyinCollator.compare(a, b);
}

export function safeSegment(input: string) {
  return input
    .trim()
    .replace(/[\\/#?%<>:"|*]/g, "-")
    .replace(/\s+/g, " ")
    .replace(/\.+$/g, "")
    .replace(/-+/g, "-")
    .trim();
}

export function createUniqueSlug(base: string, used: Set<string>, fallback: string) {
  const normalizedBase = safeSegment(base) || safeSegment(fallback) || "item";
  let candidate = normalizedBase;
  let index = 2;
  while (used.has(candidate)) {
    candidate = `${normalizedBase}-${index}`;
    index += 1;
  }
  used.add(candidate);
  return candidate;
}

export function uniqueStrings(values: Array<string | undefined | null>) {
  return Array.from(
    new Set(
      values
        .map((value) => (typeof value === "string" ? value.trim() : ""))
        .filter(Boolean),
    ),
  );
}

export function compactText(value?: string) {
  return (value ?? "").trim();
}

export function normalizePinyinInitial(value?: string, fallback?: string) {
  const source = compactText(value) || compactText(fallback);
  if (!source) return "#";
  const latinMatch = source.match(/[A-Za-z0-9]/);
  if (!latinMatch) return "#";
  return latinMatch[0].toUpperCase();
}

export function tailInitialFromPinyin(value?: string, fallback?: string) {
  const source = compactText(value) || compactText(fallback);
  if (!source) return "#";
  const tokens = source.match(/[A-Za-z0-9]+/g);
  if (!tokens || tokens.length === 0) return "#";
  const tail = tokens[tokens.length - 1];
  return tail[0]?.toUpperCase() ?? "#";
}

export function formatCreditsLine(
  credits?: {
    lyricists?: string[];
    composers?: string[];
    performers?: string[];
    original_singers?: string[];
  },
) {
  if (!credits) return "";
  const parts: string[] = [];
  if (credits.lyricists?.length) parts.push(`词 ${credits.lyricists.join(" / ")}`);
  if (credits.composers?.length) parts.push(`曲 ${credits.composers.join(" / ")}`);
  if (credits.performers?.length) parts.push(`唱 ${credits.performers.join(" / ")}`);
  if (credits.original_singers?.length) {
    parts.push(`原唱 ${credits.original_singers.join(" / ")}`);
  }
  return parts.join(" · ");
}
