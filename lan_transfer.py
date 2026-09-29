#!/usr/bin/env python3
"""
LAN File Transfer - 局域网文件传输工具
在任一台电脑上运行，另一台通过浏览器访问即可上传/下载文件。

用法:
    python lan_transfer.py                  # 使用默认端口 8765，共享当前目录
    python lan_transfer.py -p 9000          # 指定端口
    python lan_transfer.py -d ~/Desktop     # 指定共享目录
"""

import http.server
import socketserver
import os
import sys
import json
import urllib.parse
import socket
import argparse
import cgi
import io
import html
import mimetypes
import shutil
import platform
from datetime import datetime
from pathlib import Path

VERSION = "1.0"


def get_local_ip():
    """获取本机局域网 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📁 局域网文件传输</title>
<style>
  :root {
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --text2: #94a3b8;
    --accent: #38bdf8;
    --accent2: #818cf8;
    --green: #34d399;
    --red: #f87171;
    --hover: #263548;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 20px;
  }
  .container { max-width: 900px; margin: 0 auto; }
  header {
    text-align: center;
    padding: 30px 0 20px;
  }
  header h1 {
    font-size: 1.8em;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
  }
  header p { color: var(--text2); font-size: 0.9em; }

  /* 上传区域 */
  .upload-zone {
    border: 2px dashed var(--border);
    border-radius: 16px;
    padding: 40px;
    text-align: center;
    margin: 20px 0;
    transition: all 0.3s;
    cursor: pointer;
    background: var(--card);
  }
  .upload-zone:hover, .upload-zone.dragover {
    border-color: var(--accent);
    background: rgba(56, 189, 248, 0.05);
  }
  .upload-zone .icon { font-size: 3em; margin-bottom: 10px; }
  .upload-zone p { color: var(--text2); margin: 5px 0; }
  .upload-zone input[type="file"] { display: none; }

  /* 进度条 */
  .progress-container {
    margin: 15px 0;
    display: none;
  }
  .progress-bar {
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 3px;
    width: 0%;
    transition: width 0.3s;
  }
  .progress-text {
    font-size: 0.85em;
    color: var(--text2);
    margin-top: 5px;
    text-align: center;
  }

  /* 路径导航 */
  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 12px 16px;
    background: var(--card);
    border-radius: 10px;
    margin-bottom: 15px;
    flex-wrap: wrap;
    font-size: 0.9em;
  }
  .breadcrumb a {
    color: var(--accent);
    text-decoration: none;
  }
  .breadcrumb a:hover { text-decoration: underline; }
  .breadcrumb span { color: var(--text2); }

  /* 文件列表 */
  .file-list {
    background: var(--card);
    border-radius: 12px;
    overflow: hidden;
  }
  .file-item {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    transition: background 0.2s;
    gap: 12px;
  }
  .file-item:last-child { border-bottom: none; }
  .file-item:hover { background: var(--hover); }
  .file-icon { font-size: 1.3em; flex-shrink: 0; width: 30px; text-align: center; }
  .file-info { flex: 1; min-width: 0; }
  .file-name {
    color: var(--text);
    text-decoration: none;
    font-weight: 500;
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .file-name:hover { color: var(--accent); }
  .file-meta {
    font-size: 0.8em;
    color: var(--text2);
    margin-top: 2px;
  }
  .file-actions { flex-shrink: 0; }
  .btn-download {
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 5px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85em;
    transition: all 0.2s;
  }
  .btn-download:hover {
    background: var(--accent);
    color: var(--bg);
  }
  .empty-state {
    text-align: center;
    padding: 40px;
    color: var(--text2);
  }

  /* Toast 通知 */
  .toast {
    position: fixed;
    bottom: 30px;
    right: 30px;
    padding: 12px 20px;
    border-radius: 10px;
    color: white;
    font-size: 0.9em;
    z-index: 1000;
    animation: slideIn 0.3s ease;
    max-width: 350px;
  }
  .toast.success { background: #059669; }
  .toast.error { background: #dc2626; }
  @keyframes slideIn {
    from { transform: translateX(100px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>📁 局域网文件传输</h1>
    <p>当前共享: {share_path} | {hostname}</p>
  </header>

  <!-- 上传区域 -->
  <div class="upload-zone" id="uploadZone" onclick="document.getElementById('fileInput').click()">
    <div class="icon">☁️</div>
    <p><strong>拖拽文件到此处上传</strong></p>
    <p>或点击选择文件（支持多选）</p>
    <input type="file" id="fileInput" multiple>
  </div>

  <div class="progress-container" id="progressContainer">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="progress-text" id="progressText">上传中...</div>
  </div>

  <!-- 路径导航 -->
  <div class="breadcrumb" id="breadcrumb"></div>

  <!-- 文件列表 -->
  <div class="file-list" id="fileList"></div>
</div>

<script>
const currentPath = "{current_path}";

// 拖拽上传
const zone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');

zone.addEventListener('dragover', (e) => {
  e.preventDefault();
  zone.classList.add('dragover');
});
zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
zone.addEventListener('drop', (e) => {
  e.preventDefault();
  zone.classList.remove('dragover');
  uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', () => uploadFiles(fileInput.files));

function uploadFiles(files) {
  if (!files.length) return;
  const formData = new FormData();
  for (const f of files) formData.append('files', f);

  const prog = document.getElementById('progressContainer');
  const fill = document.getElementById('progressFill');
  const text = document.getElementById('progressText');
  prog.style.display = 'block';
  fill.style.width = '0%';

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload?path=' + encodeURIComponent(currentPath));

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = (e.loaded / e.total * 100).toFixed(1);
      fill.style.width = pct + '%';
      text.textContent = `上传中... ${pct}% (${formatSize(e.loaded)} / ${formatSize(e.total)})`;
    }
  };

  xhr.onload = () => {
    prog.style.display = 'none';
    if (xhr.status === 200) {
      showToast('✅ 上传成功！', 'success');
      location.reload();
    } else {
      showToast('❌ 上传失败: ' + xhr.responseText, 'error');
    }
  };
  xhr.onerror = () => {
    prog.style.display = 'none';
    showToast('❌ 网络错误', 'error');
  };
  xhr.send(formData);
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(2) + ' GB';
}

function showToast(msg, type) {
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// 加载文件列表
function loadFiles() {
  fetch('/api/list?path=' + encodeURIComponent(currentPath))
    .then(r => r.json())
    .then(data => {
      renderBreadcrumb(data.breadcrumb);
      renderFiles(data.files);
    });
}

function renderBreadcrumb(parts) {
  const bc = document.getElementById('breadcrumb');
  bc.innerHTML = '';
  parts.forEach((p, i) => {
    if (i > 0) {
      const sep = document.createElement('span');
      sep.textContent = ' / ';
      bc.appendChild(sep);
    }
    const a = document.createElement('a');
    a.textContent = p.name;
    a.href = '/?path=' + encodeURIComponent(p.path);
    bc.appendChild(a);
  });
}

function getFileIcon(name, isDir) {
  if (isDir) return '📁';
  const ext = name.split('.').pop().toLowerCase();
  const icons = {
    pdf: '📄', doc: '📝', docx: '📝', txt: '📃', md: '📃',
    jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', svg: '🖼️', webp: '🖼️',
    mp4: '🎬', avi: '🎬', mkv: '🎬', mov: '🎬',
    mp3: '🎵', wav: '🎵', flac: '🎵',
    zip: '📦', rar: '📦', '7z': '📦', tar: '📦', gz: '📦',
    py: '🐍', js: '💛', ts: '💙', java: '☕', c: '⚙️', cpp: '⚙️',
    html: '🌐', css: '🎨', json: '📋', xml: '📋', yaml: '📋', yml: '📋',
    exe: '⚡', dmg: '💿', iso: '💿',
    xls: '📊', xlsx: '📊', csv: '📊', ppt: '📽️', pptx: '📽️',
  };
  return icons[ext] || '📄';
}

function renderFiles(files) {
  const list = document.getElementById('fileList');
  if (!files.length) {
    list.innerHTML = '<div class="empty-state">📭 此目录为空</div>';
    return;
  }
  list.innerHTML = '';
  files.forEach(f => {
    const item = document.createElement('div');
    item.className = 'file-item';

    const icon = document.createElement('div');
    icon.className = 'file-icon';
    icon.textContent = getFileIcon(f.name, f.is_dir);

    const info = document.createElement('div');
    info.className = 'file-info';

    const name = document.createElement('a');
    name.className = 'file-name';
    name.textContent = f.name;
    if (f.is_dir) {
      name.href = '/?path=' + encodeURIComponent(f.path);
    } else {
      name.href = '/download?path=' + encodeURIComponent(f.path);
    }

    const meta = document.createElement('div');
    meta.className = 'file-meta';
    meta.textContent = f.is_dir ? '文件夹' : `${f.size} · ${f.modified}`;

    info.appendChild(name);
    info.appendChild(meta);

    item.appendChild(icon);
    item.appendChild(info);

    if (!f.is_dir) {
      const actions = document.createElement('div');
      actions.className = 'file-actions';
      const btn = document.createElement('button');
      btn.className = 'btn-download';
      btn.textContent = '下载';
      btn.onclick = () => window.location.href = '/download?path=' + encodeURIComponent(f.path);
      actions.appendChild(btn);
      item.appendChild(actions);
    }

    list.appendChild(item);
  });
}

loadFiles();
</script>
</body>
</html>"""


