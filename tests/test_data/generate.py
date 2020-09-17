import random
import string

# Change one variable to regenerate a test file
generate_implicit = False
generate_clitics = False
generate_roman = False
generate_skip = False
generate_replacement = False
generate_disambiguation = False
generate_file = False
generate_empty_line = False
generate_sentence = False
generate_window = False
generate_capitalize = False
generate_generic = True

ROMAN_NUMERAL_TABLE = [
    ("M", 1000), ("CM", 900), ("D", 500),
    ("CD", 400), ("C", 100),  ("XC", 90),
    ("L", 50),   ("XL", 40),  ("X", 10),
    ("IX", 9),   ("V", 5),    ("IV", 4),
    ("I", 1)
]


def roman_number(number: int) -> str:
    """ Convert an integer to Roman
    Source : https://codereview.stackexchange.com/a/147718
    Thanks to https://codereview.stackexchange.com/users/119968/alex """
    roman_numerals = []
    for numeral, value in ROMAN_NUMERAL_TABLE:
        count, number = divmod(number, value)
        roman_numerals.append(numeral * count)

    return ''.join(roman_numerals)


def randomString(start: str = "", length: int = 10) -> str:
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return start+''.join(random.choice(letters) for i in range(length-len(start)))


# I am using different numbers of sequence size to be sure tests are not being right on another corpus
if generate_window:  # Make false to remove running
    with open("window.tsv", "w") as f:
        f.write("lem\tpos\ttok\n")
        for lines in range(200):
            f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                rand1=randomString(start="lem_", length=10),
                rand2=randomString(start="pos_", length=10),
                rand3=randomString(start="tok_", length=10)
            ))

if generate_sentence:
    with open("sentence.tsv", "w") as f:
        f.write("lem\tpos\ttok\n")
        for lines in range(190):
            if (lines + 1) % 19 == 0:
                f.write(".\tPONfor\t.\n")
            else:
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1=randomString(start="lem_", length=10),
                    rand2=randomString(start="pos_", length=10),
                    rand3=randomString(start="tok_", length=10)
                ))


if generate_empty_line:
    with open("empty_line.tsv", "w") as f:
        f.write("lem\tpos\ttok\n")
        for lines in range(180):
            f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                rand1=randomString(start="lem_", length=10),
                rand2=randomString(start="pos_", length=10),
                rand3=randomString(start="tok_", length=10)
            ))
            if (lines + 1) % 18 == 0:
                f.write("\n")

if generate_file:
    with open("file.tsv", "w") as f:
        f.write("lem\tpos\ttok\n")
        for lines in range(170):
            f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                rand1=randomString(start="lem_", length=10),
                rand2=randomString(start="pos_", length=10),
                rand3=randomString(start="tok_", length=10)
            ))

if generate_implicit:
    with open("implicit.tsv", "w") as f:
        for lines in range(160):
            f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                rand1=randomString(start="lem_", length=10),
                rand2=randomString(start="pos_", length=10),
                rand3=randomString(start="tok_", length=10)
            ))


if generate_disambiguation:
    with open("disambiguation.tsv", "w") as f:
        for lines in range(150):
            f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                rand1=randomString(start="lem_", length=10)+str(random.randint(0, 10)),
                rand2=randomString(start="pos_", length=10)+str(random.randint(0, 10)),
                rand3=randomString(start="tok_", length=10)+str(random.randint(0, 10))
            ))

if generate_replacement:
    at_least_one_zero = False
    at_least_one_one = False
    with open("replacement.tsv", "w") as f:
        for lines in range(140):
            if lines % 7 == 0:
                if not at_least_one_one:
                    rndint = 1
                    at_least_one_one = True
                elif at_least_one_zero:
                    rndint = 0
                    at_least_one_zero = True
                else:
                    rndint = random.randint(0, 10)
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1=rndint,
                    rand2=rndint,  # Keeping it in POS to keep track of the original value in tests
                    rand3=rndint
                ))
            else:
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1=randomString(start="lem_", length=10),
                    rand2=randomString(start="pos_", length=10),
                    rand3=randomString(start="tok_", length=10)
                ))

if generate_skip:
    at_least_one_zero = False
    at_least_one_one = False
    with open("skip.tsv", "w") as f:
        for lines in range(200):
            if (lines + 1) % 10 == 0:
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1="removed_by_pos",
                    rand2="PUNfrt",
                    rand3="lala"
                ))
            elif (lines + 1) % 5 == 0:
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1=".",
                    rand2="removed_by_token",
                    rand3="."
                ))
            else:
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1=randomString(start="lem_", length=10),
                    rand2=randomString(start="pos_", length=10),
                    rand3=randomString(start="tok_", length=10)
                ))

            if (lines + 1) % 20 == 0:
                f.write("\n")


if generate_roman:
    at_least_one_zero = False
    at_least_one_one = False
    with open("roman_numbers.tsv", "w") as f:
        for lines in range(300):
            if (lines + 1) % 5 == 0:
                randint = roman_number(random.randint(1, 5000))
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1=randint,
                    rand2="RomNum",
                    rand3=randint
                ))
            else:
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1=randomString(start="lem_", length=10),
                    rand2=randomString(start="pos_", length=10),
                    rand3=randomString(start="tok_", length=10)
                ))

            if (lines + 1) % 10 == 0: # Window of 10...
                f.write("\n")

if generate_clitics:
    with open("clitics.tsv", "w") as f:
        for lines in range(300):
            if (lines + 1) % 5 == 0:
                f.write("ne\tPOS\tne\n")
            else:
                f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                    rand1=randomString(start="lem_", length=10),
                    rand2=randomString(start="pos_", length=10),
                    rand3=randomString(start="tok_", length=10)
                ))

            if (lines + 1) % 10 == 0:  # Window of 10...
                f.write("\n")

if generate_capitalize:
    with open("capitalize.tsv", "w") as f:
        for lines in range(500):
            f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                rand1=randomString(start="lem_", length=10),
                rand2=randomString(start="pos_", length=10),
                rand3=randomString(start="tok_", length=10)
            ))

            if (lines + 1) % 10 == 0:  # Window of 10...
                f.write("\n")

if generate_generic:
    with open("generic.tsv", "w") as f:
        for lines in range(500):
            f.write("{rand1}\t{rand2}\t{rand3}\n".format(
                rand1=randomString(start="lem_", length=10),
                rand2=randomString(start="pos_", length=10),
                rand3=randomString(start="tok_", length=10)
            ))

            if (lines + 1) % 10 == 0:  # Window of 10...
                f.write("\n")
