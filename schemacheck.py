#!/usr/bin/env python

import sys
import re
import traceback
import types

class InvalidSchema(Exception): pass

absent = object()

def regexp(pat):
    r = re.compile(pat)
    def match(v):
        return False if r.match(v) else "regexp failed: " + pat
    return match

def nonempty_string():
    def match(v):
        if (isinstance(v, str) or isinstance(v, unicode)) \
                and len(v) > 0:
            return False
        else:
            return "Expected non-empty string"
    return match

def dictionary(keyType, valueType):
    def match(v):
        haveResult = False
        result = {}
        for (key, val) in v.iteritems():
            intermediate = validate(key, keyType)
            if intermediate:
                result["key " + str(key)] = intermediate
                haveResult = True
            else:
                intermediate = validate(val, valueType)
                if intermediate:
                    result["valueAt " + str(key)] = intermediate
                    haveResult = True
        return result if haveResult else False
    return match

def array_of(t):
    def match(v):
        haveResult = False
        result = {}
        counter = 0
        for val in v:
            intermediate = validate(val, t)
            if intermediate:
                result[counter] = intermediate
                haveResult = True
            counter = counter + 1
        return result if haveResult else False
    return match

def merge(*pieces):
    result = {}
    for piece in pieces:
        result.update(piece)
    return result

def optional(t):
    def match(v):
        return False if v == absent else validate(v, t)
    return match

def email():
    return regexp(r"^\S+@[^.\s]\S*\.[^.\s]{2,}$")

def or_dict(d):
    def match(v):
        result = {}
        for (key, valType) in d.iteritems():
            intermediate = validate(v, valType)
            if not intermediate: return False
            result[key] = intermediate
        return result
    if isinstance(d, dict) and d:
        return match
    else:
        raise InvalidSchema("or_dict with non-dictionary or no options")

def validate(v, t):
    if isinstance(t, types.FunctionType):
        try:
            return t(v)
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
    'regexp': regexp,
    'nonempty_string': nonempty_string,
    'dictionary': dictionary,
    'array_of': array_of,
    'merge': merge,
    'optional': optional,
    'email': email,
    'or_dict': or_dict
}

def load_schema(filename, extendingEnvironment = None):
    f = file("plugin.schema.js")
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
