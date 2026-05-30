"""
generate_thumbnail.py — Generate a movie poster-style thumbnail using Pillow + FFmpeg.

Output: 1280×720 JPG with:
  - Best frame from the hook scene (background)
  - Dark gradient overlay
  - Movie title text (top-left)
  - Cherry Drama watermark (bottom-right)
"""
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

THUMBNAIL_W = 1280
THUMBNAIL_H = 720
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../assets/logo.jpg")

_FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FALLBACK_FONTS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _extract_frame(video_path: str, timestamp: float, output_path: str) -> bool:
    """Extract a single frame from the video at the given timestamp. Returns success bool."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(max(0.0, timestamp)),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return os.path.exists(output_path)
    except subprocess.CalledProcessError:
        return False


def generate_thumbnail(
    video_path: str,
    movie_title: str,
    hook_timestamp: float,
    output_path: str,
) -> None:
    """
    Generate a movie poster-style thumbnail.

    Args:
        video_path:      Path to the source video.
        movie_title:     Title text to overlay.
        hook_timestamp:  Timestamp for the background frame (hook scene).
        output_path:     Where to save the thumbnail (.jpg).
    """
    thumb_dir = os.path.dirname(output_path)
    os.makedirs(thumb_dir, exist_ok=True)
    frame_path = os.path.join(thumb_dir, "_thumb_frame.jpg")

    # ── 1. Extract frame from hook scene ─────────────────────────────────────
    got_frame = _extract_frame(video_path, hook_timestamp, frame_path)

    if got_frame:
        bg = Image.open(frame_path).convert("RGB")
        bg = bg.resize((THUMBNAIL_W, THUMBNAIL_H), Image.LANCZOS)
    else:
        bg = Image.new("RGB", (THUMBNAIL_W, THUMBNAIL_H), color=(26, 10, 15))

    # ── 2. Dark gradient overlay ──────────────────────────────────────────────
    overlay = Image.new("RGBA", (THUMBNAIL_W, THUMBNAIL_H))
    draw_ov = ImageDraw.Draw(overlay)
    for y in range(THUMBNAIL_H):
        alpha = int(120 + 100 * (y / THUMBNAIL_H))
        draw_ov.line([(0, y), (THUMBNAIL_W, y)], fill=(0, 0, 0, alpha))
    bg = bg.convert("RGBA")
    bg = Image.alpha_composite(bg, overlay).convert("RGB")

    draw = ImageDraw.Draw(bg)

    # ── 3. "Cherry Drama" badge (top-left) ────────────────────────────────────
    badge_font = _load_font(28)
    badge_text = "Cherry Drama"
    draw.rectangle([30, 28, 220, 62], fill=(194, 24, 91))
    draw.text((40, 32), badge_text, font=badge_font, fill=(255, 255, 255))

    # ── 4. Movie title (left side, lower area) ────────────────────────────────
    title_font = _load_font(64)
    small_font = _load_font(32)

    # Word-wrap title to fit ~900px width
    words = movie_title.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=title_font)
        if bbox[2] > 860 and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    y_title = THUMBNAIL_H - 180
    for line in lines[:3]:
        draw.text((50, y_title), line, font=title_font, fill=(255, 255, 255),
                  stroke_width=2, stroke_fill=(0, 0, 0))
        y_title += 72

    # ── 5. "Recap" label ──────────────────────────────────────────────────────
    draw.text((50, THUMBNAIL_H - 50), "Recap", font=small_font, fill=(255, 179, 204),
              stroke_width=1, stroke_fill=(0, 0, 0))

    # ── 6. Logo watermark (bottom-right) ─────────────────────────────────────
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_h = 80
            ratio = logo_h / logo.height
            logo_w = int(logo.width * ratio)
            logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

            # Semi-transparent logo
            r, g, b, a = logo.split()
            a = a.point(lambda x: int(x * 0.8))
            logo = Image.merge("RGBA", (r, g, b, a))

            pos = (THUMBNAIL_W - logo_w - 30, THUMBNAIL_H - logo_h - 20)
            bg = bg.convert("RGBA")
            bg.paste(logo, pos, logo)
            bg = bg.convert("RGB")
        except Exception as exc:
            print(f"[thumbnail] Logo overlay failed (continuing): {exc}", flush=True)

    # ── 7. Save ───────────────────────────────────────────────────────────────
    bg.save(output_path, "JPEG", quality=92, optimize=True)

    if os.path.exists(frame_path):
        try:
            os.unlink(frame_path)
        except OSError:
            pass

    print(f"[thumbnail] Saved: {output_path}", flush=True)
