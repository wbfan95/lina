import type { APIRoute } from "astro";
import { getSongSummaries } from "@/lib/content";

export const GET: APIRoute = async () => {
  const songs = await getSongSummaries();
  const payload = songs.map((song) => ({
    id: song.id,
    title: song.title,
    pinyin: song.pinyin,
    aliases: song.aliases,
    year: song.year,
    work: song.work,
  }));

  return new Response(JSON.stringify(payload, null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=0, must-revalidate",
    },
  });
};
