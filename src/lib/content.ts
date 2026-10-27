import { promises as fs } from "node:fs";
import path from "node:path";
import type {
  PersonProfile,
  PersonSummary,
  Song,
  SongCredits,
  SongSummary,
  TimelineEntry,
  TimelineYear,
  WorkSummary,
} from "@/types/content";
import {
  compareText,
  createUniqueSlug,
  normalizePinyinInitial,
  tailInitialFromPinyin,
  uniqueStrings,
} from "@/lib/utils";

const rootDir = process.cwd();
const songsDir = path.join(rootDir, "src", "content", "songs");
const peopleDir = path.join(rootDir, "src", "content", "people");

async function readJsonFile<T>(filePath: string): Promise<T> {
  const raw = await fs.readFile(filePath, "utf-8");
  return JSON.parse(raw) as T;
}

async function listJsonFiles(dirPath: string) {
  try {
    const names = await fs.readdir(dirPath);
    return names
      .filter((name) => name.endsWith(".json") && name !== "index.json")
      .map((name) => path.join(dirPath, name));
  } catch {
    return [];
  }
}

function normalizeSongCredits(raw: unknown): SongCredits | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const source = raw as Record<string, unknown>;
  const credits: SongCredits = {
    lyricists: Array.isArray(source.lyricists) ? uniqueStrings(source.lyricists as string[]) : undefined,
    composers: Array.isArray(source.composers) ? uniqueStrings(source.composers as string[]) : undefined,
    arrangers: Array.isArray(source.arrangers) ? uniqueStrings(source.arrangers as string[]) : undefined,
    performers: Array.isArray(source.performers) ? uniqueStrings(source.performers as string[]) : undefined,
    original_singers: Array.isArray(source.original_singers)
      ? uniqueStrings(source.original_singers as string[])
      : undefined,
  };
  return Object.values(credits).some((value) => value && value.length) ? credits : undefined;
}

function normalizeSong(raw: Record<string, unknown>): Song {
  const id = typeof raw.id === "string" && raw.id.trim() ? raw.id.trim() : String(raw.title ?? "").trim();
  const title = typeof raw.title === "string" && raw.title.trim() ? raw.title.trim() : id;
  const year = typeof raw.year === "number" ? raw.year : undefined;
  const aliases = Array.isArray(raw.aliases) ? uniqueStrings(raw.aliases as string[]) : [];
  const work =
    raw.work && typeof raw.work === "object"
      ? {
          category: typeof (raw.work as Record<string, unknown>).category === "string"
            ? ((raw.work as Record<string, unknown>).category as string).trim()
            : undefined,
          title: typeof (raw.work as Record<string, unknown>).title === "string"
            ? ((raw.work as Record<string, unknown>).title as string).trim()
            : undefined,
          usage: typeof (raw.work as Record<string, unknown>).usage === "string"
            ? ((raw.work as Record<string, unknown>).usage as string).trim()
            : undefined,
        }
      : undefined;
  const lyrics =
    raw.lyrics && typeof raw.lyrics === "object"
      ? {
          language:
            typeof (raw.lyrics as Record<string, unknown>).language === "string"
              ? ((raw.lyrics as Record<string, unknown>).language as string).trim()
              : undefined,
          text:
            typeof (raw.lyrics as Record<string, unknown>).text === "string"
              ? ((raw.lyrics as Record<string, unknown>).text as string).trim()
              : undefined,
        }
      : undefined;

  return {
    id,
    title,
    pinyin: typeof raw.pinyin === "string" ? raw.pinyin.trim() : undefined,
    aliases,
    year,
    work: work && (work.category || work.title || work.usage) ? work : undefined,
    credits: normalizeSongCredits(raw.credits),
    lyrics: lyrics && (lyrics.language || lyrics.text) ? lyrics : undefined,
    scores: Array.isArray(raw.scores) ? uniqueStrings(raw.scores as string[]) : [],
    videos: Array.isArray(raw.videos) ? uniqueStrings(raw.videos as string[]) : [],
    notes: Array.isArray(raw.notes) ? uniqueStrings(raw.notes as string[]) : [],
  };
}

