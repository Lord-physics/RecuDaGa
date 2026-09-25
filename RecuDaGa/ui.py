"""Interfaz Tkinter: selecci�n, ejecuci�n cancelable y resultados."""
import ctypes
import subprocess
import sys
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .deep import carve, photorec
from .devices import check_destination, disk_for_path, inventory, is_admin, probe_physical
from .recovery import recover_tree
from .report import save_report


class App(tk.Tk):
    def __init__(self, initial=None):
        super().__init__()
        self.title("RecuDaGa")
        self.geometry("810x600")
        self.minsize(700, 520)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.disks = []
        self.letters = {}
        self.mode = tk.StringVar(value="Archivos accesibles")
        self.source = tk.StringVar()
        self.destination = tk.StringVar()
        self.engine = tk.StringVar(value="Firmas b�sicas")
        self.photorec_exe = tk.StringVar()
        if initial:
            self.mode.set(initial.get("mode") or self.mode.get())
            self.source.set(initial.get("source") or "")
            self.destination.set(initial.get("destination") or "")
            self.engine.set(initial.get("engine") or self.engine.get())
            self.photorec_exe.set(initial.get("photorec") or "")
        self._build()
        self.after(50, self._poll)
        self.refresh_disks()

    def _build(self):
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Recuperaci�n local de archivos", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(body, text="El origen se lee sin modificarlo. Elige un destino en otro disco f�sico.").pack(anchor="w", pady=(2, 12))
        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Label(row, text="Modo", width=12).pack(side="left")
        mode_box = ttk.Combobox(row, textvariable=self.mode, state="readonly",
                                values=("Archivos accesibles", "Disco no reconocido / an�lisis profundo"))
        mode_box.pack(side="left", fill="x", expand=True)
        mode_box.bind("<<ComboboxSelected>>", lambda _event: self._update_mode())
        ttk.Button(row, text="Actualizar discos", command=self.refresh_disks).pack(side="left", padx=(8, 0))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(12, 0))
        ttk.Label(row, text="Origen", width=12).pack(side="left")
        self.source_box = ttk.Combobox(row, textvariable=self.source)
        self.source_box.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Carpeta", command=self._choose_source).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Imagen", command=self._choose_image).pack(side="left", padx=(4, 0))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(12, 0))
        ttk.Label(row, text="Destino", width=12).pack(side="left")
        ttk.Entry(row, textvariable=self.destination).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Elegir", command=self._choose_destination).pack(side="left", padx=(8, 0))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(12, 0))
        ttk.Label(row, text="Motor", width=12).pack(side="left")
        self.engine_box = ttk.Combobox(row, textvariable=self.engine, state="readonly",
                                       values=("Firmas b�sicas", "PhotoRec externo"))
        self.engine_box.pack(side="left", fill="x", expand=True)
        self.engine_box.bind("<<ComboboxSelected>>", lambda _event: self._update_mode())
        ttk.Button(row, text="Elegir PhotoRec", command=self._choose_photorec).pack(side="left", padx=(8, 0))
        self.engine_label = ttk.Label(body, text="")
        self.engine_label.pack(anchor="w", pady=(5, 0))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(15, 6))
        self.start_button = ttk.Button(row, text="Iniciar recuperaci�n", command=self.start)
        self.start_button.pack(side="left")
        ttk.Button(row, text="Cancelar", command=self.cancel.set).pack(side="left", padx=(8, 0))
        self.busy = ttk.Progressbar(row, mode="indeterminate")
        self.busy.pack(side="left", fill="x", expand=True, padx=(16, 0))
        self.status = ttk.Label(body, text="Preparado")
        self.status.pack(anchor="w")
        self.log = tk.Text(body, height=17, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, pady=(8, 0))
        self._update_mode()

    def _append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _update_mode(self):
        deep = self.mode.get() != "Archivos accesibles"
        self.engine_box.configure(state="readonly" if deep else "disabled")
        if deep:
            description = ("Firmas b�sicas: JPEG, PNG y PDF, sin nombres originales."
                           if self.engine.get() == "Firmas b�sicas" else
                           "PhotoRec: formatos que admita su versi�n; binario externo no incluido.")
        else:
            description = "Copia archivos legibles y valida formatos admitidos; intenta reconstruir ZIP da�ados."
        self.engine_label.configure(text=description)

    def refresh_disks(self):
        try:
            self.disks, self.letters = inventory()
            choices = [f"{letter}:\\" for letter in sorted(self.letters)]
            choices += [f"\\\\.\\PhysicalDrive{int(d['Number'])}" for d in self.disks]
            self.source_box.configure(values=choices)
            self._append(f"Discos detectados: {len(self.disks)}; unidades con letra: {len(self.letters)}")
            for disk in self.disks:
                self._append(f"Disco {disk['Number']}: {disk.get('FriendlyName', '')} � {disk.get('OperationalStatus', '')}")
        except RuntimeError as exc:
            self.disks, self.letters = [], {}
            self.source_box.configure(values=[])
            self._append(f"Enumeraci�n no disponible: {exc}. Prueba ejecutar como administrador fuera de un entorno restringido.")

    def _choose_source(self):
        value = filedialog.askdirectory(title="Selecciona carpeta o unidad de origen")
        if value:
            self.source.set(value)

    def _choose_image(self):
        value = filedialog.askopenfilename(title="Selecciona una imagen de disco para an�lisis profundo")
        if value:
            self.source.set(value)
            self.mode.set("Disco no reconocido / an�lisis profundo")
            self._update_mode()

    def _choose_destination(self):
        value = filedialog.askdirectory(title="Selecciona carpeta de destino en otro disco")
        if value:
            self.destination.set(value)

    def _choose_photorec(self):
        value = filedialog.askopenfilename(title="Selecciona photorec_win.exe", filetypes=[("Ejecutable", "*.exe")])
        if value:
            self.photorec_exe.set(value)
            self.engine.set("PhotoRec externo")
            self._update_mode()

    def _prepare(self):
        source = self.source.get().strip()
        if not source:
            raise ValueError("Selecciona un origen.")
        physical = source.lower().startswith("\\\\.\\physicaldrive")
        if physical:
            try:
                number = int(source[len(r"\\.\PhysicalDrive"):])
            except (IndexError, ValueError):
                raise ValueError("Ruta de disco f�sico no v�lida.") from None
            if number not in {int(d["Number"]) for d in self.disks}:
                raise ValueError("El disco f�sico no aparece en el inventario actual.")
            source_disk = number
            if self.mode.get() == "Archivos accesibles":
                raise ValueError("Selecciona el modo de an�lisis profundo para un disco f�sico.")
        else:
            path = Path(source)
            if not path.exists():
                raise ValueError("El origen no existe o Windows no puede acceder a �l.")
            if self.mode.get() == "Archivos accesibles" and not path.is_dir():
                raise ValueError("El rescate de archivos accesibles requiere una carpeta o unidad.")
            if self.mode.get() != "Archivos accesibles" and not path.is_file():
                raise ValueError("El an�lisis profundo requiere un disco f�sico o una imagen de disco.")
            source_disk = disk_for_path(path, self.letters)
        destination = check_destination(source_disk, self.destination.get(), self.letters)
        if physical:
            probe = probe_physical(source_disk)
            if probe != "Lectura permitida":
                raise ValueError(probe)
        if self.mode.get() == "Disco no reconocido / an�lisis profundo" and self.engine.get() == "PhotoRec externo":
            exe = Path(self.photorec_exe.get())
            if exe.name.lower() not in {"photorec.exe", "photorec_win.exe"} or not exe.is_file():
                raise ValueError("Selecciona photorec_win.exe o photorec.exe para este motor.")
        return source, destination

    def start(self):
        if self.running:
            return
        try:
            source, destination = self._prepare()
        except (OSError, ValueError) as exc:
            if ("permisos de administrador" in str(exc) and not is_admin()
                    and self.source.get().lower().startswith(r"\\.\physicaldrive")):
                if messagebox.askyesno("Permisos de lectura",
                                       "Windows exige permisos de administrador para leer este disco f�sico. �Reabrir la aplicaci�n con esos permisos?"):
                    self._elevate()
                return
            messagebox.showerror("No se puede iniciar", str(exc))
            return
        self.cancel.clear()
        self.running = True
        self.start_button.configure(state="disabled")
        self.busy.start(10)
        mode, engine, exe = self.mode.get(), self.engine.get(), self.photorec_exe.get()
        threading.Thread(target=self._run, args=(source, destination, mode, engine, exe), daemon=True).start()

    def _elevate(self):
        arguments = subprocess.list2cmdline([
            "-m", "RecuDaGa", "--source", self.source.get(), "--destination",
            self.destination.get(), "--mode", self.mode.get(), "--engine",
            self.engine.get(), "--photorec", self.photorec_exe.get()])
        shell = ctypes.windll.shell32
        shell.ShellExecuteW.restype = ctypes.c_void_p
        result = shell.ShellExecuteW(None, "runas", sys.executable, arguments,
                                     str(Path(__file__).resolve().parent.parent), 1)
        if not result or result <= 32:
            messagebox.showerror("No se pudo elevar", "Windows no autoriz� la apertura con permisos de administrador.")
        else:
            self.destroy()

    def _run(self, source, destination, mode, engine, exe):
        run_dir = Path(destination) / ("RecuDaGa_" + __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        progress = lambda count, name, status: self.events.put(("progress", count, name, status))
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            if mode == "Archivos accesibles":
                entries = recover_tree(source, run_dir, self.cancel, progress)
            elif engine == "PhotoRec externo":
                entries = photorec(exe, source, run_dir, self.cancel, progress)
            else:
                entries = carve(source, run_dir, self.cancel, progress)
            report = save_report(run_dir, mode, source, entries, self.cancel.is_set())
            failed = sum(item["estado"] == "fallido" for item in entries)
            self.events.put(("done", len(entries), failed, str(report), self.cancel.is_set()))
        except Exception as exc:
            detail = str(exc)
            if run_dir.is_dir():
                try:
                    report = save_report(run_dir, mode, source, [{
                        "origen": str(source), "destino": None, "bytes": 0,
                        "estado": "fallido", "evidencia": detail}], self.cancel.is_set())
                    detail += f". Informe: {report}"
                except OSError:
                    pass
            self.events.put(("error", detail, str(run_dir)))

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    _, count, name, status = event
                    self.status.configure(text=f"{count} resultados � {name}: {status}")
                elif event[0] == "done":
                    _, count, failed, report, cancelled = event
                    self._append(f"{'Cancelado' if cancelled else 'Terminado'}: {count} resultados, {failed} fallidos. Informe: {report}")
                    self.status.configure(text="Cancelado" if cancelled else f"Terminado; fallidos: {failed}")
                    self._idle()
                elif event[0] == "error":
                    _, detail, run_dir = event
                    self._append(f"Error: {detail}. Salida parcial: {run_dir}")
                    self.status.configure(text="Error")
                    self._idle()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _idle(self):
        self.running = False
        self.busy.stop()
        self.start_button.configure(state="normal")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    for field in ("source", "destination", "mode", "engine", "photorec"):
        parser.add_argument("--" + field)
    App(vars(parser.parse_args())).mainloop()
