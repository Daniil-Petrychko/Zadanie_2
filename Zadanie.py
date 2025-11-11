import os
import sys
import random
import re
import tkinter as tk
from collections import Counter
from tkinter import messagebox
from tkinter import ttk

# ---------------- Konštanty ----------------
ICON_FILE = "app.ico"
ROOM_RE = re.compile(r'^(?:BA1|S31)_\d{3}$')
BA_NUMBERS = tuple(f"{b+n:03d}" for b in (0, 100, 200, 300) for n in range(1, 13))
S31_NUMBERS = tuple(f"{n:03d}" for n in range(1, 76))
VALID_BA = {f"BA1_{n}" for n in BA_NUMBERS}
VALID_S31 = {f"S31_{n}" for n in S31_NUMBERS}
FIXED_BA = ["BA1_003", "BA1_011", "BA1_105", "BA1_207", "BA1_303", "BA1_001", "BA1_210"]
FIXED_S31 = ["S31_002", "S31_015", "S31_023", "S31_034", "S31_045", "S31_058", "S31_071"]
FIXED_SET = FIXED_BA + FIXED_S31
PLACEHOLDER = "Zadajte kódy (BA1_003, S31_015, ...) oddelené čiarkou alebo medzerou"
EXPECTED_TOTAL, EXPECTED_BA = 14, 7

