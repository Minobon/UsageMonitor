"""tray_icon.png から build_icon.ico を生成する (ビルド用ヘルパー)"""

import struct
import io
from PIL import Image

SIZES = [16, 24, 32, 48, 64, 128, 256]

src = Image.open("assets/tray_icon.png").convert("RGBA")

# 各サイズのPNGデータを生成
png_frames = []
for s in SIZES:
    resized = src.resize((s, s), Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    png_frames.append(buf.getvalue())

# ICOフォーマット手動構築
num = len(SIZES)
# ヘッダー: reserved(2) + type(2) + count(2) = 6バイト
header = struct.pack("<HHH", 0, 1, num)

# ディレクトリエントリ: 各16バイト
# オフセットはヘッダー＋全ディレクトリエントリの後から
data_offset = 6 + num * 16

entries = []
for i, s in enumerate(SIZES):
    png = png_frames[i]
    w = 0 if s >= 256 else s  # ICOフォーマットでは256は0として格納
    h = w
    # ICONDIRENTRYフォーマット: width(1), height(1), colors(1), reserved(1),
    #               planes(2), bitcount(2), size(4), offset(4)
    entry = struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png), data_offset)
    entries.append(entry)
    data_offset += len(png)

with open("build_icon.ico", "wb") as f:
    f.write(header)
    for e in entries:
        f.write(e)
    for png in png_frames:
        f.write(png)

print(f"build_icon.ico generated ({num} sizes: {SIZES})")
