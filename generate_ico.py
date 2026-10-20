from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

def create_icon_image(size: int = 256) -> Image.Image:
    # Scale coordinates proportionally to size
    scale = size / 256.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def s(val):
        return val * scale

    # Outer ambient glow
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((s(30), s(15), s(226), s(211)), fill=(124, 102, 220, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=s(10)))
    img.alpha_composite(glow)

    draw = ImageDraw.Draw(img)

    # Bulb glass dome
    # Main bulb circle + neck
    draw.ellipse((s(46), s(26), s(210), s(190)), fill="#8b5cf6", outline="#ffffff", width=max(1, int(s(4))))
    
    # Inner radial highlight on dome
    draw.ellipse((s(65), s(45), s(140), s(120)), fill="#a78bfa")
    draw.ellipse((s(75), s(52), s(115), s(92)), fill="#c4b5fd")
    draw.ellipse((s(82), s(58), s(102), s(78)), fill="#ffffff")

    # Bulb base neck transition
    draw.polygon([
        (s(80), s(165)),
        (s(176), s(165)),
        (s(164), s(205)),
        (s(92), s(205))
    ], fill="#7c66dc", outline="#ffffff", width=max(1, int(s(3))))

    # 3D Cinema Glasses over the bulb (stylized cinema theme)
    # Glasses frame
    frame_y = s(100)
    # Left red lens
    draw.rounded_rectangle((s(68), frame_y, s(120), frame_y + s(38)), radius=s(6), fill="#ef4444", outline="#0f172a", width=max(1, int(s(4))))
    # Right cyan lens
    draw.rounded_rectangle((s(136), frame_y, s(188), frame_y + s(38)), radius=s(6), fill="#06b6d4", outline="#0f172a", width=max(1, int(s(4))))
    # Bridge
    draw.rectangle((s(118), frame_y + s(10), s(138), frame_y + s(20)), fill="#0f172a")
    # Brow bar
    draw.line((s(60), frame_y + s(2), s(196), frame_y + s(2)), fill="#0f172a", width=max(2, int(s(5))))
    # Temples
    draw.line((s(52), frame_y + s(6), s(68), frame_y + s(6)), fill="#0f172a", width=max(2, int(s(5))))
    draw.line((s(188), frame_y + s(6), s(204), frame_y + s(6)), fill="#0f172a", width=max(2, int(s(5))))

    # Screw base
    screw_y = s(195)
    draw.rounded_rectangle((s(94), screw_y, s(162), screw_y + s(42)), radius=s(4), fill="#475569", outline="#334155", width=max(1, int(s(2))))
    
    # Thread lines
    draw.line((s(96), screw_y + s(10), s(160), screw_y + s(10)), fill="#94a3b8", width=max(1, int(s(3))))
    draw.line((s(96), screw_y + s(22), s(160), screw_y + s(22)), fill="#64748b", width=max(1, int(s(3))))
    draw.line((s(98), screw_y + s(33), s(158), screw_y + s(33)), fill="#94a3b8", width=max(1, int(s(3))))

    # Contact point
    draw.polygon([
        (s(108), screw_y + s(42)),
        (s(148), screw_y + s(42)),
        (s(140), screw_y + s(54)),
        (s(116), screw_y + s(54))
    ], fill="#cbd5e1", outline="#94a3b8", width=max(1, int(s(2))))

    return img

def generate_ico(output_path: Path):
    sizes = [256, 128, 64, 48, 32, 16]
    images = [create_icon_image(sz) for sz in sizes]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        output_path,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=images[1:]
    )
    print(f"Generated ICO at: {output_path}")

if __name__ == "__main__":
    work_dir = Path(__file__).resolve().parent
    generate_ico(work_dir / "luzcinema.ico")
    generate_ico(work_dir.parent / "outputs" / "LuzCinema" / "luzcinema.ico")
    generate_ico(work_dir.parent / "luzcinema.ico")
