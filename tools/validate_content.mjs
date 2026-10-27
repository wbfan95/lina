#!/usr/bin/env node
/**
 * 内容一致性校验：在构建前运行，任何"歌曲声明了不存在的曲谱"或
 * "曲谱目录没有对应歌曲"都视为错误，避免页面静默丢失内容。
 *
 * 用法：node tools/validate_content.mjs
 */
import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const songsDir = path.join(root, "src", "content", "songs");
const scoresDir = path.join(root, "src", "content", "scores");
const peopleDir = path.join(root, "src", "content", "people");

const errors = [];
const warnings = [];
const err = (msg) => errors.push(msg);
const warn = (msg) => warnings.push(msg);

// ---------- 歌曲 ----------
const songFiles = readdirSync(songsDir).filter(
  (name) => name.endsWith(".json") && name !== "index.json",
);

/** @type {Map<string, object>} */
const songsById = new Map();

for (const fileName of songFiles) {
  const filePath = path.join(songsDir, fileName);
  const baseName = path.basename(fileName, ".json");
  let song;
  try {
    song = JSON.parse(readFileSync(filePath, "utf-8"));
  } catch (e) {
    err(`[songs/${fileName}] JSON 解析失败：${e.message}`);
    continue;
  }

  const id = typeof song.id === "string" ? song.id.trim() : "";
  const title = typeof song.title === "string" ? song.title.trim() : "";
  if (!id || !title) {
    err(`[songs/${fileName}] 缺少 id 或 title`);
    continue;
  }
  if (songsById.has(id)) {
    err(`[songs/${fileName}] id「${id}」与 ${songsById.get(id).__file} 重复`);
    continue;
  }
  song.__file = fileName;
  songsById.set(id, song);

  if (id !== baseName) {
    warn(`[songs/${fileName}] id「${id}」与文件名不一致`);
  }
  if (!song.pinyin || !String(song.pinyin).trim()) {
    warn(`[songs/${fileName}]「${title}」缺少 pinyin（影响拼音排序与首字筛选）`);
  }
  if (
    song.year !== undefined &&
    !(Number.isInteger(song.year) && song.year >= 1900 && song.year <= 2100)
  ) {
    err(`[songs/${fileName}] year「${song.year}」不是合理年份`);
  }
  if (song.lyrics && typeof song.lyrics.text === "string" && !song.lyrics.text.trim()) {
    err(`[songs/${fileName}]「${title}」lyrics.text 为空`);
  }
  if (song.videos !== undefined) {
    for (const video of song.videos ?? []) {
      if (!/^https?:\/\//.test(String(video))) {
        err(`[songs/${fileName}] 视频链接不是 http(s) 地址：${video}`);
      }
    }
  }
  for (const scoreFile of song.scores ?? []) {
    const imagePath = path.join(scoresDir, id, String(scoreFile));
    if (!existsSync(imagePath)) {
      err(`[songs/${fileName}]「${title}」声明的曲谱不存在：scores/${id}/${scoreFile}`);
    }
  }
}

// ---------- 曲谱目录 ----------
for (const entry of readdirSync(scoresDir)) {
  const dirPath = path.join(scoresDir, entry);
  if (!statSync(dirPath).isDirectory()) {
    err(`[scores] 目录下存在散落文件：${entry}`);
    continue;
  }
  if (!songsById.has(entry)) {
    err(`[scores/${entry}] 没有对应 id 的歌曲（孤儿曲谱目录）`);
  }
  for (const sub of readdirSync(dirPath)) {
    if (statSync(path.join(dirPath, sub)).isDirectory()) {
      warn(`[scores/${entry}] 出现嵌套子目录：${sub}`);
    }
  }
}

// ---------- 人物 ----------
for (const fileName of readdirSync(peopleDir).filter((name) => name.endsWith(".json"))) {
  try {
    const person = JSON.parse(readFileSync(path.join(peopleDir, fileName), "utf-8"));
    if (!String(person.name ?? person.id ?? "").trim()) {
      err(`[people/${fileName}] 缺少 name`);
    }
  } catch (e) {
    err(`[people/${fileName}] JSON 解析失败：${e.message}`);
  }
}

// ---------- 汇总 ----------
const songCount = songsById.size;
const scoreDirCount = readdirSync(scoresDir).length;
console.log(`歌曲 ${songCount} 首 · 曲谱目录 ${scoreDirCount} 个`);

for (const message of warnings) console.warn(`  ⚠ ${message}`);
for (const message of errors) console.error(`  ✗ ${message}`);

if (errors.length > 0) {
  console.error(`校验未通过：${errors.length} 个错误，${warnings.length} 个警告`);
  process.exit(1);
}
console.log(`校验通过${warnings.length ? `（${warnings.length} 个警告）` : ""}`);
