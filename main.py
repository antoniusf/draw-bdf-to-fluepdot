from dataclasses import dataclass
import re
import math
import requests

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


charpattern = re.compile("STARTCHAR [^\n]+\nENCODING (?P<encoding>[0-9]+)\n.*?DWIDTH (?P<dwidth>[ 0-9]+)\n.*?BBX (?P<bbx>[ 0-9-]+)\n.*?BITMAP\n(?P<bitmap>([0-9A-F]+\n)+)ENDCHAR", re.DOTALL)

def parse_bdf(fname):

    with open(fname) as f:
        contents = f.read()

    glyphs = {}

    for charmatch in charpattern.finditer(contents):
        #print(charmatch.group(0))
        #print(charmatch.group("bbx"))
        #print()

        encoding = int(charmatch.group("encoding"))
        advance = int(charmatch.group("dwidth").split(" ")[0])
        offsx = int(charmatch.group("bbx").split(" ")[2])
        offsy = int(charmatch.group("bbx").split(" ")[3])

        bitmap = [int(v, 16) for v in charmatch.group("bitmap").split("\n") if v != ""]

        glyph = Glyph(
                advance=advance,
                encoding=encoding,
                offsx=offsx,
                offsy=offsy,
                bitmap=bitmap
                )

        glyphs[glyph.encoding] = glyph

    return glyphs

def draw_text(glyphs, fb, x, y, text):

    for letter in text:
        if (glyph := glyphs.get(ord(letter))):

            for y_index in range(len(glyph.bitmap)):
                draw_y = (len(glyph.bitmap) - 1) - y_index + glyph.offsy
                bitmap_row = glyph.bitmap[y_index]

                padded_width = math.ceil(bitmap_row.bit_length() / 8) * 8
                for x_index in range(padded_width):
                    draw_x = (padded_width - 1) - x_index + glyph.offsx

                    if bitmap_row & (1 << x_index):
                        fb.set(draw_x + x, draw_y + y)

            x += glyph.advance

glyphs = parse_bdf("gerhard-12.bdf")

fb = FB(115, 16)
draw_text(glyphs, fb, 10, 3, "2021-06-02 Wed.")
requests.post("http://<put-fluepdot-ip-here>/framebuffer", data=str(fb).encode("ascii"))