function toSongSummary(song: Song): SongSummary {
  return {
    id: song.id,
    title: song.title,
    pinyin: song.pinyin ?? song.title,
    aliases: song.aliases,
    year: song.year,
    work: song.work,
    credits: song.credits,
    hasScores: song.scores.length > 0,
    hasVideos: song.videos.length > 0,
    scoreCount: song.scores.length,
    titleHeadInitial: normalizePinyinInitial(song.pinyin, song.title),
    titleTailInitial: tailInitialFromPinyin(song.pinyin, song.title),
  };
}

let songsCache: Promise<Song[]> | undefined;

export async function getAllSongs() {
  if (!songsCache) {
    songsCache = (async () => {
      const files = await listJsonFiles(songsDir);
      const songs = await Promise.all(files.map((file) => readJsonFile<Record<string, unknown>>(file)));
      return songs
        .map(normalizeSong)
        .filter((song) => song.id && song.title)
        .sort((a, b) => compareText(a.title, b.title));
    })();
  }
  return songsCache;
}

export async function getSongSummaries() {
  const songs = await getAllSongs();
  return songs.map(toSongSummary);
}

async function readPeopleProfiles() {
  const files = await listJsonFiles(peopleDir);
  const rawProfiles = await Promise.all(files.map((file) => readJsonFile<Record<string, unknown>>(file)));
  return rawProfiles
    .map((raw) => {
      const name =
        typeof raw.name === "string" && raw.name.trim()
          ? raw.name.trim()
          : typeof raw.id === "string"
            ? raw.id.trim()
            : "";
      if (!name) return null;
      return {
        id: typeof raw.id === "string" && raw.id.trim() ? raw.id.trim() : name,
        name,
        aliases: Array.isArray(raw.aliases) ? uniqueStrings(raw.aliases as string[]) : undefined,
        type: typeof raw.type === "string" ? raw.type.trim() : undefined,
        bio: typeof raw.bio === "string" ? raw.bio.trim() : undefined,
        tags: Array.isArray(raw.tags) ? uniqueStrings(raw.tags as string[]) : undefined,
      } satisfies PersonProfile;
    })
    .filter(Boolean) as PersonProfile[];
}

const roleMap = {
  lyricists: "作词",
  composers: "作曲",
  arrangers: "编曲",
  performers: "演唱",
  original_singers: "原唱",
} as const;

export async function getAllPeople() {
  const [songs, profiles] = await Promise.all([getAllSongs(), readPeopleProfiles()]);
  const profileByName = new Map<string, PersonProfile>();
  profiles.forEach((profile) => {
    profileByName.set(profile.name, profile);
    if (profile.id !== profile.name) profileByName.set(profile.id, profile);
  });

  const peopleMap = new Map<string, PersonSummary>();
  const usedSlugs = new Set<string>();

  function ensurePerson(name: string) {
    const profile = profileByName.get(name);
    const key = profile?.id ?? name;
    if (!peopleMap.has(key)) {
      const id = profile?.id ?? name;
      const displayName = profile?.name ?? name;
      peopleMap.set(key, {
        id,
        name: displayName,
        aliases: profile?.aliases ?? [],
        type: profile?.type,
        bio: profile?.bio,
        tags: profile?.tags ?? [],
        slug: createUniqueSlug(id, usedSlugs, displayName),
        roles: {},
        totalSongs: 0,
      });
    }
    return peopleMap.get(key)!;
  }

  profiles.forEach((profile) => {
    ensurePerson(profile.name);
  });

  songs.forEach((song) => {
    const summary = toSongSummary(song);
    (Object.keys(roleMap) as Array<keyof typeof roleMap>).forEach((roleKey) => {
      const names = song.credits?.[roleKey];
      names?.forEach((name) => {
        const person = ensurePerson(name);
        if (!person.roles[roleMap[roleKey]]) person.roles[roleMap[roleKey]] = [];
        person.roles[roleMap[roleKey]].push(summary);
      });
    });
  });

  return Array.from(peopleMap.values())
    .map((person) => {
      const dedupedRoles = Object.fromEntries(
        Object.entries(person.roles)
          .map(([role, songsForRole]) => [
            role,
            Array.from(new Map(songsForRole.map((song) => [song.id, song])).values()).sort((a, b) =>
              compareText(a.title, b.title),
            ),
          ])
          .filter(([, songsForRole]) => songsForRole.length > 0),
      );
      const totalSongs = Array.from(
        new Set(Object.values(dedupedRoles).flatMap((songsForRole) => songsForRole.map((song) => song.id))),
      ).length;
      return {
        ...person,
        roles: dedupedRoles,
        totalSongs,
      };
    })
    .sort((a, b) => compareText(a.name, b.name));
}

