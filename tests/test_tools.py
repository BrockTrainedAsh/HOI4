#!/usr/bin/env python3
"""
Stdlib-only regression tests for the toolkit's Python tools.

Run:  python3 -m unittest -v tests.test_tools
  or: python3 tests/test_tools.py

These cover the pure logic we can verify without the game / Cheat Engine:
mod_version_bump (descriptor rewrite + launcher-DB sync), extract_baseline
(WeMod target catalog), ce_log_watch (failure diagnosis), and that the shipped
.CT is well-formed XML.
"""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # __name__ != "__main__", so main() does not run
    return mod


eb = _load("extract_baseline")
mvb = _load("mod_version_bump")
clw = _load("ce_log_watch")


class WeModCatalog(unittest.TestCase):
    def test_every_target_has_required_keys(self):
        keys = {"feature", "route", "status", "baseline", "offset", "console", "notes"}
        self.assertGreater(len(eb.WEMOD_TARGETS), 20)
        for t in eb.WEMOD_TARGETS:
            self.assertEqual(set(t.keys()), keys, t.get("feature"))
            self.assertIn(t["status"], {"baseline", "new", "console", "external"})

    def test_special_project_target_present(self):
        feats = " | ".join(t["feature"].lower() for t in eb.WEMOD_TARGETS)
        self.assertIn("special project", feats)

    def test_write_targets_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            eb.write_targets(eb.WEMOD_TARGETS, d / "t.lua", d / "t.json")
            data = json.loads((d / "t.json").read_text())
            self.assertEqual(len(data["targets"]), len(eb.WEMOD_TARGETS))
            self.assertTrue((d / "t.lua").read_text().startswith("--"))


class VersionBump(unittest.TestCase):
    def test_descriptor_rewrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ugc_x.mod"
            p.write_text('name="Test"\nsupported_version="1.9.*"\n', encoding="utf-8")
            status, msg, _ = mvb.process(p, "1.19.*", dry_run=False, make_backup=False)
            self.assertEqual(status, "changed")
            self.assertIn('supported_version="1.19.*"', p.read_text())

    def test_descriptor_noop_when_already_target(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ugc_y.mod"
            p.write_text('name="T"\nsupported_version="1.19.*"\n', encoding="utf-8")
            status, _, _ = mvb.process(p, "1.19.*", dry_run=False, make_backup=False)
            self.assertEqual(status, "ok")

    def test_sync_launcher_db(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "launcher-v2.sqlite"
            con = sqlite3.connect(str(db))
            con.execute("CREATE TABLE mods (id INTEGER PRIMARY KEY, displayName TEXT, "
                        "name TEXT, steamId TEXT, pdxId TEXT, requiredVersion TEXT)")
            con.executemany("INSERT INTO mods (id, displayName, requiredVersion) VALUES (?,?,?)",
                            [(1, "A", "1.9.*"), (2, "B", "1.15.*"), (3, "C", "1.19.*")])
            con.commit(); con.close()

            report, err = mvb.sync_launcher_db(db, "1.19.*", dry_run=False, make_backup=False)
            self.assertIsNone(err)
            self.assertEqual(len(report), 2)  # only the two stale rows

            con = sqlite3.connect(str(db))
            vers = {r[0] for r in con.execute("SELECT requiredVersion FROM mods")}
            con.close()
            self.assertEqual(vers, {"1.19.*"})

    def test_sync_launcher_db_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "launcher-v2.sqlite"
            con = sqlite3.connect(str(db))
            con.execute("CREATE TABLE mods (id INTEGER PRIMARY KEY, displayName TEXT, "
                        "name TEXT, steamId TEXT, pdxId TEXT, requiredVersion TEXT)")
            con.execute("INSERT INTO mods (id, displayName, requiredVersion) VALUES (1,'A','1.9.*')")
            con.commit(); con.close()
            report, err = mvb.sync_launcher_db(db, "1.19.*", dry_run=True, make_backup=False)
            self.assertIsNone(err)
            self.assertEqual(len(report), 1)
            con = sqlite3.connect(str(db))
            v = con.execute("SELECT requiredVersion FROM mods").fetchone()[0]
            con.close()
            self.assertEqual(v, "1.9.*")  # unchanged


class CeLogVerdict(unittest.TestCase):
    def test_not_attached_is_flagged(self):
        lines = ["[00:00:00] ===== DIAGNOSTICS =====",
                 "[00:00:00] WARNING: not attached to a process!"]
        v = " ".join(clw.verdict(clw.scan(lines)))
        self.assertIn("NOT attached", v)

    def test_focus_never_true_is_flagged(self):
        lines = ["[00:00:00] engine ready", "[00:00:00] ===== DIAGNOSTICS =====",
                 "[00:00:01] watch 1: focused=false  isKeyPressed(W)=false"]
        v = " ".join(clw.verdict(clw.scan(lines)))
        self.assertIn("focus detection FAILED", v)

    def test_full_success_path(self):
        lines = ["[00:00:00] engine ready", "[00:00:00] ===== DIAGNOSTICS =====",
                 "[00:00:01] watch 1: focused=true  isKeyPressed(W)=true",
                 "[00:00:01] send: opening console", "[00:00:02] send: DONE 'pp 1000'"]
        v = " ".join(clw.verdict(clw.scan(lines)))
        self.assertIn("OK", v)


class CeLogStructured(unittest.TestCase):
    SUMMARY = ("[12:00:00] DIAGSUMMARY attached=true api_fgwin=function api_iskey=function "
               "api_inputquery=function api_timer=function focus_seen=true wkey_seen=true "
               "errors=0 hold=60 gap=45")

    def test_parse_summary(self):
        s = clw.parse_summary([self.SUMMARY])
        self.assertEqual(s["attached"], "true")
        self.assertEqual(s["focus_seen"], "true")
        self.assertEqual(s["hold"], "60")

    def test_parse_summary_absent(self):
        self.assertIsNone(clw.parse_summary(["[..] just a normal line"]))

    def test_structured_all_ok(self):
        s = clw.parse_summary([self.SUMMARY])
        v = " ".join(clw.structured_verdict(s, []))
        self.assertIn("OK", v)

    def test_structured_not_attached(self):
        v = " ".join(clw.structured_verdict({"attached": "false"}, []))
        self.assertIn("NOT attached", v)

    def test_structured_focus_failed(self):
        v = " ".join(clw.structured_verdict({"attached": "true", "focus_seen": "false"}, []))
        self.assertIn("focus never detected", v)

    def test_structured_reports_errors(self):
        v = " ".join(clw.structured_verdict(
            {"attached": "true", "focus_seen": "true", "wkey_seen": "true"},
            ["drain: attempt to call a nil value"]))
        self.assertIn("caught error", v)

    def test_parse_errors(self):
        errs = clw.parse_errors(["[12:00:00] [ERR] drain: boom", "[12:00:01] normal line"])
        self.assertEqual(errs, ["drain: boom"])


class ShippedTable(unittest.TestCase):
    def test_ct_is_valid_xml(self):
        ct = ROOT / "tables" / "HOI4 Console Cheats.CT"
        ET.parse(ct)  # raises if malformed
        entries = ET.parse(ct).findall(".//CheatEntry")
        self.assertGreaterEqual(len(entries), 13)


if __name__ == "__main__":
    unittest.main(verbosity=2)
