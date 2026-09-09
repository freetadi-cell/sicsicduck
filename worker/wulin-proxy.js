/**
 * Wulin Cloudflare Worker — GitHub API Proxy
 *
 * 前端打呢個 Worker，Worker 再轉發去 GitHub API。
 * 個 GitHub PAT token 擺喺 Worker 嘅 Environment Variables (Secrets) 度，
 * 前端完全唔會見到 token。
 *
 * Env vars (set via `wrangler secret put`):
 *   GITHUB_PAT  — GitHub Personal Access Token
 *
 * 支援：
 *   GET  /api/players             → 讀取 players.json
 *   PUT  /api/players             → 更新 players.json（body: JSON）
 *   GET  /api/world               → 讀取 wulin_world.json
 *   PUT  /api/world               → 更新 wulin_world.json（body: JSON）
 *   OPTIONS                      → CORS preflight
 */

const GH_OWNER = "freetadi-cell";
const GH_REPO  = "sicsicduck";
const FILES = {
  players: "data/players.json",
  world:   "data/wulin_world.json",
};

const CORS = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age":       "86400",
};

function jsonResp(body, status = 200, extraHeaders = {}) {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS, ...extraHeaders },
  });
}

async function ghGet(pat, fileKey) {
  const filePath = FILES[fileKey];
  const r = await fetch(
    `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/contents/${filePath}`,
    {
      headers: {
        Authorization: `Bearer ${pat}`,
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "wulin-worker",
      },
    }
  );
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`GitHub GET ${r.status}: ${text}`);
  }
  return r.json(); // { content, sha, ... }
}

async function ghPut(pat, fileKey, content, sha, commitMsg) {
  const filePath = FILES[fileKey];
  const body = {
    message: commitMsg || `Wulin: update ${filePath}`,
    content: btoa(unescape(encodeURIComponent(content))),
    sha,
    branch: "master",
  };
  const r = await fetch(
    `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/contents/${filePath}`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${pat}`,
        "Content-Type": "application/json",
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "wulin-worker",
      },
      body: JSON.stringify(body),
    }
  );
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`GitHub PUT ${r.status}: ${text}`);
  }
  return r.json();
}

export default {
  async fetch(request, env) {
    const pat = env.GITHUB_PAT;
    if (!pat) return jsonResp({ error: "Worker not configured" }, 500);

    const url = new URL(request.url);
    const method = request.method;
    const path = url.pathname;

    // CORS preflight
    if (method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    // GET /api/players — 讀取
    if (method === "GET" && path === "/api/players") {
      try {
        const data = await ghGet(pat, "players");
        const accounts = JSON.parse(
          decodeURIComponent(escape(atob(data.content)))
        );
        return jsonResp({ accounts, sha: data.sha });
      } catch (e) {
        return jsonResp({ error: e.message }, 502);
      }
    }

    // PUT /api/players — 更新
    if (method === "PUT" && path === "/api/players") {
      try {
        const { accounts, sha } = await request.json();
        if (!accounts || !sha) {
          return jsonResp({ error: "Missing accounts or sha" }, 400);
        }
        const content = JSON.stringify(accounts, null, 2);
        await ghPut(pat, "players", content, sha, "Wulin: update player data");
        return jsonResp({ ok: true });
      } catch (e) {
        return jsonResp({ error: e.message }, 502);
      }
    }

    // GET /api/world — 讀取 wulin_world.json
    if (method === "GET" && path === "/api/world") {
      try {
        const data = await ghGet(pat, "world");
        const world = JSON.parse(
          decodeURIComponent(escape(atob(data.content)))
        );
        return jsonResp({ world, sha: data.sha });
      } catch (e) {
        return jsonResp({ error: e.message }, 502);
      }
    }

    // PUT /api/world — 更新 wulin_world.json
    if (method === "PUT" && path === "/api/world") {
      try {
        const { world, sha, message } = await request.json();
        if (!world || !sha) {
          return jsonResp({ error: "Missing world or sha" }, 400);
        }
        const content = JSON.stringify(world, null, 2);
        await ghPut(pat, "world", content, sha, message || "Wulin: update world data");
        return jsonResp({ ok: true });
      } catch (e) {
        return jsonResp({ error: e.message }, 502);
      }
    }

    return jsonResp({ error: "Not found" }, 404);
  },
};
