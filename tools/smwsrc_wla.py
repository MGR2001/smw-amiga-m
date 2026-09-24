#!/usr/bin/env python3
"""
smwsrc_wla.py - adapta una COPIA del fuente de smw-src a WLA-DX 9.x.

smw-src se ensamblaba con una WLA modificada (bin/*.exe, sin fuente) que
entiende dos cosas que la WLA-DX normal no:

1. Etiquetas locales con '@', con anidamiento:
       Padre:   @Hijo:   @@Nieto:        (definiciones)
       @Hijo   @@Nieto   Padre@Hijo@Nieto (referencias)
   -> Padre, Padre_AT_Hijo, Padre_AT_Hijo_AT_Nieto.
2. .ASC "texto\\n": marca el ULTIMO caracter con el bit 7 (fin de cadena de
   SMW). En WLA-DX 9.x eso se escribe "x\\>".

La tercera diferencia (DL dentro de .ENUM) se parchea en la WLA misma (ver
tools/setup_cloud.sh). Con las tres, la ROM sale con CRC32 B19ED489 = SMW (U).

    python tools/smwsrc_wla.py <copia>/project/mw_e10
"""
import os
import re
import sys

GL = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):')
LOC = re.compile(r'^(@@?)([A-Za-z0-9_]+):')
REF = re.compile(r'(?<![A-Za-z0-9_@"])([A-Za-z_][A-Za-z0-9_]*)?((?:@@?[A-Za-z0-9_]+)+)')
ASC = re.compile(r'(\.ASC\s+"[^"\n]*?)\\n"')


def fix_labels(src):
    glob = sub = ''
    out = []
    for ln in src.split('\n'):
        code, sep, com = ln.partition(';')
        m = GL.match(code)
        if m:
            glob, sub = m.group(1), ''
        else:
            m = LOC.match(code)
            if m:
                if m.group(1) == '@':
                    sub = m.group(2)
                    code = glob + '_AT_' + m.group(2) + ':' + code[m.end():]
                else:
                    code = glob + '_AT_' + sub + '_AT_' + m.group(2) + ':' + code[m.end():]

        def rep(mm):
            head, tail = mm.group(1), mm.group(2)
            if head:
                return head + tail.replace('@@', '@').replace('@', '_AT_')
            if tail.startswith('@@'):
                return glob + '_AT_' + sub + '_AT_' + tail[2:].replace('@', '_AT_')
            return glob + '_AT_' + tail[1:].replace('@', '_AT_')
        if '"' not in code:
            code = REF.sub(rep, code)
        out.append(code + sep + com)
    return '\n'.join(out)


def main():
    root = sys.argv[1]
    n = 0
    for dp, _, fs in os.walk(root):
        for f in fs:
            if not re.search(r'\.(s|S|a|i)$', f):
                continue
            p = os.path.join(dp, f)
            src = open(p, encoding='latin-1').read()
            new = fix_labels(src) if '@' in src else src
            new = ASC.sub(r'\1\\>"', new)
            if new != src:
                open(p, 'w', encoding='latin-1').write(new)
                n += 1
    print('smwsrc_wla: %d ficheros adaptados' % n)


if __name__ == '__main__':
    main()