# ---------------- Pomocné funkcie ----------------
def resource_path(rel: str) -> str:
    """Cesta k zdroju fungujúca v .py, PyInstaller onefile aj onedir."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))  # pylint: disable=protected-access  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)

def normalize(code: str) -> str:
    """Normalizácia: veľké písmená, '-'/' ' → '_', doplnenie podčiarkovníka po BA1/S31."""
    c = code.strip().upper().replace('-', '_').replace(' ', '_')
    return re.sub(r'^(BA1|S31)(?=\d{3}$)', r'\1_', c)

def parse_input(text: str):
    """Rozdelí vstup podľa čiarky/medzery a každý prvok normalizuje."""
    return [normalize(p) for p in re.split(r'[,\s]+', text.strip()) if p]

def is_valid(code: str) -> bool:
    """Platný formát a patriaci do povolených množín."""
    return bool(ROOM_RE.fullmatch(code)) and (code in VALID_BA or code in VALID_S31)

def partition(codes):
    """Rozdelí kódy na BA1, S31 a neplatné, následne utriedi podľa čísla."""
    ba, s, bad = [], [], []
    for c in codes:
        if not is_valid(c):
            bad.append(c)
        elif c.startswith("BA1_"):
            ba.append(c)
        else:
            s.append(c)
    key = lambda x: int(x.split('_')[1])
    ba.sort(key=key); s.sort(key=key)
    return ba, s, bad

def duplicates(codes):
    """Zoznam duplicitných kódov (normalizovaných)."""
    cnt = Counter(codes)
    return sorted(k for k, v in cnt.items() if v > 1)

def random_sample(total=EXPECTED_TOTAL, ba_count=EXPECTED_BA):
    """Vygeneruje náhodnú vzorku 7x BA1 a 7x S31 (spolu 14)."""
    if total != EXPECTED_TOTAL or ba_count != EXPECTED_BA:
        raise ValueError("Nesprávne parametre vzorky.")
    rng = random.SystemRandom()
    ba_sel = rng.sample(BA_NUMBERS, ba_count)
    s_sel = rng.sample(S31_NUMBERS, total - ba_count)
    out = [f"BA1_{n}" for n in ba_sel] + [f"S31_{n}" for n in s_sel]
    rng.shuffle(out)
    return out

# ---------------- Aplikácia ----------------
class RoomsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Triedenie miestností (BA1 / S31)")
        self._nastav_ikonu()

        self.placeholder_active = True

        frm = ttk.Frame(root, padding=10); frm.pack(fill="both", expand=True)
        inp = ttk.Labelframe(frm, text="Vstup"); inp.pack(fill="x")
        self.txt = tk.Text(inp, height=4, wrap="word"); self.txt.pack(fill="x", padx=6, pady=6)
        self.txt.tag_config("invalid", background="#ffd6d6")
        self.txt.tag_config("duplicate", background="#fff3b3")
        self._set_placeholder()
        self.txt.bind("<FocusIn>", self._on_focus_in)
        self.txt.bind("<FocusOut>", self._on_focus_out)

        btns = ttk.Frame(inp); btns.pack(fill="x", padx=6, pady=(0,6))
        for text, cmd in (
            ("Fixná sada", self.load_fixed),
            ("Náhodná sada", self.load_random),
            ("Spracovať", self.process),
            ("Vyčistiť", self.clear),
            ("Kopírovať výsledok", self.copy_result)
        ):
            ttk.Button(btns, text=text, command=cmd).pack(side="left", padx=(0,6))

        res = ttk.Frame(frm); res.pack(fill="both", expand=True, pady=(10,4))
        for i in range(3): res.columnconfigure(i, weight=1)

        box_ba = ttk.Labelframe(res, text="Blok BA1"); box_ba.grid(row=0, column=0, sticky="nsew", padx=(0,6))
        self.list_ba = tk.Listbox(box_ba, height=14); self.list_ba.pack(fill="both", expand=True, padx=4, pady=4)

        box_s = ttk.Labelframe(res, text="Blok S31"); box_s.grid(row=0, column=1, sticky="nsew", padx=(0,6))
        self.list_s = tk.Listbox(box_s, height=14); self.list_s.pack(fill="both", expand=True, padx=4, pady=4)

        box_stats = ttk.Labelframe(res, text="Štatistika"); box_stats.grid(row=0, column=2, sticky="nsew")
        self.stats = tk.Text(box_stats, height=14, wrap="word", state="disabled"); self.stats.pack(fill="both", expand=True, padx=4, pady=4)

        status = ttk.Frame(frm); status.pack(fill="x", pady=(4,0))
        self.status = ttk.Label(status, text="Pripravené."); self.status.pack(anchor="w")
        self.txt.focus_set()

    # ---------- Ikona ----------
    def _nastav_ikonu(self):
        """Nastaví ikonu okna/panela úloh z vloženého alebo lokálneho .ico."""
        path = resource_path(ICON_FILE)
        if os.path.isfile(path):
            try:
                self.root.iconbitmap(path)
            except (tk.TclError, OSError) as e:
                print("Ikona nebola nastavená:", e)

    # ---------- Placeholder ----------
    def _set_placeholder(self):
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", PLACEHOLDER)
        self.txt.config(fg="#777")
        self.placeholder_active = True

    def _on_focus_in(self, _):
        if self.placeholder_active:
            self.txt.delete("1.0", "end")
            self.txt.config(fg="#000")
            self.placeholder_active = False

    def _on_focus_out(self, _):
        if not self.txt.get("1.0", "end").strip():
            self._set_placeholder()

    # ---------- Akcie ----------
    def load_fixed(self):
        self._ensure_active()
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", ", ".join(FIXED_SET))
        self._status("Fixná sada načítaná.")

    def load_random(self):
        self._ensure_active()
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", ", ".join(random_sample()))
        self._status("Náhodná sada načítaná.")

    def clear(self):
        self.list_ba.delete(0, "end"); self.list_s.delete(0, "end")
        self._set_placeholder()
        self._stats([], [], [], [], [])
        self._highlight(set(), set())
        self._status("Vyčistené.")

    def process(self):
        if self.placeholder_active:
            self._status("Žiadne dáta.", "orange"); return
        codes = parse_input(self.txt.get("1.0", "end"))
        ba, s, bad = partition(codes)
        dups = duplicates(codes)

        self.list_ba.delete(0,"end"); self.list_s.delete(0,"end")
        if ba: self.list_ba.insert("end", *ba)
        if s: self.list_s.insert("end", *s)

        self._highlight(set(bad), set(dups))
        self._stats(codes, ba, s, bad, dups)

        msg = f"Spracovaných {len(codes)}. BA1: {len(ba)}, S31: {len(s)}, neplatné: {len(bad)}, duplicitné: {len(dups)}."
        if len(codes) != EXPECTED_TOTAL:
            msg += f" Očakávaných {EXPECTED_TOTAL}."
        self._status(msg, "orange" if (len(codes)!=EXPECTED_TOTAL or bad or dups) else "green")

        if bad: messagebox.showwarning("Neplatné kódy", ", ".join(bad))
        if dups: messagebox.showwarning("Duplicitné kódy", ", ".join(dups))

    def copy_result(self):
        if self.placeholder_active: return
        codes = parse_input(self.txt.get("1.0", "end"))
        ba, s, bad = partition(codes)
        out = f"BA1 ({len(ba)}): {', '.join(ba)}\nS31 ({len(s)}): {', '.join(s)}"
        if bad: out += "\nNeplatné: " + ", ".join(bad)
        self.root.clipboard_clear(); self.root.clipboard_append(out)
        self._status("Výsledok skopírovaný.", "green")

    # ---------- Pomocné ----------
    def _ensure_active(self):
        if self.placeholder_active:
            self.placeholder_active = False
            self.txt.delete("1.0", "end")
            self.txt.config(fg="#000")

    def _status(self, text, color="gray"):
        self.status.config(text=text, foreground=color)

    def _highlight(self, invalid: set, dups: set):
        """Zvýrazní tokeny vo vstupe podľa sád neplatných a duplicitných."""
        self.txt.tag_remove("invalid","1.0","end")
        self.txt.tag_remove("duplicate","1.0","end")
        if self.placeholder_active: return
        content = self.txt.get("1.0","end-1c")
        for m in re.finditer(r'[^,\s]+', content):
            norm = normalize(m.group())
            start, end = f"1.0+{m.start()}c", f"1.0+{m.end()}c"
            if norm in invalid:
                self.txt.tag_add("invalid", start, end)
            elif norm in dups:
                self.txt.tag_add("duplicate", start, end)

    def _stats(self, all_codes, ba, s, bad, dups):
        self.stats.config(state="normal"); self.stats.delete("1.0","end")
        self.stats.insert("end", f"Zadané: {len(all_codes)}\nBA1: {len(ba)}\nS31: {len(s)}\nNeplatné: {len(bad)}\nDuplicitné: {len(dups)}\n")
        total_valid = len(ba)+len(s)
        if total_valid:
            self.stats.insert("end", f"Podiel BA1: {len(ba)/total_valid*100:.1f}% | S31: {len(s)/total_valid*100:.1f}%\n")
        if bad: self.stats.insert("end", "\nNeplatné:\n" + ", ".join(bad) + "\n")
        if dups: self.stats.insert("end", "\nDuplicitné:\n" + ", ".join(dups) + "\n")
        self.stats.config(state="disabled")

def main():
    root = tk.Tk()
    RoomsApp(root)
    root.minsize(760, 460)
    root.mainloop()

if __name__ == "__main__":
    main()