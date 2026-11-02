"""Interface gráfica do Eldervale Launcher (customtkinter)."""
import os
import queue
import subprocess
import sys
import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw

from . import config, selfupdate, versions

BG = "#0e131a"
PANEL = "#141b25"
CARD = "#1b2431"
GOLD = "#e9b44c"
GREEN = "#3f9b35"
GREEN_H = "#4fb843"
TEXT = "#e8edf3"
MUTED = "#8b98aa"
DANGER = "#b9473f"

CONTENT_W, CONTENT_H = 890, 584


def fmt_mb(n):
    return f"{n / 1048576:.1f} MB"


def make_cover(w, h):
    p = config.asset_path("cover.jpg")
    if p.exists():
        im = Image.open(p).convert("RGB")
        r = max(w / im.width, h / im.height)
        im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        left, top = (im.width - w) // 2, (im.height - h) // 2
        im = im.crop((left, top, left + w, top + h))
    else:  # fallback: degradê no clima do jogo (céu ao amanhecer -> vale verde)
        im = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(im)
        top_c, mid_c, bot_c = (88, 150, 214), (246, 190, 150), (62, 120, 62)
        for y in range(h):
            t = y / h
            if t < 0.55:
                k = t / 0.55
                c = tuple(int(top_c[i] + (mid_c[i] - top_c[i]) * k) for i in range(3))
            else:
                k = (t - 0.55) / 0.45
                c = tuple(int(mid_c[i] + (bot_c[i] - mid_c[i]) * k) for i in range(3))
            d.line([(0, y), (w, y)], fill=c)
        d.text((w // 2 - 70, h // 2 - 40), "ElderVale", fill=(255, 245, 225))
    shade = Image.new("L", (w, h), 0)
    sd = ImageDraw.Draw(shade)
    for y in range(h - 150, h):
        sd.line([(0, y), (w, y)], fill=int(170 * (y - (h - 150)) / 150))
    im.paste(Image.new("RGB", (w, h), (8, 12, 18)), (0, 0), shade)
    return im


class App(ctk.CTk):
    W, H = 1100, 680
    SIDEBAR, BAR = 210, 96

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Eldervale Launcher")
        self.geometry(f"{self.W}x{self.H}")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.settings = config.Settings()
        self.q = queue.Queue()
        self.manifest = None
        self.online = False
        self.news = []
        self.choices = []          # [(label, key)]
        self.busy = False
        self.cancel = threading.Event()
        self.proc = None
        self._then_play = False
        self.pages = {}
        self.nav = {}

        self._build_ui()
        self._rebuild_choices()
        self._show_page("play")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    # ------------------------------------------------------------------ dados
    def all_versions(self):
        remote = list((self.manifest or {}).get("versions", []))
        ids = {v["id"] for v in remote}
        for vid, entry in versions.installed_versions().items():
            if vid not in ids:
                remote.append(entry)
        remote.sort(key=lambda v: v.get("releaseTime", ""), reverse=True)
        return remote

    def latest_id(self):
        lid = ((self.manifest or {}).get("latest") or {}).get("release")
        if lid:
            return lid
        for v in self.all_versions():
            if versions.is_installed(v["id"]) and v.get("type", "release") == "release":
                return v["id"]
        return None

    def current_version(self):
        vs = {v["id"]: v for v in self.all_versions()}
        key = self.settings["selected"]
        if key == "latest":
            return vs.get(self.latest_id())
        return vs.get(key) or vs.get(self.latest_id())

    # --------------------------------------------------------------------- UI
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        side = ctk.CTkFrame(self, width=self.SIDEBAR, corner_radius=0, fg_color=PANEL)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="ELDERVALE", font=ctk.CTkFont("Georgia", 26, "bold"), text_color=GOLD).pack(pady=(26, 0))
        ctk.CTkLabel(side, text="L A U N C H E R", font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(0, 24))
        for key, text in (("play", "🎮  Jogar"), ("news", "📰  Novidades"),
                          ("notes", "📜  Notas de atualização"), ("settings", "⚙  Configurações")):
            b = ctk.CTkButton(side, text=text, anchor="w", height=42, corner_radius=8,
                              fg_color="transparent", hover_color=CARD, text_color=TEXT,
                              font=ctk.CTkFont(size=14), command=lambda k=key: self._show_page(k))
            b.pack(fill="x", padx=12, pady=3)
            self.nav[key] = b
        self.launcher_note = ctk.CTkLabel(side, text="", text_color=GOLD, wraplength=180, font=ctk.CTkFont(size=11))
        self.launcher_note.pack(side="bottom", pady=(0, 6))
        ctk.CTkLabel(side, text=f"Launcher v{config.LAUNCHER_VERSION}  •  Niro Works",
                     text_color=MUTED, font=ctk.CTkFont(size=11)).pack(side="bottom", pady=(0, 2))

        content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        self.content = content

        self._build_play_page()
        self._build_list_page("news", "Novidades")
        self._build_list_page("notes", "Notas de atualização")
        self._build_settings_page()

        bar = ctk.CTkFrame(self, height=self.BAR, corner_radius=0, fg_color=PANEL)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure((0, 2), weight=1, uniform="side")
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=22)
        ctk.CTkLabel(left, text="VERSÃO", text_color=MUTED, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.version_menu = ctk.CTkOptionMenu(left, values=["—"], width=290, height=36, fg_color=CARD,
                                              button_color=CARD, button_hover_color="#26334a",
                                              command=self._on_select)
        self.version_menu.pack(anchor="w", pady=(2, 0))

        mid = ctk.CTkFrame(bar, fg_color="transparent")
        mid.grid(row=0, column=1)
        self.play_btn = ctk.CTkButton(mid, text="JOGAR", width=270, height=54, corner_radius=6,
                                      fg_color=GREEN, hover_color=GREEN_H,
                                      font=ctk.CTkFont(size=22, weight="bold"), command=self._on_play)
        self.play_btn.pack()
        self.play_sub = ctk.CTkLabel(mid, text="", text_color=MUTED, font=ctk.CTkFont(size=11))
        self.play_sub.pack(pady=(3, 0))

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=22)
        self.status = ctk.CTkLabel(right, text="Pronto", text_color=MUTED, anchor="e", width=280)
        self.status.grid(row=0, column=0, columnspan=2, sticky="e")
        self.progress = ctk.CTkProgressBar(right, width=230, progress_color=GREEN)
        self.progress.grid(row=1, column=0, pady=(6, 0), sticky="e")
        self.cancel_btn = ctk.CTkButton(right, text="✕", width=36, height=22, fg_color=DANGER,
                                        hover_color="#d05a50", command=lambda: self.cancel.set())
        self.cancel_btn.grid(row=1, column=1, padx=(6, 0), pady=(6, 0))
        self.progress.grid_remove()
        self.cancel_btn.grid_remove()

    def _page_frame(self, key):
        f = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0)
        f.grid(row=0, column=0, sticky="nsew")
        self.pages[key] = f
        return f

    def _build_play_page(self):
        f = self._page_frame("play")
        self.cover = ctk.CTkImage(make_cover(CONTENT_W, CONTENT_H), size=(CONTENT_W, CONTENT_H))
        ctk.CTkLabel(f, text="", image=self.cover).place(x=0, y=0, relwidth=1, relheight=1)
        self.badge = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=10)
        self.badge.place(x=24, y=CONTENT_H - 78)
        self.badge_title = ctk.CTkLabel(self.badge, text="", font=ctk.CTkFont(size=15, weight="bold"), text_color=GOLD)
        self.badge_title.pack(anchor="w", padx=16, pady=(10, 0))
        self.badge_sub = ctk.CTkLabel(self.badge, text="", text_color=MUTED, font=ctk.CTkFont(size=12))
        self.badge_sub.pack(anchor="w", padx=16, pady=(0, 10))

    def _build_list_page(self, key, title):
        f = self._page_frame(key)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont("Georgia", 26, "bold"), text_color=GOLD).pack(anchor="w", padx=28, pady=(22, 8))
        box = ctk.CTkScrollableFrame(f, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        setattr(self, f"{key}_box", box)

    def _build_settings_page(self):
        f = self._page_frame("settings")
        ctk.CTkLabel(f, text="Configurações", font=ctk.CTkFont("Georgia", 26, "bold"), text_color=GOLD).pack(anchor="w", padx=28, pady=(22, 12))
        card = ctk.CTkFrame(f, fg_color=CARD, corner_radius=10)
        card.pack(fill="x", padx=28)

        self.var_beta = ctk.BooleanVar(value=self.settings["show_beta"])
        self.var_close = ctk.BooleanVar(value=self.settings["close_on_launch"])
        ctk.CTkSwitch(card, text="Mostrar versões beta/snapshot na lista", variable=self.var_beta,
                      command=self._on_toggle_beta).pack(anchor="w", padx=20, pady=(18, 8))
        ctk.CTkSwitch(card, text="Fechar o launcher ao iniciar o jogo", variable=self.var_close,
                      command=lambda: self.settings.__setitem__("close_on_launch", self.var_close.get())
                      ).pack(anchor="w", padx=20, pady=8)
        ctk.CTkLabel(card, text=f"Pasta do jogo:  {config.DATA_DIR}", text_color=MUTED,
                     wraplength=780, justify="left").pack(anchor="w", padx=20, pady=(8, 10))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(anchor="w", padx=20, pady=(0, 18))
        for text, cmd, color in (("Abrir pasta", self._open_folder, "#2a3a52"),
                                 ("Reinstalar versão", self._reinstall, "#2a3a52"),
                                 ("Remover versão", self._remove, DANGER)):
            ctk.CTkButton(row, text=text, command=cmd, fg_color=color, width=150).pack(side="left", padx=(0, 10))

    # ------------------------------------------------------------- navegação
    def _show_page(self, key):
        self.pages[key].tkraise()
        for k, b in self.nav.items():
            b.configure(fg_color=CARD if k == key else "transparent", text_color=GOLD if k == key else TEXT)

    # ---------------------------------------------------------- seletor/play
    def _rebuild_choices(self):
        self.choices = []
        latest = self.latest_id()
        if latest:
            self.choices.append((f"★ Última versão ({latest})", "latest"))
        for v in self.all_versions():
            kind = v.get("type", "release")
            if kind != "release" and not self.settings["show_beta"] and v["id"] != self.settings["selected"]:
                continue
            label = v["id"] + ("" if kind == "release" else f"  [{kind}]")
            if versions.is_installed(v["id"]):
                label += "  ✓"
            self.choices.append((label, v["id"]))
        labels = [c[0] for c in self.choices] or ["—"]
        self.version_menu.configure(values=labels)
        key = self.settings["selected"]
        cur = next((c[0] for c in self.choices if c[1] == key), labels[0])
        self.version_menu.set(cur)
        self._refresh_play()

    def _on_select(self, label):
        key = next((k for l, k in self.choices if l == label), "latest")
        self.settings["selected"] = key
        self._refresh_play()

    def _refresh_play(self):
        v = self.current_version()
        if self.busy:
            self.play_btn.configure(state="disabled", text="AGUARDE…")
        elif not v:
            self.play_btn.configure(state="disabled", text="SEM VERSÃO")
            self.play_sub.configure(text="Conecte-se à internet para baixar o jogo")
        else:
            installed = versions.is_installed(v["id"])
            self.play_btn.configure(state="normal", text="JOGAR" if installed else "BAIXAR E JOGAR")
            self.play_sub.configure(text=f"Eldervale {v['id']}")
        latest = self.latest_id()
        self.badge_title.configure(text=f"Eldervale {latest}" if latest else "Eldervale")
        self.badge_sub.configure(text="Última versão disponível" + ("" if self.online or not self.manifest else "")
                                 if self.online else "Modo offline — jogando versões instaladas")

    def _set_busy(self, busy):
        self.busy = busy
        if busy:
            self.progress.set(0)
            self.progress.grid()
            self.cancel_btn.grid()
        else:
            self.progress.grid_remove()
            self.cancel_btn.grid_remove()
        self.version_menu.configure(state="disabled" if busy else "normal")
        self._refresh_play()

    # ------------------------------------------------------ ações principais
    def _on_play(self):
        v = self.current_version()
        if not v or self.busy:
            return
        if versions.is_installed(v["id"]):
            self._launch(v)
        else:
            self._start_install(v, then_play=True)

    def _start_install(self, v, then_play):
        if self.busy:
            return
        self.cancel = threading.Event()
        self._then_play = then_play
        self._set_busy(True)
        self.status.configure(text=f"Preparando {v['id']}…")

        def work():
            try:
                versions.install_version(v, lambda d, t, s: self.q.put(("progress", d, t, s)), self.cancel)
                self.q.put(("installed", v))
            except versions.Cancelled:
                self.q.put(("cancelled",))
            except Exception as e:
                self.q.put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _launch(self, v):
        try:
            self.proc = versions.launch(v)
        except Exception as e:
            messagebox.showerror("Eldervale", f"Não foi possível iniciar o jogo:\n{e}")
            return
        self.settings["last_played"] = v["id"]
        self.status.configure(text="Jogo em execução…")
        if self.settings["close_on_launch"]:
            self.after(800, self.destroy)
            return
        self.iconify()
        proc = self.proc
        threading.Thread(target=lambda: self.q.put(("game_exit", proc.wait())), daemon=True).start()

    # ------------------------------------------------------------ configurações
    def _on_toggle_beta(self):
        self.settings["show_beta"] = self.var_beta.get()
        self._rebuild_choices()

    def _open_folder(self):
        path = str(config.DATA_DIR)
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _reinstall(self):
        v = self.current_version()
        if v:
            self._start_install(v, then_play=False)

    def _remove(self):
        v = self.current_version()
        if v and versions.is_installed(v["id"]) and messagebox.askyesno("Remover", f"Remover a versão {v['id']}? Seus saves são mantidos."):
            versions.uninstall(v["id"])
            self._rebuild_choices()
            self._fill_notes()

    # --------------------------------------------------------- páginas de lista
    def _fill_news(self):
        for w in self.news_box.winfo_children():
            w.destroy()
        if not self.news:
            ctk.CTkLabel(self.news_box, text="Sem novidades no momento.", text_color=MUTED).pack(pady=30)
        for n in self.news:
            card = ctk.CTkFrame(self.news_box, fg_color=CARD, corner_radius=10)
            card.pack(fill="x", padx=6, pady=6)
            ctk.CTkLabel(card, text=n.get("title", ""), font=ctk.CTkFont(size=17, weight="bold"), text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 0))
            ctk.CTkLabel(card, text=n.get("date", ""), text_color=GOLD, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)
            ctk.CTkLabel(card, text=n.get("text", ""), wraplength=760, justify="left", text_color=MUTED).pack(anchor="w", padx=16, pady=(6, 10))
            if n.get("url"):
                ctk.CTkButton(card, text="Ler mais", width=100, fg_color="#2a3a52",
                              command=lambda u=n["url"]: webbrowser.open(u)).pack(anchor="w", padx=16, pady=(0, 12))

    def _fill_notes(self):
        for w in self.notes_box.winfo_children():
            w.destroy()
        for v in self.all_versions():
            card = ctk.CTkFrame(self.notes_box, fg_color=CARD, corner_radius=10)
            card.pack(fill="x", padx=6, pady=6)
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=16, pady=(12, 0))
            ctk.CTkLabel(head, text=f"Eldervale {v['id']}", font=ctk.CTkFont(size=17, weight="bold"), text_color=GOLD).pack(side="left")
            kind = v.get("type", "release")
            if kind != "release":
                ctk.CTkLabel(head, text=f" {kind} ", fg_color="#2a3a52", corner_radius=6).pack(side="left", padx=8)
            if versions.is_installed(v["id"]):
                ctk.CTkLabel(head, text="instalada ✓", text_color=GREEN_H).pack(side="left", padx=8)
            ctk.CTkLabel(head, text=(v.get("releaseTime") or "")[:10], text_color=MUTED).pack(side="right")
            ctk.CTkLabel(card, text=v.get("changelog") or "Sem notas para esta versão.", wraplength=760,
                         justify="left", text_color=MUTED).pack(anchor="w", padx=16, pady=(6, 8))
            ctk.CTkButton(card, text="Usar esta versão", width=140, fg_color="#2a3a52",
                          command=lambda vid=v["id"]: self._use_version(vid)).pack(anchor="w", padx=16, pady=(0, 12))

    def _use_version(self, vid):
        self.settings["selected"] = vid
        self._rebuild_choices()
        self._show_page("play")

    # ------------------------------------------------------------------ diálogos
    def _dialog(self, title, header, body, primary_text, primary_cmd, secondary_text="Depois"):
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("520x430")
        dlg.configure(fg_color=PANEL)
        dlg.transient(self)
        ctk.CTkLabel(dlg, text=header, font=ctk.CTkFont("Georgia", 22, "bold"), text_color=GOLD).pack(anchor="w", padx=24, pady=(22, 8))
        box = ctk.CTkTextbox(dlg, fg_color=CARD, text_color=TEXT, wrap="word", height=250)
        box.pack(fill="both", expand=True, padx=24)
        box.insert("1.0", body or "Sem notas de atualização.")
        box.configure(state="disabled")
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=18)
        ctk.CTkButton(row, text=primary_text, fg_color=GREEN, hover_color=GREEN_H, height=40,
                      command=lambda: (dlg.destroy(), primary_cmd())).pack(side="left")
        ctk.CTkButton(row, text=secondary_text, fg_color="#2a3a52", height=40,
                      command=dlg.destroy).pack(side="left", padx=10)
        dlg.after(150, dlg.lift)

    def _show_update_dialog(self, entry):
        def go():
            self.settings["selected"] = "latest"
            self._rebuild_choices()
            v = self.current_version()
            if v and not versions.is_installed(v["id"]):
                self._start_install(v, then_play=False)
        self._dialog("Nova atualização", f"Eldervale {entry['id']} chegou!", entry.get("changelog"), "Atualizar agora", go)

    # -------------------------------------------------------------- threads/fila
    def _refresh_worker(self):
        manifest, online = versions.fetch_manifest()
        news = versions.fetch_news()
        self.q.put(("refreshed", manifest, online, news))
        data = selfupdate.check()
        if data:
            self.q.put(("launcher_update", data))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                getattr(self, "_on_" + msg[0])(*msg[1:])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _on_refreshed(self, manifest, online, news):
        self.manifest, self.online, self.news = manifest, online, news
        self._rebuild_choices()
        self._fill_news()
        self._fill_notes()
        latest = self.latest_id() if manifest else None
        if online and latest:
            last = self.settings["last_seen_latest"]
            self.settings["last_seen_latest"] = latest
            if last and last != latest:
                entry = next((v for v in manifest["versions"] if v["id"] == latest), None)
                if entry:
                    self._show_update_dialog(entry)

    def _on_progress(self, done, total, stage):
        if total:
            self.progress.set(done / total)
        if stage == "Extraindo":
            self.status.configure(text=f"Extraindo… {done}/{total}")
        else:
            self.status.configure(text=f"{stage}… {fmt_mb(done)}" + (f" / {fmt_mb(total)}" if total else ""))

    def _on_installed(self, v):
        self._set_busy(False)
        self.status.configure(text=f"Eldervale {v['id']} instalado")
        self._rebuild_choices()
        self._fill_notes()
        if self._then_play:
            self._launch(v)

    def _on_cancelled(self):
        self._set_busy(False)
        self.status.configure(text="Download cancelado")

    def _on_error(self, msg):
        self._set_busy(False)
        self.status.configure(text="Erro")
        messagebox.showerror("Eldervale", msg)

    def _on_game_exit(self, code):
        self.deiconify()
        self.status.configure(text="Pronto" if code == 0 else f"O jogo fechou (código {code})")

    def _on_launcher_update(self, data):
        if not selfupdate.can_self_update():
            self.launcher_note.configure(text=f"Launcher {data['version']} disponível (atualize manualmente)")
            return
        self._dialog("Atualização do launcher", f"Launcher {data['version']}", data.get("changelog"),
                     "Atualizar launcher", lambda: self._download_launcher(data))

    def _download_launcher(self, data):
        self.cancel = threading.Event()
        self._set_busy(True)
        self.status.configure(text="Baixando launcher…")

        def work():
            try:
                path = selfupdate.download(data, lambda d, t, s: self.q.put(("progress", d, t, s)), self.cancel)
                self.q.put(("launcher_downloaded", path))
            except Exception as e:
                self.q.put(("error", f"Falha ao atualizar o launcher: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _on_launcher_downloaded(self, path):
        selfupdate.finalize(path)  # no Linux/macOS reinicia aqui; no Windows um .bat faz a troca
        self.destroy()

    def _on_close(self):
        if self.busy and not messagebox.askyesno("Eldervale", "Há um download em andamento. Sair mesmo assim?"):
            return
        self.cancel.set()
        self.destroy()


def run():
    App().mainloop()
