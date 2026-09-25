import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
import zlib

from RecuDaGa.deep import carve, photorec
from RecuDaGa.devices import check_destination
from RecuDaGa.recovery import recover_tree
from RecuDaGa.repair import repair_zip
from RecuDaGa.report import save_report
from RecuDaGa.validation import validate


def png_chunk(name, data):
    return len(data).to_bytes(4, "big") + name + data + zlib.crc32(name + data).to_bytes(4, "big")


def tiny_png():
    return (b"\x89PNG\r\n\x1a\n" +
            png_chunk(b"IHDR", (1).to_bytes(4, "big") * 2 + b"\x08\x02\x00\x00\x00") +
            png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) +
            png_chunk(b"IEND", b""))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_copy_tree_and_report(self):
        source = self.base / "origen"
        (source / "sub").mkdir(parents=True)
        (source / "sub" / "foto.png").write_bytes(tiny_png())
        output = self.base / "salida"
        entries = recover_tree(source, output, threading.Event(), lambda *_: None)
        self.assertEqual(entries[0]["estado"], "validado")
        self.assertEqual((output / "archivos/sub/foto.png").read_bytes(), tiny_png())
        report = save_report(output, "test", source, entries)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["total"], 1)

    def test_truncated_png_detected(self):
        path = self.base / "rota.png"
        path.write_bytes(tiny_png()[:-5])
        self.assertEqual(validate(path)[0], False)

    def test_cancel_before_start(self):
        source = self.base / "origen"
        source.mkdir()
        (source / "a.txt").write_text("abc")
        cancel = threading.Event()
        cancel.set()
        self.assertEqual(recover_tree(source, self.base / "salida", cancel, lambda *_: None), [])

    def test_read_failure_is_reported(self):
        source = self.base / "origen"
        source.mkdir()
        bad = source / "bad.bin"
        bad.write_bytes(b"test")
        original_open = open

        def fail_source(path, mode="r", *args, **kwargs):
            if Path(path) == bad and mode == "rb":
                raise OSError("simulated read failure")
            return original_open(path, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=fail_source):
            entries = recover_tree(source, self.base / "salida", threading.Event(), lambda *_: None)
        self.assertEqual(entries[0]["estado"], "fallido")
        self.assertIn("simulated read failure", entries[0]["evidencia"])

    def test_same_physical_disk_rejected(self):
        with self.assertRaisesRegex(ValueError, "mismo disco"):
            check_destination(7, self.base, {self.base.drive[0].upper(): 7})
        self.assertEqual(check_destination(8, self.base, {self.base.drive[0].upper(): 7}), self.base.resolve())

    def test_carve_controlled_image(self):
        image = self.base / "disk.img"
        image.write_bytes(b"\x00" * 64 + tiny_png() + b"\x00" * 64)
        entries = carve(image, self.base / "salida", threading.Event(), lambda *_: None)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["offset"], 64)
        self.assertEqual(entries[0]["estado"], "validado")

    def test_carve_incomplete_file_is_partial(self):
        image = self.base / "disk.img"
        image.write_bytes(b"\x00" * 16 + b"\xff\xd8\xff" + b"fragmento sin cierre")
        entries = carve(image, self.base / "salida", threading.Event(), lambda *_: None)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["estado"], "parcial")
        self.assertTrue(Path(entries[0]["destino"]).exists())

    def test_zip_rebuild_omits_bad_entry(self):
        path = self.base / "files.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("good.txt", b"GOOD DATA")
            z.writestr("bad.txt", b"BAD DATA")
        damaged = path.read_bytes().replace(b"BAD DATA", b"XXX DATA", 1)
        path.write_bytes(damaged)
        self.assertEqual(validate(path)[0], False)
        repaired, detail = repair_zip(path)
        self.assertIsNotNone(repaired, detail)
        with zipfile.ZipFile(repaired) as z:
            self.assertEqual(z.namelist(), ["good.txt"])
        self.assertEqual(validate(repaired)[0], True)

    def test_photorec_adapter_builds_read_only_scan_command(self):
        executable = self.base / "photorec_win.exe"
        executable.write_bytes(b"simulated executable")
        image = self.base / "disk.img"
        image.write_bytes(b"\0" * 512)
        with patch("RecuDaGa.deep.subprocess.Popen") as start:
            process = start.return_value
            process.poll.return_value = 0
            process.returncode = 0
            self.assertEqual(photorec(executable, image, self.base / "salida",
                                      threading.Event(), lambda *_: None), [])
        command = start.call_args.args[0]
        self.assertEqual(command[-1], "fileopt,everything,enable,wholespace,search")
        self.assertEqual(command[-2], str(image))


if __name__ == "__main__":
    unittest.main()
