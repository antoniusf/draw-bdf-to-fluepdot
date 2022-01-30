from dataclasses import dataclass
import re
import math
import requests
import argparse

class ParseError(RuntimeError):
    pass

@dataclass
class Grid:
    column_offsets: list[int]
    row_offsets: list[int]

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
    glyphs: list[Glyph]


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

def pixel_iterator(numbers):

    pos = 0
    while pos < len(numbers):
        yield (numbers[pos], numbers[pos + 1])
        pos += 2


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

    return font_size, glyphs


def get_text_width(glyphs, text):

    width = 0
    for letter in text[:-1]:
        if (glyph := glyphs.get(ord(letter))) :
            width += glyph.advance

    # last letter gets special treatment, we don't want to 
    # add the space past the last letter
    if (glyph := glyphs.get(ord(letter))):
        width += glyph.width + glyph.offsx

    return width


def draw_text(glyphs, fb, x, y, text, fill=True):

    start_x = x

    for symbol in symbol_iterator(text):

        letter = symbol

        if (glyph := glyphs.get(ord(letter))) :

            for y_index in range(len(glyph.bitmap)):
                draw_y = - (len(glyph.bitmap) - 1) + y_index - glyph.offsy
                bitmap_row = glyph.bitmap[y_index]

                padded_width = math.ceil(bitmap_row.bit_length() / 8) * 8
                for x_index in range(padded_width):
                    draw_x = (padded_width - 1) - x_index + glyph.offsx

                    if bitmap_row & (1 << x_index):
                        fb.set(draw_x + int(x), draw_y + y, fill)

            x += glyph.advance

def parse_point_list(string):

    if string == "":
        return []

    if not re.fullmatch(r"[0-9]+( [0-9]+)*", string):
        raise ValueError("Invalid string format")

    numbers = string.split(" ")
    if len(numbers) % 2 != 0:
        raise ValueError("Uneven number of values, they must always be given in x-y-pairs")

    return [int(number) for number in numbers]


argparser = argparse.ArgumentParser(description="render bdf fonts to fluepdot")
argparser.add_argument("host", type=str, help="hostname or ip address of the fluepdot")
argparser.add_argument("--font_file", type=str, action="append", help="bdf font file(s) to load. can be specified multiple times")

args = argparser.parse_args()

fonts = []

for filename in args.font_file:
    font_size, glyphs = parse_bdf(filename)
    fonts.append(Font(font_size, glyphs))

def parse_row_or_column(line):

    assert line.startswith("  ")
    tokens = []

    for token in line.split():
        if not re.fullmatch("[0-9]+|fill", token):
            raise ParseError(f"Unknown token in row or column definition: '{token}'")

        if re.fullmatch("[0-9]+", token):
            token = int(token)

        tokens.append(token)

    return tokens

def compute_fill_size(tokens, total_size):

    used_space = sum(token for token in tokens if type(token) == int)
    free_space = total_size - used_space

    if free_space > 0:
        num_fills = tokens.count("fill")
        fill_size = int(free_space / num_fills)

    return [fill_size if token == "fill" else token for token in tokens]


def cumsum(numbers):

    total = 0
    result = [0]

    for number in numbers:
        total += number
        result.append(total)

    return result

def handle_element(line, grid, fb, fonts):

    op, line = line.split(maxsplit=1)

    if op == "fill-text" or op == "unfill-text":
        align, left, right, top, bottom, text = line.split(maxsplit=5)
        left = grid.column_offsets[int(left)]
        right = grid.column_offsets[int(right)]
        top = grid.row_offsets[int(top)]
        # bottom is *exclusive* the value from the grid, since that's
        # where the next element already begins. hence the -1
        bottom = grid.row_offsets[int(bottom)] - 1

        text_size = get_text_width(fonts[0].glyphs, text)
        space = right - left - text_size

        if align == "left":
            left = left

        elif align == "center":
            left = left + space//2

        elif align == "right":
            left = left + space

        print(left, right, space, bottom)

        draw_text(fonts[0].glyphs, fb, left, bottom, text, fill=op.startswith("fill"))

    elif op == "fill-rect" or op == "unfill-rect":
        left, right, top, bottom = line.split()

        for x in range(grid.column_offsets[int(left)], grid.column_offsets[int(right)]):
            for y in range(grid.row_offsets[int(top)], grid.row_offsets[int(bottom)]):
                fb.set(x, y, fill=op.startswith("fill"))


# read input
modes = ["expect column header", "columns", "rows", "elements"]
mode = modes[0]

grid = Grid([], [])
fb = FB(115, 16)

while True:
    line = input()

    if line == "":
        continue

    if mode == "expect column header":
        if line != "columns:":
            raise ParseError("Expected column header like so: 'columns:', without any whitespace")

        mode = "columns"

    elif mode == "columns":
        if line.startswith("  "):
            # parse column
            grid.column_offsets.extend(cumsum(compute_fill_size(parse_row_or_column(line), fb.width)))
        elif line == "rows:":
            mode = "rows"
        else:
            raise ParseError("Expected either a column definition (line starting with two spaces), or a row header like so: 'rows:', without any whitespace")

    elif mode == "rows":
        if line.startswith("  "):
            # parse row
            grid.row_offsets.extend(cumsum(compute_fill_size(parse_row_or_column(line), fb.height)))
        elif line == "elements:":
            mode = "elements"
            print(grid)
        else:
            raise ParseError("Expected either a row definition (line starting with two spaces), or an elements header like so: 'elements:', without any whitespace")

    elif mode == "elements":
        if line.startswith("  "):
            handle_element(line, grid, fb, fonts)
        elif line == "end":
            break
        else:
            raise ParseError("Expected either an element definition (line starting with two spaces), or an end token like so: 'end', without any whitespace")

        print(str(fb))



#draw_text(glyphs, fb, args.margin_left, args.y, args.text, line_height=round(args.line_height / 100 * font_size), space_per_hfill=space_per_hfill)

#for pixel in pixel_iterator(args.set_pixels):

#    fb.set(pixel[0], pixel[1])

print(str(fb))
#requests.post(f"http://{args.host}/framebuffer", data=str(fb).encode("ascii"))
