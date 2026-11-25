# Source Comment Check

Check comments in the Git index before committing, or compare two Git revisions. The check reports new or edited explanatory comments with their file and line number. Existing comments outside the change can stay until their code is revisited.

## Local Git

From a stable checkout of this tool, use Python 3.13 and a Git client that supports named hooks:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python install_hook.py
```

The installer adds a named pre-commit hook to the current user's Git configuration. Existing repository hooks still run. Every working copy using this Git configuration uses the same checker. Update the stable checkout to a reviewed revision and refresh its virtual environment when requirements change.

To remove just this hook, run `git config --global --remove-section hook.source-comment-check`. Clients with a separate Git configuration need their own installation.

## GitHub

Call the shared action from a pull request workflow with read access to repository contents. A push workflow can also compare the previous and new revisions. The action reports a failing status for violations. Repository settings and the delivery process determine whether a failing status blocks merging.

```yaml
name: Source comments
on: pull_request
permissions:
  contents: read
jobs:
  comments:
    runs-on: ubuntu-latest
    steps:
      - uses: johan-eilertsen/source-comment-check@main
```

## Run directly

From a repository with changes, use the tool's checkout and its virtual environment:

```sh
"$TOOL/.venv/bin/python" -EsB "$TOOL/check_comments.py" --staged
"$TOOL/.venv/bin/python" -EsB "$TOOL/check_comments.py" --base "$BASE" --head "$HEAD_REVISION"
```

Use the checked tree's Git attributes `linguist-generated` and `linguist-vendored` to identify generated and third-party files stored alongside authored sources. Review changes to these attributes as changes in scope.

If documentation is published from untagged JSDoc in specific JavaScript or TypeScript files, mark those inputs in `.gitattributes`, for example `src/api.ts source-comment-documentation`. Ordinary explanatory comments in the same file are still checked.

## Policy

An ordinary explanation such as `// Keep the old selection` is reported if the change adds or edits it. Comment markers in a string, a regular expression or JSX text are data. The checker preserves recognized tool directives, license notices, shebangs and structured documentation. It reports findings without editing the source.

Supported sources include JavaScript, TypeScript, JSX, TSX, Python, shell, CSS, HTML, Swift, Ruby, Go, Rust, Kotlin, YAML, PostgreSQL and PowerShell. The check also recognizes Python and shell commands by their interpreter line, Brewfiles, TOML and common JSON-with-comments configurations. Dockerfile support uses a prebuilt grammar on Apple Silicon and x86-64 Linux, including the GitHub runner. A Dockerfile change on a platform without that grammar reports the missing capability. Conventional generated and vendored paths are skipped.

For a different policy, [Lauren Tan’s review skill](https://github.com/cursor/plugins/tree/main/pstack/skills/no-comments) helps decide which comments to remove. [Matt Pocock’s project rule](https://github.com/mattpocock/course-video-manager/blob/887f7904647a41ab997911817b60bd90e9304680/lint/rules/no-comments.ts) shows how to enforce a comment policy in a JavaScript or TypeScript project. This tool uses the same check across supported languages and Git repositories.

## Development

Run `python -m unittest discover -v` in the tool environment. Contributions that affect a language should include a small accepted example and a rejected example. The MIT license permits reuse and adaptation.
