from dataclasses import dataclass
import re
import math
import requests
import argparse


@dataclass
class Glyph:
    advance: int
    encoding: int
    offsx: int
    offsy: int
    bitmap: list[int]


class FB:
    def __init__(self, width, height):

        self.width = width
        self.height = height
        self.pitch = width + 1
        self.fb = ([" "] * self.width + ["\n"]) * self.height

    def set(self, x, y):

        if (0 <= x < self.width) and (0 <= y < self.height):
            y = self.height - 1 - y

            pos = x + self.pitch * y
            self.fb[pos] = "X"

    def __str__(self):
        return "".join(self.fb)


charpattern = re.compile(
    "STARTCHAR [^\n]+\nENCODING (?P<encoding>[0-9]+)\n.*?DWIDTH (?P<dwidth>[ 0-9]+)\n.*?BBX (?P<bbx>[ 0-9-]+)\n.*?BITMAP\n(?P<bitmap>([0-9A-F]+\n)+)ENDCHAR",
    re.DOTALL,
)


sizepattern = re.compile("SIZE (?P<size>[0-9]+) [0-9]+ [0-9]+\n")

def parse_bdf(fname):

    with open(fname) as f:
        contents = f.read()

    glyphs = {}

    for charmatch in charpattern.finditer(contents):
        # print(charmatch.group(0))
        # print(charmatch.group("bbx"))
        # print()

        encoding = int(charmatch.group("encoding"))
        advance = int(charmatch.group("dwidth").split(" ")[0])
        offsx = int(charmatch.group("bbx").split(" ")[2])
        offsy = int(charmatch.group("bbx").split(" ")[3])

        bitmap = [int(v, 16) for v in charmatch.group("bitmap").split("\n") if v != ""]

        glyph = Glyph(
            advance=advance, encoding=encoding, offsx=offsx, offsy=offsy, bitmap=bitmap
        )

        glyphs[glyph.encoding] = glyph

    font_size = int(sizepattern.search(contents).group("size"))

    return font_size, glyphs


def get_text_width(glyphs, text):

    width = 0
    for letter in text:
        if (glyph := glyphs.get(ord(letter))) :
            width += glyph.advance

    return width


def draw_text(glyphs, fb, x, y, text, line_height):

    start_x = x

    for letter in text:

        if letter == "\n":
            y -= line_height
            x = start_x

        if (glyph := glyphs.get(ord(letter))) :

            for y_index in range(len(glyph.bitmap)):
                draw_y = (len(glyph.bitmap) - 1) - y_index + glyph.offsy
                bitmap_row = glyph.bitmap[y_index]

                padded_width = math.ceil(bitmap_row.bit_length() / 8) * 8
                for x_index in range(padded_width):
                    draw_x = (padded_width - 1) - x_index + glyph.offsx

                    if bitmap_row & (1 << x_index):
                        fb.set(draw_x + x, draw_y + y)

            x += glyph.advance


argparser = argparse.ArgumentParser(description="render bdf fonts to fluepdot")
argparser.add_argument("host", type=str, help="hostname or ip address of the fluepdot")
argparser.add_argument("font_file", type=str, help="bdf font file")
argparser.add_argument("text", type=str, help="text to draw")
argparser.add_argument("-x", type=int, help="x position for drawing text", default=0)
argparser.add_argument("-y", type=int, help="y position for drawing text", default=0)
argparser.add_argument("--line-height", type=int, help="line height in percent of the font size", default=120)
argparser.add_argument(
    "--anchor-x",
    choices=["left", "right", "center"],
    default="left",
    help="set the horizontal anchor point (-x is taken as an offset to this)",
)

args = argparser.parse_args()

font_size, glyphs = parse_bdf(args.font_file)

fb = FB(115, 16)

if args.anchor_x == "center":
    text_width = get_text_width(glyphs, args.text)
    free_space = fb.width - text_width
    # this rounds down, meaning that the text will tend to go left instead
    # of right if it can't be centered exactly
    left_pad = free_space // 2
    args.x += left_pad

elif args.anchor_x == "right":
    text_width = get_text_width(glyphs, args.text)
    free_space = fb.width - text_width
    left_pad = free_space
    args.x += left_pad

draw_text(glyphs, fb, args.x, args.y, args.text, line_height=round(args.line_height / 100 * font_size))
requests.post(f"http://{args.host}/framebuffer", data=str(fb).encode("ascii"))
