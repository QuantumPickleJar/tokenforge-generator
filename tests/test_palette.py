from PIL import Image

from tokenforge_local.models import FilamentColor
from tokenforge_local.palette import map_image_to_palette


def test_palette_nearest_color_mapping():
    img = Image.new("RGB", (2, 1))
    img.putpixel((0, 0), (5, 5, 5))
    img.putpixel((1, 0), (250, 250, 250))
    colors = [FilamentColor("Black", "#000000"), FilamentColor("White", "#ffffff")]
    posterized, indices = map_image_to_palette(img, colors)
    assert indices.tolist() == [[0, 1]]
    assert posterized.getpixel((0, 0)) == (0, 0, 0)
    assert posterized.getpixel((1, 0)) == (255, 255, 255)
