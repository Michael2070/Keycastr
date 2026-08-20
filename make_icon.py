"""生成 ShortcutNotifier 的程序图标 icon.ico"""
from PIL import Image, ImageDraw


def make_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = max(2, size // 32)
    d.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size // 5, fill='#2D2B3E',
        outline='#FFFFFF', width=max(2, size // 24))
    gap = size // 12
    cols, rows = 4, 3
    kw = (size - 4 * gap - (cols - 1) * gap) // cols
    kh = (size - 4 * gap - (rows - 1) * gap) // rows
    for r in range(rows):
        for c in range(cols):
            x0 = 2 * gap + c * (kw + gap)
            y0 = 2 * gap + r * (kh + gap)
            d.rounded_rectangle(
                [x0, y0, x0 + kw, y0 + kh],
                radius=max(2, size // 32), fill='#ECF0F1')
    dot_r = max(2, size // 14)
    d.ellipse(
        [size - 3 * gap - dot_r, size - 3 * gap - dot_r,
         size - 3 * gap + dot_r, size - 3 * gap + dot_r],
        fill='#2ECC71', outline='#FFFFFF', width=max(2, size // 32))
    return img


if __name__ == '__main__':
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [make_icon(s) for s in sizes]
    images[-1].save(
        'icon.ico', format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1])
    print('icon.ico 已生成')
