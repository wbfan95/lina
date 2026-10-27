import type { ImageMetadata } from "astro";

const scoreImages = import.meta.glob("/src/content/scores/**/*.{jpg,jpeg,png,webp,avif,gif}", {
  eager: true,
  import: "default",
}) as Record<string, ImageMetadata>;

export function getScoreImage(songId: string, fileName: string) {
  const imagePath = `/src/content/scores/${songId}/${fileName}`;
  return scoreImages[imagePath];
}
