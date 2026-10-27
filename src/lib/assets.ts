const scoreImages = import.meta.glob("/src/content/scores/**/*.{jpg,jpeg,png,webp,avif}", {
  eager: true,
  import: "default",
}) as Record<string, string>;

export function getScoreImageUrl(songId: string, fileName: string) {
  const imagePath = `/src/content/scores/${songId}/${fileName}`;
  return scoreImages[imagePath];
}
