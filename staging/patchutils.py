import sys
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

        self.patch_author       = header.get('author', None)
        self.patch_email        = header.get('email', None)
        self.patch_subject      = header.get('subject', None)
        self.patch_revision     = header.get('revision', 1)
        self.signed_off_by      = header.get('signedoffby', [])
        self.is_binary          = False
    def read(self):
        """Return the full patch as a string."""
        return "".join(chunk for chunk in self.read_chunks())

class _PatchReader(object):
    def __init__(self, filename, fp=None):
        self.fp       = fp if fp is not None else open(filename)
    def read_hunk(self):
        """Read one hunk from a patch file."""
        line = self.peek()
        if line is None or not line.startswith("@@ -"):
            return None
        r = re.match("^@@ -(([0-9]+),)?([0-9]+) \+(([0-9]+),)?([0-9]+) @@", line)
        if not r: raise PatchParserError("Unable to parse hunk header '%s'." % line)
        srcpos = max(int(r.group(2)) - 1, 0) if r.group(2) else 0
        dstpos = max(int(r.group(5)) - 1, 0) if r.group(5) else 0
        srclines, dstlines = int(r.group(3)), int(r.group(6))
        if srclines <= 0 and dstlines <= 0:
            raise PatchParserError("Empty hunk doesn't make sense.")
        self.read()

        srcdata = []
        dstdata = []

        try:
            while srclines > 0 or dstlines > 0:
                line = self.read().rstrip("\n")
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
            line = self.peek()
            if line is None or not line.startswith("\\ "): break
            self.read()
        return (srcpos, srcdata, dstpos, dstdata)
def _read_single_patch(fp, header, oldname=None, newname=None):
    """Internal function to read a single patch from a file."""
    patch = PatchObject(fp.filename, header)
    patch.offset_begin = fp.tell()
    patch.oldname = oldname
    patch.newname = newname
    # Skip over initial diff --git header
    line = fp.peek()
    if line.startswith("diff --git "):
        fp.read()
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
            break
        fp.read()

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
    else:
        patch.modified_file = patch.oldname

    # Decide between binary and textual patch
    if line is None or line.startswith("diff --git ") or line.startswith("--- "):
        if oldname != newname:
            raise PatchParserError("Stripped old- and new name doesn't match.")

    elif line.startswith("@@ -"):
        while fp.read_hunk() is not None:
            pass
    elif line.rstrip() == "GIT binary patch":
        if patch.oldsha1 is None or patch.newsha1 is None:
            raise PatchParserError("Missing index header, sha1 sums required for binary patch.")
        elif patch.oldname != patch.newname:
            raise PatchParserError("Stripped old- and new name doesn't match for binary patch.")
        fp.read()
        line = fp.read()
        if line is None: raise PatchParserError("Unexpected end of file.")
        r = re.match("^(literal|delta) ([0-9]+)", line)
        if not r: raise NotImplementedError("Only literal/delta patches are supported.")
        patch.is_binary = True
        # Skip over patch data
        while True:
            if line is None or line.strip() == "":
                break
    else:
        raise PatchParserError("Unknown patch format.")
    patch.offset_end = fp.tell()
    return patch
def _parse_author(author):
    if sys.version_info[0] > 2:
        author = str(email.header.make_header(email.header.decode_header(author)))
    else:
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
    r = re.match("^(.*)\\[%s\\]$" % version, subject, re.IGNORECASE)
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

