#!/usr/bin/env python3
import os

from flask import Flask, jsonify, request, render_template_string

import sync
import youtube_client as yt
from airsonic_client import AirsonicError
from db import get_conn

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/users")
def api_users():
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT u.id, u.channel_title, u.handle,
               (SELECT COUNT(*) FROM playlists p WHERE p.user_id = u.id) AS playlist_count
        FROM users u ORDER BY u.channel_title COLLATE NOCASE
        """
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/users", methods=["POST"])
def api_add_user():
    value = (request.get_json(silent=True) or {}).get("value", "").strip()
    if not value:
        return jsonify({"error": "falta el canal"}), 400
    try:
        user_id = sync.add_user(value)
    except (yt.YouTubeError, Exception) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"user_id": user_id})


@app.route("/api/users/<int:user_id>/playlists")
def api_user_playlists(user_id):
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT p.id, p.title, p.item_count, p.last_synced_at,
               (SELECT COUNT(*) FROM tracks t WHERE t.playlist_id = p.id) AS tracks_synced,
               (SELECT COUNT(*) FROM tracks t WHERE t.playlist_id = p.id AND t.owned = 1) AS owned_count
        FROM playlists p WHERE p.user_id = ? ORDER BY p.title COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/playlists", methods=["POST"])
def api_add_playlist():
    value = (request.get_json(silent=True) or {}).get("value", "").strip()
    if not value:
        return jsonify({"error": "falta la playlist"}), 400
    try:
        playlist_id = sync.add_playlist(value)
    except (yt.YouTubeError, Exception) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"playlist_id": playlist_id})


@app.route("/api/playlists/<int:playlist_id>/tracks")
def api_playlist_tracks(playlist_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT video_id, position, raw_title, parsed_artist, parsed_title, owned, owned_source "
        "FROM tracks WHERE playlist_id = ? ORDER BY position",
        (playlist_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/playlists/<int:playlist_id>/sync", methods=["POST"])
def api_sync_playlist(playlist_id):
    try:
        sync.sync_playlist(playlist_id)
    except (yt.YouTubeError, AirsonicError, Exception) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


HTML_PAGE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YT Playlists</title>
<style>
:root {
    --bg: #0a0e27; --surface: #16213e; --surface-2: #1f2d4a; --border: #2d3e5f;
    --text: #b0b8c9; --text-muted: #7a8694; --accent: #35bf88; --accent-2: #8e44ad;
    --warning: #f39c12; --danger: #e74c3c;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: var(--bg); color: var(--text); padding: 20px; }
h1 { color: #fff; margin-bottom: 16px; font-size: 20px; }
.add-forms { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
.add-form { display: flex; gap: 6px; background: var(--surface); padding: 10px; border-radius: 8px; border: 1px solid var(--border); flex: 1; min-width: 280px; }
.add-form input { flex: 1; padding: 6px 8px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; }
.add-form input:focus { outline: none; border-color: var(--accent); }
.add-form label { font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px; }
button { background: var(--accent); color: var(--bg); border: none; padding: 7px 14px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 13px; white-space: nowrap; }
button.secondary { background: var(--surface-2); color: var(--text); }
button:disabled { opacity: 0.5; cursor: default; }
.error { color: var(--danger); font-size: 12px; margin-top: 4px; }
.user-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 10px; overflow: hidden; }
.user-header { display: flex; align-items: center; gap: 10px; padding: 12px 14px; cursor: pointer; }
.user-header:hover { background: var(--surface-2); }
.user-title { font-weight: bold; color: #fff; font-size: 14px; }
.user-meta { color: var(--text-muted); font-size: 12px; margin-left: auto; }
.playlists { display: none; padding: 0 14px 12px; }
.playlists.open { display: block; }
.playlist-row { background: var(--surface-2); border-radius: 8px; margin-top: 8px; overflow: hidden; }
.playlist-header { display: flex; align-items: center; gap: 10px; padding: 10px 12px; cursor: pointer; }
.playlist-title { font-size: 13px; color: var(--text); }
.playlist-meta { color: var(--text-muted); font-size: 11px; margin-left: auto; }
.owned-badge { font-size: 11px; padding: 1px 7px; border-radius: 4px; background: var(--surface); }
.owned-badge.has-data { color: var(--accent); }
.tracks { display: none; padding: 0 12px 10px; }
.tracks.open { display: block; }
table { width: 100%; border-collapse: collapse; margin-top: 4px; }
th, td { padding: 6px 8px; text-align: left; font-size: 12px; border-bottom: 1px solid var(--border); }
th { color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 10px; }
.mark { display: inline-block; width: 18px; text-align: center; }
.mark.yes { color: var(--accent); }
.mark.no { color: var(--text-muted); }
.raw-title { color: var(--text-muted); font-size: 11px; }
a.video-link { color: var(--text); text-decoration: none; }
a.video-link:hover { text-decoration: underline; }
.empty { color: var(--text-muted); font-size: 12px; padding: 10px 0; }
</style>
</head>
<body>
<h1>YT Playlists — REPEAT-ONE</h1>
<div class="add-forms">
    <div class="add-form">
        <div style="flex:1">
            <label>Añadir usuario (@handle, URL de canal o ID)</label>
            <input type="text" id="new_user" placeholder="@handle">
        </div>
        <button onclick="addUser()" style="align-self:flex-end">+ Usuario</button>
    </div>
    <div class="add-form">
        <div style="flex:1">
            <label>Añadir playlist suelta (URL o ID)</label>
            <input type="text" id="new_playlist" placeholder="https://youtube.com/playlist?list=...">
        </div>
        <button onclick="addPlaylist()" style="align-self:flex-end">+ Playlist</button>
    </div>
</div>
<div id="add-error" class="error"></div>
<div id="users"></div>

<script>
function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

async function loadUsers() {
    const r = await fetch('/api/users');
    const users = await r.json();
    const container = document.getElementById('users');
    if (!users.length) {
        container.innerHTML = '<div class="empty">Todavía no sigues a ningún usuario. Añade uno arriba.</div>';
        return;
    }
    container.innerHTML = users.map(u => `
        <div class="user-card" data-user-id="${u.id}">
            <div class="user-header" onclick="toggleUser(${u.id})">
                <span class="user-title">${escapeHtml(u.channel_title)}</span>
                <span class="user-meta">${u.handle ? escapeHtml(u.handle) + ' · ' : ''}${u.playlist_count} playlist${u.playlist_count === 1 ? '' : 's'}</span>
            </div>
            <div class="playlists" id="playlists-${u.id}"></div>
        </div>
    `).join('');
}

async function toggleUser(userId) {
    const el = document.getElementById('playlists-' + userId);
    const opening = !el.classList.contains('open');
    el.classList.toggle('open');
    if (opening && !el.dataset.loaded) {
        el.dataset.loaded = '1';
        await loadPlaylists(userId);
    }
}

async function loadPlaylists(userId) {
    const el = document.getElementById('playlists-' + userId);
    const r = await fetch(`/api/users/${userId}/playlists`);
    const playlists = await r.json();
    if (!playlists.length) {
        el.innerHTML = '<div class="empty">Sin playlists públicas.</div>';
        return;
    }
    el.innerHTML = playlists.map(p => `
        <div class="playlist-row" data-playlist-id="${p.id}">
            <div class="playlist-header" onclick="togglePlaylist(${p.id})">
                <span class="playlist-title">${escapeHtml(p.title)}</span>
                <span class="owned-badge ${p.tracks_synced ? 'has-data' : ''}">${p.tracks_synced ? p.owned_count + '/' + p.tracks_synced + ' ya tienes' : (p.item_count || 0) + ' canciones · sin sincronizar'}</span>
                <button class="secondary" onclick="event.stopPropagation(); syncPlaylist(${p.id}, ${userId})">Sincronizar</button>
            </div>
            <div class="tracks" id="tracks-${p.id}"></div>
        </div>
    `).join('');
}

async function togglePlaylist(playlistId) {
    const el = document.getElementById('tracks-' + playlistId);
    const opening = !el.classList.contains('open');
    el.classList.toggle('open');
    if (opening) {
        await loadTracks(playlistId);
    }
}

async function loadTracks(playlistId) {
    const el = document.getElementById('tracks-' + playlistId);
    const r = await fetch(`/api/playlists/${playlistId}/tracks`);
    const tracks = await r.json();
    if (!tracks.length) {
        el.innerHTML = '<div class="empty">Todavía no sincronizada — pulsa "Sincronizar".</div>';
        return;
    }
    el.innerHTML = `
        <table>
            <thead><tr><th></th><th>Artista</th><th>Canción</th><th>Título original</th></tr></thead>
            <tbody>
                ${tracks.map(t => `
                    <tr>
                        <td><span class="mark ${t.owned ? 'yes' : 'no'}">${t.owned ? '✓' : '✗'}</span></td>
                        <td>${escapeHtml(t.parsed_artist || '')}</td>
                        <td><a class="video-link" href="https://www.youtube.com/watch?v=${encodeURIComponent(t.video_id)}" target="_blank" rel="noopener">${escapeHtml(t.parsed_title)}</a></td>
                        <td class="raw-title">${escapeHtml(t.raw_title)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function syncPlaylist(playlistId, userId) {
    const el = document.getElementById('tracks-' + playlistId);
    el.classList.add('open');
    el.innerHTML = '<div class="empty">Sincronizando…</div>';
    const r = await fetch(`/api/playlists/${playlistId}/sync`, { method: 'POST' });
    const data = await r.json();
    if (data.error) {
        el.innerHTML = `<div class="error">${escapeHtml(data.error)}</div>`;
        return;
    }
    await loadPlaylists(userId);
    document.getElementById('tracks-' + playlistId).classList.add('open');
    await loadTracks(playlistId);
}

async function addUser() {
    const input = document.getElementById('new_user');
    const value = input.value.trim();
    if (!value) return;
    document.getElementById('add-error').textContent = '';
    const r = await fetch('/api/users', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({value}) });
    const data = await r.json();
    if (data.error) { document.getElementById('add-error').textContent = data.error; return; }
    input.value = '';
    loadUsers();
}

async function addPlaylist() {
    const input = document.getElementById('new_playlist');
    const value = input.value.trim();
    if (!value) return;
    document.getElementById('add-error').textContent = '';
    const r = await fetch('/api/playlists', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({value}) });
    const data = await r.json();
    if (data.error) { document.getElementById('add-error').textContent = data.error; return; }
    input.value = '';
    loadUsers();
}

loadUsers();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
