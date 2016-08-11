        self.patch_author       = header['author']
        self.patch_email        = header['email']
        self.patch_subject      = header['subject']
        self.patch_revision     = header['revision'] if header.has_key('revision') else 1
        self.signed_off_by      = header['signedoffby'] if header.has_key('signedoffby') else []
        self.isbinary           = False
    def is_binary(self):
        return self.isbinary

class _FileReader(object):
    def __init__(self, filename):
        self.fp       = open(self.filename)
def read_patch(filename):
    """Iterates over all patches contained in a file, and returns PatchObject objects."""
    def _read_single_patch(fp, header, oldname=None, newname=None):
        """Internal function to read a single patch from a file."""
        patch = PatchObject(fp.filename, header)
        patch.offset_begin = fp.tell()
        patch.oldname = oldname
        patch.newname = newname
        # Skip over initial diff --git header
        line = fp.peek()
        if line.startswith("diff --git "):
            assert fp.read() == line

        # Read header
        while True:
            line = fp.peek()
            if line is None:
                break
            elif line.startswith("--- "):
                patch.oldname = line[4:].strip()
            elif line.startswith("+++ "):
                patch.newname = line[4:].strip()
            elif line.startswith("old mode") or line.startswith("deleted file mode"):
                pass # ignore
            elif line.startswith("new mode "):
                patch.newmode = line[9:].strip()
            elif line.startswith("new file mode "):
                patch.newmode = line[14:].strip()
            elif line.startswith("new mode") or line.startswith("new file mode"):
                raise PatchParserError("Unable to parse header line '%s'." % line)
            elif line.startswith("copy from") or line.startswith("copy to"):
                raise NotImplementedError("Patch copy header not implemented yet.")
            elif line.startswith("rename "):
                raise NotImplementedError("Patch rename header not implemented yet.")
            elif line.startswith("similarity index") or line.startswith("dissimilarity index"):
                pass # ignore
            elif line.startswith("index "):
                r = re.match("^index ([a-fA-F0-9]*)\.\.([a-fA-F0-9]*)", line)
                if not r: raise PatchParserError("Unable to parse index header line '%s'." % line)
                patch.oldsha1, patch.newsha1 = r.group(1), r.group(2)
            else:
                break
            assert fp.read() == line
        if patch.oldname is None or patch.newname is None:
            raise PatchParserError("Missing old or new name.")
        elif patch.oldname == "/dev/null" and patch.newname == "/dev/null":
            raise PatchParserError("Old and new name is /dev/null?")
        if patch.oldname.startswith("a/"):
            patch.oldname = patch.oldname[2:]
        elif patch.oldname != "/dev/null":
            raise PatchParserError("Old name in patch doesn't start with a/.")
        if patch.newname.startswith("b/"):
            patch.newname = patch.newname[2:]
        elif patch.newname != "/dev/null":
            raise PatchParserError("New name in patch doesn't start with b/.")
        if patch.newname != "/dev/null":
            patch.modified_file = patch.newname
            patch.modified_file = patch.oldname

        # Decide between binary and textual patch
        if line is None or line.startswith("diff --git ") or line.startswith("--- "):
            if oldname != newname:
                raise PatchParserError("Stripped old- and new name doesn't match.")

        elif line.startswith("@@ -"):
            while True:
                line = fp.peek()
                if line is None or not line.startswith("@@ -"):
                    break

                r = re.match("^@@ -(([0-9]+),)?([0-9]+) \+(([0-9]+),)?([0-9]+) @@", line)
                if not r: raise PatchParserError("Unable to parse hunk header '%s'." % line)
                srcpos = max(int(r.group(2)) - 1, 0) if r.group(2) else 0
                dstpos = max(int(r.group(5)) - 1, 0) if r.group(5) else 0
                srclines, dstlines = int(r.group(3)), int(r.group(6))
                if srclines <= 0 and dstlines <= 0:
                    raise PatchParserError("Empty hunk doesn't make sense.")
                assert fp.read() == line

                try:
                    while srclines > 0 or dstlines > 0:
                        line = fp.read()[0]
                        if line == " ":
                            if srclines == 0 or dstlines == 0:
                                raise PatchParserError("Corrupted patch.")
                            srclines -= 1
                            dstlines -= 1
                        elif line == "-":
                            if srclines == 0:
                                raise PatchParserError("Corrupted patch.")
                            srclines -= 1
                        elif line == "+":
                            if dstlines == 0:
                                raise PatchParserError("Corrupted patch.")
                            dstlines -= 1
                        elif line == "\\":
                            pass # ignore
                        else:
                            raise PatchParserError("Unexpected line in hunk.")
                except TypeError: # triggered by None[0]
                    raise PatchParserError("Truncated patch.")
                while True:
                    line = fp.peek()
                    if line is None or not line.startswith("\\ "): break
                    assert fp.read() == line
        elif line.rstrip() == "GIT binary patch":
            if patch.oldsha1 is None or patch.newsha1 is None:
                raise PatchParserError("Missing index header, sha1 sums required for binary patch.")
            elif patch.oldname != patch.newname:
                raise PatchParserError("Stripped old- and new name doesn't match for binary patch.")
            assert fp.read() == line
            if line is None: raise PatchParserError("Unexpected end of file.")
            r = re.match("^(literal|delta) ([0-9]+)", line)
            if not r: raise NotImplementedError("Only literal/delta patches are supported.")
            patch.isbinary = True

            # Skip over patch data
            while True:
                line = fp.read()
                if line is None or line.strip() == "":
                    break
        else:
            raise PatchParserError("Unknown patch format.")
        patch.offset_end = fp.tell()
        return patch
    def _parse_author(author):
        r =  re.match("\"?([^\"]*)\"? <(.*)>", author)
        if r is None: raise NotImplementedError("Failed to parse From - header.")
        return r.group(1).strip(), r.group(2).strip()

    def _parse_subject(subject):
        version = "(v|try|rev|take) *([0-9]+)"
        subject = subject.strip()
        if subject.endswith("."): subject = subject[:-1]
        r = re.match("^\\[PATCH([^]]*)\\](.*)$", subject, re.IGNORECASE)
        if r is not None:
            subject = r.group(2).strip()
            r = re.search(version, r.group(1), re.IGNORECASE)
            if r is not None: return subject, int(r.group(2))
        r = re.match("^(.*)\\(%s\\)$" % version, subject, re.IGNORECASE)
        if r is not None: return r.group(1).strip(), int(r.group(3))
        r = re.match("^(.*)[.,] +%s$" % version, subject, re.IGNORECASE)
        if r is not None: return r.group(1).strip(), int(r.group(3))
        r = re.match("^([^:]+) %s: (.*)$" % version, subject, re.IGNORECASE)
        if r is not None: return "%s: %s" % (r.group(1), r.group(4)), int(r.group(3))
        r = re.match("^(.*) +%s$" % version, subject, re.IGNORECASE)
        if r is not None: return r.group(1).strip(), int(r.group(3))
        r = re.match("^(.*)\\(resend\\)$", subject, re.IGNORECASE)
        if r is not None: return r.group(1).strip(), 1
        return subject, 1
    with _FileReader(filename) as fp:
                assert fp.read() == line
                assert fp.read() == line
                    assert fp.read() == line
                if not header.has_key('signedoffby'):
                assert fp.read() == line
                assert fp.read() == line
    result = tempfile.NamedTemporaryFile(delete=False)
        return tempfile._TemporaryFileWrapper(file=open(result.name, 'r+b'), \
    with tempfile.NamedTemporaryFile() as diff:
        exitcode = subprocess.call(["diff", "-u", original.name, patched.name],
        diff.flush()
        diff.seek(0)
        line = diff.readline()
        line = diff.readline()
        while True:
            line = diff.readline()
            if line == "":
                break

            # Parse each hunk, and extract the srclines and dstlines. This algorithm is very
            # similar to _read_single_patch.
            if not line.startswith("@@ -"):
                raise PatchParserError("Unable to parse line '%s'." % line)

            r = re.match("^@@ -(([0-9]+),)?([0-9]+) \+(([0-9]+),)?([0-9]+) @@", line)
            if not r: raise PatchParserError("Unable to parse hunk header '%s'." % line)
            srcpos = max(int(r.group(2)) - 1, 0) if r.group(2) else 0
            dstpos = max(int(r.group(5)) - 1, 0) if r.group(5) else 0
            srclines, dstlines = int(r.group(3)), int(r.group(6))
            if srclines <= 0 and dstlines <= 0:
                raise PatchParserError("Empty hunk doesn't make sense.")

            srcdata = []
            dstdata = []

            try:
                while srclines > 0 or dstlines > 0:
                    line = diff.readline().rstrip("\n")
                    if line[0] == " ":
                        if srclines == 0 or dstlines == 0:
                            raise PatchParserError("Corrupted patch.")
                        srcdata.append(line[1:])
                        dstdata.append(line[1:])
                        srclines -= 1
                        dstlines -= 1
                    elif line[0] == "-":
                        if srclines == 0:
                            raise PatchParserError("Corrupted patch.")
                        srcdata.append(line[1:])
                        srclines -= 1
                    elif line[0] == "+":
                        if dstlines == 0:
                            raise PatchParserError("Corrupted patch.")
                        dstdata.append(line[1:])
                        dstlines -= 1
                    elif line[0] == "\\":
                        pass # ignore
                    else:
                        raise PatchParserError("Unexpected line in hunk.")
            except IndexError: # triggered by ""[0]
                raise PatchParserError("Truncated patch.")
        # We don't need the diff anymore, all hunks are in memory
        diff.close()

    with tempfile.NamedTemporaryFile() as intermediate:
                intermediate.write("#if defined(%s)\n" % ifdef)
                intermediate.write("\n#else  /* %s */\n" % ifdef)
                intermediate.write("\n".join(srcdata))
        # Now we can finally compute the diff between the patched file and our intermediate file
        diff = tempfile.NamedTemporaryFile()
        exitcode = subprocess.call(["diff", "-u", patched.name, intermediate.name],
        # We expect this output format from 'diff', if this is not the case things might go wrong.