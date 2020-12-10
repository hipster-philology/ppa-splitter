# Documentation

The purpose of _Protogenie_ is to prepare data to train a lemmatiser and/or POS tagger.
All available data is split into three different folders (a second command is responsible for "glueing" things together):
1. A train set
2. An development set
3. A testing (or evaluation) set

<span style="color:red; font-weight:bold">_Protogenie_ expects CSV- or TSV-like resources.</span>

After running _Protogenie_, the result should be the following

```txt
FOLDER
|-mydata.tsv
|-OUTPUT
    |-DEV
        |-mydata.tsv
    |-TEST
        |-mydata.tsv
    |-TRAIN
        |-mydata.tsv
```

Using the same example, the repartition of the data between the three folders is done directly with the command line:

```bash
$ protogenie build mydata.tsv -d 0.1 -e 0.1
```

The `-d` (for `development`) and the `-e` (for `evaluation` or testing) flags are followed by a decimal number representing the percentage taken in the original dataset (`0.1`=`10%`). The final breakdown would therefore be the following:

1. 10% for the dev set
2. 10% for the eval/test set
3. 80% for the train set

<span style="color:red; font-weight:bold">_Protogenie_ does not create test sets directly from tokens, but from groups of tokens (_e.g._ sentences). If the dataset is small, the amount of tokens might not be equal to the expected percentages – on the other hand, on rather larger corpora (>200/300k tokens), there should be no problem.</span>


# Configuration file

## Start configuration

