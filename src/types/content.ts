export interface SongWork {
  category?: string;
  title?: string;
  usage?: string;
}

export interface SongCredits {
  lyricists?: string[];
  composers?: string[];
  arrangers?: string[];
  performers?: string[];
  original_singers?: string[];
}

export interface SongLyrics {
  language?: string;
  text?: string;
}

export interface Song {
  id: string;
  title: string;
  pinyin?: string;
  aliases: string[];
  year?: number;
  work?: SongWork;
  credits?: SongCredits;
  lyrics?: SongLyrics;
  scores: string[];
  videos: string[];
  notes: string[];
}

export interface SongSummary {
  id: string;
  title: string;
  pinyin: string;
  aliases: string[];
  year?: number;
  work?: SongWork;
  credits?: SongCredits;
  hasScores: boolean;
  hasVideos: boolean;
  scoreCount: number;
  titleHeadInitial: string;
  titleTailInitial: string;
}

export interface PersonProfile {
  id: string;
  name: string;
  aliases?: string[];
  type?: string;
  bio?: string;
  tags?: string[];
}

export interface PersonSummary extends PersonProfile {
  slug: string;
  roles: Record<string, SongSummary[]>;
  totalSongs: number;
}

export interface WorkSummary {
  id: string;
  slug: string;
  title: string;
  category?: string;
  usageSet: string[];
  songs: SongSummary[];
}

export interface TimelineEntry {
  year: number;
  songTitle: string;
  subtitle?: string;
  aliases: string[];
  lyricists: string[];
  composers: string[];
  originalSingers: string[];
  duets: string[];
  isMedley: boolean;
  language?: string;
  notes: string[];
  media?:
    | {
        category?: string;
        title?: string;
        usage?: string;
        productionYear?: number;
      }
    | undefined;
  matchedSongId?: string;
}

export interface TimelineYear {
  year: number;
  entries: TimelineEntry[];
}
