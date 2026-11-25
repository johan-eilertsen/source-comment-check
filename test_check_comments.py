import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECK = Path(__file__).resolve().with_name("check_comments.py")


class CommentCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        GIT_AUTHOR_NAME="Tester", GIT_COMMITTER_NAME="Tester",
                        GIT_AUTHOR_EMAIL="tester@example.invalid", GIT_COMMITTER_EMAIL="tester@example.invalid")
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.check_output(["git", *args], env=self.env, cwd=self.root, text=True).strip()

    def stage(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.git("--literal-pathspecs", "add", "--", path)

    def commit(self):
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def run_check(self, *args, status, directory=None):
        result = subprocess.run([sys.executable, "-B", str(CHECK), *args], cwd=directory or self.root,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(status, result.returncode, result.stderr)
        return result.stderr

    def test_unborn_repository_uses_staged_bytes(self):
        self.stage("app.js", "export const label = '// text';\n")
        (self.root / "app.js").write_text("// not staged\n")
        self.run_check("--staged", status=0)
        self.stage("app.js", "// explain the implementation\n")
        (self.root / "app.js").unlink()
        self.assertIn("app.js:1:", self.run_check("--staged", status=1))

    def test_shifted_legacy_comment_and_deletion_pass(self):
        self.stage("src/app.js", "// old comment\nexport const a = 1;\n")
        self.stage("removed.js", "// old comment\n")
        self.commit()
        self.stage("src/app.js", "const b = 2;\n// old comment\nexport const a = 3;\n")
        self.git("rm", "-q", "--", "removed.js")
        self.run_check("--staged", directory=self.root / "src", status=0)

    def test_committed_range_ignores_index_and_working_files(self):
        self.stage("app.js", "// old comment\nexport const a = 1;\n")
        base = self.commit()
        self.stage("app.js", "// old comment\nexport const a = 1;\n// explain a\n")
        head = self.commit()
        self.stage("app.js", "export const a = 1;\n")
        error = self.run_check("--base", base, "--head", head, status=1)
        self.assertIn("app.js:3:", error)
        self.assertNotIn("app.js:1:", error)
        self.run_check("--base", base, "--head", base, status=0)
        self.run_check("--base", base, "--head", "missing-revision", status=2)

    def test_removing_lines_inside_a_multiline_comment_still_edits_it(self):
        self.stage("app.js", "/*\nold text\nother text\n*/\nexport {};\n")
        self.commit()
        self.stage("app.js", "/*\nother text\n*/\nexport {};\n")
        self.assertIn("app.js:1:", self.run_check("--staged", status=1))

    def test_new_comment_previously_inside_string_is_detected(self):
        self.stage("app.js", "const value = `\n// looks like a comment\n`;\n")
        self.commit()
        self.stage("app.js", "const value = 1;\n// looks like a comment\n")
        self.assertIn("app.js:2:", self.run_check("--staged", status=1))

    def test_legacy_inline_comment_on_an_edited_line_is_reported(self):
        self.stage("app.js", "const value = 1; // old comment\n")
        self.commit()
        self.stage("app.js", "const value = 2; // old comment\n")
        self.assertIn("app.js:1:", self.run_check("--staged", status=1))

    def test_renamed_file_keeps_unchanged_comments(self):
        self.stage("app.js", "// old comment\nexport const value = 123;\n")
        self.commit()
        self.git("mv", "app.js", "renamed.js")
        self.run_check("--staged", status=0)
        self.stage("renamed.js", "// old comment\nexport const value = 123;\n// new\n")
        error = self.run_check("--staged", status=1)
        self.assertIn("renamed.js:3:", error)
        self.assertNotIn("renamed.js:1:", error)

    def test_exclusions_come_from_checked_tree_or_index(self):
        self.stage(".gitattributes", "*.min.js linguist-generated\nvendored.js linguist-vendored=true\n")
        base = self.commit()
        self.stage("app.min.js", "// from generator\n")
        self.stage("vendored.js", "// from vendor\n")
        (self.root / ".gitattributes").write_text("")
        self.run_check("--staged", status=0)
        head = self.commit()
        self.stage(".gitattributes", "")
        self.run_check("--base", base, "--head", head, status=0)

    def test_symlink_is_never_followed_and_binary_source_fails_closed(self):
        (self.root / "linked.js").symlink_to("missing-target")
        self.git("add", "--", "linked.js")
        self.run_check("--staged", status=0)
        (self.root / "binary.js").write_bytes(b"\0\xfe\xff")
        self.git("add", "--", "binary.js")
        self.assertIn("binary.js", self.run_check("--staged", status=2))

    def test_documentation_inputs_only_exempt_docblocks_in_marked_files(self):
        self.stage(".gitattributes", "api/*.ts source-comment-documentation\n")
        base = self.commit()
        doc = "/** Returns the public value. */\nexport const value = 1;\n"
        self.stage("api/value.ts", doc)
        self.stage("app.ts", doc)
        (self.root / ".gitattributes").write_text("*.ts source-comment-documentation\n")
        error = self.run_check("--staged", status=1)
        self.assertIn("app.ts:1:", error)
        self.assertNotIn("api/value.ts", error)
        self.stage("app.ts", "export const value = 1;\n")
        self.run_check("--staged", status=0)
        head = self.commit()
        self.stage(".gitattributes", "")
        self.run_check("--base", base, "--head", head, status=0)
        self.stage(".gitattributes", "api/*.ts source-comment-documentation\n")
        self.stage("api/value.ts", doc + "// line explanation\n/* block explanation */\n")
        error = self.run_check("--staged", status=1)
        self.assertIn("api/value.ts:3:", error)
        self.assertIn("api/value.ts:4:", error)

    def test_shebang_change_reclassifies_an_unchanged_data_line(self):
        self.stage("bin/run", "#!/bin/bash\ncat <<'END'\n# becomes code\nEND\n")
        base = self.commit()
        self.stage("bin/run", "#!/usr/bin/env python3\nvalue = 1\n# becomes code\n")
        error = self.run_check("--staged", status=1)
        self.assertIn("bin/run:3:", error)
        head = self.commit()
        self.stage("bin/run", "plain file\n")
        self.assertIn("bin/run:3:", self.run_check("--base", base, "--head", head, status=1))

    def test_unknown_extensionless_and_binary_files_are_not_source(self):
        (self.root / "data").write_bytes(b"\x7fELF\0" + b"\xff" * 20000)
        (self.root / "binary").write_bytes(b"#!/usr/bin/env python3\n" + b"a" * 10000 + b"\0\xff")
        self.git("add", "--", "data", "binary")
        self.stage("script", "#!/usr/bin/awk -f\n# data\n")
        self.run_check("--staged", status=0)
        self.commit()
        self.stage("script", "#!/bin/sh\n# data\n")
        self.assertIn("script:2:", self.run_check("--staged", status=1))

    def test_unusual_filename(self):
        name = "-line\nname.js"
        self.stage(name, "// new comment\n")
        self.stage("::error::file.js", "// new comment\n")
        diagnostic = self.run_check("--staged", status=1)
        self.assertIn("name.js", diagnostic)
        self.assertIn("::error::file.js", diagnostic)
        self.assertFalse(any(line.startswith("::") for line in diagnostic.splitlines()))


if __name__ == "__main__":
    unittest.main()
