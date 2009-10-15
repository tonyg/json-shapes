#!/usr/bin/env python

import sys
import re
import traceback
import types

class InvalidDescriptor(Exception): pass

absent = object()

class Descriptor:
    def match(self, v):
        raise NotImplementedError("Subclass responsibility")

class RegexpDescriptor(Descriptor):
    def __init__(self, pat):
        self.pat = pat
        self.r = re.compile(pat)
    def match(self, v):
        return False if self.r.match(v) else "regexp failed: " + self.pat

class NumberDescriptor(Descriptor):
    def match(self, v):
        return False if isinstance(v, int) or isinstance(v, float) else "Expected number"

class StringDescriptor(Descriptor):
    def match(self, v):
        return False if isinstance(v, str) or isinstance(v, unicode) else "Expected string"

class NonemptyStringDescriptor(Descriptor):
    def match(self, v):
        if (isinstance(v, str) or isinstance(v, unicode)) \
                and len(v) > 0:
            return False
        else:
            return "Expected non-empty string"

class WildDescriptor(Descriptor):
    def match(self, v):
        return False

class NegationDescriptor(Descriptor):
    def __init__(self, t):
        self.t = t
    def match(self, v):
        return False if validate(v, self.t) else "Negation failed"

class MapDescriptor(Descriptor):
    def __init__(self, keyType, valueType):
        self.keyType = keyType
        self.valueType = valueType
    def match(self, v):
        haveResult = False
        result = {}
        for (key, val) in v.iteritems():
            intermediate = validate(key, self.keyType)
            if intermediate:
                result["key " + str(key)] = intermediate
                haveResult = True
            else:
                intermediate = validate(val, self.valueType)
                if intermediate:
                    result["valueAt " + str(key)] = intermediate
                    haveResult = True
        return result if haveResult else False

class ArrayDescriptor(Descriptor):
    def __init__(self, elementType):
        self.elementType = elementType
    def match(self, v):
        haveResult = False
        result = {}
        counter = 0
        for val in v:
            intermediate = validate(val, self.elementType)
            if intermediate:
                result[counter] = intermediate
                haveResult = True
            counter = counter + 1
        return result if haveResult else False

def merge_dicts(*pieces):
    result = {}
    for piece in pieces:
        result.update(piece)
    return result

class OptionalDescriptor(Descriptor):
    def __init__(self, t):
        self.t = t
    def match(self, v):
        return False if v == absent else validate(v, self.t)

class EmailDescriptor(RegexpDescriptor):
    def __init__(self):
        # TODO: better error message
        RegexpDescriptor.__init__(self, r"^\S+@[^.\s]\S*\.[^.\s]{2,}$")

class GeneralAlternationDescriptor(Descriptor):
    def __init__(self, options):
        self.options = options
    def match(self, v):
        result = {}
        for (key, valType) in self.options.iteritems():
            intermediate = validate(v, valType)
            if not intermediate: return False
            result[key] = intermediate
        return result

class NamedAlternationDescriptor(GeneralAlternationDescriptor):
    def __init__(self, options):
        if not (isinstance(options, dict) and options):
            raise InvalidDescriptor("or_dict with non-dictionary or no options")
        GeneralAlternationDescriptor.__init__(self, options)

class PositionalAlternationDescriptor(GeneralAlternationDescriptor):
    def __init__(self, *optionlist):
        if not optionlist:
            raise InvalidDescriptor("_or with no options")
        GeneralAlternationDescriptor.__init__(self, dict(zip(range(len(optionlist)), optionlist)))

class AndDescriptor(Descriptor):
    def __init__(self, *schemas):
        self.schemas = schemas
    def match(self, v):
        for t in self.schemas:
            intermediate = validate(v, t)
            if intermediate: return intermediate
        return False

def validate(v, t):
    if isinstance(t, Descriptor):
        try:
            return t.match(v)
        except:
            (t, v, tb) = sys.exc_info()
            err = '\n'.join(traceback.format_exception_only(t, v))
            return "Predicate failed: " + err

    if v == t:
        return False

    if type(v) != type(t):
        return "Type mismatch: expected " + str(type(t))

    if type(t) == dict:
        if not t.get("_extensible", False):
            # Ensure there's nothing in the object that the schema doesn't have.
            extraKeys = set(v) - (set(t) - set(["_extensible"]))
            if extraKeys: return "Unexpected properties: " + (', '.join(extraKeys))
        haveResult = False
        result = {}
        for (key, valType) in t.iteritems():
            if not key == "_extensible":
                intermediate = validate(v.get(key, absent), valType)
                if intermediate:
                    haveResult = True
                    result[key] = intermediate
        return result if haveResult else False
    elif type(t) == list:
        if len(v) != len(t):
            return "Length mismatch: expected array of length " + str(len(t))
        haveResult = False
        result = {}
        for i in range(len(t)):
            intermediate = validate(v[i], t[i])
            if intermediate:
                haveResult = True
                result[str(i)] = intermediate
        return result if haveResult else False
    else:
        return "Value mismatch: expected " + str(t)

global_environment = {
    'regexp': RegexpDescriptor,
    'nonempty_string': NonemptyStringDescriptor,
    'dictionary': MapDescriptor,
    'array_of': ArrayDescriptor,
    'merge': merge_dicts,
    'optional': OptionalDescriptor,
    'email': EmailDescriptor,
    'or_dict': NamedAlternationDescriptor,
    'number': NumberDescriptor,
    'string': StringDescriptor,
    'anything': WildDescriptor,
    '_not': NegationDescriptor,
    '_or': PositionalAlternationDescriptor,
    '_and': AndDescriptor,
    'true': True,
    'false': False,
    'null': None
}

def load_schema(filename, extendingEnvironment = None):
    f = file(filename)
    q = f.read()
    f.close()
    results = dict(extendingEnvironment or {})
    exec q in global_environment, results
    return results

if __name__ == '__main__':
    env = {}
    for arg in sys.argv[1:-1]:
        env = load_schema(arg, env)

    typename = sys.argv[-1]
    t = env[typename]

    try:
        import json
    except ImportError:
        import simplejson as json

    v = json.loads(sys.stdin.read())
    result = validate(v, t)
    if result:
        print json.dumps(result)
        sys.exit(1)
    else:
        sys.exit(0)
