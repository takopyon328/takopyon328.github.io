#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ニコニコ風コメントスクリーン
============================
教室のPCでこのスクリプトを起動すると、学生がスマホやPCのブラウザから
コメントを投稿でき、起動したPCの画面(表示ページ)にコメントが
右から左へ流れます。

使い方:
    python server.py            # ポート8000で起動
    python server.py 8080       # ポートを指定して起動

起動後:
    教員PC(表示用) : http://localhost:8000/screen をブラウザで開く
    学生(投稿用)   : http://<このPCのIPアドレス>:8000/ にアクセス

Python 3.7 以上の標準ライブラリのみで動作します(追加インストール不要)。
"""

import json
import queue
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8000
MAX_COMMENT_LENGTH = 60          # コメントの最大文字数
MIN_POST_INTERVAL = 1.0          # 同一IPからの連続投稿の最小間隔(秒)
ALLOWED_COLORS = {
    "white": "#ffffff",
    "red": "#ff5252",
    "orange": "#ffa726",
    "yellow": "#ffee58",
    "green": "#66bb6a",
    "cyan": "#4dd0e1",
    "pink": "#f06292",
}
ALLOWED_SIZES = {"small", "medium", "large"}

# NGワード(必要に応じて追加してください)
NG_WORDS = []

# ---------------------------------------------------------------------------
# コメント配信(SSE)の管理
# ---------------------------------------------------------------------------

_clients_lock = threading.Lock()
_clients = []          # 表示ページごとの queue.Queue
_last_post = {}        # IPアドレス -> 最終投稿時刻
_comment_count = 0


def broadcast(comment: dict):
    """全ての表示ページにコメントを配信する"""
    with _clients_lock:
        for q in _clients:
            try:
                q.put_nowait(comment)
            except queue.Full:
                pass


# ---------------------------------------------------------------------------
# HTML(学生用 投稿ページ)
# ---------------------------------------------------------------------------

POST_PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>コメント投稿</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
    background: #1a1a2e; color: #eee; min-height: 100vh;
    display: flex; align-items: center; justify-content: center; padding: 16px;
  }
  .card {
    width: 100%; max-width: 480px; background: #16213e;
    border-radius: 16px; padding: 24px; box-shadow: 0 8px 32px rgba(0,0,0,.4);
  }
  h1 { font-size: 1.2rem; margin-bottom: 16px; text-align: center; }
  textarea {
    width: 100%; font-size: 1.1rem; padding: 12px; border-radius: 10px;
    border: 2px solid #0f3460; background: #0f1626; color: #fff;
    resize: none; height: 4.5em; outline: none;
  }
  textarea:focus { border-color: #e94560; }
  .label { font-size: .8rem; color: #aaa; margin: 14px 0 6px; }
  .colors { display: flex; gap: 10px; flex-wrap: wrap; }
  .color-btn {
    width: 36px; height: 36px; border-radius: 50%; border: 3px solid transparent;
    cursor: pointer; transition: transform .1s;
  }
  .color-btn.selected { border-color: #e94560; transform: scale(1.15); }
  .sizes { display: flex; gap: 8px; }
  .size-btn {
    flex: 1; padding: 8px; border-radius: 10px; border: 2px solid #0f3460;
    background: #0f1626; color: #ccc; cursor: pointer; font-size: .9rem;
  }
  .size-btn.selected { border-color: #e94560; color: #fff; background: #1f2a4a; }
  button.send {
    width: 100%; margin-top: 20px; padding: 14px; font-size: 1.1rem;
    font-weight: bold; color: #fff; background: #e94560; border: none;
    border-radius: 12px; cursor: pointer;
  }
  button.send:active { transform: scale(.98); }
  button.send:disabled { background: #555; }
  .msg { text-align: center; margin-top: 12px; font-size: .85rem; height: 1.2em; }
  .msg.ok { color: #66bb6a; }
  .msg.err { color: #ff5252; }
  .count { text-align: right; font-size: .75rem; color: #888; margin-top: 4px; }
</style>
</head>
<body>
<div class="card">
  <h1>💬 コメントを送ろう</h1>
  <textarea id="text" maxlength="__MAXLEN__" placeholder="コメントを入力(__MAXLEN__文字まで)" autofocus></textarea>
  <div class="count"><span id="len">0</span>/__MAXLEN__</div>
  <div class="label">色</div>
  <div class="colors" id="colors"></div>
  <div class="label">大きさ</div>
  <div class="sizes">
    <button class="size-btn" data-size="small">小</button>
    <button class="size-btn selected" data-size="medium">中</button>
    <button class="size-btn" data-size="large">大</button>
  </div>
  <button class="send" id="send">送信する</button>
  <div class="msg" id="msg"></div>
</div>
<script>
const COLORS = __COLORS__;
let color = "white", size = "medium";

const colorsEl = document.getElementById("colors");
for (const [name, hex] of Object.entries(COLORS)) {
  const b = document.createElement("button");
  b.className = "color-btn" + (name === "white" ? " selected" : "");
  b.style.background = hex;
  b.onclick = () => {
    color = name;
    colorsEl.querySelectorAll(".color-btn").forEach(x => x.classList.remove("selected"));
    b.classList.add("selected");
  };
  colorsEl.appendChild(b);
}

document.querySelectorAll(".size-btn").forEach(b => {
  b.onclick = () => {
    size = b.dataset.size;
    document.querySelectorAll(".size-btn").forEach(x => x.classList.remove("selected"));
    b.classList.add("selected");
  };
});

const textEl = document.getElementById("text");
const msgEl = document.getElementById("msg");
const sendBtn = document.getElementById("send");
textEl.addEventListener("input", () => {
  document.getElementById("len").textContent = textEl.value.length;
});
textEl.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
sendBtn.onclick = send;

async function send() {
  const text = textEl.value.trim();
  if (!text) return;
  sendBtn.disabled = true;
  try {
    const res = await fetch("/api/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, color, size })
    });
    if (res.ok) {
      textEl.value = "";
      document.getElementById("len").textContent = "0";
      msgEl.textContent = "送信しました!";
      msgEl.className = "msg ok";
    } else {
      const data = await res.json().catch(() => ({}));
      msgEl.textContent = data.error || "送信に失敗しました";
      msgEl.className = "msg err";
    }
  } catch {
    msgEl.textContent = "通信エラーが発生しました";
    msgEl.className = "msg err";
  }
  setTimeout(() => { msgEl.textContent = ""; }, 2500);
  sendBtn.disabled = false;
  textEl.focus();
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTML(教員用 表示ページ)
# ---------------------------------------------------------------------------

SCREEN_PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>コメントスクリーン</title>
<style>
  * { margin: 0; padding: 0; }
  html, body { width: 100%; height: 100%; overflow: hidden; }
  body { background: #000; cursor: default; }
  body.bg-green { background: #00ff00; }
  body.bg-white { background: #fff; }
  #stage { position: fixed; inset: 0; }
  .comment {
    position: absolute; white-space: nowrap; font-weight: bold;
    font-family: "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
    text-shadow: 2px 2px 2px #000, -1px -1px 2px #000,
                 1px -1px 2px #000, -1px 1px 2px #000;
    will-change: transform; left: 100%;
  }
  body.bg-white .comment {
    text-shadow: 2px 2px 2px #999, -1px -1px 2px #999,
                 1px -1px 2px #999, -1px 1px 2px #999;
  }
  #info {
    position: fixed; bottom: 16px; right: 16px; z-index: 10;
    background: rgba(0,0,0,.7); color: #fff; padding: 14px 18px;
    border-radius: 12px; font-family: "Meiryo", sans-serif; font-size: 16px;
    text-align: center;
  }
  #info .url { font-size: 22px; font-weight: bold; color: #ffee58; margin: 6px 0; }
  #info img { display: block; margin: 8px auto 0; background: #fff; padding: 6px; border-radius: 8px; }
  #info .hint { font-size: 11px; color: #aaa; margin-top: 8px; }
  #status {
    position: fixed; top: 12px; left: 12px; z-index: 10; font-size: 12px;
    color: #888; font-family: monospace;
  }
</style>
</head>
<body>
<div id="stage"></div>
<div id="info">
  📱 スマホでコメントを送ろう
  <div class="url" id="url"></div>
  <img id="qr" width="140" height="140" alt="">
  <div class="hint">H: この案内を隠す / F: 全画面 / C: クリア</div>
</div>
<div id="status"></div>
<script>
const stage = document.getElementById("stage");
const statusEl = document.getElementById("status");

// 背景色: /screen?bg=green (クロマキー用) や ?bg=white も指定可能
const bg = new URLSearchParams(location.search).get("bg");
if (bg === "green") document.body.classList.add("bg-green");
if (bg === "white") document.body.classList.add("bg-white");

// 投稿用URLとQRコードを表示(QRはネット接続時のみ表示される)
const postUrl = location.protocol + "//" + location.host + "/";
document.getElementById("url").textContent = postUrl.replace(/\\/$/, "");
const qr = document.getElementById("qr");
qr.src = "https://api.qrserver.com/v1/create-qr-code/?size=140x140&data=" +
         encodeURIComponent(postUrl);
qr.onerror = () => { qr.style.display = "none"; };

document.addEventListener("keydown", e => {
  const k = e.key.toLowerCase();
  if (k === "h") {
    const info = document.getElementById("info");
    info.style.display = info.style.display === "none" ? "" : "none";
  } else if (k === "f") {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  } else if (k === "c") {
    stage.innerHTML = "";
    lanes.fill(0);
  }
});

// --- レーン管理(コメント同士が重ならないように流す) ---
const SIZE_PX = { small: 28, medium: 42, large: 60 };
const DURATION = 8000;   // 画面を横切る時間(ミリ秒)
const LANE_HEIGHT = 70;
let lanes = [];

function resetLanes() {
  const n = Math.max(1, Math.floor(window.innerHeight / LANE_HEIGHT) - 1);
  lanes = new Array(n).fill(0);   // 各レーンが空く時刻
}
resetLanes();
window.addEventListener("resize", resetLanes);

function pickLane(commentWidth) {
  const now = performance.now();
  // コメントの末尾が右端を抜けるまでの時間だけレーンを占有する
  const speed = (window.innerWidth + commentWidth) / DURATION;
  const occupy = commentWidth / speed + 500;
  for (let i = 0; i < lanes.length; i++) {
    if (lanes[i] <= now) { lanes[i] = now + occupy; return i; }
  }
  const i = Math.floor(Math.random() * lanes.length);
  lanes[i] = now + occupy;
  return i;
}

function showComment(c) {
  const el = document.createElement("div");
  el.className = "comment";
  el.textContent = c.text;
  el.style.color = c.color;
  el.style.fontSize = (SIZE_PX[c.size] || SIZE_PX.medium) + "px";
  stage.appendChild(el);

  const w = el.offsetWidth;
  const lane = pickLane(w);
  el.style.top = (lane * LANE_HEIGHT + 10) + "px";

  const distance = window.innerWidth + w;
  const anim = el.animate(
    [{ transform: "translateX(0)" }, { transform: `translateX(-${distance}px)` }],
    { duration: DURATION, easing: "linear" }
  );
  anim.onfinish = () => el.remove();
}

// --- サーバーからコメントを受信(SSE) ---
function connect() {
  const es = new EventSource("/api/stream");
  es.onopen = () => { statusEl.textContent = ""; };
  es.onmessage = e => { showComment(JSON.parse(e.data)); };
  es.onerror = () => {
    statusEl.textContent = "再接続中...";
    es.close();
    setTimeout(connect, 2000);
  };
}
connect();
</script>
</body>
</html>
"""