def read_patch(filename, fp=None):
    """Iterates over all patches contained in a file, and returns PatchObject objects."""
    with _PatchReader(filename, fp) as fp:
                header.pop('signedoffby', None)
                fp.read()
                fp.read()
                    fp.read()
                header.pop('signedoffby', None)
                if 'signedoffby' not in header:
                fp.read()
                fp.read()
    result = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        return tempfile._TemporaryFileWrapper(file=open(result.name, 'r+'), \
def _preprocess_source(fp):
    """Simple C preprocessor to determine where we can safely add #ifdef instructions."""
    _re_state0 = re.compile("(\"|/[/*])")
    _re_state1 = re.compile("(\\\\\"|\\\\\\\\|\")")
    _re_state2 = re.compile("\\*/")
    # We need to read the original file, and figure out where lines can be splitted
    lines = []
    for line in fp:
        lines.append(line.rstrip("\n"))
    split = set([0])
    state = 0
    i = 0
    while i < len(lines):
        # Read a full line (and handle line continuation)
        line = lines[i]
        i += 1
        while line.endswith("\\"):
            if i >= len(lines):
                raise CParserError("Unexpected end of file.")
            line = line[:-1] + lines[i]
        # To find out where we can add our #ifdef tags we use a simple
        # statemachine. This allows finding the beginning of a multiline
        # instruction or comment.
        j = 0
        while True:
            # State 0: No context
                match = _re_state0.search(line, j)
                if match is None: break

                if match.group(0) == "\"":
                    state = 1 # Begin of string
                elif match.group(0) == "/*":
                    state = 2 # Begin of comment
                elif match.group(0) == "//":
                    break # Rest of the line is a comment, which can be safely ignored
                else:
                    assert 0

            # State 1: Inside of string
            elif state == 1:
                match = _re_state1.search(line, j)
                if match is None:
                    raise CParserError("Line ended in the middle of a string.")

                if match.group(0) == "\"":
                    state = 0 # End of string
                elif match.group(0) != "\\\"" and match.group(0) != "\\\\":
                    assert 0

            # State 2: Multiline comment
            elif state == 2:
                match = _re_state2.search(line, j)
                if match is None: break

                if match.group(0) == "*/":
                    state = 0 # End of comment
                else:
                    assert 0

            else:
                raise CParserError("Internal state error.")
            j = match.end()

        # Only in state 0 (no context) we can split here
        if state == 0:
            split.add(i)
    # Ensure that the last comment is properly terminated
    if state != 0:
        raise CParserError("Unexpected end of file.")
    return lines, split

def generate_ifdef_patch(original, patched, ifdef):
    """Generate a patch which adds #ifdef where necessary to keep both the original and patched version."""
    with tempfile.NamedTemporaryFile(mode='w+') as diff:
        original.seek(0)
        fp = _PatchReader(diff.name, diff)
        fp.seek(0)
        line = fp.read()
        line = fp.read()
        while fp.peek() is not None:
            srcpos, srcdata, dstpos, dstdata = fp.read_hunk()
    with tempfile.NamedTemporaryFile(mode='w+') as intermediate:
        diff = tempfile.NamedTemporaryFile(mode='w+')

if __name__ == "__main__":
    import unittest

    # Basic tests for _parse_author() and _parse_subject()
    class PatchParserTests(unittest.TestCase):
        def test_author(self):
            author = _parse_author("Author Name <author@email.com>")
            self.assertEqual(author, ("Author Name", "author@email.com"))

            author = _parse_author("=?UTF-8?q?Author=20Name?= <author@email.com>")
            self.assertEqual(author, ("Author Name", "author@email.com"))

        def test_subject(self):
            subject = _parse_subject("[PATCH v3] component: Subject.")
            self.assertEqual(subject, ("component: Subject", 3))

            subject = _parse_subject("[PATCH] component: Subject (v3).")
            self.assertEqual(subject, ("component: Subject", 3))

            subject = _parse_subject("[PATCH] component: Subject (try 3).")
            self.assertEqual(subject, ("component: Subject", 3))

            subject = _parse_subject("[PATCH] component: Subject (take 3).")
            self.assertEqual(subject, ("component: Subject", 3))

            subject = _parse_subject("[PATCH] component: Subject (rev 3).")
            self.assertEqual(subject, ("component: Subject", 3))

            subject = _parse_subject("[PATCH] component: Subject [v3].")
            self.assertEqual(subject, ("component: Subject", 3))

            subject = _parse_subject("[PATCH] component: Subject, v3.")
            self.assertEqual(subject, ("component: Subject", 3))

            subject = _parse_subject("[PATCH] component: Subject v3.")
            self.assertEqual(subject, ("component: Subject", 3))

            subject = _parse_subject("[PATCH] component: Subject (resend).")
            self.assertEqual(subject, ("component: Subject", 1))

    # Basic tests for read_patch()
    class PatchReaderTests(unittest.TestCase):
        def test_simple(self):
            with open("tests/simple.patch") as fp:
                source = fp.read().split("\n")

            # Test formatted git patch with author and subject
            patchfile = tempfile.NamedTemporaryFile(mode='w+')
            patchfile.write("\n".join(source))
            patchfile.flush()

            patches = list(read_patch(patchfile.name))
            self.assertEqual(len(patches), 1)
            self.assertEqual(patches[0].patch_author,   "Author Name")
            self.assertEqual(patches[0].patch_email,    "author@email.com")
            self.assertEqual(patches[0].patch_subject,  "component: Replace arg1 with arg2.")
            self.assertEqual(patches[0].patch_revision, 3)
            self.assertEqual(patches[0].signed_off_by,  [("Author Name", "author@email.com"),
                                                         ("Other Developer", "other@email.com")])
            self.assertEqual(patches[0].filename,       patchfile.name)
            self.assertEqual(patches[0].is_binary,      False)
            self.assertEqual(patches[0].modified_file,  "test.txt")

            lines = patches[0].read().rstrip("\n").split("\n")
            self.assertEqual(lines, source[10:23])

            # Test with git diff
            del source[0:10]
            self.assertTrue(source[0].startswith("diff --git"))
            patchfile = tempfile.NamedTemporaryFile(mode='w+')
            patchfile.write("\n".join(source))
            patchfile.flush()

            patches = list(read_patch(patchfile.name))
            self.assertEqual(len(patches), 1)
            self.assertEqual(patches[0].patch_author,   None)
            self.assertEqual(patches[0].patch_email,    None)
            self.assertEqual(patches[0].patch_subject,  None)
            self.assertEqual(patches[0].patch_revision, 1)
            self.assertEqual(patches[0].signed_off_by,  [])
            self.assertEqual(patches[0].filename,       patchfile.name)
            self.assertEqual(patches[0].is_binary,      False)
            self.assertEqual(patches[0].modified_file, "test.txt")

            lines = patches[0].read().rstrip("\n").split("\n")
            self.assertEqual(lines, source[:13])

            # Test with unified diff
            del source[0:2]
            self.assertTrue(source[0].startswith("---"))
            patchfile = tempfile.NamedTemporaryFile(mode='w+')
            patchfile.write("\n".join(source))
            patchfile.flush()

            patches = list(read_patch(patchfile.name))
            self.assertEqual(len(patches), 1)
            self.assertEqual(patches[0].patch_author,   None)
            self.assertEqual(patches[0].patch_email,    None)
            self.assertEqual(patches[0].patch_subject,  None)
            self.assertEqual(patches[0].patch_revision, 1)
            self.assertEqual(patches[0].signed_off_by,  [])
            self.assertEqual(patches[0].filename,       patchfile.name)
            self.assertEqual(patches[0].is_binary,      False)
            self.assertEqual(patches[0].modified_file,  "test.txt")

            lines = patches[0].read().rstrip("\n").split("\n")
            self.assertEqual(lines, source[:11])

            # Test with StringIO buffer
            fp = StringIO("\n".join(source))
            patches = list(read_patch("unknown.patch", fp))
            self.assertEqual(len(patches), 1)
            self.assertEqual(patches[0].patch_author,   None)
            self.assertEqual(patches[0].patch_email,    None)
            self.assertEqual(patches[0].patch_subject,  None)
            self.assertEqual(patches[0].patch_revision, 1)
            self.assertEqual(patches[0].signed_off_by,  [])
            self.assertEqual(patches[0].filename,       "unknown.patch")
            self.assertEqual(patches[0].is_binary,      False)
            self.assertEqual(patches[0].modified_file,  "test.txt")

        def test_multi(self):
            with open("tests/multi.patch") as fp:
                source = fp.read().split("\n")

            patchfile = tempfile.NamedTemporaryFile(mode='w+')
            patchfile.write("\n".join(source))
            patchfile.flush()

            patches = list(read_patch(patchfile.name))
            self.assertEqual(len(patches), 3)

            self.assertEqual(patches[0].patch_author,   "Author Name")
            self.assertEqual(patches[0].patch_email,    "author@email.com")
            self.assertEqual(patches[0].patch_subject,  "component: Replace arg1 with arg2.")
            self.assertEqual(patches[0].patch_revision, 3)
            self.assertEqual(patches[0].signed_off_by,  [("Author Name", "author@email.com"),
                                                         ("Other Developer", "other@email.com")])
            self.assertEqual(patches[0].filename,       patchfile.name)
            self.assertEqual(patches[0].is_binary,      False)
            self.assertEqual(patches[0].modified_file,  "other_test.txt")

            lines = patches[0].read().rstrip("\n").split("\n")
            self.assertEqual(lines, source[11:24])

            self.assertEqual(patches[1].patch_author,   "Author Name")
            self.assertEqual(patches[1].patch_email,    "author@email.com")
            self.assertEqual(patches[1].patch_subject,  "component: Replace arg1 with arg2.")
            self.assertEqual(patches[1].patch_revision, 3)
            self.assertEqual(patches[1].signed_off_by,  [("Author Name", "author@email.com"),
                                                         ("Other Developer", "other@email.com")])
            self.assertEqual(patches[1].filename,       patchfile.name)
            self.assertEqual(patches[1].is_binary,      False)
            self.assertEqual(patches[1].modified_file,  "test.txt")

            lines = patches[1].read().rstrip("\n").split("\n")
            self.assertEqual(lines, source[24:46])

            self.assertEqual(patches[2].patch_author,   "Other Developer")
            self.assertEqual(patches[2].patch_email,    "other@email.com")
            self.assertEqual(patches[2].patch_subject,  "component: Replace arg2 with arg3.")
            self.assertEqual(patches[2].patch_revision, 4)
            self.assertEqual(patches[2].signed_off_by,  [("Other Developer", "other@email.com")])
            self.assertEqual(patches[2].filename,       patchfile.name)
            self.assertEqual(patches[2].is_binary,      False)
            self.assertEqual(patches[2].modified_file,  "test.txt")

            lines = patches[2].read().rstrip("\n").split("\n")
            self.assertEqual(lines, source[58:71])

    # Basic tests for apply_patch()
    class PatchApplyTests(unittest.TestCase):
        def test_apply(self):
            source = ["line1();", "line2();", "line3();",
                      "function(arg1);",
                      "line5();", "line6();", "line7();"]
            original = tempfile.NamedTemporaryFile(mode='w+')
            original.write("\n".join(source + [""]))
            original.flush()

            source = ["@@ -1,7 +1,7 @@",
                      " line1();", " line2();", " line3();",
                      "-function(arg1);",
                      "+function(arg2);",
                      " line5();", " line6();", " line7();"]
            patchfile = tempfile.NamedTemporaryFile(mode='w+')
            patchfile.write("\n".join(source + [""]))
            patchfile.flush()

            expected = ["line1();", "line2();", "line3();",
                        "function(arg2);",
                        "line5();", "line6();", "line7();"]
            result = apply_patch(original, patchfile, fuzz=0)
            lines = result.read().rstrip("\n").split("\n")
            self.assertEqual(lines, expected)

            expected = ["line1();", "line2();", "line3();",
                        "function(arg1);",
                        "line5();", "line6();", "line7();"]
            result = apply_patch(result, patchfile, reverse=True, fuzz=0)
            lines = result.read().rstrip("\n").split("\n")
            self.assertEqual(lines, expected)

    # Basic tests for _preprocess_source()
    class PreprocessorTests(unittest.TestCase):
        def test_preprocessor(self):
            source = ["int a; // comment 1",
                      "int b; // comment 2 \\",
                      "          comment 3 \\",
                      "          comment 4",
                      "int c; // comment with \"quotes\"",
                      "int d; // comment with /* c++ comment */",
                      "int e; /* multi \\",
                      "          line",
                      "          comment */",
                      "char *x = \"\\\\\";",
                      "char *y = \"abc\\\"def\";",
                      "char *z = \"multi\" \\",
                      "          \"line\"",
                      "          \"string\";"]
            lines, split = _preprocess_source(source)
            self.assertEqual(lines, source)
            self.assertEqual(split, set([0, 1, 4, 5, 6, 9, 10, 11, 13, 14]))

    # Basic tests for generate_ifdef_patch()
    class GenerateIfdefPatchTests(unittest.TestCase):
        def test_ifdefined(self):
            source = ["line1();", "line2();", "line3();",
                      "function(arg1, \\",
                      "         arg2, \\",
                      "         arg3);",
                      "line5();", "line6();", "line7();"]
            source1 = tempfile.NamedTemporaryFile(mode='w+')
            source1.write("\n".join(source + [""]))
            source1.flush()

            source = ["line1();", "line2();", "line3();",
                      "function(arg1, \\",
                      "         new_arg2, \\",
                      "         arg3);",
                      "line5();", "line6();", "line7();"]
            source2  = tempfile.NamedTemporaryFile(mode='w+')
            source2.write("\n".join(source + [""]))
            source2.flush()

            diff = generate_ifdef_patch(source1, source1, "PATCHED")
            self.assertEqual(diff, None)

            diff = generate_ifdef_patch(source2, source2, "PATCHED")
            self.assertEqual(diff, None)

            expected = ["@@ -1,9 +1,15 @@",
                        " line1();", " line2();", " line3();",
                        "+#if defined(PATCHED)",
                        " function(arg1, \\",
                        "          new_arg2, \\",
                        "          arg3);",
                        "+#else  /* PATCHED */",
                        "+function(arg1, \\",
                        "+         arg2, \\",
                        "+         arg3);",
                        "+#endif /* PATCHED */",
                        " line5();", " line6();", " line7();"]
            diff = generate_ifdef_patch(source1, source2, "PATCHED")
            lines = diff.read().rstrip("\n").split("\n")
            self.assertEqual(lines, expected)

            expected = ["@@ -1,9 +1,15 @@",
                        " line1();", " line2();", " line3();",
                        "+#if defined(PATCHED)",
                        " function(arg1, \\",
                        "          arg2, \\",
                        "          arg3);",
                        "+#else  /* PATCHED */",
                        "+function(arg1, \\",
                        "+         new_arg2, \\",
                        "+         arg3);",
                        "+#endif /* PATCHED */",
                        " line5();", " line6();", " line7();"]
            diff = generate_ifdef_patch(source2, source1, "PATCHED")
            lines = diff.read().rstrip("\n").split("\n")
            self.assertEqual(lines, expected)

    unittest.main()