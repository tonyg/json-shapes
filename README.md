# JSON-Shapes

JSON-Shapes describe how to

 - *validate* your data
 - *render* your data
 - construct *user interfaces* for manipulating your data
 - *merge* your data
 - *refactor* your data

all with a single, simple syntax.

## Syntax

JSON-Shapes are [polyglot
programs](http://en.wikipedia.org/wiki/Polyglot_%28computing%29),
simultaneously valid when read as any one of

 - a slight extension of JSON itself
 - Javascript source code
 - Python source code

The extensions to JSON are the addition of a function-call-*like* form
to the language:

    identifier(value, value, ...)

the addition of definitions:

    identifier = value;

and support for multiple definitions in a single file.

## Example

...
