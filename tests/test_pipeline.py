import importlib.machinery
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(KIT, "bin", "pipeline")
FIXTURES = os.path.join(KIT, "tests", "fixtures")


def load_module():
    loader = importlib.machinery.SourceFileLoader("pipeline_mod", PIPELINE)
    spec = importlib.util.spec_from_loader("pipeline_mod", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


pipeline = load_module()


def fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


PROFILE = {
    "kit_version": "0.1.0",
    "artifacts_dir": "specs",
    "runner": "generic",
    "test_globs": ["tests/**"],
    "shared_globs": ["tests/fixtures/**"],
    "protected_globs": ["Makefile", ".claude/pipeline.json"],
    "cmd": {
        "lint": ["true"],
        "typecheck": ["true"],
        "test_slice": ["rtk sh ./run_tests.sh {test_files}"],
        "test_all": ["sh ./run_tests.sh"],
    },
    "docs": {"nestjs": "/nestjs/docs.nestjs.com"},
}

RUN_TESTS = "#!/bin/sh\ncode=$(cat .test_exit 2>/dev/null || echo 0)\necho \"ran: $*\"\nexit $code\n"


class ParserTests(unittest.TestCase):
    def test_jest(self):
        self.assertEqual(pipeline.parse_output("jest", fixture("jest-red.txt"), 1), {"passed": 2, "failed": 1, "ran": True})
        self.assertEqual(pipeline.parse_output("jest", fixture("jest-green.txt"), 0), {"passed": 3, "failed": 0, "ran": True})

    def test_rspec(self):
        self.assertEqual(pipeline.parse_output("rspec", fixture("rspec-red.txt"), 1), {"passed": 3, "failed": 2, "ran": True})
        self.assertEqual(pipeline.parse_output("rspec", fixture("rspec-green.txt"), 0), {"passed": 4, "failed": 0, "ran": True})

    def test_go(self):
        self.assertEqual(pipeline.parse_output("go", fixture("go-red.txt"), 1), {"passed": 2, "failed": 1, "ran": True})
        self.assertEqual(pipeline.parse_output("go", fixture("go-green.txt"), 0), {"passed": 3, "failed": 0, "ran": True})
        self.assertEqual(pipeline.parse_output("go", "ok  \tpkg/a\t0.1s\nFAIL\tpkg/b\t0.2s\n", 1), {"passed": 1, "failed": 1, "ran": True})

    def test_pytest(self):
        self.assertEqual(pipeline.parse_output("pytest", fixture("pytest-red.txt"), 1), {"passed": 3, "failed": 1, "ran": True})
        self.assertEqual(pipeline.parse_output("pytest", fixture("pytest-green.txt"), 0), {"passed": 4, "failed": 0, "ran": True})

    def test_generic_and_no_summary(self):
        self.assertEqual(pipeline.parse_output("generic", "", 0), {"passed": 1, "failed": 0, "ran": True})
        self.assertEqual(pipeline.parse_output("generic", "", 2), {"passed": 0, "failed": 1, "ran": True})
        self.assertEqual(pipeline.parse_output("jest", "Error: cannot find module", 1)["ran"], False)

    def test_strip_rtk(self):
        self.assertEqual(pipeline.strip_rtk("rtk npx jest x"), "npx jest x")
        self.assertEqual(pipeline.strip_rtk("npx jest x"), "npx jest x")


class GlobTests(unittest.TestCase):
    def test_double_star(self):
        self.assertTrue(pipeline.glob_match("src/a/b/c.spec.ts", "src/**/*.spec.ts"))
        self.assertTrue(pipeline.glob_match("src/c.spec.ts", "src/**/*.spec.ts"))
        self.assertTrue(pipeline.glob_match("test/x/y.py", "test/**"))
        self.assertFalse(pipeline.glob_match("src/c.ts", "src/**/*.spec.ts"))

    def test_basename_patterns(self):
        self.assertTrue(pipeline.glob_match("Makefile", "Makefile"))
        self.assertTrue(pipeline.glob_match("jest.config.js", "jest.config.*"))
        self.assertTrue(pipeline.glob_match("./tsconfig.build.json", "tsconfig*.json"))
        self.assertFalse(pipeline.glob_match("src/Makefile.txt", "Makefile"))

    def test_bash_targets(self):
        self.assertEqual(pipeline.bash_targets("echo x > tests/a.sh && cat tests/a.sh"), ["tests/a.sh"])
        self.assertEqual(pipeline.bash_targets("sed -i '' 's/a/b/' src/x.ts"), ["src/x.ts"])
        self.assertEqual(pipeline.bash_targets("rm -rf tests/old tests/older"), ["tests/old", "tests/older"])
        self.assertEqual(pipeline.bash_targets("git checkout -- src/x.ts"), ["src/x.ts"])
        self.assertEqual(pipeline.bash_targets("npm test 2>&1 | tail -3"), [])


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="delivery-kit-test-")
        self.repo = os.path.realpath(os.path.join(self.tmp, "repo"))
        self.state_dir = os.path.join(self.tmp, "state")
        os.makedirs(self.repo)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write(".gitignore", ".test_exit\n")
        self.write("run_tests.sh", RUN_TESTS)
        self.write("Makefile", "all:\n\ttrue\n")
        self.write("src/x.ts", "export const x = 1;\n")
        self.write("tests/test_a.sh", "echo a\n")
        self.write("tests/fixtures/f.json", "{}\n")
        self.write(".claude/pipeline.json", json.dumps(PROFILE, indent=2) + "\n")
        self.write("specs/feat/slices/S01/SPEC.md", "# S01\n\n## Tests\n\n- tests/test_a.sh\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True)

    def write(self, rel, content):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def set_exit(self, code):
        self.write(".test_exit", f"{code}\n")

    def cli(self, *args, stdin=None, cwd=None):
        env = {**os.environ, "PIPELINE_STATE_DIR": self.state_dir}
        return subprocess.run([sys.executable, PIPELINE, *args], cwd=cwd or self.repo, input=stdin,
                              capture_output=True, text=True, env=env)

    def hook(self, name, fixture_name, **overrides):
        with open(os.path.join(FIXTURES, fixture_name)) as f:
            data = json.load(f)
        data["cwd"] = self.repo
        data.update(overrides)
        return self.cli("hook", name, stdin=json.dumps(data))

    def state(self):
        with open(os.path.join(self.state_dir, "feat", "S01", "state.json")) as f:
            return json.load(f)

    def evidence(self):
        path = os.path.join(self.state_dir, "feat", "S01", "evidence.jsonl")
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def start(self, phase=None):
        self.assertEqual(self.cli("start", "feat", "--slice", "S01", "--tier", "S").returncode, 0)
        if phase:
            self.assertEqual(self.cli("phase", phase).returncode, 0)


class InitDoctorTests(RepoCase):
    def test_init_refuses_then_forces(self):
        src = os.path.join(self.tmp, "nest.json")
        with open(src, "w") as f:
            json.dump({**PROFILE, "artifacts_dir": "docs/specs"}, f)
        self.assertEqual(self.cli("init", "--from", src).returncode, 1)
        r = self.cli("init", "--from", src, "--force")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(os.path.join(self.repo, "docs", "specs")))

    def test_init_on_fresh_repo(self):
        fresh = os.path.join(self.tmp, "fresh")
        os.makedirs(fresh)
        subprocess.run(["git", "init", "-q"], cwd=fresh, check=True)
        src = os.path.join(self.tmp, "p.json")
        with open(src, "w") as f:
            json.dump(PROFILE, f)
        self.assertEqual(self.cli("init", "--from", src, cwd=fresh).returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(fresh, ".claude", "pipeline.json")))

    def test_doctor_passes_on_clean_green_repo(self):
        r = self.cli("doctor")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("FAIL", r.stdout)
        self.assertIn("plugin hooks", r.stdout)

    def test_doctor_fails_on_red_suite_and_dirty_tree(self):
        self.set_exit(1)
        r = self.cli("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL test_all", r.stdout)
        self.set_exit(0)
        self.write("src/x.ts", "changed\n")
        r = self.cli("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL working tree clean", r.stdout)

    def test_doctor_allows_empty_cmd_lists(self):
        self.write(".claude/pipeline.json", json.dumps({**PROFILE, "cmd": {**PROFILE["cmd"], "typecheck": [], "e2e": []}}))
        self.git("commit", "-qam", "empty steps")
        r = self.cli("doctor")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_doctor_rejects_unknown_runner(self):
        self.write(".claude/pipeline.json", json.dumps({**PROFILE, "runner": "mocha"}))
        self.git("commit", "-qam", "runner")
        r = self.cli("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL runner", r.stdout)