export async function getAllWorks() {
  const songs = await getAllSongs();
  const map = new Map<string, WorkSummary>();
  const usedSlugs = new Set<string>();

  songs.forEach((song) => {
    if (!song.work?.title) return;
    const key = `${song.work.title}::${song.work.category ?? ""}`;
    if (!map.has(key)) {
      map.set(key, {
        id: key,
        slug: createUniqueSlug(song.work.title, usedSlugs, key),
        title: song.work.title,
        category: song.work.category,
        usageSet: [],
        songs: [],
      });
    }
    const work = map.get(key)!;
    if (song.work?.usage && !work.usageSet.includes(song.work.usage)) {
      work.usageSet.push(song.work.usage);
    }
    work.songs.push(toSongSummary(song));
  });

  return Array.from(map.values())
    .map((work) => ({
      ...work,
      usageSet: work.usageSet.sort(compareText),
      songs: work.songs.sort((a, b) => compareText(a.title, b.title)),
    }))
    .sort((a, b) => compareText(a.title, b.title));
}

export async function getYearGroups() {
  const songs = await getSongSummaries();
  const map = new Map<number, SongSummary[]>();
  songs.forEach((song) => {
    if (!song.year) return;
    if (!map.has(song.year)) map.set(song.year, []);
    map.get(song.year)!.push(song);
  });
  return Array.from(map.entries())
    .map(([year, items]) => ({
      year,
      songs: items.sort((a, b) => compareText(a.title, b.title)),
    }))
    .sort((a, b) => a.year - b.year);
}

export async function getTimelineYears(): Promise<TimelineYear[]> {
  const songs = await getAllSongs();
  const timelineMap = new Map<number, TimelineEntry[]>();

  songs.forEach((song) => {
    if (!song.year) return;
    if (!timelineMap.has(song.year)) timelineMap.set(song.year, []);
    timelineMap.get(song.year)!.push({
      year: song.year,
      songTitle: song.title,
      subtitle: song.aliases.length > 0 ? `又名：${song.aliases.join(" / ")}` : undefined,
      aliases: song.aliases,
      lyricists: song.credits?.lyricists ?? [],
      composers: song.credits?.composers ?? [],
      originalSingers: song.credits?.original_singers ?? [],
      duets: [],
      isMedley: song.notes.some((note) => note.includes("串烧")),
      language:
        song.lyrics?.language && song.lyrics.language !== "zh" ? song.lyrics.language : undefined,
      notes: song.notes,
      media: song.work
        ? {
            category: song.work.category,
            title: song.work.title,
            usage: song.work.usage,
          }
        : undefined,
      matchedSongId: song.id,
    });
  });

  return Array.from(timelineMap.entries())
    .map(([year, entries]) => ({
      year,
      entries: entries.sort((a, b) => compareText(a.songTitle, b.songTitle)),
    }))
    .sort((a, b) => a.year - b.year);
}

export async function getSiteStats() {
  const [songs, people, works, years] = await Promise.all([
    getAllSongs(),
    getAllPeople(),
    getAllWorks(),
    getYearGroups(),
  ]);
  return {
    songs: songs.length,
    people: people.length,
    works: works.length,
    years: years.length,
  };
}