class TransferHandler(http.server.BaseHTTPRequestHandler):
    """处理文件传输的 HTTP 请求"""

    share_dir = "."

    def log_message(self, format, *args):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"  [{timestamp}] {args[0]}")

    def _safe_path(self, rel_path):
        """防止路径穿越攻击"""
        base = Path(self.share_dir).resolve()
        target = (base / rel_path).resolve()
        if not str(target).startswith(str(base)):
            return None
        return target

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        rel_path = params.get("path", [""])[0]

        if path == "/" or path == "":
            self._serve_page(rel_path)
        elif path == "/api/list":
            self._serve_file_list(rel_path)
        elif path == "/download":
            self._serve_download(rel_path)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/upload":
            params = urllib.parse.parse_qs(parsed.query)
            rel_path = params.get("path", [""])[0]
            self._handle_upload(rel_path)
        else:
            self.send_error(404)

    def _serve_page(self, rel_path):
        """渲染主页面"""
        safe = self._safe_path(rel_path)
        if safe is None:
            self.send_error(403, "禁止访问")
            return

        share_display = str(Path(self.share_dir).resolve())
        hostname = socket.gethostname()

        page = HTML_TEMPLATE.replace("{share_path}", html.escape(share_display))
        page = page.replace("{hostname}", html.escape(hostname))
        page = page.replace("{current_path}", html.escape(rel_path))

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))

    def _serve_file_list(self, rel_path):
        """返回文件列表 JSON"""
        safe = self._safe_path(rel_path)
        if safe is None or not safe.is_dir():
            self.send_error(403)
            return

        files = []
        try:
            entries = sorted(safe.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            entries = []

        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                stat = entry.stat()
                rel = str(entry.relative_to(Path(self.share_dir).resolve()))
                files.append({
                    "name": entry.name,
                    "path": rel,
                    "is_dir": entry.is_dir(),
                    "size": format_size(stat.st_size) if not entry.is_dir() else "",
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
            except (PermissionError, OSError):
                continue

        # 面包屑导航
        breadcrumb = [{"name": "🏠 根目录", "path": ""}]
        if rel_path:
            parts = Path(rel_path).parts
            for i, part in enumerate(parts):
                breadcrumb.append({
                    "name": part,
                    "path": str(Path(*parts[: i + 1])),
                })

        result = {"files": files, "breadcrumb": breadcrumb}
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))

    def _serve_download(self, rel_path):
        """下载文件"""
        safe = self._safe_path(rel_path)
        if safe is None or not safe.is_file():
            self.send_error(404, "文件不存在")
            return

        mime_type, _ = mimetypes.guess_type(str(safe))
        if mime_type is None:
            mime_type = "application/octet-stream"

        file_size = safe.stat().st_size
        encoded_name = urllib.parse.quote(safe.name)

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header(
            "Content-Disposition",
            f"attachment; filename*=UTF-8''{encoded_name}",
        )
        self.end_headers()

        with open(safe, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def _handle_upload(self, rel_path):
        """处理文件上传"""
        safe = self._safe_path(rel_path)
        if safe is None:
            self.send_error(403, "禁止访问")
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400, "无效请求")
            return

        # 解析 multipart 数据
        boundary = content_type.split("boundary=")[1].encode()
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 手动解析 multipart
        parts = body.split(b"--" + boundary)
        saved_files = []

        for part in parts:
            if b"filename=" not in part:
                continue

            # 提取文件名
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            header = part[:header_end].decode("utf-8", errors="replace")
            file_data = part[header_end + 4:]
            if file_data.endswith(b"\r\n"):
                file_data = file_data[:-2]

            # 从 header 中提取文件名
            filename = None
            for line in header.split("\r\n"):
                if "filename=" in line:
                    # 处理 filename="xxx" 或 filename*=utf-8''xxx
                    if 'filename="' in line:
                        start = line.index('filename="') + 10
                        end = line.index('"', start)
                        filename = line[start:end]
                    break

            if not filename or not filename.strip():
                continue

            # 安全文件名
            filename = Path(filename).name
            if not filename:
                continue

            save_path = safe / filename

            # 如果文件已存在，添加序号
            if save_path.exists():
                stem = save_path.stem
                suffix = save_path.suffix
                counter = 1
                while save_path.exists():
                    save_path = safe / f"{stem}({counter}){suffix}"
                    counter += 1

            with open(save_path, "wb") as f:
                f.write(file_data)
            saved_files.append(filename)
            print(f"  📥 收到文件: {filename} ({format_size(len(file_data))})")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"已保存 {len(saved_files)} 个文件".encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(
        description="局域网文件传输工具 - 通过浏览器在局域网内传输文件"
    )
    parser.add_argument("-p", "--port", type=int, default=8765, help="服务端口 (默认: 8765)")
    parser.add_argument(
        "-d", "--dir", type=str, default=".", help="共享目录 (默认: 当前目录)"
    )
    args = parser.parse_args()

    share_dir = os.path.abspath(args.dir)
    if not os.path.isdir(share_dir):
        print(f"❌ 目录不存在: {share_dir}")
        sys.exit(1)

    TransferHandler.share_dir = share_dir
    local_ip = get_local_ip()

    # 允许端口复用
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("0.0.0.0", args.port), TransferHandler)

    print()
    print("=" * 55)
    print("   📁  局域网文件传输工具 v" + VERSION)
    print("=" * 55)
    print()
    print(f"  📂 共享目录: {share_dir}")
    print(f"  🖥️  本机系统: {platform.system()} {platform.release()}")
    print()
    print("  ┌─────────────────────────────────────────────┐")
    print(f"  │  在另一台电脑浏览器中打开:                  │")
    print(f"  │                                             │")
    print(f"  │  👉  http://{local_ip}:{args.port:<5}                  │")
    print(f"  │                                             │")
    print("  └─────────────────────────────────────────────┘")
    print()
    print(f"  本机也可访问: http://localhost:{args.port}")
    print()
    print("  按 Ctrl+C 停止服务")
    print("─" * 55)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  👋 服务已停止")
        server.server_close()


if __name__ == "__main__":
    main()
