import unittest

from comment_policy import executable_code_path, prohibited_comments


class CommentPolicyTests(unittest.TestCase):
    def assert_comments(self, path, source, expected):
        self.assertEqual(list(prohibited_comments(path, source)), expected)

    def test_javascript_ranges_strings_regex_and_template_interpolation(self):
        source = (
            "const url = 'https://example.test/*value*/';\n"
            "const matcher = /[//]/;\n"
            "const template = `/* no */ ${1 /* real */}`;\n"
            "/* explanation\n * continued */ // another\n"
        )
        self.assert_comments("core/graph.mjs", source, [(3, 3), (4, 5), (5, 5)])

    def test_jsx_text_is_not_javascript(self):
        source = (
            'const A = () => <span title="/* string */">https://example.test/\n'
            'Hello // text {/* actual */} goodbye</span>;\n'
        )
        for path in ("test.jsx", "test.tsx"):
            with self.subTest(path=path):
                self.assert_comments(path, source, [(2, 2)])

    def test_js_directives_and_structured_documentation(self):
        source = (
            "#!/usr/bin/env node\n"
            "// @ts-expect-error: compatibility fixture\n"
            "call(0);\n"
            "// eslint-disable-next-line no-console -- prints the sample\n"
            "console.log(1);\n"
            "/** An explanation without tool input. */\n"
            "/**\n * @param {string} name display name\n * @returns {boolean}\n */\n"
            "let s = '//# sourceMappingURL=not-a-comment';\n"
            "// TODO: eslint-disable-next-line does not belong here\n"
            "// eslint-disable-not-a-command prose\n"
            "// @ts-ignoreish\n"
            "/// <reference types=\"node\" />\n"
        )
        self.assert_comments("index.ts", source, [(6, 6), (12, 12), (13, 13), (14, 14)])

    def test_licenses_do_not_exempt_ordinary_prose(self):
        source = (
            "/* SPDX-License-Identifier: MIT */\n"
            "/*!\n * @license MIT\n * Copyright (c) 2020 Someone\n */\n"
            "// We once discussed MIT licenses.\n"
            "/*! A note */\n"
        )
        self.assert_comments("source.js", source, [(6, 6), (7, 7)])

    def test_oxlint_and_biome_require_directive_syntax(self):
        source = (
            "// oxlint-disable-next-line no-console, no-plusplus\n"
            "logger(); // oxlint-disable-line no-console\n"
            "/* oxlint-disable */\n/* oxlint-enable no-console */\n"
            "// biome-ignore lint/suspicious/noExplicitAny: tool input is untyped\n"
            "// An example of biome-ignore lint/style/useConst: prose\n"
            "// biome-ignore lint/suspicious/noDoubleEquals without a reason separator\n"
            "// biome-ignore not/a/biome/category: ordinary prose\n"
            "// oxlint-disableword ignore all of this\n"
        )
        self.assert_comments("check.ts", source, [(6, 6), (7, 7), (8, 8), (9, 9)])

    def test_apache_header_has_a_bounded_end(self):
        source = (
            "// Copyright 2026 Contributor\n"
            "// Licensed under the Apache License, Version 2.0 (the \"License\");\n"
            "// you may not use this file except in compliance with the License.\n"
            "// You may obtain a copy of the License at\n"
            "//\n//     https://www.apache.org/licenses/LICENSE-2.0\n"
            "//\n// Unless required by applicable law or agreed to in writing, software\n"
            "// distributed under the License is distributed on an \"AS IS\" BASIS,\n"
            "// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
            "// See the License for the specific language governing permissions and\n"
            "// limitations under the License.\n"
            "// Do not skip this explanation.\n"
        )
        self.assert_comments("api.ts", source, [(13, 13)])
        self.assert_comments("api.ts", "// Copyright 2026 A\n// ordinary header note", [(2, 2)])

    def test_exported_prose_doc_requires_identifiable_documentation_input(self):
        self.assert_comments("api.ts", "/** @public Published API. */\nexport function x(){}", [])
        self.assert_comments("api.ts", "/** Someone wrote this once. */\nexport function y(){}", [(1, 1)])

    def test_python_literals_and_directives(self):
        source = (
            "#!/usr/bin/python3\n# -*- coding: utf-8 -*-\n"
            "'''# not a comment'''\n"
            'value = "# still a string"  # type: ignore[assignment]\n'
            "# noqa: F401, E501\n"
            "flag = True  # why\n"
            "# merely mentions noqa\n"
            "# eslint-disable-line\n"
            "# type: this is only a note about types\n"
            "v = None  # type: dict[str, int]\n"
        )
        self.assert_comments("main.py", source, [(6, 6), (7, 7), (8, 8), (9, 9)])

    def test_postgres_nested_comments_and_quoted_markers(self):
        source = (
            "-- migrate:up\nSELECT '--literal', $tag$/* text */$tag$;\n"
            "/* outer\n /* nested */\n more */ /* next */ -- last\n"
        )
        self.assert_comments("migration.sql", source, [(3, 5), (5, 5), (5, 5)])

    def test_bash_heredoc(self):
        source = (
            "#!/bin/bash\n# shellcheck disable=SC2154\n"
            "cat <<'DATA'\n# literal\nDATA\n"
            "echo sample#fragment\n# actual\n"
        )
        self.assert_comments("script.sh", source, [(7, 7)])

    def test_html_document_and_embedded_languages(self):
        source = (
            '<!doctype html><div title="<!-- literal -->">Example</div>\n'
            "<!-- actual -->\n<script type='application/json'>\"// data\"</script>\n"
            "<script type=module>const a='// literal';\n// actual\n</script>\n"
            '<style>p{content:"/* data */";} /* actual */</style>'
        )
        self.assert_comments("page.html", source, [(2, 2), (5, 5), (7, 7)])

    def test_other_languages(self):
        cases = {
            "theme.css": ('p::before{content:"/* literal */"} /* real */', [(1, 1)]),
            "a.swift": ('/// API docs\nlet x = #"// literal"#\n/* outer /* inner */ end */', [(3, 3)]),
            "a.rb": ("# frozen_string_literal: true\nx='#literal'\n# actual", [(3, 3)]),
            "a.go": ("//go:embed fixture.txt\nvar x = `// text`\n// real", [(3, 3)]),
            "a.rs": ('/// generated docs\nfn f(){ let s = r#"// text"#; /* actual */ }', [(2, 2)]),
            "a.kt": ('/** API docs */\nval x = "// text"\n// actual', [(3, 3)]),
            "a.yaml": ('# yaml-language-server: $schema=x\na: |\n  # literal\n# actual', [(4, 4)]),
            "a.ps1": ("#Requires -Version 7\n$x=@'\n# literal\n'@\n<# first\nlast #>", [(5, 6)]),
        }
        for path, (source, expected) in cases.items():
            with self.subTest(path=path):
                self.assert_comments(path, source, expected)

    def test_native_doc_markers_are_language_specific(self):
        self.assert_comments("lib/Package.swift", "// swift-tools-version: 6.0\n// explanation", [(2, 2)])
        self.assert_comments("view.swift", "// swift-tools-version: 6.0", [(1, 1)])
        self.assert_comments("import.ts", "import(/* @vite-ignore */ url);\n// @vite-ignore this", [(2, 2)])
        self.assert_comments("a.kt", "/// prose\n/*!" + " prose */", [(1, 1), (2, 2)])
        self.assert_comments("a.swift", "//! prose\n//// prose", [(1, 1), (2, 2)])
        self.assert_comments("a.rs", "/// API docs\n//// prose\n/*** ordinary */", [(2, 2), (3, 3)])

    def test_paths_and_known_generator_signature(self):
        for path in ["README.md", "app/vendor/widget.js", "third_party/example.py",
                     "node_modules/module/index.js", "bundle.min.js", "lib/model.generated.ts",
                     "generated/models.py", "api/service_pb2.py"]:
            with self.subTest(path=path):
                self.assertFalse(executable_code_path(path))
                self.assert_comments(path, "// bad", [])
        self.assertTrue(executable_code_path("src/vendor-query.ts"))
        self.assertTrue(executable_code_path("tests/check.py"))
        self.assert_comments("service.go", "// Code generated by protoc-gen-go. DO NOT EDIT.\n// data", [])
        self.assert_comments("service.go", "// should be generated\n// because\n", [(1, 1), (2, 2)])


if __name__ == "__main__":
    unittest.main()
