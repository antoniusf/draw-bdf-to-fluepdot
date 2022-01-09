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

def symbol_iterator(characters):

    previous_was_backslash = False

    for character in characters:

        if previous_was_backslash:
            if character == "n":
                yield "\n"

            elif character == "\\":
                yield "\\"

            elif character == "h":
                yield "hfill"

            else:
                yield character

            previous_was_backslash = False

        elif character == "\\":
            previous_was_backslash = True

        else:
            yield character


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
    for symbol in symbol_iterator(text):
        if symbol == "hfill":
            continue

        letter = symbol

        if (glyph := glyphs.get(ord(letter))) :
            width += glyph.advance

    return width


def draw_text(glyphs, fb, x, y, text, line_height, space_per_hfill):

    start_x = x

    for symbol in symbol_iterator(text):

        if symbol == "hfill":
            x += space_per_hfill
            continue

        letter = symbol

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
                        fb.set(draw_x + int(x), draw_y + y)

            x += glyph.advance


argparser = argparse.ArgumentParser(description="render bdf fonts to fluepdot")
argparser.add_argument("host", type=str, help="hostname or ip address of the fluepdot")
argparser.add_argument("font_file", type=str, help="bdf font file")
argparser.add_argument("text", type=str, help="text to draw")
argparser.add_argument("-y", type=int, help="y position for drawing text", default=0)
argparser.add_argument("--line-height", type=int, help="line height in percent of the font size", default=120)
argparser.add_argument("--margin-left", type=int, help="distance from text to left edge of the display", default=0)
argparser.add_argument("--margin-right", type=int, help="dinstance from text to right edge of the display", default=0)

args = argparser.parse_args()

print(str(args.text))

font_size, glyphs = parse_bdf(args.font_file)

fb = FB(115, 16)

number_of_hfills = sum(1 if symbol == "hfill" else 0 for symbol in symbol_iterator(args.text))
print(number_of_hfills)

if number_of_hfills > 0:
    text_width = get_text_width(glyphs, args.text)
    free_space = fb.width - text_width - args.margin_left - args.margin_right
    space_per_hfill = free_space / number_of_hfills
    print(space_per_hfill)

else:
    space_per_hfill = None

draw_text(glyphs, fb, args.margin_left, args.y, args.text, line_height=round(args.line_height / 100 * font_size), space_per_hfill=space_per_hfill)
print(str(fb))
#requests.post(f"http://{args.host}/framebuffer", data=str(fb).encode("ascii"))