class FlowTests(RepoCase):
    def test_start_phase_and_status(self):
        self.start()
        st = self.state()
        self.assertEqual(st["phase"], "plan")
        self.assertEqual(st["tier"], "S")
        self.assertIsNone(st["base_tree"])
        with open(os.path.join(self.state_dir, "current.json")) as f:
            self.assertEqual(json.load(f), {"feature": "feat", "slice": "S01"})
        self.assertEqual(self.cli("phase", "implement").returncode, 0)
        self.assertRegex(self.state()["base_tree"], r"^[0-9a-f]{40}$")
        r = self.cli("status")
        self.assertEqual(r.returncode, 0)
        self.assertIn('"phase": "implement"', r.stdout)

    def test_commands_without_state_fail_cleanly(self):
        r = self.cli("phase", "tests")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no current feature", r.stderr)

    def test_test_records_red_green_and_hashes(self):
        self.start("tests")
        self.set_exit(1)
        r = self.cli("test")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        row = self.evidence()[-1]
        self.assertEqual(row["kind"], "red")
        self.assertEqual(row["parsed"]["failed"], 1)
        self.assertIn("tests/test_a.sh", row["test_hashes"])
        self.assertNotIn("rtk", row["cmd"])
        self.assertIn("test_a.sh", row["cmd"])
        self.set_exit(0)
        self.assertEqual(self.cli("test").returncode, 0)
        self.assertEqual(self.evidence()[-1]["kind"], "green")
        r = self.cli("test", "--files", "tests/other.sh")
        self.assertEqual(self.evidence()[-1]["test_hashes"], {"tests/other.sh": "missing"})

    def test_test_files_strip_prefix(self):
        self.write(".claude/pipeline.json", json.dumps({**PROFILE, "test_files_strip_prefix": "tests/"}))
        self.git("commit", "-qam", "prefix")
        self.start("tests")
        self.set_exit(1)
        r = self.cli("test")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        row = self.evidence()[-1]
        self.assertIn("run_tests.sh test_a.sh", row["cmd"])
        self.assertIn("tests/test_a.sh", row["test_hashes"])
        self.assertEqual(self.cli("validate", "--quick").returncode, 1)
        self.assertEqual(self.evidence()[-1]["steps"]["test_slice"], 1)

    def test_check_red(self):
        self.start("tests")
        r = self.cli("check", "red")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no red run", r.stderr)
        self.set_exit(1)
        self.cli("test")
        self.assertEqual(self.cli("check", "red").returncode, 0)
        self.write("tests/test_a.sh", "echo a2\n")
        r = self.cli("check", "red")
        self.assertEqual(r.returncode, 2)
        self.assertIn("tests/test_a.sh", r.stderr)

    def test_validate_quick_and_protected_diff(self):
        self.start("implement")
        r = self.cli("validate", "--quick")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        row = self.evidence()[-1]
        self.assertEqual(row["kind"], "validate")
        self.assertEqual(row["protected_dirty"], [])
        self.assertEqual(set(row["steps"]), {"lint", "typecheck", "test_slice"})
        self.write("Makefile", "all:\n\tfalse\n")
        self.write("tests/test_a.sh", "echo tampered\n")
        r = self.cli("validate", "--quick")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(sorted(self.evidence()[-1]["protected_dirty"]), ["Makefile", "tests/test_a.sh"])
        self.assertIn("protected paths changed", r.stdout)

    def test_validate_full_runs_probes(self):
        self.start("implement")
        probe = os.path.join(self.repo, "specs/feat/slices/S01/probes/01-health.sh")
        self.write("specs/feat/slices/S01/probes/01-health.sh", "#!/bin/sh\nexit 7\n")
        os.chmod(probe, os.stat(probe).st_mode | stat.S_IEXEC)
        r = self.cli("validate")
        self.assertEqual(r.returncode, 1)
        kinds = [e["kind"] for e in self.evidence()]
        self.assertIn("probe", kinds)
        self.assertEqual(self.evidence()[-1]["steps"]["probe:01-health.sh"], 7)
        r = self.cli("probe")
        self.assertEqual(r.returncode, 1)
        self.assertIn("probe 01-health.sh: exit 7", r.stdout)

    def test_validate_marks_flaky(self):
        self.start("implement")
        self.write("run_tests.sh", "#!/bin/sh\nif [ -f .flake ]; then rm .flake; exit 1; fi\nexit 0\n")
        self.write(".gitignore", ".test_exit\n.flake\n")
        self.git("commit", "-qam", "flaky runner")
        self.cli("phase", "implement")
        self.write(".flake", "1")
        r = self.cli("validate", "--quick")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(self.evidence()[-1]["flaky"])
        self.assertIn("flaky", r.stdout)

    def test_check_green_blocks_then_blocked_at_three(self):
        self.start("implement")
        self.set_exit(1)
        for n in (1, 2):
            r = self.cli("check", "green")
            self.assertEqual(r.returncode, 2)
            self.assertIn(f"({n}/3)", r.stderr)
            self.assertEqual(self.state()["block_count"], n)
        r = self.cli("check", "green")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.state()["status"], "blocked")
        self.assertEqual(self.state()["block_count"], 3)

    def test_check_green_passes(self):
        self.start("implement")
        r = self.cli("check", "green")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.state()["block_count"], 0)

    def test_check_commit_requires_fresh_validate_and_verdict(self):
        self.start("implement")
        r = self.cli("check", "commit")
        self.assertEqual(r.returncode, 2)
        self.assertIn("code review verdict is missing", r.stderr)
        self.assertEqual(self.evidence()[-1]["kind"], "validate")
        self.assertEqual(self.cli("verdict", "code", "PASS").returncode, 0)
        self.assertEqual(self.cli("check", "commit").returncode, 0)
        self.write("src/x.ts", "export const x = 2;\n")
        self.set_exit(1)
        r = self.cli("check", "commit")
        self.assertEqual(r.returncode, 2)
        self.assertIn("validate is red", r.stderr)
        self.set_exit(0)
        self.assertEqual(self.cli("validate", "--quick").returncode, 0)
        self.assertEqual(self.cli("check", "commit").returncode, 0)

    def test_check_commit_needs_feature_verdict_when_probes_exist(self):
        self.start("implement")
        self.write("specs/feat/slices/S01/probes/01.sh", "#!/bin/sh\nexit 0\n")
        self.cli("verdict", "code", "PASS")
        r = self.cli("check", "commit")
        self.assertEqual(r.returncode, 2)
        self.assertIn("feature verdict is missing", r.stderr)
        self.cli("verdict", "feature", "PASS")
        self.assertEqual(self.cli("check", "commit").returncode, 0)

    def test_verdict_copies_findings(self):
        self.start("review")
        findings = os.path.join(self.tmp, "f.md")
        with open(findings, "w") as f:
            f.write("- none\n")
        self.assertEqual(self.cli("verdict", "code", "FAIL", "--findings", findings).returncode, 0)
        self.assertEqual(self.state()["verdicts"], {"code": "FAIL"})
        self.assertTrue(os.path.isfile(os.path.join(self.state_dir, "feat", "S01", "findings-code.md")))

    def test_check_claims(self):
        self.write("specs/feat/PLAN.md", "\n".join([
            "# Plan",
            "Open: [NEEDS CLARIFICATION: which queue]",
            "| claim | receipt | tag |",
            "|---|---|---|",
            "| x is 1 | src/x.ts:1 | V |",
            "| y is 2 | src/x.ts:99 | V |",
            "| z | | V |",
            "| w | src/missing.ts:3 | V |",
            "| guess | | A |",
            "Docs: `/nestjs/docs.nestjs.com` and `/prisma/docs`.",
            "See https://example.com/a.md:5 for nothing.",
            "",
        ]))
        r = self.cli("check", "claims", "specs/feat/PLAN.md")
        self.assertEqual(r.returncode, 2)
        err = r.stderr
        self.assertIn("PLAN.md:2: unresolved [NEEDS CLARIFICATION]", err)
        self.assertIn("PLAN.md:6: receipt src/x.ts:99", err)
        self.assertIn("PLAN.md:7: row tagged V has no receipt", err)
        self.assertIn("PLAN.md:8: receipt src/missing.ts:3", err)
        self.assertIn("doc id /prisma/docs", err)
        self.assertNotIn("PLAN.md:5:", err)
        self.assertNotIn("PLAN.md:9:", err)
        self.assertNotIn("PLAN.md:11:", err)
        self.write("specs/feat/PLAN.md", "| x | src/x.ts:1 | V |\n")
        self.assertEqual(self.cli("check", "claims", "specs/feat/PLAN.md").returncode, 0)


