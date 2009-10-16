#!/usr/bin/env python

import sys
import re
import traceback
import types
import operator

class InvalidDescriptor(Exception): pass

class AbsentValue:
    def __init__(self, name):
        self.name = name
    def __eq__(self, other):
        return is_absent(other)
    def __str__(self):
        return repr(self)
    def __repr__(self):
        return 'AbsentValue(%s)' % (self.name,)

def is_absent(v):
    return isinstance(v, AbsentValue)

class Descriptor:
    def validate(self, v):
        try:
            return self._validate(v)
        except:
            (t, v, tb) = sys.exc_info()
            err = '\n'.join(traceback.format_exception(t, v, tb))
            return "Predicate failed: " + err

    def _validate(self, v):
        raise NotImplementedError("Subclass responsibility")

class RegexpDescriptor(Descriptor):
    def __init__(self, pat):
        self.pat = pat
        self.r = re.compile(pat)
    def _validate(self, v):
        return False if self.r.match(v) else "regexp failed: " + self.pat

class NumberDescriptor(Descriptor):
    def _validate(self, v):
        return False if isinstance(v, int) or isinstance(v, float) else "Expected number"

class StringDescriptor(Descriptor):
    def _validate(self, v):
        return False if isinstance(v, str) or isinstance(v, unicode) else "Expected string"

class BooleanDescriptor(Descriptor):
    def _validate(self, v):
        return False if isinstance(v, bool) else "Expected boolean"

class NonemptyStringDescriptor(StringDescriptor):
    def _validate(self, v):
        return StringDescriptor._validate(self, v) or \
               (False if len(v) > 0 else "Expected non-empty string")

class ExactLiteralValueValidatorMixin:
    def __init__(self, literal):
        self.literal = literal
    def _validate(self, v):
        if v == self.literal:
            return False

        if type(v) != type(self.literal):
            return "Type mismatch: expected " + str(type(self.literal))
        else:
            return "Value mismatch: expected " + repr(self.literal)

class ExactStringDescriptor(ExactLiteralValueValidatorMixin, StringDescriptor): pass
class ExactNumberDescriptor(ExactLiteralValueValidatorMixin, NumberDescriptor): pass
class ExactBooleanDescriptor(ExactLiteralValueValidatorMixin, BooleanDescriptor): pass

class ExactNullDescriptor(Descriptor):
    def _validate(self, v):
        return False if v is None else "Expected null"

class WildDescriptor(Descriptor):
    def _validate(self, v):
        return False

class NegationDescriptor(Descriptor):
    def __init__(self, t):
        self.t = expand(t)
    def _validate(self, v):
        return False if self.t.validate(v) else "Negation failed"

class MapDescriptor(Descriptor):
    def __init__(self, keyType, valueType):
        self.keyType = expand(keyType)
        self.valueType = expand(valueType)
    def _validate(self, v):
        haveResult = False
        result = {}
        for (key, val) in v.iteritems():
            intermediate = self.keyType.validate(key)
            if intermediate:
                result["key " + str(key)] = intermediate
                haveResult = True
            else:
                intermediate = self.valueType.validate(val)
                if intermediate:
                    result["valueAt " + str(key)] = intermediate
                    haveResult = True
        return result if haveResult else False

class ArrayDescriptor(Descriptor):
    def __init__(self, elementType):
        self.elementType = expand(elementType)
    def _validate(self, v):
        haveResult = False
        result = {}
        counter = 0
        for val in v:
            intermediate = self.elementType.validate(val)
            if intermediate:
                result[counter] = intermediate
                haveResult = True
            counter = counter + 1
        return result if haveResult else False

def merge_dicts(*pieces):
    result = {}
    for piece in pieces:
        if isinstance(piece, dict):
            result.update(piece)
        else:
            result.update(piece.as_dict())
    return result

class OptionalDescriptor(Descriptor):
    def __init__(self, t):
        self.t = expand(t)
    def _validate(self, v):
        return False if is_absent(v) else self.t.validate(v)

class EmailDescriptor(RegexpDescriptor):
    def __init__(self):
        # TODO: better error message
        RegexpDescriptor.__init__(self, r"^\S+@[^.\s]\S*\.[^.\s]{2,}$")

class GeneralAlternationDescriptor(Descriptor):
    def __init__(self, options):
        self.options = expand_dict(options)
    def _validate(self, v):
        result = {}
        for (key, valType) in self.options.iteritems():
            intermediate = valType.validate(v)
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
        self.schemas = expand_list(schemas)
    def _validate(self, v):
        for t in self.schemas:
            intermediate = t.validate(v)
            if intermediate: return intermediate
        return False

class ExtensibleDictDescriptor(Descriptor):
    def __init__(self, t):
        self.t = expand_dict(t)
    def _validate(self, v):
        haveResult = False
        result = {}
        for (key, valType) in self.t.iteritems():
            intermediate = valType.validate(v.get(key, AbsentValue(key)))
            if intermediate:
                haveResult = True
                result[key] = intermediate
        return result if haveResult else False
    def as_dict(self):
        result = dict(self.t)
        result["_extensible"] = True
        return result

class ExactDictDescriptor(ExtensibleDictDescriptor):
    def _validate(self, v):
        extraKeys = set(v) - set(self.t)
        if extraKeys: return "Unexpected properties: " + (', '.join(extraKeys))
        return ExtensibleDictDescriptor._validate(self, v)
    def as_dict(self):
        return self.t

class ListDescriptor(Descriptor):
    def __init__(self, t):
        self.t = expand_list(t)
    def _validate(self, v):
        if len(v) != len(self.t):
            return "Length mismatch: expected array of length " + str(len(self.t))
        haveResult = False
        result = {}
        for i in range(len(self.t)):
            intermediate = self.t[i].validate(v[i])
            if intermediate:
                haveResult = True
                result[str(i)] = intermediate
        return result if haveResult else False

def expand_dict(d):
    return dict((k, expand(v)) for (k, v) in d.iteritems())

def expand_list(xs):
    return [expand(x) for x in xs]

def expand(t):
    if isinstance(t, Descriptor):
        return t

    if isinstance(t, dict):
        t = dict(t) # make a copy, as we'll be altering it
        if t.pop("_extensible", False):
            return ExtensibleDictDescriptor(t)
        else:
            return ExactDictDescriptor(t)

    if isinstance(t, list):
        return ListDescriptor(t)

    if isinstance(t, str) or isinstance(t, unicode):
        return ExactStringDescriptor(t) # TODO: coerce to unicode maybe?

    if isinstance(t, int) or isinstance(t, float):
        return ExactNumberDescriptor(t)

    if isinstance(t, bool):
        return ExactBooleanDescriptor(t)

    if t is None:
        return ExactNullDescriptor()

    raise InvalidDescriptor("Invalid proto-descriptor passed to expand", t)

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
    sourcetext = f.read()
    f.close()
    results = dict(extendingEnvironment or {})
    exec sourcetext in global_environment, results
    for key in results:
        results[key] = expand(results[key])
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
    result = t.validate(v)
    if result:
        print json.dumps(result)
        sys.exit(1)
    else:
        sys.exit(0)
