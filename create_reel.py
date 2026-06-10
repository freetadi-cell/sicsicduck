#!/usr/bin/env python3
"""
香港銀行定期存款利率 IG Reel 生成器
"""

from PIL import Image, ImageDraw, ImageFont
import os
import subprocess
import json

# Config
WIDTH, HEIGHT = 1080, 1920
FPS = 30
FRAME_DIR = '/home/freet/.openclaw/workspace/hk_deposit_rates/reel_frames'
OUTPUT = '/home/freet/.openclaw/workspace/hk_deposit_rates/hk_deposit_rates_reel.mp4'

# Bank rates data
DATA = {
    'hkd_3m': [
        ('平安數字銀行', 'PAObank', '2.85%', 1),
        ('富邦銀行', 'Fubon', '2.8%', 2),
        ('中信銀行（國際）', 'CITIC', '2.7%', 3),
    ],
    'hkd_6m': [
        ('星展銀行', 'DBS', '3.0%', 1),
        ('平安數字銀行', 'PAObank', '2.85%', 2),
        ('富邦銀行 / WeLab', '', '2.8%', 3),
    ],
    'hkd_12m': [
        ('象象銀行 / 平安', '', '2.9%', 1),
        ('富邦 / WeLab / 富融', '', '2.8%', 2),
        ('理慧銀行', 'livi', '2.7%', 3),
    ],
    'usd_3m': [
        ('富邦銀行', 'Fubon', '4.0%', 1),
        ('創興銀行', 'Chong Hing', '3.7%', 2),
        ('中信銀行（國際）', 'CITIC', '3.65%', 3),
    ],
    'usd_6m': [
        ('富邦 / 星展', '', '3.8%', 1),
        ('創興 / 富融 / 象象', '', '3.7%', 2),
        ('東亞銀行', 'BEA', '3.6%', 3),
    ],
    'usd_12m': [
        ('富邦 / 平安', '', '3.8%', 1),
        ('富融 / 象象', '', '3.7%', 2),
        ('東亞銀行', 'BEA', '3.6%', 3),
    ]
}

# Colors
COLORS = {
    'bg': '#1a1a2e',
    'card': '#16213e',
    'gold': '#f4d03f',
    'green': '#2ecc71',
    'red': '#e74c3c',
    'white': '#ffffff',
    'gray': '#95a5a6',
    'accent': '#e94560',
    'gradient_top': '#1a1a2e',
    'gradient_bottom': '#0f0f1a',
}

