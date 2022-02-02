from dataclasses import dataclass
import re
import math
#import requests
import argparse
import os.path

@dataclass
class Glyph:
    advance: int
    encoding: int
    width: int
    offsx: int
    offsy: int
    bitmap: list[int]

@dataclass
class Font:
    font_size: int
    glyphs: dict[Glyph]

    def get_text_width(self, text):

        width = 0
        for letter in text[:-1]:
            if (glyph := self.glyphs.get(ord(letter))) :
                width += glyph.advance

        # last letter gets special treatment, we don't want to 
        # add the space past the last letter
        if (glyph := self.glyphs.get(ord(letter))):
            width += glyph.width + glyph.offsx

        return width


class FB:
    def __init__(self, width, height):

        self.width = width
        self.height = height
        self.pitch = width + 1
        self.fb = ([" "] * self.width + ["\n"]) * self.height

    def set(self, x, y, fill=True):

        if (0 <= x < self.width) and (0 <= y < self.height):

            pos = x + self.pitch * y

            if fill:
                self.fb[pos] = "X"
            else:
                self.fb[pos] = " "

    def __str__(self):
        return "".join(self.fb)

    def draw_text(self, font, align, left, right, top, bottom, text, fill=True):

        glyphs = font.glyphs

        # note: bottom and right are exclusive values, meaning
        # they are the coordinates of the first pixels that
        # aren't part of the draw area anymore. for right,
        # this isn't noticeable -- (right - left) is still the
        # total amount of space available, and we'll start drawing
        # from the left anyways. for bottom though, we'll actually
        # set the lowest pixels, so we have to compensate and add one.
        # (see below)

        text_size = font.get_text_width(text)
        space = right - left - text_size

        if align == "left":
            left = left

        elif align == "center":
            left = left + space//2

        elif align == "right":
            left = left + space

        x = left

        for letter in text:

            if (glyph := glyphs.get(ord(letter))) :

                for y_index in range(len(glyph.bitmap)):
                    draw_y = - (len(glyph.bitmap) - 1) + y_index - glyph.offsy
                    bitmap_row = glyph.bitmap[y_index]

                    padded_width = math.ceil(bitmap_row.bit_length() / 8) * 8
                    for x_index in range(padded_width):
                        draw_x = (padded_width - 1) - x_index + glyph.offsx

                        if bitmap_row & (1 << x_index):
                            # see note above on why it's (bottom - 1)
                            self.set(draw_x + int(x), draw_y + bottom - 1, fill)

                x += glyph.advance


    def draw_rect(self, left, right, top, bottom, fill=True):

        for x in range(left, right):
            for y in range(top, bottom):
                self.set(x, y, fill=fill)


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
        width = int(charmatch.group("bbx").split(" ")[0])
        offsx = int(charmatch.group("bbx").split(" ")[2])
        offsy = int(charmatch.group("bbx").split(" ")[3])

        bitmap = [int(v, 16) for v in charmatch.group("bitmap").split("\n") if v != ""]

        glyph = Glyph(
            advance=advance, encoding=encoding, width=width, offsx=offsx, offsy=offsy, bitmap=bitmap
        )

        glyphs[glyph.encoding] = glyph

    font_size = int(sizepattern.search(contents).group("size"))

    return Font(font_size, glyphs)

if __name__ == "__main__":

    fb = FB(115, 16)

    riley_5 = parse_bdf("/home/antonius/RILEY-5.bdf")
    fb.draw_text(riley_5, "center", 2, 17, 2, 7, "SUN")
    fb.draw_rect(1, 18, 8, 15)
    fb.draw_text(riley_5, "left", 2, 17, 9, 14, "EB", fill=False)

    fb.draw_rect(19, 38, 0, 16)
    fb.draw_rect(20, 37, 1, 15, fill=False)
    fb.draw_text(riley_5, "center", 21, 36, 2, 7, "MON")
    fb.draw_rect(20, 37, 8, 15)
    fb.draw_text(riley_5, "left", 21, 36, 9, 14, "EBDP", fill=False)

    print(str(fb))
    #requests.post(f"http://{args.host}/framebuffer", data=str(fb).encode("ascii"))
