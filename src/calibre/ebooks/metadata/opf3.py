#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from collections import defaultdict
import re

from lxml import etree

from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.utils import parse_opf
from calibre.ebooks.oeb.base import OPF2_NSMAP, OPF

# Utils {{{
# http://www.idpf.org/epub/vocab/package/pfx/
reserved_prefixes = {
    'dcterms':  'http://purl.org/dc/terms/',
    'epubsc':   'http://idpf.org/epub/vocab/sc/#',
    'marc':     'http://id.loc.gov/vocabulary/',
    'media':    'http://www.idpf.org/epub/vocab/overlays/#',
    'onix':     'http://www.editeur.org/ONIX/book/codelists/current.html#',
    'rendition':'http://www.idpf.org/vocab/rendition/#',
    'schema':   'http://schema.org/',
    'xsd':      'http://www.w3.org/2001/XMLSchema#',
}

_xpath_cache = {}
_re_cache = {}

def XPath(x):
    try:
        return _xpath_cache[x]
    except KeyError:
        _xpath_cache[x] = ans = etree.XPath(x, namespaces=OPF2_NSMAP)
        return ans

def regex(r, flags=0):
    try:
        return _re_cache[(r, flags)]
    except KeyError:
        _re_cache[(r, flags)] = ans = re.compile(r, flags)
        return ans
# }}}

# Prefixes {{{

def parse_prefixes(x):
    return {m.group(1):m.group(2) for m in re.finditer(r'(\S+): \s*(\S+)', x)}

def read_prefixes(root):
    ans = reserved_prefixes.copy()
    ans.update(parse_prefixes(root.get('prefix') or ''))
    return ans

def expand_prefix(raw, prefixes):
    return regex(r'(\S+)\s*:\s*(\S+)').sub(lambda m:(prefixes.get(m.group(1), m.group(1)) + ':' + m.group(2)), raw)
# }}}

# Refines {{{
def read_refines(root):
    ans = defaultdict(list)
    for meta in XPath('./opf:metadata/opf:meta[@refines]')(root):
        r = meta.get('refines') or ''
        if r.startswith('#'):
            ans[r[1:]].append(meta)
    return ans
# }}}

# Identifiers {{{
def parse_identifier(ident, val, refines):
    idid = ident.get('id')
    refines = refines[idid]
    scheme = None
    lval = val.lower()

    def finalize(scheme, val):
        if not scheme or not val:
            return None, None
        scheme = scheme.lower()
        if scheme in ('http', 'https'):
            return None, None
        if scheme.startswith('isbn'):
            scheme = 'isbn'
        if scheme == 'isbn':
            val = val.split(':')[-1]
            val = check_isbn(val)
            if val is None:
                return None, None
        return scheme, val

    # Try the OPF 2 style opf:scheme attribute, which will be present, for
    # example, in EPUB 3 files that have had their metadata set by an
    # application that only understands EPUB 2.
    scheme = ident.get(OPF('scheme'))
    if scheme and not lval.startswith('urn:'):
        return finalize(scheme, val)

    # Technically, we should be looking for refines that define the scheme, but
    # the IDioticPF created such a bad spec that they got their own
    # examples wrong, so I cannot be bothered doing this.

    # Parse the value for the scheme
    if lval.startswith('urn:'):
        val = val[4:]

    prefix, rest = val.partition(':')[::2]
    return finalize(prefix, rest)

def read_identifiers(root, prefixes, refines):
    ans = defaultdict(list)
    for ident in XPath('./opf:metadata/dc:identifier')(root):
        val = (ident.text or '').strip()
        if val:
            scheme, val = parse_identifier(ident, val, refines)
            if scheme and val:
                ans[scheme].append(val)
    return ans
# }}}

def read_metadata(root):
    ans = Metadata(_('Unknown'), [_('Unknown')])
    prefixes, refines = read_prefixes(root), read_refines(root)
    identifiers = read_identifiers(root, prefixes, refines)
    ids = {}
    for key, vals in identifiers.iteritems():
        if key == 'calibre':
            ans.application_id = vals[0]
        elif key != 'uuid':
            ids[key] = vals[0]
    ans.set_identifiers(ids)

    return ans

def get_metadata(stream):
    root = parse_opf(stream)
    return read_metadata(root)

if __name__ == '__main__':
    import sys
    print(get_metadata(open(sys.argv[-1], 'rb')))