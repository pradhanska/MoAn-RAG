/**
 * CineAI — Cloudflare Pages Function (serverless, zero build step).
 *
 * POST /api/ask  { "question": "...", "mode": "auto" }
 *   -> grounded answer JSON (Jikan / TVMaze keyless; TMDB / OMDb opt-in via env)
 *
 * This is the JS twin of the Python `moan/` pipeline used by the Streamlit app,
 * so the demo page and the CLI/UI share the same retrieval -> context -> answer flow.
 * The demo answers with the built-in grounded template engine (no LLM key needed);
 * the Streamlit app additionally supports any OpenAI-compatible LLM on top.
 */

const JIKAN = "https://api.jikan.moe/v4";
const TVMAZE = "https://api.tvmaze.com";
const TIMEOUT = 12_000;

// ------------------------------------------------------------------ helpers
async function getJSON(url, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const target = qs ? `${url}?${qs}` : url;
  for (let attempt = 0; attempt < 2; attempt++) {   // one retry for transient 504/429
    try {
      const res = await fetch(target, { signal: AbortSignal.timeout(TIMEOUT) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      if (attempt === 0) await new Promise((r) => setTimeout(r, 800));
    }
  }
  return null;
}

const num = (v) => (v === null || v === undefined || isNaN(Number(v)) ? null : Number(v));

// ------------------------------------------------------------------ parsing
const ANIME_HINTS = ["anime", "manga", "manhwa", "waifu", "otaku", "sensei", "sakura"];
const TV_HINTS = ["tv show", "series", "television", "tv", "sitcom"];
const MOVIE_HINTS = ["movie", "film", "cinema", "directed", "director", "actor", "actress", "flick"];

const LEADERS = [
  /^tell\s+me\s+(?:about|everything\s+about|what\s+you\s+know\s+about)\s+/i,
  /^what\s+(?:is|are|was|were)\s+/i,
  /^who\s+(?:is|was|directed|directed\s+the)\s+/i,
  /^when\s+(?:is|was|did)\s+/i,
  /^where\s+(?:is|was)\s+/i,
  /^which\s+\s+/i,
  /^how\s+(?:many|much|long|good)\s+/i,
  /^do\s+you\s+know\s+/i,
  /^can\s+you\s+\s+/i,
  /^is\s+there\s+/i,
  /^are\s+there\s+/i,
  /^recommend\s+(?:me\s+)?\s+/i,
];

const CRUFT = new Set([
  "have", "has", "had", "about", "released", "release", "episodes", "episode count",
  "rating", "score", "rank", "like", "similar", "me", "in", "on", "at", "of", "with", "and",
  "the", "movie", "film",
]);

function detectMedia(question) {
  const q = question.toLowerCase();
  if (ANIME_HINTS.some((h) => q.includes(h))) return "anime";
  if (TV_HINTS.some((h) => q.includes(h))) return "tv";
  if (MOVIE_HINTS.some((h) => q.includes(h))) return "movie";
  return "auto";
}

function cleanTitle(raw) {
  let s = raw.replace(/\?/g, "").trim();
  for (const re of LEADERS) {
    const hit = s.match(re);
    if (hit) { s = s.slice(hit[0].length).trim(); break; }
  }
  s = s.replace(/^the\s+/i, "").trim();
  const media = s.match(/^(movie|film|anime|manga|tv show|tv series|tv|show|series|cinema)\s+(.+)$/i);
  if (media) s = media[2].replace(/^the\s+/i, "").trim();
  let lower = s.toLowerCase();
  let changed = true;
  while (changed && lower) {
    changed = false;
    for (const w of CRUFT) {
      if (lower.endsWith(` ${w}`)) {
        s = s.slice(0, -(w.length + 1)).trim();
        lower = s.toLowerCase();
        changed = true;
        break;
      }
    }
  }
  return s.trim();
}

const PATTERNS = [
  /["“”″]([^"“”″]+)["“”″]/,
  /\bwho\s+directed\s+(.+?)\s*\??$/i,
  /\bdirected\s+by\s+(.+?)\s*\??$/i,
  /\bhow\s+many\s+(?:episodes|seasons)\s+(?:does\s+|did\s+)?(.+?)\s*(?:have|has|had)?\s*\??$/i,
  /\b(?:when|what\s+year)\s+(?:was|is)\s+(.+?)\s*(?:released|made)?\s*\??$/i,
  /\brelease\s+year\s+of\s+(.+)/i,
  /\bif\s+(?:i|you)\s+liked\s+(.+)/i,
  /\bsimilar\s+to\s+(.+)/i,
  /\brecommend\s+(?:me\s+)?(?:an\s+|a\s+)?(?:anime|manga|movie|film|tv\s*show|series|show)\s+like\s+(.+)/i,
  /\brecommend\s+(?:me\s+)?(?:an\s+|a\s+)?(.+)/i,
  /\bwhat\s+is\s+(.+?)\s+(?:about|based\s+on)\s*\??$/i,
];

function parse(question) {
  const raw = (question || "").trim();
  const media = detectMedia(raw);
  const intent = /recommend|similar|if\s+(?:i|you)\s+liked/i.test(raw) ? "recommend" : "fact";
  let title = null;
  for (const re of PATTERNS) {
    const m = raw.match(re);
    if (m && m[1] && m[1].trim()) { title = m[1].trim().replace(/\s*\?$/, ""); break; }
  }
  if (!title) title = cleanTitle(raw);
  return { media, title: title || null, intent, raw };
}

// ------------------------------------------------------------------ providers
async function jikanSearch(title, wantDirector, intent) {
  const data = await getJSON(`${JIKAN}/anime`, { q: title, limit: 3, order_by: "popularity", sort: "asc" });
  const items = (data && data.data) || [];
  const out = [];
  for (const it of items.slice(0, 3)) {
    out.push({
      provider: "jikan", kind: "anime",
      title: it.title || it.title_english || "",
      year: it.aired && it.aired.prop && it.aired.prop.from && it.aired.prop.from.year,
      url: it.url || "", mal_id: it.mal_id,
      score: num(it.score), episodes: it.episodes, status: it.status,
      genres: (it.genres || []).map((g) => g.name),
      overview: it.synopsis || null, director: null, cast: [], reason: null,
    });
  }
  const top = out[0];
  if (!top) return [];
  if (wantDirector && top.mal_id) {
    const full = await getJSON(`${JIKAN}/anime/${top.mal_id}/full`);
    const staff = full && full.data && full.data.staff ? full.data.staff : [];
    const dir = staff.find((p) => (p.positions || []).some((pos) => pos.position === "Director"));
    top.director = dir && dir.person ? dir.person.name : null;
  }
  if (intent === "recommend" && top.mal_id) {
    const rec = await getJSON(`${JIKAN}/anime/${top.mal_id}/recommendations`);
    for (const item of (rec && rec.data || []).slice(0, 4)) {
      const e = item.entry || {};
      out.push({
        provider: "jikan", kind: "anime", title: e.title || "",
        year: null, url: e.url || "", mal_id: e.mal_id,
        score: null, episodes: null, status: null, genres: [],
        overview: null, director: null, cast: [], reason: item.reason || null,
      });
    }
  }
  return out;
}

async function tvmazeSearch(title, wantEpisodes) {
  const data = await getJSON(`${TVMAZE}/singlesearch/shows`, { q: title });
  if (!data || typeof data !== "object") return [];
  let episodes = null, seasons = null;
  if (wantEpisodes && data.id) {
    const eps = await getJSON(`${TVMAZE}/shows/${data.id}/episodes`);
    if (Array.isArray(eps)) {
      episodes = eps.length;
      seasons = new Set(eps.map((e) => e.season).filter(Boolean)).size;
    }
  }
  return [{
    provider: "tvmaze", kind: "tv", title: data.name || "",
    year: data.premiered ? String(data.premiered).slice(0, 4) : null,
    url: data.url || "", mal_id: null,
    score: num(data.rating && data.rating.average), episodes, seasons, status: data.status || null,
    genres: Array.isArray(data.genres) ? data.genres : [],
    overview: data.summary ? data.summary.replace(/<[^>]+>/g, "").trim() : null,
    director: null, cast: [], reason: null,
  }];
}

async function tmdbSearch(title, env) {
  const key = (env && env.TMDB_API_KEY || "").trim();
  if (!key) return [];
  const data = await getJSON("https://api.themoviedb.org/3/search/multi", { api_key: key, query: title, adult: "false" });
  const out = [];
  for (const it of ((data && data.results) || []).slice(0, 3)) {
    const media = it.media_type === "movie" ? "movie" : "tv";
    out.push({
      provider: "tmdb", kind: media,
      title: it.title || it.name || "",
      year: String(it.release_date || it.first_air_date || "").slice(0, 4) || null,
      url: `https://www.themoviedb.org/${media}/${it.id}`, mal_id: null,
      score: num(it.vote_average), episodes: null, seasons: null, status: null,
      genres: [], overview: it.overview || null, director: null, cast: [], reason: null,
    });
  }
  return out;
}

async function omdbSearch(title, env) {
  const key = (env && env.OMDB_API_KEY || "").trim();
  if (!key) return [];
  const data = await getJSON("https://www.omdbapi.com/", { apikey: key, t: title, plot: "short" });
  if (!data || data.Response !== "True") return [];
  const kind = data.Type === "movie" ? "movie" : "tv";
  return [{
    provider: "omdb", kind,
    title: data.Title || "", year: data.Year || null,
    url: `https://www.imdb.com/title/${data.imdbID || ""}/`, mal_id: null,
    score: num(data.imdbRating), episodes: num(data.totalSeasons), seasons: null,
    status: null,
    genres: String(data.Genre || "").split(",").map((g) => g.trim()).filter(Boolean),
    overview: data.Plot || null, director: data.Director || null,
    cast: String(data.Actors || "").split(",").map((a) => a.trim()).filter(Boolean).slice(0, 4),
    reason: null,
  }];
}

function searchOrder(media, wantEpisodes) {
  const tv = "tvmaze", ji = "jikan";
  if (media === "anime") return [ji, tv, "tmdb"];
  if (media === "tv") return [tv, "tmdb", ji];
  if (media === "movie") return ["tmdb", "omdb", ji, tv];
  return [tv, ji, "tmdb", "omdb"];
}

// ------------------------------------------------------------------ context / answer
function buildContext(records) {
  return records
    .map((r, i) => {
      const lines = [`- title: ${r.title || "unknown"} (${r.kind})`];
      if (r.year) lines.push(`- year: ${r.year}`);
      if (r.score !== null) lines.push(`- score: ${r.score.toFixed(1)}/10`);
      if (r.episodes !== null) lines.push(`- episodes: ${r.episodes}`);
      if (r.seasons !== null) lines.push(`- seasons: ${r.seasons}`);
      if (r.status) lines.push(`- status: ${r.status}`);
      if (r.genres && r.genres.length) lines.push(`- genres: ${r.genres.join(", ")}`);
      if (r.director) lines.push(`- director: ${r.director}`);
      if (r.cast && r.cast.length) lines.push(`- cast: ${r.cast.slice(0, 4).join(", ")}`);
      if (r.reason) lines.push(`- why: ${r.reason}`);
      if (r.overview) {
        let ov = r.overview;
        if (ov.length > 420) ov = ov.slice(0, 420).replace(/\s+\S*$/, "") + "…";
        lines.push(`- synopsis: ${ov}`);
      }
      if (r.url) lines.push(`- source: ${r.url}`);
      return `[${i + 1}] ${r.title || "unknown"}\n${lines.join("\n")}`;
    })
    .join("\n\n");
}

function collectSources(records) {
  const seen = new Set();
  return records
    .filter((r) => r.url && !seen.has(`${r.provider}|${r.title}`) && (seen.add(`${r.provider}|${r.title}`), true))
    .map((r) => ({ provider: r.provider, title: r.title, url: r.url }));
}

function truncate(s, n) {
  return s.length > n ? `${s.slice(0, n).replace(/\s+\S*$/, "")}…` : s;
}

function templateAnswer(records, question, intent) {
  if (!records.length) return "I couldn't find a match for that title in the movie/anime databases.";
  const top = records[0];
  const name = top.title || "that title";
  const kind = top.kind || "title";
  const q = question.toLowerCase();

  if (intent === "recommend") {
    const recs = records.slice(1).filter((r) => r.title);
    if (recs.length) {
      const bits = recs.slice(0, 4).map((r) => {
        let bit = `"${r.title}"`;
        if (r.reason) bit += ` — ${truncate(r.reason.trim(), 110)}`;
        return bit;
      });
      const via = "MyAnimeList";
      return `If you liked ${name}, you might enjoy: ${bits.join("; ")}. Each pick is a verified ${via} recommendation — tap the sources for details.`;
    }
    return `I found ${name} but no verified recommendations were available for it.`;
  }

  const sentences = [];
  if (/directed|director/.test(q)) {
    sentences.push(top.director
      ? `${name} was directed by ${top.director} (${kind}, ${top.year || "year unknown"}).`
      : `I found ${name} but the database does not list a director for it.`);
  } else if (/episodes|season/.test(q)) {
    if (/seasons/.test(q) && top.seasons !== null) {
      sentences.push(`${name} has ${top.seasons} seasons (${kind}, ${top.year || "year unknown"}).`);
    } else if (top.episodes !== null) {
      sentences.push(`${name} has ${top.episodes} episodes (${kind}, ${top.year || "year unknown"}).`);
    } else {
      sentences.push(`${name} (${kind}) — I couldn't confirm an episode/season count from the source data.`);
    }
  } else if (/year|released|when/.test(q)) {
    sentences.push(`${name} was released in ${top.year || "an unknown year"} (${kind}).`);
  } else if (/rating|score|good|rank/.test(q)) {
    sentences.push(top.score !== null
      ? `${name} has a rating of ${top.score.toFixed(1)}/10 (${kind}, ${top.year || "year unknown"}).`
      : `No rating was available for ${name} in the source data.`);
  } else {
    let intro = `${name} is a ${kind}`;
    if (top.year) intro += ` from ${top.year}`;
    if (top.genres && top.genres.length) intro += ` in the ${top.genres.slice(0, 3).join(", ")} vein`;
    intro += ".";
    sentences.push(intro);
  }

  if (records.length > 1 && !sentences.some((s) => s.includes("couldn't") || s.includes("could not"))) {
    const alt = records.slice(1, 3).filter((r) => r.title).map((r) => `"${r.title}"`).join(", ");
    if (alt) sentences.push(`Other close matches: ${alt}.`);
  }
  if (top.overview) sentences.push(`Quick synopsis: ${truncate(top.overview, 300)}`);
  return sentences.join(" ");
}

// ------------------------------------------------------------------ handler
const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" },
});