To organise such a repartition, _Protogenie_ requires configuration files written in XML. This design choice was made to allow for validation and control of the configuration (this way, if your configuration file is valid but it does not do what it should do, we know it's a bug!).

The scheme used for validation is available inside the package, and with each version by simply typing `protogenie get-scheme [DESTINATION]`. You can also find the latest version here:
 [https://hipster-philology.github.io/protogenie/protogenie/schema.rng](https://hipster-philology.github.io/protogenie/protogenie/schema.rng)

To control that your configuration file is valid and well-formed, we recommend that you use a tool to [validate](#validation) it.

## Validation

While XML validation is not a feature of _Protogenie_, you might be interested in some methods to do that:

- You can install `pip install jingtrang` and then run `pyjing path/to/schema.rng path/to/xml`
- Oxygen XML Editor provides validation while editing.
- Probably [XML Mind Editor](https://www.xmlmind.com/xmleditor/download.shtml) does to.
- Feel free to propose others if you have knowledge we don't

## Basic configuration

Minimal configuration requires:
1. `<corpora>` with, for each `<corpus>`, a `<splitter>` and a `<header>`. It describes how the original data have to be processed (_e.g._ where the file is, and how it has to be split).
2. `<output>` with a `<header>`. It describes how data will be generated (_e.g._ name of the columns in the final file, `.tsv` or `.csv` format).

It should therefore look like the following:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://hipster-philology.github.io/protogenie/protogenie/schema.rng"
     schematypens="http://relaxng.org/ns/structure/1.0"?>
<config>
    <corpora>
        <corpus path="" column_marker="">
            <header /><!-- Need completion-->
            <splitter /><!-- Need completion-->
        </corpus>
    </corpora>
    <output>
        <header /> <!-- Need completion-->
    </output>
</config>
```

The basic function of _Protogenie_ is to help you split your source files and dispatch them among different training sets.
Let's see what we can do [there](#configuring-a-single-corpus)

# Configuring a single corpus

## `<corpus>`

The element `<corpus>` require two attributes:
1. `@path`
2. `@column_marker`

### `@path`

`path` should be the relative path from the configuration file to the corpus file. *ie.* if I have the following
structure:

```
my_corpora/one_file.tsv
my_corpora/two_file.tsv
my_config/config.xml
```

we will have `path='../my_corpora/one_file.tsv'`. It is possible to grab all the files with a joker `path='../my_corpora/*.tsv'`.

### `@column_marker`

Column markers are a simple character that separates columns. If you use tabulations, you need to enter `TAB`.

- CSV file would probably have `column_marker=','`
- TSV file would have `column_marker='TAB'`

## `<header>`

It is possible that you deal with corpus from different providers, hence, possibly following some
different ways to share the data. In this context, we need to know what is what.

The header can follow two different schemes

### When we have no headers in the file

If you have no headers in your source file, you can declare them, by column position (starting from 0) to keys:

```xml
<header type="order">
    <key map-to="form">2</key>
    <key map-to="lemma">0</key>
    <key map-to="POS">1</key>
</header>

```

will map `have;VERB;had` to `lemma=have`, `POS=VERB` and `form=had`. It is very important that you keep your `map-to`
the same across your corpora.

### When you have headers

#### When your headers are clean, and you don't need to change them

Your headers are clean ? Column `lemma` needs to stay `lemma` for your output software ? Then it's simple: you can use
`type='explicit'` and distinguish column you wanna keep

```xml
<header type="explicit">
    <key>lemma</key>
    <key>form</key>
</header>
```

This example will ignore `POS` column if there was one.

#### When your headers differ

Say you have two files, whose headers are respectively: `form;lemma;POS` and `token;lemma;POS`. Well, we got you covered: if you want to map `token` to `form`, simply use the `map-to` attribute:

```xml
<corpora>
    <corpus path="./1.csv" column_marker=";">
        <header type="explicit">
            <key>lemma</key>
            <key>form</key>
            <key>POS</key>
        </header>
    </corpus>
    <corpus path="./2.csv" column_marker=";">
        <header type="explicit">
            <key>lemma</key>
            <!-- key=token is transformed into the map-to value "form" -->
            <key map-to="form">token</key>
            <key>POS</key>
        </header>
    </corpus>
</corpora>
```

#### You have repeating headers ?

Well, this starts to feels like it could be cumbersome... Maybe you could speed up things right ?
We got you covered. You can declare a default header and use it when appropriate with `<header type="default" />`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://hipster-philology.github.io/protogenie/protogenie/schema.rng"
     schematypens="http://relaxng.org/ns/structure/1.0"?>
<config>
    <default-header>
        <header type="explicit">
            <key>lemma</key>
            <key map-to="token">form</key>
            <key>POS</key>
        </header>
    </default-header>
    <corpora>
        <corpus path="./corpus/1.tsv" column_marker="TAB">
            <header type="default" />
        </corpus>
        <corpus path="./corpus/2.tsv" column_marker="TAB">
            <header type="default" />
        </corpus>
        <corpus path="./corpus/3.tsv" column_marker="TAB">
            <header type="default" />
        </corpus>
        <corpus path="./corpus/4.tsv" column_marker="TAB">
            <header type="order">
                <key map-to="token">0</key>
                <key map-to="lemma">1</key>
                <key map-to="POS">2</key>
            </header>
        </corpus>
    </corpora>
</config>
```

## `<splitter>`

Now that we now how to read the files, it's time to cut them ! Splitters are responsible for creating chunks from your
source file. For exemple, if you have 100 sentences and you use the [Regular Expression splitter](#regular-expression-splitter), these
sentences will be treated as single chunk. If you have a training ratio of 0.8, 80 sentences will go to the `train`
folder.

Splitters have a name that you need to enter into the `name` attribute of the `<splitter>` tag. Some splitters
have more configurability than others.

Each splitter is specific to each corpus: you can modify how you split things among your corpora

### File Splitter

The file splitter will simply cut your file at the ration asked. It will treat the file as a continuous stream, and once
reaching your ratio, it will cut the file.

```xml
<splitter name="file_split"/>
```

*eg.*: you use a training ratio of 80%, a dev ratio of 10% and a test ratio of 10% as well. Your source file is 1000
lines long. The 800 first lines with go to `train`, lines 801-900 to `dev` and 901-1000 to `test`.

#### Token Window

The token window splitter will create chunk of *n* (*n*=`window`) tokens. It will treat the file as a continuous stream,
and every *n* token will create a new chunk. It requires a `window` attribute (integer).

```xml
<splitter name="token_window" window="20"/>
```

*eg.*: If you have a window of 20 and 200 lines, you will have (200/20) = 10 chunks. These chunks will be then
dispatched according to your ratio.

### Regular Expression splitter

The punctuation splitter will create chunk when the `matchPattern` attributes matches at least one column.

```xml
<splitter name="regexp" matchPattern="[?\.!]"/>
```

*eg.*: When finding a `.` in a column, with the splitter and matchPattern from the example, the previous tokens will be
put into a chunk.

```
1 1 1
2 2 2
. x x
3 3 3
? x x
```
will split things this way : `(1, 2, .)` and `(3, ?)`

### Empty lines

Some people leave empty lines in a file to differentiate chunks. That makes our life easier potentially, as we can say
an empty line is the end of a chunk.

```xml
<splitter name="empty_line"/>
```

*eg.*: Given the following content:

```
1 1 1
2 2 2

. x x
3 3 3

? x x
```

The empty line splitter will split things this way : `(1, 2)`, `(., 3)`, and `(?)`.

## `<output>`

The `<output>` element allows user to control the format of the dev, train and test files.
If we use the `<default-header>`, it is possible to re-use it the following way:

```xml
<output column_marker="TAB">
    <header name="default"/>
</output>
```

## Post-processing

Protogenie includes post-processing options: those will be run over the output of the previously split files. They are
run sequentially (one after the other) and should be added in the node `<postprocessing>` of `<config>` such as below.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config>
    <output/><!-- Need completion-->
    <postprocessing>
        <!-- Post-processing intervention are found here -->
    </postprocessing>
    <corpora>
        <corpus>
            <splitter /><!-- Need completion-->
            <header /><!-- Need completion-->
        </corpus>
    </corpora>
</config>
```

### Clitic

If your corpus contains tokens separated tokens, you might be interested in rejoining them in order to train your corpus
to recognize specific enclitics or proclitics, such as `Nihilne in mentem?` where `Nihil` and `-ne` are technically
two separate tokens.

The model is the following:

```xml
<config>
    <!--...-->
    <postprocessing>
        <clitic type="enclitic" glue_char="界" matchPattern="^ne2$" source="lemma">
            <transfer>lemma</transfer>
            <transfer no-glue-char="true">token</transfer>
        </clitic>
    </postprocessing>
    <!--...-->
</config>
```

Confronted with the following input

| token | lemma | POS |
| ----- | ----- | --- |
| nihil | nihil | PRO |
| ne | ne2 | CONJ |

It will produces the following output

| token | lemma | POS |
| ----- | ----- | --- |
| nihil*ne* | nihil*界ne2* | PRO |

The glue token is not applied on token, the lemma value is transfered to the previous row and the POS is lost.
`@glue_char` is used to concatenate columns such as `lemma` here,

### Capitalization

This post-processing function capitalizes (*ie.* makes the first letter of words upper-case) randomly or always first 
words of chunks (*ie.* sentences) and random letters inside. It also provides an uppercase mask creation, where it
replaces uppercased letters with lowercase letters the [Neutral Chess Queen UTF-8 character](https://www.compart.com/fr/unicode/U+1FA01).

The model is the following:

```xml
<config>
    <!--...-->
    <postprocessing>
        <capitalize column-token="token" caps-to-utf8-marker="true">
            <first-word when="never">
                <sentence-marker name="empty_line"/>
            </first-word>
            <first-letters when="ratio" ratio="0.5"/>
        </capitalize>
    </postprocessing>
    <!--...-->
</config>
```

1. <kbd>column-token</kbd> specifies the name of the column containing the raw form of the tokens
2. (Optional) <kbd>column-lemma</kbd> does the same thing for lemma
3. <kbd>caps-to-utf8-marker</kbd> activates masking uppercased letters.
4. <kbd>first-word</kbd> is activated when <kbd>when</kbd> is set to a value between `always`, `random` and `ratio`.
    1. <kbd>when="ratio"</kbd> requires a second <kbd>ratio</kbd> value which needs to be a float between .0 and 1.0 (a percentage basically)
    2. <kbd>when=random</kbd> is basically a shortcut for the latter where ratio=0.5
    3. To identify sentences, you need to set up <kbd>sentence-marker</kbd>
        1. It can be <kbd>name="empty_line"</kbd>, in which case chunks are separated by empty line (default output)
        2. It can be <kbd>name="regexp"</kbd>, in which case it takes a `@matchPattern` attribute (for regular expression)
        and a column that needs to be matched in `@source`, *.ie* `<sentence-matcher name="regexp" matchPattern="[\.!?]" source="lemma" />`
5. <kbd>first-letters</kbd> works with the same when/ratio attribute than <kbd>first-word</kbd>. It applies said capitalization
    to random words inside chunks.
     