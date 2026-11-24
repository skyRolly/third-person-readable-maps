"""Regression coverage for the source-bound Netty compatibility focus erratum."""

import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "diagnostics/issue45-runtime/assess_upstream_compatibility.py"
REGISTER = ROOT / "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23/priority-register-v6.json"
OLD = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23/remediation-compatibility.json"
CORRECTED = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23/remediation-compatibility-v2.json"

SPEC = importlib.util.spec_from_file_location("issue45_netty_focus", SCRIPT)
FOCUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FOCUS)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "issue45_runtime_validator_for_focus",
    ROOT / "diagnostics/issue45-runtime/validate_runtime_evidence.py")
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class NettyFocusErratumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.register = json.loads(REGISTER.read_text(encoding="utf-8"))
        cls.report = json.loads(CORRECTED.read_text(encoding="utf-8"))

    def test_cross_platform_java_tests_have_independent_native_exit_codes(self):
        workflow = (ROOT / ".github/workflows/credential-guard-tests.yml").read_text(
            encoding="utf-8")
        archive_cmd = "python diagnostics/issue45-runtime/validate_runtime_evidence.py"
        controls_cmd = "python diagnostics/issue45-runtime/run_controls.py"
        runtime_cmd = ('python -m unittest discover -s tests '
                       '-p "test_issue45_runtime_pipeline_evidence.py" -v')
        erratum_cmd = ('python -m unittest discover -s tests '
                       '-p "test_issue45_netty_compatibility_focus.py" -v')

        def required_checks(major):
            work = "issue45-agent-j21" if major == 21 else "issue45-agent-café-j25"
            work_dir = '"${{ runner.temp }}/' + work + '"'
            evidence_dir = '"${{ runner.temp }}/issue45-evidence-j' + str(major) + '"'
            control_label = (
                "Exercise Issue 45 diagnostic privacy and populated snapshots on Java 21"
                if major == 21 else
                "Exercise Issue 45 diagnostic class transformations on Java 25")
            return (
                (control_label, f"{controls_cmd} --work-dir {work_dir} --fresh-evidence-dir {evidence_dir}"),
                (f"Validate regenerated Java {major} runtime archive",
                 f"{archive_cmd} --evidence-dir {evidence_dir} --expected-synthetic-java-major {major}"),
                (f"Test Java {major} runtime evidence and privacy regressions", runtime_cmd),
                (f"Test Java {major} Netty erratum mutation regressions", erratum_cmd),
            )

        def step_fields(source: str) -> list[dict]:
            """Read the guard workflow's simple block-style step mappings.

            This deliberately checks the repository's supported layout, not
            arbitrary YAML. Every sequence item starts a new step (including
            unnamed steps); comments and blank lines do not end a step.
            Block-valued run commands cannot satisfy the isolation contract.
            """
            def mapping_field(field):
                # A space before ':' is legal YAML, as are simple quoted keys.
                # Normalize before matching or detecting duplicates. Complex
                # keys, tags, aliases and merge keys are outside this layout;
                # reject rather than silently overlook a security-relevant key.
                match = re.fullmatch(
                    r"""(?:([A-Za-z0-9_-]+)|'([A-Za-z0-9_-]+)'|"([A-Za-z0-9_-]+)")[ ]*:(.*)""",
                    field)
                if match is None:
                    raise ValueError("unsupported workflow mapping field")
                key = next(part for part in match.groups()[:3] if part is not None)
                value = match[4].strip().split(" #", 1)[0].strip()
                if value.startswith("#"):
                    value = ""
                return key, value

            event_name = r"""(?:[A-Za-z0-9_-]+|'[A-Za-z0-9_-]+'|"[A-Za-z0-9_-]+")"""
            # Decode only quoted hexadecimal escapes in nested trigger keys.
            # They can spell the same ASCII filter/description names without
            # changing YAML semantics. Never use this grammar for root/jobs/
            # guard/step keys: their strict mapping_field policy is unchanged.
            nested_key = (
                r"""(?:[A-Za-z0-9_-]+|'[A-Za-z0-9_-]+'|"(?:[A-Za-z0-9_-]|\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}))+")""")

            def nested_mapping_field(field):
                match = re.fullmatch(rf"({nested_key})[ \t]*:[ \t]*(.*)", field)
                if match is None:
                    return None
                key = match[1]
                if key.startswith('"'):
                    def decode_hex(escape):
                        codepoint = int(escape[0][2:], 16)
                        if codepoint > 0x10ffff or 0xd800 <= codepoint <= 0xdfff:
                            raise ValueError("invalid Unicode escape in nested trigger key")
                        return chr(codepoint)
                    key = re.sub(r"\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8})",
                                 decode_hex, key[1:-1])
                elif key.startswith("'"):
                    key = key[1:-1]
                return key, match[2]

            event_flow_list = re.compile(
                rf"\[[ \t]*{event_name}(?:[ \t]*,[ \t]*{event_name})*[ \t]*,?[ \t]*\]")

            def trigger_flow_complete(parts, field):
                # Only simple event tokens may be consumed while a flow list
                # is open. A root mapping key must never become list content.
                # YAML permits tabs as flow-token separation, not as block
                # indentation or characters inside these simple event names.
                field = re.split(r"[ \t]+#", field, maxsplit=1)[0].rstrip(" \t")
                if not re.fullmatch(r"""[A-Za-z0-9_'" \t,\[\]-]+""", field):
                    raise ValueError("unsupported flow trigger list content")
                parts.append(field)
                if "]" not in field:
                    return False
                if not event_flow_list.fullmatch(" ".join(parts)):
                    raise ValueError("malformed flow trigger list")
                return True

            def quoted_scalar_end(field, quote):
                """Find a closing quote, without interpreting scalar contents."""
                i = 0
                while i < len(field):
                    char = field[i]
                    if quote == '"' and char == "\\":
                        i += 2
                        continue
                    if char == quote:
                        if char == "'" and field[i:i + 2] == "''":
                            i += 2
                            continue
                        return i + 1
                    i += 1
                return None

            def consume_description_quote(field):
                nonlocal nested_description_quote
                end = quoted_scalar_end(field, nested_description_quote)
                if end is None:
                    return
                remainder = field[end:]
                if remainder.strip() and not re.fullmatch(r"[ \t]+#.*", remainder):
                    raise ValueError("extra content after quoted description")
                nested_description_quote = None

            def nested_filter_flow_complete(field):
                # Filter patterns are not event identifiers: glob characters,
                # slashes, and quoted brackets are legitimate here. Track
                # only a scalar flow list's boundary, not filter semantics.
                # Do not consume mapping keys or nested collections while
                # looking for the closing bracket.
                nonlocal nested_filter_quote
                while field:
                    if nested_filter_quote is not None:
                        # A quote opened on a preceding physical line remains
                        # open across YAML folding or a backslash continuation.
                        # Inside it, brackets and hash characters are data.
                        end = quoted_scalar_end(field, nested_filter_quote)
                        if end is None:
                            return False
                        nested_filter_quote = None
                        field = field[end:]
                        continue
                    field = field.lstrip(" \t")
                    if not field or field.startswith("#"):
                        return False
                    if field[0] == "]":
                        remainder = field[1:].strip(" \t")
                        if remainder and not remainder.startswith("#"):
                            raise ValueError("extra content after nested filter list")
                        return True
                    if field[0] in "'\"":
                        nested_filter_quote = field[0]
                        field = field[1:]
                        continue
                    if field[0] == ",":
                        field = field[1:]
                        continue
                    # A colon separating a mapping key must not be consumed
                    # as a continuation token, even at zero indentation.
                    # Once a plain scalar starts, apostrophes and double
                    # quotes inside it are literal characters, not openers.
                    # A separated # begins a comment; a colon followed by
                    # separation or a flow delimiter remains a mapping key.
                    plain = re.match(
                        r"""(?:[^ \t,\[\]{}:'"]|:(?![ \t,\[\]{}]|$))"""
                        r"""(?:(?![ \t]#)[^,\[\]{}:]|:(?![ \t,\[\]{}]|$))*""",
                        field)
                    if plain is None:
                        raise ValueError("unsupported nested filter flow content")
                    field = field[plain.end():]
                return False

            steps = []
            current = None
            parent_key = None
            seen_jobs = seen_guard = seen_steps = False
            in_trigger_block = False
            trigger_layout = None
            trigger_indent = None
            trigger_flow = []
            nested_filter_flow = False
            nested_filter_quote = None
            nested_filter_value_indent = None
            nested_description_value_indent = None
            nested_description_quote = None
            nested_scalar_indent = None
            seen_document_start = seen_document_content = document_ended = False
            filter_keys = {"branches", "branches-ignore", "paths", "paths-ignore",
                           "tags", "tags-ignore", "types", "workflows", "options"}
            in_jobs = False
            in_guard = False
            in_steps = False
            for line in source.splitlines():
                # A comment-looking line inside an open quoted scalar is
                # text, not a YAML comment. Keep its closing quote visible.
                if nested_filter_quote is None and nested_description_quote is None and (
                        not line.strip() or line.lstrip().startswith("#")):
                    continue
                indent = len(line) - len(line.lstrip(" "))
                if document_ended:
                    raise ValueError("content after YAML document end")
                # Allow one optional standalone start/end indicator only at
                # the document boundaries, not while a trigger value is open.
                marker = re.fullmatch(r"(---|\.\.\.)(?:[ \t]+(?:#.*)?)?", line)
                if (marker and trigger_layout != "flow" and not nested_filter_flow
                        and nested_description_quote is None):
                    if marker[1] == "---":
                        if seen_document_start or seen_document_content:
                            raise ValueError("multiple YAML documents")
                        seen_document_start = True
                    else:
                        if not seen_document_content:
                            raise ValueError("empty YAML document")
                        document_ended = True
                    continue
                seen_document_content = True
                # Track the collection kind and indentation of an open on:
                # value. Nested event filters may contain their own lists,
                # but sibling event mappings and scalar sequence items cannot
                # be mixed, and an indentless list cannot start after a map.
                root_item = indent == 0 and (line == "-" or line.startswith("- "))
                if in_trigger_block and trigger_layout == "flow":
                    if trigger_flow_complete(trigger_flow, line.strip().split(" #", 1)[0].strip()):
                        trigger_layout = "complete"
                    continue
                if in_trigger_block and (nested_filter_quote is not None
                                         or nested_description_quote is not None) and indent == 0:
                    # Keep the existing conservative root boundary policy for
                    # both kinds of open quoted scalar.
                    document_marker = re.match(r"(?:---|\.\.\.)(?:[ \t]|$)", line)
                    if (re.match(rf"{nested_key}[ \t]*:", line)
                            or line.startswith(("? ", "<<:")) or document_marker):
                        raise ValueError("root mapping inside unfinished quoted scalar")
                if in_trigger_block and nested_filter_flow:
                    nested_filter_flow = not nested_filter_flow_complete(line.strip())
                    continue
                if in_trigger_block and nested_description_quote is not None:
                    consume_description_quote(line.strip())
                    continue
                if in_trigger_block and nested_scalar_indent is not None:
                    # Indented block-scalar text is not YAML structure, even
                    # when it looks like a filter or contains Markdown links.
                    if indent > nested_scalar_indent:
                        continue
                    nested_scalar_indent = None
                if (nested_filter_value_indent is not None
                        and indent <= nested_filter_value_indent):
                    nested_filter_value_indent = None
                if (nested_description_value_indent is not None
                        and indent <= nested_description_value_indent):
                    nested_description_value_indent = None
                if in_trigger_block and line[indent:].startswith("\t"):
                    raise ValueError("tab indentation outside an open flow trigger list")
                if in_trigger_block and (indent > 0 or root_item):
                    field = line.strip().split(" #", 1)[0].strip()
                    if trigger_layout == "complete":
                        raise ValueError("extra content after complete trigger value")
                    if trigger_layout is None and indent > 0:
                        if field.startswith("["):
                            trigger_layout = ("complete" if trigger_flow_complete(trigger_flow, field)
                                              else "flow")
                            continue
                        if re.fullmatch(event_name, field):
                            trigger_layout = "complete"
                            continue
                    scalar_item = re.fullmatch(rf"- +{event_name}", field)
                    if trigger_layout is None:
                        trigger_layout = "sequence" if scalar_item else "mapping"
                        trigger_indent = indent
                        if trigger_layout == "mapping" and indent == 0:
                            raise ValueError("unsupported root trigger item")
                    if trigger_layout == "sequence":
                        if not scalar_item or indent != trigger_indent:
                            raise ValueError("mixed or inconsistently indented trigger sequence")
                    elif indent < trigger_indent:
                        raise ValueError("mixed trigger mapping and sequence")
                    elif indent == trigger_indent:
                        mapping_field(field)
                    else:
                        # A bracket at the start of arbitrary nested text is
                        # not a filter list. Only known list-valued fields (or
                        # their immediately following indented value) qualify.
                        value = line.strip()
                        pending = nested_filter_value_indent is not None
                        pending_description = nested_description_value_indent is not None
                        nested_filter_value_indent = nested_description_value_indent = None
                        if pending_description and value.startswith(("'", '"')):
                            nested_description_quote = value[0]
                            consume_description_quote(value[1:])
                        elif pending and value.startswith("["):
                            nested_filter_flow = not nested_filter_flow_complete(value[1:])
                        else:
                            nested = nested_mapping_field(value)
                            if nested is not None:
                                key, value = nested
                                header = re.split(r"[ \t]+#", value, maxsplit=1)[0].strip()
                                if header.startswith("#"):
                                    header = ""
                                if re.fullmatch(r"[|>](?:[1-9][+-]?|[+-][1-9]?)?", header):
                                    nested_scalar_indent = indent
                                elif key == "description":
                                    if value.startswith(("'", '"')):
                                        nested_description_quote = value[0]
                                        consume_description_quote(value[1:])
                                    elif not header:
                                        nested_description_value_indent = indent
                                elif key in filter_keys:
                                    if value.startswith("["):
                                        nested_filter_flow = not nested_filter_flow_complete(value[1:])
                                    elif not header:
                                        nested_filter_value_indent = indent
                    # Other event filter contents are outside the native shell
                    # contract; actionlint validates the actual workflow.
                    continue
                if indent == 0:
                    # Apply the same restricted mapping grammar at the root.
                    # Never interpret an unrecognized key as an unrelated
                    # section: escaped or explicit keys could denote defaults
                    # or jobs and change every required native command.
                    key, value = mapping_field(line)
                    in_trigger_block = key == "on" and not value
                    trigger_layout = trigger_indent = None
                    trigger_flow = []
                    nested_filter_flow = False
                    nested_filter_quote = None
                    nested_filter_value_indent = nested_scalar_indent = None
                    nested_description_value_indent = nested_description_quote = None
                    if key == "on" and value.startswith("["):
                        in_trigger_block = True
                        trigger_layout = ("complete" if trigger_flow_complete(trigger_flow, value)
                                          else "flow")
                    elif key == "on" and re.fullmatch(event_name, value):
                        in_trigger_block = True
                        trigger_layout = "complete"
                    if key == "defaults":
                        raise ValueError("workflow defaults may override the native shell")
                    # Ignore unrelated section bodies, not unknown key syntax.
                    # Do not carry guard/steps state across a boundary.
                    in_jobs = key == "jobs"
                    if in_jobs:
                        if seen_jobs or value:
                            raise ValueError("duplicate or unsupported jobs mapping")
                        seen_jobs = True
                    in_guard = in_steps = False
                    current = None
                    continue
                if not in_jobs:
                    continue
                if indent == 2:
                    key, value = mapping_field(line.strip())
                    in_guard = key == "guard"
                    if in_guard:
                        if seen_guard or value:
                            raise ValueError("duplicate or unsupported guard mapping")
                        seen_guard = True
                    in_steps = False
                    current = None
                    continue
                if not in_guard:
                    continue
                if indent == 4:
                    key, value = mapping_field(line.strip())
                    if key in {"if", "continue-on-error", "defaults"}:
                        raise ValueError("guard job may skip checks or override native execution")
                    in_steps = key == "steps"
                    if in_steps:
                        if seen_steps or value:
                            raise ValueError("duplicate or unsupported steps mapping")
                        seen_steps = True
                    current = None
                    # The header is not itself a sequence item.
                    continue
                if not in_steps:
                    continue
                if line == "      -" or line.startswith("      - "):
                    current = {}
                    parent_key = None
                    steps.append(current)
                    field = line[8:]
                    if not field.strip() or field.lstrip().startswith("#"):
                        continue
                elif current is not None and line.startswith("        "):
                    field = line[8:]
                    if field.startswith(" "):
                        if parent_key == "run" and current.get("run", "").startswith(("|", ">")):
                            current["script"] = current.get("script", "") + "\n" + field.strip()
                        elif parent_key == "with":
                            if not field.startswith("  ") or field.startswith("   "):
                                raise ValueError("unsupported workflow with indentation")
                            key, value = mapping_field(field[2:])
                            if key == "java-version":
                                if key in current:
                                    current["duplicate"] = True
                                current[key] = value
                        continue
                else:
                    raise ValueError("unsupported workflow step layout")
                key, value = mapping_field(field)
                parent_key = key
                if key in {"name", "run", "uses", "with", "if", "continue-on-error", "shell"}:
                    if key in current:
                        current["duplicate"] = True
                    current[key] = value
            if trigger_layout == "flow" or nested_filter_flow or nested_description_quote is not None:
                raise ValueError("unterminated trigger list or quoted description")
            return steps

        def all_native_checks_isolated(source: str) -> bool:
            try:
                steps = step_fields(source)
            except ValueError:
                return False
            java = None
            seen = []
            invocations = {command: 0 for command in
                           (controls_cmd, archive_cmd, runtime_cmd, erratum_cmd)}
            for step in steps:
                if step.get("uses", "").startswith("actions/setup-java@"):
                    # A skipped or failure-tolerant setup cannot establish the
                    # Java identity of the subsequent native checks.
                    if step.get("duplicate") or "if" in step or "continue-on-error" in step:
                        return False
                    java = step.get("java-version", "").strip("'\"").split(".", 1)[0]
                run = step.get("run", "")
                script = run + "\n" + step.get("script", "")
                for command in invocations:
                    invocations[command] += script.count(command)
                for major in (21, 25):
                    for label, command in required_checks(major):
                        if step.get("name") == label:
                            if (java != str(major) or run != command or step.get("duplicate")
                                    or "if" in step or "continue-on-error" in step
                                    or "shell" in step):
                                return False
                            seen.append((major, label))
            return (seen == [(major, label) for major in (21, 25)
                             for label, _ in required_checks(major)]
                    and all(count == 2 for count in invocations.values()))

        self.assertTrue(all_native_checks_isolated(workflow))

        # Build semantic fixtures independently of the formatting in the
        # checked-in workflow. Exercise the same predicate as the real file.
        def setup(major):
            return (f"      - uses: actions/setup-java@pinned\n"
                    f"        with:\n          java-version: '{major}.0.1'\n")

        def check(major, index, comment=False):
            label, command = required_checks(major)[index]
            return (f"      - name: {label}\n"
                    + ("        # Harmless comment\n\n" if comment else "")
                    + f"        run: {command}\n")

        prefix = "jobs:\n  guard:\n    steps:\n"
        j21 = [check(21, i) for i in range(4)]
        j25 = [check(25, i) for i in range(4)]
        tail = setup(25) + "".join(j25)
        good = prefix + setup(21) + "".join(j21) + tail
        self.assertTrue(all_native_checks_isolated(good))
        benign = (prefix + setup(21) + j21[0] + check(21, 1, comment=True)
                  + "      # Between steps\n\n" + j21[2] + j21[3]
                  + "      - id: unrelated\n        run: python -V\n" + tail)
        self.assertTrue(all_native_checks_isolated(benign))
        # Unrelated sections and sibling jobs must not enter the step parser.
        for suffix in ("", "concurrency:\n  group: guard-ci\n  cancel-in-progress: true\n",
                       "  other:\n    steps:\n      - run: python -V\n"):
            with self.subTest(unrelated_suffix=suffix):
                self.assertTrue(all_native_checks_isolated(
                    "on:\n  - push\n  - pull_request\n" + good + suffix))
        self.assertTrue(all_native_checks_isolated(
            good.replace("    steps:\n", "    steps: # list header\n", 1)))
        self.assertFalse(all_native_checks_isolated(
            good.replace("    steps:\n", "    steps:\n      unexpected: true\n", 1)))
        self.assertFalse(all_native_checks_isolated(
            good.replace("  guard:\n", "  unrelated:\n", 1)))
        # Job-level gates and duplicate structural keys cannot be ignored.
        for modifier in ("if : false", '"if" : ${{ false }}', "continue-on-error : true"):
            mutated = good.replace("  guard:\n", f"  guard:\n    {modifier}\n", 1)
            self.assertNotEqual(good, mutated)
            self.assertFalse(all_native_checks_isolated(mutated))
        for suffix in ('"jobs" : {}\n', '  "guard" : {}\n', '    "steps" : []\n'):
            self.assertFalse(all_native_checks_isolated(good + suffix))
        # A custom PowerShell template does not get GitHub's default exit
        # propagation wrapper. Preserve the implicit OS shell for each
        # required native command, and reject inherited defaults as well.
        for major in (21, 25):
            for index in range(4):
                original = check(major, index)
                for override in ("shell: pwsh -File {0}", '"shell" : pwsh -File {0}',
                                 "shell : bash {0}", "shell: pwsh"):
                    mutated = good.replace(original, original + f"        {override}\n", 1)
                    with self.subTest(java=major, check=index, shell=override):
                        self.assertNotEqual(good, mutated)
                        self.assertFalse(all_native_checks_isolated(mutated))
        for defaults in ("defaults:\n  run:\n    shell: pwsh -File {0}\n",
                         '"defaults" : {run: {shell: "pwsh -File {0}"}}\n'):
            self.assertFalse(all_native_checks_isolated(defaults + good))
            self.assertFalse(all_native_checks_isolated(good + defaults))
        for defaults in ("    defaults:\n      run:\n        shell: pwsh -File {0}\n",
                         '    "defaults" : {run: {shell: "pwsh -File {0}"}}\n'):
            self.assertFalse(all_native_checks_isolated(
                good.replace("    steps:\n", defaults + "    steps:\n", 1)))
        # Escaped or explicit top-level keys must never be silently ignored.
        # This parser deliberately rejects unsupported representations,
        # rather than trying to implement YAML escape/complex-key semantics.
        for key in (r'"\u0064efaults"', r'"\x64efaults"',
                    r'"\U00000064efaults"', r'"def\u0061ults"'):
            for value in (":\n  run:\n    shell: pwsh -File {0}\n",
                          ': {run: {shell: "pwsh -File {0}"}}\n'):
                defaults = key + value
                for mutated in (defaults + good, good + defaults):
                    with self.subTest(root_key=key, value=value):
                        self.assertNotEqual(good, mutated)
                        self.assertFalse(all_native_checks_isolated(mutated))
        for extra in ("? defaults\n: {run: {shell: 'pwsh -File {0}'}}\n",
                      '<<: {defaults: {run: {shell: "pwsh -File {0}"}}}\n',
                      r'"\u006aobs" : {}' + "\n"):
            self.assertFalse(all_native_checks_isolated(extra + good))
            self.assertFalse(all_native_checks_isolated(good + extra))
        self.assertTrue(all_native_checks_isolated(
            '"on" :\n  - push\n  - pull_request\n'
            + good + "'concurrency' :\n  group: guard-ci\n"))
        # A block sequence may align with its on key in valid YAML.
        # Exercise both positions so exiting jobs and re-entering root
        # classification cannot accidentally hide a defaults override.
        for header in ("on:", '"on" : # events', "'on':"):
            triggers = header + "\n- push\n# events\n\n- 'pull_request' # PRs\n- \"workflow_dispatch\"\n"
            for source in (triggers + good, good + triggers):
                with self.subTest(trigger_header=header, position=source.startswith(header)):
                    self.assertTrue(all_native_checks_isolated(source))
                    self.assertFalse(all_native_checks_isolated(
                        source + "defaults:\n  run:\n    shell: pwsh -File {0}\n"))
                    self.assertFalse(all_native_checks_isolated(
                        source + r'"\u0064efaults": {run: {shell: "pwsh -File {0}"}}' + "\n"))
        # An arbitrary root sequence, a nonempty on value, or a sequence
        # under jobs must not obtain the trigger-list exception.
        for malformed in ("- push\n" + good,
                          good + "- push\n",
                          "on: push\n- pull_request\n" + good,
                          "on:\n- push\npermissions:\n- pull_request\n" + good,
                          "on:\n- {defaults: {run: {shell: pwsh}}}\n" + good,
                          "on:\n- push\njobs:\n- pull_request\n" + good):
            self.assertFalse(all_native_checks_isolated(malformed))
        # Independently authored trigger fixtures distinguish collection
        # kinds, not just the presence of a preceding on header.
        for triggers in (
                "on:\n  push:\n    branches:\n      - main\n  pull_request:\n",
                "on:\n  push:\n    branches:\n    - main\n  workflow_dispatch:\n",
                "on:\n  - push\n  - pull_request\n",
                "on:\n- push\n- pull_request\n",
                "on: [push, pull_request]\n",
                "on: push\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(valid_triggers=triggers):
                    self.assertTrue(all_native_checks_isolated(source))
                    self.assertFalse(all_native_checks_isolated(
                        source + r'"\u0064efaults": {run: {shell: "pwsh -File {0}"}}' + "\n"))
        for triggers in (
                "on:\n  push:\n- pull_request\n",
                "on:\n  push:\n  - pull_request\n",
                "on:\n  push:\n    branches:\n      - main\n- pull_request\n",
                "on:\n- push\n  pull_request:\n",
                "on:\n  - push\n  pull_request:\n",
                "on:\n  - push\n- pull_request\n",
                "on:\n- push\n  - pull_request\n",
                "on:\n  - push\n    - pull_request\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(mixed_triggers=triggers):
                    self.assertFalse(all_native_checks_isolated(source))
        # A flow-style event list has the same value whether it follows
        # the on key or occupies an indented line. Multi-line lists must
        # consume only event tokens, not a following root mapping.
        for triggers in (
                "on: [push, pull_request]\n",
                "on:\n  [push, pull_request]\n",
                '"on" : # events\n  ["push", \'pull_request\',] # list\n',
                "on: [push,\n  pull_request]\n",
                "on:\n  [\n    push, # comment\n    pull_request,\n  ]\n",
                "on: [\npush,\npull_request\n]\n",
                "on:\n  push\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(flow_triggers=triggers):
                    self.assertTrue(all_native_checks_isolated(source))
                    for defaults in ("defaults: {run: {shell: 'pwsh -File {0}'}}\n",
                                     r'"\u0064efaults": {run: {shell: "pwsh -File {0}"}}' + "\n"):
                        self.assertFalse(all_native_checks_isolated(source + defaults))
        for triggers in (
                "on:\n  [push, pull_request]\n  - workflow_dispatch\n",
                "on: [push, pull_request]\n  push:\n",
                "on:\n  [push, pull_request]\n- workflow_dispatch\n",
                "on:\n  [push,\n",
                "on: [push,\n",
                "on:\n  [push,, pull_request]\n",
                "on: [push,, pull_request]\n",
                "on:\n  [push, {pull_request: {}}]\n",
                "on:\n  [push,\ndefaults: {run: {shell: pwsh}}\n]\n",
                "on:\n  [push,\n" + r'"\u0064efaults": {}' + "\n]\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(invalid_flow_triggers=triggers):
                    self.assertFalse(all_native_checks_isolated(source))
        # Horizontal tabs are valid flow-token separators. They are not
        # block indentation or part of an event identifier in this grammar.
        for triggers in (
                "on: [push,\tpull_request]\n",
                "on:\n  [push,\tpull_request]\n",
                'on: [\tpush\t, \t"pull_request"\t,\t]\n',
                "on: [push,\t# comment\n  pull_request]\t# end\n",
                "on:\n  [push,\n  \tpull_request,\t]\n",
                "on: [push,\n\tpull_request]\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(tab_flow_triggers=triggers):
                    self.assertTrue(all_native_checks_isolated(source))
                    for defaults in ("defaults: {run: {shell: 'pwsh -File {0}'}}\n",
                                     r'"\u0064efaults": {run: {shell: "pwsh -File {0}"}}' + "\n"):
                        self.assertFalse(all_native_checks_isolated(source + defaults))
        for triggers in (
                "on: [pu\tsh, pull_request]\n",
                'on: ["pu\tsh", pull_request]\n',
                "on: [push,\t, pull_request]\n",
                "on:\n \t[push, pull_request]\n",
                "on:\n\t[push, pull_request]\n",
                "on: [push,\t\n",
                "on: [push,\t\ndefaults: {run: {shell: pwsh}}\n]\n",
                "on: [push,\t\n" + r'"\u0064efaults": {}' + "\n]\n",
                "on: [push,\tpull_request]\n\t- workflow_dispatch\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(invalid_tab_flow_triggers=triggers):
                    self.assertFalse(all_native_checks_isolated(source))
        # A nested event-filter flow list has its own continuation boundary.
        # It can wrap at tabs, and its patterns are not simple event names.
        for triggers in (
                "on:\n  push:\n    branches: [main,\n      \trelease/**]\n",
                "on:\n  push:\n    branches: [main,\n\trelease/**]\n",
                "on:\n  push:\n    branches:\n      [main,\n      \t'release/[0-9]']\n",
                "on:\n  push:\n    branches: [main,\n    \t'!release/**',\n    \t'feature/#tag']\n",
                "on:\n  push:\n    branches: [main,\n      \trelease/**]\n  pull_request:\n",
                'on:\n  pull_request:\n    paths: ["src/**",\t# comment\n'
                '      \t"docs/[a-z]/**"] # done\n    types: [opened,\n      \tsynchronize]\n',
                "on:\n  push:\n    tags: [v1,\n      \tv2]\n    branches-ignore: [dev,\n      \ttest]\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(nested_filter_triggers=triggers):
                    self.assertTrue(all_native_checks_isolated(source))
                    for defaults in ("defaults: {run: {shell: 'pwsh -File {0}'}}\n",
                                     r'"\u0064efaults": {}' + "\n"):
                        self.assertFalse(all_native_checks_isolated(source + defaults))
        for triggers in (
                "on:\n  push:\n    branches: [main,\n",
                "on:\n  push:\n    branches: [main,\ndefaults: {run: {shell: pwsh}}\n]\n",
                "on:\n  push:\n    branches: [main,\n" + r'"\u0064efaults": {}' + "\n]\n",
                "on:\n  push:\n    branches: [main,\n\tjobs: {}\n]\n",
                "on:\n  push:\n    branches: [main]\n    \t- release/**\n",
                "on:\n  push:\n    branches: [main,\n      \trelease/**]\n- pull_request\n",
                "on:\n  push:\n    branches: [main,\n      \trelease/**] extra\n",
                'on:\n  push:\n    branches: [main,\n      \t"unterminated\n'):
            for source in (triggers + good, good + triggers):
                with self.subTest(invalid_nested_filter_triggers=triggers):
                    self.assertFalse(all_native_checks_isolated(source))
        # Plain scalar quotes belong to the pattern; Markdown and apparent
        # mapping/list syntax inside description scalars are not structure.
        for triggers in (
                "on:\n  push:\n    branches: [main, release/o'neil]\n",
                "on:\n  push:\n    branches: [main,\n      \trelease/o'neil]\n",
                'on:\n  push:\n    branches: [main, release/o"neil]\n',
                "on:\n  push:\n    branches: [main, 'release/o''neil', release/o'neil]\n",
                "on:\n  push:\n    branches: [main, release/o'neil, # comment: [\n"
                "      \t'feature/#tag']\n",
                "on:\n  push:\n    branches: [main, release/o'neil, release/x:y]\n",
                "on:\n  workflow_dispatch:\n    inputs:\n      target:\n"
                "        description: |\n"
                "          [Read docs](https://example.invalid/docs)\n"
                "          branches: [not an actual list\n"
                "          defaults: {run: {shell: pwsh}}\n        required: true\n",
                "on:\n  workflow_dispatch:\n    inputs:\n      target:\n"
                "        description: >- # folded prose\n          Read the guide:\n"
                "          [Documentation](https://example.invalid/docs)\n        type: string\n",
                "on:\n  workflow_dispatch:\n    inputs:\n      target:\n"
                "        description: |2-\n"
                "          [Documentation](https://example.invalid/docs)\n        type: string\n",
                "on:\n  workflow_dispatch:\n    inputs:\n      target:\n"
                "        description: >-2\n"
                "          [Documentation](https://example.invalid/docs)\n        type: string\n",
                "on:\n  workflow_dispatch:\n    inputs:\n      target:\n"
                "        description: See the\n"
                "          [Documentation](https://example.invalid/docs)\n        type: string\n",
                "on:\n  workflow_dispatch:\n    inputs:\n      target:\n"
                "        description: |\n          branches: [\n"
                "          [Documentation](https://example.invalid/docs)\n"
                "        type: choice\n        options:\n          [one,\n           \ttwo]\n",
                "on:\n  push:\n    'branches': # list\n      [main,\n       \trelease/o'neil]\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(scalar_triggers=triggers):
                    self.assertTrue(all_native_checks_isolated(source))
                    for defaults in ("defaults: {run: {shell: 'pwsh -File {0}'}}\n",
                                     r'"\u0064efaults": {}' + "\n"):
                        self.assertFalse(all_native_checks_isolated(source + defaults))
        for triggers in (
                "on:\n  push:\n    branches: [main, release/o'neil] extra\n",
                "on:\n  push:\n    branches: [main,\n      \t'not closed\n",
                "on:\n  workflow_dispatch:\n    inputs:\n      target:\n"
                "        description: |\n          [Documentation](https://example.invalid/docs)\n"
                "defaults: {run: {shell: pwsh}}\n",
                "on:\n  workflow_dispatch:\n    inputs:\n      target:\n"
                "        description: |\n          [Documentation](https://example.invalid/docs)\n"
                + r'"\u0064efaults": {}' + "\n"):
            for source in (triggers + good, good + triggers):
                with self.subTest(invalid_scalar_triggers=triggers):
                    self.assertFalse(all_native_checks_isolated(source))
        # YAML double-quoted hexadecimal escapes can spell the same nested
        # filter key. Decode only in trigger context, never security-critical
        # root/job/step keys. Verify both inline and separately wrapped lists.
        for key in (r'"\u0062ranches"', r'"\x62ranches"',
                    r'"\U00000062ranches"', r'"br\u0061nches"',
                    r'"\u0062r\u0061nches"'):
            for value in (" [main,\n      \trelease/**]\n",
                          "\n      [main,\n      \trelease/**]\n",
                          " # comment\n      [main,\n      \trelease/**]\n"):
                triggers = "on:\n  push:\n    " + key + ":" + value
                for source in (triggers + good, good + triggers):
                    with self.subTest(escaped_filter=key, value=value):
                        self.assertTrue(all_native_checks_isolated(source))
                        for defaults in ("defaults: {run: {shell: pwsh}}\n",
                                         r'"\u0064efaults": {}' + "\n"):
                            self.assertFalse(all_native_checks_isolated(source + defaults))
        for triggers in (
                'on:\n  pull_request:\n    ' + r'"\u0070aths"' +
                ': [src/**,\n      \t"docs/[a-z]/**"]\n',
                'on:\n  workflow_dispatch:\n    inputs:\n      target:\n        ' +
                r'"\u0064escription"' + ': |\n          branches: [not a list\n'
                '          [Docs](https://example.invalid/docs)\n'
                '        type: choice\n        ' + r'"\u006fptions"' +
                ':\n          [one,\n           \ttwo]\n'):
            for source in (triggers + good, good + triggers):
                self.assertTrue(all_native_checks_isolated(source))
                self.assertFalse(all_native_checks_isolated(
                    source + r'"\u0064efaults": {}' + "\n"))
        for key in (r'"\u0062ranches"', r'"\x62ranches"'):
            for value in (" [main,\n",
                          "\n      [main,\ndefaults: {run: {shell: pwsh}}\n]\n",
                          "\n      [main,\n" + r'"\u0064efaults": {}' + "\n]\n",
                          " [main]\n      \t- release/**\n"):
                triggers = "on:\n  push:\n    " + key + ":" + value
                for source in (triggers + good, good + triggers):
                    self.assertFalse(all_native_checks_isolated(source))
        # Quoted filter patterns can span physical lines. A double-quoted
        # backslash continuation preserves the exact pattern; ordinary quoted
        # folding and escaped/doubled quotes also keep brackets/hash as data.
        for key in ("branches", r'"\u0062ranches"', r'"\x62ranches"'):
            for value in (
                    ' ["release/\\\n      stable", main]\n',
                    '\n      ["release/\\\n      \tstable", main]\n',
                    ' ["release/\\\nstable"]\n',
                    ' ["release/\\\n      #stable"]\n',
                    ' ["release/\\\n      [0-9]/**"]\n',
                    ' ["release/\\\n      stable\\"candidate"]\n',
                    " ['release/\n      o''neil']\n",
                    ' ["release/\n      stable"]\n',
                    ' ["release/\\\n      stable",\n      \tmain]\n'):
                triggers = "on:\n  push:\n    " + key + ":" + value
                for source in (triggers + good, good + triggers):
                    with self.subTest(wrapped_quoted_filter=key, value=value):
                        self.assertTrue(all_native_checks_isolated(source))
                        for defaults in ("defaults: {run: {shell: pwsh}}\n",
                                         r'"\u0064efaults": {}' + "\n"):
                            self.assertFalse(all_native_checks_isolated(source + defaults))
        for value in (
                ' ["release/\\\n',
                ' ["release/\\\n      stable\n',
                ' ["release/\\\ndefaults: {run: {shell: pwsh}}\n      stable"]\n',
                ' ["release/\\\n' + r'"\u0064efaults": {}' + '\n      stable"]\n',
                ' ["release/\\\njobs: {}\n      stable"]\n',
                ' ["release/\\\n      stable"] extra\n',
                ' ["release/\\\n      stable"]\n      \t- main\n'):
            triggers = "on:\n  push:\n    " + r'"\u0062ranches"' + ":" + value
            for source in (triggers + good, good + triggers):
                with self.subTest(invalid_wrapped_quote=value):
                    self.assertFalse(all_native_checks_isolated(source))
        # Document marker prefixes in quoted path text are not indicators.
        # A real marker at column zero still cannot continue an open quote.
        for key in ("paths", r'"\u0070aths"', "branches"):
            for suffix in ("---stable", "...hidden", "----", ".../docs", "---", "..."):
                for value in (' ["release/\\\n' + suffix + '"]\n',
                              '\n      ["release/\\\n' + suffix + '", main]\n'):
                    triggers = "on:\n  push:\n    " + key + ":" + value
                    for source in (triggers + good, good + triggers):
                        with self.subTest(marker_prefix=key, suffix=suffix):
                            self.assertTrue(all_native_checks_isolated(source))
                            for defaults in ("defaults: {run: {shell: pwsh}}\n",
                                             r'"\u0064efaults": {}' + "\n"):
                                self.assertFalse(all_native_checks_isolated(source + defaults))
        for marker in ("---", "...", "--- # document", "... # document",
                       "---\t# document", "...\t# document", "--- stable", "... hidden"):
            triggers = ('on:\n  push:\n    ' + r'"\u0070aths"' +
                        ': ["release/\\\n' + marker + '\n      stable"]\n')
            for source in (triggers + good, good + triggers):
                with self.subTest(document_marker=marker):
                    self.assertFalse(all_native_checks_isolated(source))
        # Quoted dispatch descriptions are text, even when a continuation
        # resembles a filter key. A genuine options list after the closing
        # quote still has its own flow continuation boundary.
        for key in ("description", r'"\u0064escription"'):
            for description in (
                    ' "Choose a color\n          options: [blue, green]"\n',
                    " 'Choose a color\n          options: [blue, green] and it''s fine'\n",
                    '\n          "Choose a color\n          options: [blue, green]"\n',
                    ' "Choose a color\\\n          # options: [blue, green]"\n',
                    ' "Choose a color\n          options: [blue, green]\\" now" # comment\n'):
                triggers = ("on:\n  workflow_dispatch:\n    inputs:\n      color:\n        "
                            + key + ":" + description
                            + "        type: choice\n        options: [blue,\n          \tgreen]\n")
                for source in (triggers + good, good + triggers):
                    with self.subTest(quoted_description=description, key=key):
                        self.assertTrue(all_native_checks_isolated(source))
                        for defaults in ("defaults: {run: {shell: pwsh}}\n",
                                         r'"\u0064efaults": {}' + "\n"):
                            self.assertFalse(all_native_checks_isolated(source + defaults))
        for description in (
                ' "Choose a color\n          options: [blue, green]\n',
                ' "Choose a color\n          options: [blue, green]" trailing\n',
                ' "Choose a color\ndefaults: {}\n          stable"\n',
                ' "Choose a color\n---\n          stable"\n'):
            triggers = ("on:\n  workflow_dispatch:\n    inputs:\n      color:\n"
                        "        description:" + description)
            for source in (triggers + good, good + triggers):
                self.assertFalse(all_native_checks_isolated(source))

        # One optional standalone start/end marker does not affect a single
        # workflow mapping. Never accept a second document or trailing data.
        for start in ("", "---\n", "# leading comment\n--- # start\n"):
            for end in ("", "...\n", "... \t# end\n# trailing comment\n"):
                source = start + good + end
                with self.subTest(document_start=start, document_end=end):
                    self.assertTrue(all_native_checks_isolated(source))
                    self.assertFalse(all_native_checks_isolated(
                        start + "defaults: {run: {shell: pwsh}}\n" + good + end))
                    self.assertFalse(all_native_checks_isolated(
                        start + good + r'"\u0064efaults": {}' + "\n" + end))
        for source in ("---\n---\n" + good, good + "---\n", good + "...\n...\n",
                       good + "...\n---\n" + good, good + "...\ndefaults: {}\n",
                       good + "...\n" + r'"\u0064efaults": {}' + "\n",
                       "...\n" + good, "---\n...\n" + good,
                       "on: [push,\n---\n" + good, "on: [push,\n...\n" + good):
            self.assertFalse(all_native_checks_isolated(source))
        # A separate unrelated step or job may set its own shell without
        # changing any required guard command's execution.
        self.assertTrue(all_native_checks_isolated(
            good + "      - run: python -V\n        shell: bash\n"))
        self.assertTrue(all_native_checks_isolated(
            good + "  other:\n    defaults:\n      run:\n        shell: bash\n"
                   "    steps:\n      - run: python -V\n"))
        # Formatting changes alone do not alter the workflow's semantics.
        spaced = good.replace("guard:", "guard :").replace("steps:", "steps :")
        for key in ("uses", "with", "java-version", "name", "run"):
            spaced = spaced.replace(key + ":", key + "  :")
        self.assertTrue(all_native_checks_isolated(spaced))
        quoted = good
        for key in ("guard", "steps", "uses", "with", "java-version", "name", "run"):
            quoted = quoted.replace(key + ":", '"' + key + '" :')
        self.assertTrue(all_native_checks_isolated(quoted))

        archive_label, archive_run = required_checks(21)[1]
        combined = (f"      - name: {archive_label}\n"
                    f"        run: |\n          {archive_run}\n          {runtime_cmd}\n")
        self.assertFalse(all_native_checks_isolated(
            prefix + setup(21) + j21[0] + combined + j21[3] + tail))
        self.assertFalse(all_native_checks_isolated(
            prefix + setup(21) + setup(25) + "".join(j21) + "".join(j25)))
        self.assertFalse(all_native_checks_isolated(
            good + f"      - id: extra-archive\n        run: {archive_run}\n"))
        self.assertFalse(all_native_checks_isolated(
            good.replace(archive_run, archive_cmd + " --evidence-dir retained-archive", 1)))
        for major in (21, 25):
            for key, value in (("if", "false"), ("if", "${{ false }}"),
                               ("continue-on-error", "true")):
                for spelling in (key, key + " ", key + "   ",
                                 "'" + key + "' ", '"' + key + '" '):
                    modifier = f"{spelling}: {value}"
                    with self.subTest(java=major, setup_modifier=modifier):
                        conditional = setup(major).replace(
                            "        with:\n", f"        {modifier}\n        with:\n", 1)
                        self.assertNotEqual(setup(major), conditional)
                        self.assertFalse(all_native_checks_isolated(
                            good.replace(setup(major), conditional, 1)))
                        # The same normalized policy applies to all eight
                        # required commands, not only the setup action.
                        for index in range(4):
                            original = check(major, index)
                            guarded = original + f"        {modifier}\n"
                            self.assertFalse(all_native_checks_isolated(
                                good.replace(original, guarded, 1)))
            # A duplicate critical field must not be hidden by spacing or
            # quoting. Unsupported escaped keys and YAML merges fail closed.
            for extra in ('          "java-version" : \'%s.0.1\'\n' % major,
                          '        "i\\u0066" : false\n',
                          '        <<: {if: false}\n'):
                with self.subTest(java=major, unsupported_or_duplicate=extra):
                    self.assertFalse(all_native_checks_isolated(
                        good.replace(setup(major), setup(major) + extra, 1)))
            _, validate_cmd = required_checks(major)[1]
            for replacement in ("", f" --expected-synthetic-java-major {46 - major}"):
                with self.subTest(java=major, validation_argument=replacement):
                    wrong = validate_cmd.replace(
                        f" --expected-synthetic-java-major {major}", replacement)
                    self.assertNotEqual(validate_cmd, wrong)
                    self.assertFalse(all_native_checks_isolated(
                        good.replace(validate_cmd, wrong, 1)))

    def test_historical_v1_report_is_immutable_and_source_bound(self):
        self.assertEqual(
            "8312b41b86992cb3dc6aff10f8d01184248abe9cadaf58b754967f157962ee09",
            hashlib.sha256(OLD.read_bytes()).hexdigest())
        self.assertEqual(
            "f4e024727fea2fd9afebf19892e5a3982fc7868c1ca294f6e16396a106871798",
            hashlib.sha256(REGISTER.read_bytes()).hexdigest())
        self.assertEqual([], FOCUS.validate_compatibility_erratum(self.report, self.register))

    def test_15_indexed_boundaries_are_not_15_focused_investigations(self):
        indexed = FOCUS.fixed_boundaries(self.register)
        focused = [row for row in indexed if row["focused_evidence"]]
        unfocused = [row for row in indexed if not row["focused_evidence"]]
        self.assertEqual((15, 7, 8), (len(indexed), len(focused), len(unfocused)))
        self.assertEqual({row["advisory_id"] for row in indexed},
                         {row["advisory_id"] for row in focused} |
                         {row["advisory_id"] for row in unfocused})
        self.assertFalse({row["advisory_id"] for row in focused} &
                         {row["advisory_id"] for row in unfocused})
        self.assertEqual(
            {"4.1": "4.1.137.Final", "4.2": "4.2.17.Final"},
            FOCUS.maximum_fixed_boundaries(indexed))
        self.assertEqual(
            FOCUS.maximum_fixed_boundaries(indexed),
            FOCUS.maximum_fixed_boundaries(focused))

    def test_forged_unfocused_advisory_cannot_claim_review(self):
        mutated = copy.deepcopy(self.register)
        item = next(row for row in mutated["advisories"]
                    if row["advisory_id"] == "GHSA-6jqx-86gh-f27w")
        self.assertIsNone(item["focused_evidence"])
        item["focused_evidence"] = "forged-review.json"
        errors = FOCUS.validate_compatibility_erratum(self.report, mutated)
        self.assertTrue(any("focus or fixed-boundary mismatch" in e for e in errors), errors)

    def test_duplicate_advisory_identity_is_rejected(self):
        mutated = copy.deepcopy(self.register)
        mutated["advisories"].append(copy.deepcopy(mutated["advisories"][0]))
        errors = FOCUS.validate_compatibility_erratum(self.report, mutated)
        self.assertTrue(any("duplicate advisory identity" in e for e in errors), errors)

    def test_modified_upstream_boundary_requires_review(self):
        mutated = copy.deepcopy(self.register)
        item = next(row for row in mutated["advisories"]
                    if row["advisory_id"] == "GHSA-c4c3-7fpv-j4q5")
        groups = item["affected_ranges"]["pkg:maven/io.netty/netty-handler"]
        changed = False
        for group in groups:
            for entry in group:
                for event in entry.get("events", []):
                    if event.get("fixed") == "4.1.137.Final":
                        event["fixed"] = "4.1.138.Final"
                        changed = True
        self.assertTrue(changed)
        errors = FOCUS.validate_compatibility_erratum(self.report, mutated)
        self.assertTrue(any("fixed-boundary mismatch" in e for e in errors), errors)

    def test_wrong_historical_and_source_provenance_rejected(self):
        for field, subfield in (("historical_v1_report", "sha256"),
                                ("source_register", "sha256")):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.report)
                mutated[field][subfield] = "0" * 64
                errors = FOCUS.validate_compatibility_erratum(mutated, self.register)
                self.assertTrue(any("report" in e or "register" in e for e in errors), errors)

    def test_full_archive_fails_closed_on_tampered_or_missing_v2(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-focus-archive-") as tmp:
            copied = Path(tmp) / "archive"
            shutil.copytree(evidence, copied)
            errors, result = VALIDATOR.validate_evidence(copied, ROOT)
            self.assertEqual([], errors)
            self.assertEqual(0, result["captured_runtime_environment_count"])
            v2_path = copied / "remediation-compatibility-v2.json"
            amended = json.loads(v2_path.read_text(encoding="utf-8"))
            amended["focused_netty_advisory_count"] = 15
            v2_path.write_text(json.dumps(amended), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(copied, ROOT)
            self.assertTrue(any("corrected Netty compatibility" in e for e in errors), errors)
            v2_path.unlink()
            errors, _ = VALIDATOR.validate_evidence(copied, ROOT)
            self.assertTrue(any("corrected Netty compatibility record missing" in e
                                for e in errors), errors)

    def test_empty_duplicate_and_partial_v2_environment_matrices_are_rejected(self):
        for changed in ([], [copy.deepcopy(self.report["environments"][0])],
                        self.report["environments"][:-1]):
            with self.subTest(rows=len(changed)):
                modified = copy.deepcopy(self.report)
                modified["environments"] = changed
                errors = FOCUS.validate_compatibility_erratum(modified, self.register)
                self.assertTrue(any("environment" in error for error in errors), errors)
        duplicate = copy.deepcopy(self.report)
        duplicate["environments"][1]["environment_id"] = duplicate["environments"][0]["environment_id"]
        errors = FOCUS.validate_compatibility_erratum(duplicate, self.register)
        self.assertTrue(any("duplicated" in error for error in errors), errors)

    def test_26_2_forged_fixed_version_with_self_consistent_flags_is_rejected(self):
        forged = copy.deepcopy(self.report)
        row = next(row for row in forged["environments"]
                   if row["environment_id"] == "minecraft-26.2-client")
        row["manifest_or_bundle_netty_version"] = "4.2.17.Final"
        row["all_indexed_netty_boundaries_met"] = True
        row["focused_netty_boundaries_met"] = True
        row["lz4_advisory_fixed_boundary_met_by_selected_artifact_version"] = True
        errors = FOCUS.validate_compatibility_erratum(forged, self.register)
        self.assertTrue(any("pinned matrix" in error for error in errors), errors)

    def test_forged_matrix_version_cannot_override_independent_verified_pin(self):
        matrix_path = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23/environment-matrix.json"
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        trusted_pins = {
            row["environment_id"]:
            (row.get("expected_netty_codec") or row.get("expected_bundled_netty_codec"))
            for row in matrix["environments"]}
        modified = copy.deepcopy(matrix)
        target = next(row for row in modified["environments"]
                      if row["environment_id"] == "minecraft-26.2-client")
        target["expected_netty_codec"] = "4.2.17.Final"
        errors = FOCUS.validate_compatibility_erratum(
            self.report, self.register, matrix=modified, pinned_versions=trusted_pins)
        self.assertTrue(any("independently verified artifact pin" in error
                            for error in errors), errors)

    def test_wrong_lz4_flag_and_unsupported_runtime_claims_are_rejected(self):
        mutations = (
            ("lz4_advisory_fixed_boundary_met_by_selected_artifact_version", True,
             "incorrect lz4_advisory"),
            ("supported_jvm_execution_verified", True, "overstates runtime"),
            ("runtime_loader_selection_verified", True, "overstates runtime"),
            ("minecraft_fabric_abi_verified", True, "overstates runtime"),
            ("no_dependency_override_performed", False, "overstates runtime"),
            ("outcome", "fixed", "overstates runtime"),
        )
        for field, value, expected_error in mutations:
            with self.subTest(field=field):
                modified = copy.deepcopy(self.report)
                modified["environments"][0][field] = value
                errors = FOCUS.validate_compatibility_erratum(modified, self.register)
                self.assertTrue(any(expected_error in error for error in errors), errors)

    def test_archived_v1_reformat_without_value_change_is_rejected(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-v1-copy-") as tmp:
            copied = Path(tmp) / "archive"
            shutil.copytree(evidence, copied)
            original = copied / "remediation-compatibility.json"
            original.write_text(json.dumps(json.loads(original.read_text(encoding="utf-8")),
                                           indent=3, sort_keys=False) + "\n",
                                encoding="utf-8")
            self.assertNotEqual(hashlib.sha256(OLD.read_bytes()).hexdigest(),
                                hashlib.sha256(original.read_bytes()).hexdigest())
            errors, _ = VALIDATOR.validate_evidence(copied, ROOT)
            self.assertTrue(any("archived Netty v1 historical report SHA-256" in error
                                for error in errors), errors)

    def test_forged_client_manifest_from_another_minecraft_release_fails_full_archive(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-forged-manifest-") as tmp:
            archive = Path(tmp) / "archive"
            shutil.copytree(evidence, archive)
            matrix_path = archive / "environment-matrix.json"
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            one19 = next(r for r in matrix["environments"]
                         if r["environment_id"] == "minecraft-1.19-client")
            newest = next(r for r in matrix["environments"]
                          if r["environment_id"] == "minecraft-26.2-client")
            # Every mutable field agrees internally; only the source-controlled
            # game identity mapping can detect the substitution.
            for name in ("manifest_path", "manifest_sha256", "expected_netty_codec"):
                one19[name] = newest[name]
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            v2_path = archive / "remediation-compatibility-v2.json"
            report = json.loads(v2_path.read_text(encoding="utf-8"))
            row = next(r for r in report["environments"]
                       if r["environment_id"] == "minecraft-1.19-client")
            row.update(manifest_or_bundle_netty_version="4.2.15.Final",
                       expected_dependency_family="4.2",
                       lz4_advisory_fixed_boundary_met_by_selected_artifact_version=True,
                       module_family_consistent_at_source_manifest=True,
                       all_indexed_netty_boundaries_met=False,
                       focused_netty_boundaries_met=False)
            v2_path.write_text(json.dumps(report), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("source-controlled environment pin mismatch" in error
                                for error in errors), errors)
            self.assertTrue(any("verified Netty artifact pins do not cover" in error
                                for error in errors), errors)

    def test_manifest_internal_id_and_digest_are_independently_checked(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        matrix = json.loads((evidence / "environment-matrix.json").read_text(encoding="utf-8"))
        client = next(row for row in matrix["environments"]
                      if row["environment_id"] == "minecraft-1.19-client")
        with tempfile.TemporaryDirectory(prefix="issue45-manifest-id-") as tmp:
            root = Path(tmp)
            manifest = ROOT / client["manifest_path"]
            manifest_copy = root / client["manifest_path"]
            manifest_copy.parent.mkdir(parents=True)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["id"] = "26.2"
            manifest_copy.write_text(json.dumps(value), encoding="utf-8")
            modified = copy.deepcopy(client)
            modified["manifest_sha256"] = hashlib.sha256(manifest_copy.read_bytes()).hexdigest()
            # A tampered manifest or archive row cannot override the independent pin.
            errors, _ = VALIDATOR.validate_environment_artifact_pin(
                modified, root, json.loads((evidence / "baseline-lock.json").read_text())["retained_files"])
            self.assertTrue(any("source-controlled environment pin mismatch" in e
                                for e in errors), errors)
            # Force the trusted digest check to pass temporarily to isolate
            # validation of the manifest's internal release id.
            with mock.patch.dict(VALIDATOR.TRUSTED_ENVIRONMENTS,
                                 {"minecraft-1.19-client": {**VALIDATOR.TRUSTED_ENVIRONMENTS["minecraft-1.19-client"],
                                     "manifest_sha256": modified["manifest_sha256"]}}):
                errors, _ = VALIDATOR.validate_environment_artifact_pin(
                    modified, root, {})
            self.assertTrue(any("manifest id differs" in e for e in errors), errors)

    def test_missing_or_nonstring_environment_id_returns_structured_invalid_archive(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        for bad in (None, ["invalid"], "", 123):
            with self.subTest(value=bad):
                with tempfile.TemporaryDirectory(prefix="issue45-malformed-id-") as tmp:
                    archive = Path(tmp) / "archive"
                    shutil.copytree(evidence, archive)
                    path = archive / "environment-matrix.json"
                    matrix = json.loads(path.read_text(encoding="utf-8"))
                    if bad is None:
                        matrix["environments"][0].pop("environment_id")
                    else:
                        matrix["environments"][0]["environment_id"] = bad
                    path.write_text(json.dumps(matrix), encoding="utf-8")
                    command = [sys.executable, str(ROOT /
                               "diagnostics/issue45-runtime/validate_runtime_evidence.py"),
                               "--evidence-dir", str(archive)]
                    process = subprocess.run(command, cwd=ROOT,
                                             capture_output=True, text=True)
                    self.assertEqual(1, process.returncode, process.stderr)
                    result = json.loads(process.stdout)
                    self.assertEqual("invalid_archive", result["result"])
                    self.assertTrue(any("identities" in e for e in result["errors"]))

    def test_v2_list_valued_id_is_normal_validation_error(self):
        bad = copy.deepcopy(self.report)
        bad["environments"][0]["environment_id"] = ["incorrect"]
        errors = FOCUS.validate_compatibility_erratum(bad, self.register)
        self.assertTrue(any("identities" in e for e in errors), errors)

    def test_v1_reformat_and_self_consistent_new_v2_digest_cannot_reanchor_history(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-immutable-v1-") as tmp:
            archive = Path(tmp) / "archive"
            shutil.copytree(evidence, archive)
            v1_path = archive / "remediation-compatibility.json"
            v1_path.write_text(json.dumps(json.loads(v1_path.read_text(encoding="utf-8")),
                                          indent=4, sort_keys=False) + "\n", encoding="utf-8")
            new_hash = hashlib.sha256(v1_path.read_bytes()).hexdigest()
            self.assertNotEqual(FOCUS.HISTORICAL_V1_SHA256, new_hash)
            v2_path = archive / "remediation-compatibility-v2.json"
            derived = json.loads(v2_path.read_text(encoding="utf-8"))
            derived["historical_v1_report"]["sha256"] = new_hash
            v2_path.write_text(json.dumps(derived), encoding="utf-8")
            with mock.patch.object(FOCUS, "OUT", archive):
                errors = FOCUS.validate_compatibility_erratum(
                    derived, self.register, archive_v1_path=v1_path)
                self.assertTrue(any("Netty v1 historical report source provenance mismatch" in e
                                    for e in errors), errors)
                self.assertTrue(any("archived Netty v1 historical report SHA-256" in e
                                    for e in errors), errors)
                with self.assertRaisesRegex(SystemExit, "historical compatibility report SHA-256 mismatch"):
                    FOCUS.main()
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("historical report" in e for e in errors), errors)

    def test_changed_canonical_v1_is_rejected_even_with_original_archive(self):
        with tempfile.TemporaryDirectory(prefix="issue45-canonical-v1-") as tmp:
            changed = Path(tmp) / "remediation-compatibility.json"
            changed.write_bytes(OLD.read_bytes() + b"\n")
            with mock.patch.object(FOCUS, "HISTORICAL_V1_PATH", changed):
                errors = FOCUS.validate_compatibility_erratum(
                    self.report, self.register, archive_v1_path=OLD)
                self.assertIn("source-controlled historical Netty v1 digest mismatch", errors)
                self.assertFalse(any("archived Netty v1 historical report SHA-256" in e
                                     for e in errors), errors)
                with self.assertRaisesRegex(SystemExit, "historical compatibility report SHA-256 mismatch"):
                    FOCUS.main()

    def test_archive_cannot_choose_an_alternate_client_module_or_server_version(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        matrix = json.loads((evidence / "environment-matrix.json").read_text(encoding="utf-8"))
        retained = json.loads((evidence / "baseline-lock.json").read_text(encoding="utf-8"))["retained_files"]
        for identity, field, value in (
                ("minecraft-1.19-client", "expected_bundled_netty_module", "netty-handler"),
                ("minecraft-1.19-dedicated-server", "expected_netty_codec", "4.2.17.Final")):
            with self.subTest(identity=identity):
                row = copy.deepcopy(next(r for r in matrix["environments"] if r["environment_id"] == identity))
                row[field] = value
                errors, pin = VALIDATOR.validate_environment_artifact_pin(row, ROOT, retained)
                self.assertIsNone(pin)
                self.assertTrue(any("unexpected Netty artifact selector" in e for e in errors), errors)

    def test_archive_controlled_server_scan_and_matching_summary_are_rejected(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-forged-server-scan-") as tmp:
            archive = Path(tmp) / "archive"
            shutil.copytree(evidence, archive)
            matrix_path = archive / "environment-matrix.json"
            baseline_path = archive / "baseline-lock.json"
            report_path = archive / "remediation-compatibility-v2.json"
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            row = next(r for r in matrix["environments"]
                       if r["environment_id"] == "minecraft-1.19-dedicated-server")
            record = row["server_bundle_source"]
            scan = json.loads((ROOT / record["source_scan_path"]).read_text(encoding="utf-8"))
            server = next(r for r in scan["servers"] if r["minecraft_version"] == "1.19")
            nested = next(r for r in server["nested_jars"]
                          if r["path"] == record["nested_netty_artifact"]["path"])
            nested.update(sha1="a" * 40, sha256="b" * 64, size_bytes=123)
            record["nested_netty_artifact"].update(
                sha1=nested["sha1"], sha256=nested["sha256"], size_bytes=nested["size_bytes"])
            forged = Path(tmp) / "fake-scan.json"
            forged.write_text(json.dumps(scan), encoding="utf-8")
            new_hash = hashlib.sha256(forged.read_bytes()).hexdigest()
            record.update(source_scan_path=str(forged), source_scan_sha256=new_hash)
            baseline["retained_files"][str(forged)] = new_hash
            report["minecraft_1_19_server_bundle"]["netty_codec_artifact"].update(
                sha1=nested["sha1"], sha256=nested["sha256"], size_bytes=nested["size_bytes"])
            for path, data in ((matrix_path, matrix), (baseline_path, baseline), (report_path, report)):
                path.write_text(json.dumps(data), encoding="utf-8")
            errors, pin = VALIDATOR.validate_environment_artifact_pin(
                row, ROOT, baseline["retained_files"])
            self.assertIsNone(pin)
            self.assertTrue(any("source-controlled official scan" in e for e in errors), errors)
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("source-controlled official scan" in e for e in errors), errors)

    def test_server_summary_live_selection_or_artifact_forgery_is_rejected(self):
        for name in ("minecraft_1_19_server_bundle", "minecraft_26_1_2_server_bundle"):
            for field, value in (("live_selection_verified", True),
                                 ("server_bundle_sha256", "0" * 64),
                                 ("netty_module_versions", ["4.2.17.Final"])):
                with self.subTest(summary=name, mutation=field):
                    edited = copy.deepcopy(self.report)
                    edited[name][field] = value
                    errors = FOCUS.validate_compatibility_erratum(edited, self.register)
                    self.assertTrue(any("server bundle summary contradicts" in e
                                        for e in errors), errors)

    def test_incorrect_environment_boundary_claim_is_rejected(self):
        mutated = copy.deepcopy(self.report)
        mutated["environments"][0]["all_indexed_netty_boundaries_met"] = True
        errors = FOCUS.validate_compatibility_erratum(mutated, self.register)
        self.assertTrue(any("incorrect all_indexed_netty_boundaries_met" in e
                            for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