async function ask(question, mode, env) {
  const query = parse(question);
  const wantEpisodes = /episodes|seasons/.test(query.raw);
  const wantDirector = /director/.test(query.raw);
  const order = searchOrder(query.media, wantEpisodes);
  const records = [];
  const warnings = [];

  if (!query.title) {
    return { question, answer: "I couldn't work out which title you meant — try quoting it, e.g. \"Spirited Away\".", provider: "local_template", model: null, sources: [], context: "", warnings: [], query };
  }

  const providers = {
    jikan: () => jikanSearch(query.title, wantDirector, query.intent),
    tvmaze: () => tvmazeSearch(query.title, wantEpisodes),
    tmdb: () => tmdbSearch(query.title, env),
    omdb: () => omdbSearch(query.title, env),
  };

  let chosen = null;
  for (const label of order) {
    if ((label === "tmdb" || label === "omdb") && !((env && env[`${label.toUpperCase()}_API_KEY`]) || "").trim()) continue;
    let batch = [];
    try { batch = await providers[label](); } catch { batch = []; }
    if (batch.length) { chosen = batch; break; }
  }
  if (chosen) {
    // jikanSearch embeds MyAnimeList recommendations when intent is "recommend";
    // every other provider answers with the grounded fact template as-is.
    records.push(...chosen);
  }

  if (!records.length) {
    let msg = `I couldn't find "${query.title}" in the movie/anime databases. Double-check the spelling — or add TMDB/OMDb keys for fuller movie/TV coverage.`;
    if (query.media === "movie" && !(env && (env.TMDB_API_KEY || env.OMDB_API_KEY))) {
      warnings.push("Heads-up: no TMDB/OMDb keys are set, so film coverage is limited right now. Add them to the Pages project settings and movies (directors, cast, ratings) unlock.");
    }
    return { question, answer: msg, provider: "local_template", model: null, sources: [], context: "", warnings, query };
  }

  const context = buildContext(records);
  const sources = collectSources(records);
  const answer = templateAnswer(records, question, query.intent);
  return { question, answer, provider: "local_template", model: null, sources, context, warnings, query };
}

export async function onRequestPost(context) {
  try {
    const body = await context.request.json().catch(() => ({}));
    const question = String(body.question || "").trim();
    const mode = String(body.mode || "auto");
    if (!question) return json({ error: "missing question" }, 400);
    return json(await ask(question, mode, context.env));
  } catch (err) {
    return json({ error: String(err && err.message || err) }, 500);
  }
}