class HookTests(RepoCase):
    def test_hooks_noop_without_profile_or_state(self):
        for name in ("h1", "h3", "h4", "h5", "h6"):
            r = self.hook(name, "h3-test-author-stop.json")
            self.assertEqual(r.returncode, 0, f"{name} without current.json: {r.stderr}")
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        for name in ("h1", "h5"):
            r = self.hook(name, "h1-test-author-edit-src-exit2.json", cwd=plain)
            self.assertEqual(r.returncode, 0, name)
        r = self.cli("hook", "h1", stdin="not json")
        self.assertEqual(r.returncode, 0)

    def test_h1_from_fixtures(self):
        self.start("tests")
        for name in sorted(os.listdir(FIXTURES)):
            if not name.startswith("h1-"):
                continue
            expected = int(name.rsplit("exit", 1)[1].split(".")[0])
            r = self.hook("h1", name)
            self.assertEqual(r.returncode, expected, f"{name}: {r.stderr}")
            if expected == 2:
                self.assertTrue(r.stderr.strip(), name)

    def test_h1_absolute_paths_and_phase_gate(self):
        self.start("tests")
        r = self.hook("h1", "h1-test-author-edit-src-exit2.json",
                      tool_input={"file_path": os.path.join(self.repo, "src", "x.ts")})
        self.assertEqual(r.returncode, 2)
        r = self.hook("h1", "h1-test-author-edit-src-exit2.json", tool_input={"file_path": "/tmp/scratch.txt"})
        self.assertEqual(r.returncode, 0)
        self.cli("phase", "plan")
        r = self.hook("h1", "h1-test-author-edit-src-exit2.json")
        self.assertEqual(r.returncode, 0)

    def test_h1_implementer_cannot_touch_protected(self):
        self.start("implement")
        r = self.hook("h1", "h1-implementer-edit-src-exit0.json", tool_input={"file_path": "Makefile"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("Makefile", r.stderr)

    def test_h3_require_red(self):
        self.start("tests")
        r = self.hook("h3", "h3-test-author-stop.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no red run", r.stderr)
        self.set_exit(1)
        self.cli("test")
        self.assertEqual(self.hook("h3", "h3-test-author-stop.json").returncode, 0)
        self.write("tests/test_a.sh", "echo edited\n")
        r = self.hook("h3", "h3-test-author-stop.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("changed since the last red run", r.stderr)

    def test_h4_require_green(self):
        self.start("implement")
        self.set_exit(1)
        self.assertEqual(self.hook("h4", "h4-implementer-stop.json").returncode, 2)
        self.assertEqual(self.hook("h4", "h4-implementer-stop.json").returncode, 2)
        self.assertEqual(self.state()["block_count"], 2)
        r = self.hook("h4", "h4-implementer-stop.json")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.state()["status"], "blocked")

    def test_h4_green_passes(self):
        self.start("implement")
        r = self.hook("h4", "h4-implementer-stop.json")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_h5_gate_commit(self):
        self.start("plan")
        self.assertEqual(self.hook("h5", "h5-git-commit.json").returncode, 0)
        self.cli("phase", "implement")
        self.assertEqual(self.hook("h5", "h5-git-commit.json", tool_input={"command": "git status"}).returncode, 0)
        self.set_exit(1)
        self.write("src/x.ts", "export const x = 3;\n")
        r = self.hook("h5", "h5-git-commit.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("validate is red", r.stderr)
        self.set_exit(0)
        self.assertEqual(self.cli("validate", "--quick").returncode, 0)
        self.cli("verdict", "code", "PASS")
        r = self.hook("h5", "h5-git-commit.json")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_h6_lint_claims(self):
        self.start("plan")
        self.write("specs/feat/PLAN.md", "| claim | src/x.ts:40 | V |\n")
        r = self.hook("h6", "h6-planner-stop.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("src/x.ts:40", r.stderr)
        self.assertEqual(self.hook("h6", "h6-reviewer-stop.json").returncode, 2)
        self.cli("phase", "review")
        self.assertEqual(self.hook("h6", "h6-reviewer-stop.json").returncode, 0)
        self.assertEqual(self.hook("h6", "h6-planner-stop.json").returncode, 2)
        self.write("specs/feat/PLAN.md", "| claim | src/x.ts:1 | V |\n")
        self.assertEqual(self.hook("h6", "h6-planner-stop.json").returncode, 0)


class HooksJsonTests(unittest.TestCase):
    def test_hooks_json_wires_all_gates(self):
        with open(os.path.join(KIT, "hooks", "hooks.json")) as f:
            data = json.load(f)
        commands = [h["command"] for group in data["hooks"].values() for entry in group for h in entry["hooks"]]
        for name in ("h1", "h3", "h4", "h5", "h6"):
            self.assertTrue(any(c.endswith(f"hook {name}") for c in commands), name)
        for c in commands:
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/bin/pipeline"', c)
        matchers = [entry["matcher"] for entry in data["hooks"]["SubagentStop"]]
        self.assertIn("^(delivery-kit:)?test-author$", matchers)
        self.assertIn("^(delivery-kit:)?implementer$", matchers)

    def test_pipeline_is_executable(self):
        self.assertTrue(os.access(PIPELINE, os.X_OK))


if __name__ == "__main__":
    unittest.main()