def get_font(size, bold=False):
    fonts = [
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for f in fonts:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except:
                pass
    return ImageFont.load_default()

def create_gradient(width, height, top_color, bottom_color):
    """Create vertical gradient"""
    gradient = Image.new('RGB', (width, 1))
    draw = ImageDraw.Draw(gradient)

    r1, g1, b1 = int(top_color[1:3], 16), int(top_color[3:5], 16), int(top_color[5:7], 16)
    r2, g2, b2 = int(bottom_color[1:3], 16), int(bottom_color[3:5], 16), int(bottom_color[5:7], 16)

    for x in range(width):
        r = int(r1 + (r2 - r1) * x / width)
        g = int(g1 + (g2 - g1) * x / width)
        b = int(b1 + (b2 - b1) * x / width)
        draw.point((x, 0), (r, g, b))

    return gradient.resize((width, height))

def create_background():
    """Create animated background"""
    bg = create_gradient(WIDTH, HEIGHT, COLORS['gradient_top'], COLORS['gradient_bottom'])
    return bg

def draw_medal(draw, center_x, center_y, rank, size=60):
    """Draw medal icon"""
    colors = [COLORS['gold'], '#c0c0c0', '#cd7f32']  # gold, silver, bronze
    color = colors[rank - 1]

    # Circle
    draw.ellipse([
        center_x - size//2, center_y - size//2,
        center_x + size//2, center_y + size//2
    ], fill=color, outline=COLORS['white'], width=3)

    # Number
    font = get_font(36, True)
    text = str(rank)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text((center_x - text_width//2, center_y - text_height//2), text, font=font, fill=COLORS['bg'])

def create_frame(title, subtitle, rows, duration_sec=3, frame_num=0, total_frames=0):
    """Create a single frame"""
    # Background
    bg = create_background()
    draw = ImageDraw.Draw(bg)

    # Title section
    title_font = get_font(56, True)
    subtitle_font = get_font(36, False)

    # Draw title
    bbox = draw.textbbox((0, 0), title, font=title_font)
    text_width = bbox[2] - bbox[0]
    draw.text((WIDTH//2 - text_width//2, 120), title, font=title_font, fill=COLORS['gold'])

    # Draw subtitle
    bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    text_width = bbox[2] - bbox[0]
    draw.text((WIDTH//2 - text_width//2, 200), subtitle, font=subtitle_font, fill=COLORS['white'])

    # Cards
    y_start = 300
    card_height = 220
    card_gap = 25

    for i, (name, name_en, rate, rank) in enumerate(rows):
        y = y_start + i * (card_height + card_gap)

        # Card background with gradient
        card_y = y
        for cy in range(card_height):
            alpha = int(30 + 20 * cy / card_height)
            card_color = (
                int(22 + alpha/2),
                int(33 + alpha/3),
                int(62 + alpha/2)
            )
            draw.rectangle([40, card_y + cy, WIDTH - 40, card_y + cy + 1], fill=tuple(card_color))

        # Card border (accent for top 3)
        border_color = COLORS['accent'] if rank <= 3 else COLORS['card']
        draw.rectangle([40, y, WIDTH - 40, y + card_height], outline=border_color, width=3)

        # Medal
        draw_medal(draw, 100, y + card_height//2, rank)

        # Bank name
        name_font = get_font(32, True)
        draw.text((160, y + 30), name, font=name_font, fill=COLORS['white'])

        # Bank name EN (if available)
        if name_en:
            name_en_font = get_font(24, False)
            draw.text((160, y + 75), name_en, font=name_en_font, fill=COLORS['gray'])

        # Rate
        rate_font = get_font(52, True)
        rate_bbox = draw.textbbox((0, 0), rate, font=rate_font)
        rate_width = rate_bbox[2] - rate_bbox[0]
        draw.text((WIDTH - 80 - rate_width, y + card_height//2 - 35), rate, font=rate_font, fill=COLORS['green'])

        # Rate label
        rate_label_font = get_font(20, False)
        draw.text((WIDTH - 80 - 50, y + card_height - 45), '年利率', font=rate_label_font, fill=COLORS['gray'])

    # Footer
    footer_font = get_font(24, False)
    footer_text = "📌 息率以新資金／網上銀行優惠為主 | 資料僅供參考"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
    footer_width = footer_bbox[2] - footer_bbox[0]
    draw.text((WIDTH//2 - footer_width//2, HEIGHT - 100), footer_text, font=footer_font, fill=COLORS['gray'])

    # Frame counter / progress
    if total_frames > 0:
        progress_text = f"{frame_num + 1}/{total_frames}"
        progress_font = get_font(20, False)
        draw.text((WIDTH//2, HEIGHT - 40), progress_text, font=progress_font, fill=COLORS['gray'], anchor='mm')

    return bg

def create_intro_frame():
    """Create intro frame"""
    bg = create_background()
    draw = ImageDraw.Draw(bg)

    # Logo/icon area
    center_y = HEIGHT // 2

    # Duck emoji (🦆) as text
    emoji_font = get_font(200)
    duck_bbox = draw.textbbox((0, 0), '🦆', font=emoji_font)
    duck_width = duck_bbox[2] - duck_bbox[0]
    draw.text((WIDTH//2 - duck_width//2, center_y - 200), '🦆', font=emoji_font)

    # Title
    title_font = get_font(64, True)
    title = '香港銀行'
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text((WIDTH//2 - title_width//2, center_y + 20), title, font=title_font, fill=COLORS['gold'])

    title2_font = get_font(64, True)
    title2 = '定期存款利率'
    title2_bbox = draw.textbbox((0, 0), title2, font=title2_font)
    title2_width = title2_bbox[2] - title2_bbox[0]
    draw.text((WIDTH//2 - title2_width//2, center_y + 100), title2, font=title2_font, fill=COLORS['white'])

    # Date
    date_font = get_font(32, False)
    date_text = '2025年6月6日更新'
    date_bbox = draw.textbbox((0, 0), date_text, font=date_font)
    date_width = date_bbox[2] - date_bbox[0]
    draw.text((WIDTH//2 - date_width//2, center_y + 180), date_text, font=date_font, fill=COLORS['gray'])

    # Subtitle
    sub_font = get_font(28, False)
    sub_text = '食息鴨 | 香港最強定存利率一覽'
    sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
    sub_width = sub_bbox[2] - sub_bbox[0]
    draw.text((WIDTH//2 - sub_width//2, HEIGHT - 150), sub_text, font=sub_font, fill=COLORS['accent'])

    return bg

def create_outro_frame():
    """Create outro frame"""
    bg = create_background()
    draw = ImageDraw.Draw(bg)

    center_y = HEIGHT // 2

    # Thanks message
    thanks_font = get_font(56, True)
    thanks = '訂閱追蹤'
    thanks_bbox = draw.textbbox((0, 0), thanks, font=thanks_font)
    thanks_width = thanks_bbox[2] - thanks_bbox[0]
    draw.text((WIDTH//2 - thanks_width//2, center_y - 100), thanks, font=thanks_font, fill=COLORS['white'])

    handle_font = get_font(48, True)
    handle = '@食息鴨'
    handle_bbox = draw.textbbox((0, 0), handle, font=handle_font)
    handle_width = handle_bbox[2] - handle_bbox[0]
    draw.text((WIDTH//2 - handle_width//2, center_y - 20), handle, font=handle_font, fill=COLORS['gold'])

    # Hashtags
    tag_font = get_font(28, False)
    tags = [
        '#香港定存 #定期存款 #香港銀行',
        '#存款利率 #息率比較 #HKD #USD',
        '#被動收入 #理財 #食息鴨'
    ]
    for i, tag in enumerate(tags):
        tag_bbox = draw.textbbox((0, 0), tag, font=tag_font)
        tag_width = tag_bbox[2] - tag_bbox[0]
        draw.text((WIDTH//2 - tag_width//2, center_y + 80 + i * 45), tag, font=tag_font, fill=COLORS['gray'])

    return bg

def create_all_frames():
    """Create all frames for the reel"""
    os.makedirs(FRAME_DIR, exist_ok=True)

    frames = []

    # Intro (3 seconds = 90 frames)
    intro = create_intro_frame()
    for _ in range(90):
        frames.append(intro)

    # HKD 3M (3 seconds = 90 frames)
    hkd_3m = create_frame('💰 港元 HKD 定存', '3個月', DATA['hkd_3m'])
    for _ in range(90):
        frames.append(hkd_3m)

    # HKD 6M (3 seconds = 90 frames)
    hkd_6m = create_frame('💰 港元 HKD 定存', '6個月', DATA['hkd_6m'])
    for _ in range(90):
        frames.append(hkd_6m)

    # HKD 12M (3 seconds = 90 frames)
    hkd_12m = create_frame('💰 港元 HKD 定存', '12個月', DATA['hkd_12m'])
    for _ in range(90):
        frames.append(hkd_12m)

    # USD 3M (3 seconds = 90 frames)
    usd_3m = create_frame('💵 美元 USD 定存', '3個月', DATA['usd_3m'])
    for _ in range(90):
        frames.append(usd_3m)

    # USD 6M (3 seconds = 90 frames)
    usd_6m = create_frame('💵 美元 USD 定存', '6個月', DATA['usd_6m'])
    for _ in range(90):
        frames.append(usd_6m)

    # USD 12M (3 seconds = 90 frames)
    usd_12m = create_frame('💵 美元 USD 定存', '12個月', DATA['usd_12m'])
    for _ in range(90):
        frames.append(usd_12m)

    # Outro (4 seconds = 120 frames)
    outro = create_outro_frame()
    for _ in range(120):
        frames.append(outro)

    return frames

def save_frames_as_images(frames):
    """Save frames as PNG files"""
    for i, frame in enumerate(frames):
        frame_path = os.path.join(FRAME_DIR, f'frame_{i:06d}.png')
        frame.save(frame_path)
        if (i + 1) % 50 == 0:
            print(f"Saved {i + 1}/{len(frames)} frames...")

def compile_to_video(frame_count, output_path):
    """Compile frames to video using ffmpeg"""
    cmd = [
        'ffmpeg',
        '-y',
        '-framerate', str(FPS),
        '-i', os.path.join(FRAME_DIR, 'frame_%06d.png'),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path
    ]

    print(f"Running ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr}")
        return False
    print(f"Video created: {output_path}")
    return True

def main():
    print("🎬 Creating IG Reel for HK Deposit Rates...")
    print(f"📐 Resolution: {WIDTH}x{HEIGHT}")
    print(f"🎞️ FPS: {FPS}")

    # Create all frames
    print("\n📝 Creating frames...")
    frames = create_all_frames()
    print(f"✅ Created {len(frames)} frames")

    # Save as images
    print("\n💾 Saving frames as images...")
    save_frames_as_images(frames)
    print("✅ All frames saved")

    # Compile to video
    print("\n🎞️ Compiling to video...")
    success = compile_to_video(len(frames), OUTPUT)

    if success:
        print(f"\n🎉 Reel created successfully!")
        print(f"📍 Location: {OUTPUT}")
        print(f"📊 Duration: {len(frames) / FPS:.1f} seconds")

        # Get file size
        size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
        print(f"📦 File size: {size_mb:.1f} MB")

        # Cleanup frames
        print("\n🧹 Cleaning up frames...")
        import shutil
        shutil.rmtree(FRAME_DIR)
        print("✅ Cleanup complete")
    else:
        print("\n❌ Failed to create video")

if __name__ == '__main__':
    main()