def render(template: str) -> bytes:
    page = (template
            .replace("__MAXLEN__", str(MAX_COMMENT_LENGTH))
            .replace("__COLORS__", json.dumps(ALLOWED_COLORS)))
    return page.encode("utf-8")


# ---------------------------------------------------------------------------
# HTTPハンドラ
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # アクセスログは出さない(コメント投稿のみコンソールに表示)

    def _send_html(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self._send_html(render(POST_PAGE))
        elif path == "/screen":
            self._send_html(render(SCREEN_PAGE))
        elif path == "/api/stream":
            self._handle_stream()
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/api/comment":
            self._send_json(404, {"error": "not found"})
            return

        ip = self.client_address[0]
        now = time.time()
        if now - _last_post.get(ip, 0) < MIN_POST_INTERVAL:
            self._send_json(429, {"error": "投稿が早すぎます。少し待ってください"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > 4096:
                raise ValueError
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            text = str(data.get("text", "")).strip()
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "不正なリクエストです"})
            return

        if not text:
            self._send_json(400, {"error": "コメントが空です"})
            return
        if len(text) > MAX_COMMENT_LENGTH:
            self._send_json(400, {"error": f"コメントは{MAX_COMMENT_LENGTH}文字以内です"})
            return
        if any(w in text for w in NG_WORDS):
            self._send_json(400, {"error": "送信できない言葉が含まれています"})
            return

        color_name = data.get("color", "white")
        color = ALLOWED_COLORS.get(color_name, ALLOWED_COLORS["white"])
        size = data.get("size", "medium")
        if size not in ALLOWED_SIZES:
            size = "medium"

        _last_post[ip] = now
        global _comment_count
        _comment_count += 1
        comment = {"text": text, "color": color, "size": size}
        broadcast(comment)
        print(f"[{time.strftime('%H:%M:%S')}] #{_comment_count} ({ip}) {text}")
        self._send_json(200, {"ok": True})

    def _handle_stream(self):
        """表示ページへのSSE配信。接続が切れるまでコメントを送り続ける"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        q = queue.Queue(maxsize=200)
        with _clients_lock:
            _clients.append(q)
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    comment = q.get(timeout=15)
                    payload = json.dumps(comment, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")  # 接続維持
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _clients_lock:
                if q in _clients:
                    _clients.remove(q)


# ---------------------------------------------------------------------------
# 起動
# ---------------------------------------------------------------------------

def get_lan_ip() -> str:
    """このPCのLAN上のIPアドレスを取得する"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 実際には送信しない(経路の特定のみ)
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main():
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"ポート番号が不正です: {sys.argv[1]}")
            sys.exit(1)

    ip = get_lan_ip()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)

    print("=" * 56)
    print("  ニコニコ風コメントスクリーン を起動しました")
    print("=" * 56)
    print()
    print(f"  【表示ページ(このPCで開く)】")
    print(f"    http://localhost:{port}/screen")
    print()
    print(f"  【投稿ページ(学生に伝えるURL)】")
    print(f"    http://{ip}:{port}/")
    print()
    print("  ※ 学生はこのPCと同じネットワーク(Wi-Fi)に接続して")
    print("     いる必要があります。")
    print("  ※ 終了するには Ctrl+C を押してください。")
    print("=" * 56)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了します。")
        server.shutdown()


if __name__ == "__main__":
    main()
