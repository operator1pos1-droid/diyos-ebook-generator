import os
import tempfile
from fpdf import FPDF

GOLD = (234, 179, 8)
WHITE = (255, 255, 255)
LIGHT = (226, 232, 240)
GREY = (148, 163, 184)

# --- Posisi nomor halaman (mm, dari pojok kiri-atas kertas A4 210x297) ---
PAGE_NUM_X = (179.0, 199.0)  # titik tengah "__" pertama (HALAMAN) dan kedua (PAGE)
PAGE_NUM_Y = 287.6           # garis dasar teks (naik/turun: kecil = naik)
PAGE_NUM_SIZE = 12           # ukuran font (pt)
PAGE_NUM_STYLE = "B"         # "B" tebal, "" biasa


class DiYosEbookPDF(FPDF):
    def __init__(self, cover_bg="cover_bg.jpg", page_bg="page_bg.jpg"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.cover_bg = cover_bg if os.path.exists(cover_bg) else None
        self.page_bg = page_bg if os.path.exists(page_bg) else None

    def header(self):
        bg = self.cover_bg if self.page_no() == 1 else self.page_bg
        if bg:
            self.image(bg, x=0, y=0, w=210, h=297)

    def footer(self):
        # page_bg.jpg tetap dipakai: teks "HALAMAN __ / PAGE __" sudah ada di gambar.
        # Nomor dicetak DI ATAS garis "__" tsb. Atur posisi/ukuran lewat konstanta PAGE_NUM_*.
        if self.page_no() > 1:
            self.set_font("Helvetica", PAGE_NUM_STYLE, PAGE_NUM_SIZE)
            self.set_text_color(*GOLD)
            s = str(self.page_no())
            w = self.get_string_width(s)
            for cx in PAGE_NUM_X:  # tengah tiap garis "__"
                self.text(cx - w / 2, PAGE_NUM_Y, s)


def clean_text(txt):
    if not txt:
        return ""
    txt = str(txt).replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    return txt.encode("latin-1", "replace").decode("latin-1")


def rupiah(n):
    return "Rp " + f"{int(n):,}".replace(",", ".")


def para(pdf, text, h=5, size=9, color=LIGHT, style=""):
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, h, clean_text(text), new_x="LMARGIN", new_y="NEXT")


def chapter(pdf, title):
    pdf.add_page()
    pdf.set_y(32)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*GOLD)
    # multi_cell agar judul panjang turun baris, tidak terpotong
    pdf.multi_cell(0, 7, clean_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y() + 1, 195, pdf.get_y() + 1)
    pdf.ln(5)


def add_image(pdf, data, x=20, w=170):
    if not data:
        return
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(data)
            path = tmp.name
        pdf.image(path, x=x, w=w)
        os.remove(path)
        pdf.ln(4)
    except Exception:
        pass


def table(pdf, head_color, cols, rows, aligns=None):
    """cols: [(judul, lebar)], rows: list of list."""
    aligns = aligns or ["L"] * len(cols)
    pdf.set_fill_color(*head_color)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 9)
    for (t, w), a in zip(cols, aligns):
        pdf.cell(w, 7, clean_text(" " + t), 1, 0, a, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*LIGHT)
    pdf.set_fill_color(30, 41, 59)
    for r in rows:
        for v, (t, w), a in zip(r, cols, aligns):
            pdf.cell(w, 6, clean_text(" " + str(v)), 1, 0, a, fill=True)
        pdf.ln()


def create_final_ebook_from_memory(data: dict) -> bytes:
    pdf = DiYosEbookPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_top_margin(32)
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    title = data.get("project_title", "PROYEK DIY").upper()
    info = data.get("info", {})

    # COVER: jika cover_bg.jpg sudah memuat teks "PANDUAN LENGKAP KREASI DIY",
    # cetak HANYA judul proyek agar tidak bertumpuk.
    pdf.add_page()
    if not pdf.cover_bg:
        pdf.set_fill_color(20, 24, 33)
        pdf.rect(0, 0, 210, 297, style="F")
        pdf.set_y(40)
        pdf.set_font("Helvetica", "B", 26)
        pdf.set_text_color(*GOLD)
        pdf.cell(0, 12, "DiYos", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(125)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*WHITE)
    pdf.multi_cell(0, 10, clean_text(title), align="C", new_x="LMARGIN", new_y="NEXT")
    if not pdf.cover_bg:
        pdf.ln(4)
        para(pdf, "PANDUAN LENGKAP KREASI DIY", 8, 13, GOLD, "B")

    # RINGKASAN PROYEK (baru): kesulitan, waktu, biaya, beban, keselamatan
    chapter(pdf, "RINGKASAN PROYEK")
    total = info.get("total_biaya", 0)
    rows = [
        ["Tingkat kesulitan", info.get("kesulitan", "-")],
        ["Estimasi waktu kerja", f"{info.get('waktu_jam', '-')} jam"],
        ["Estimasi total biaya", f"{rupiah(total)} (harga {info.get('tahun_harga', '')}, bisa berbeda per daerah)"],
        ["Batas beban (TV dll)", f"{info.get('beban_kg', '-')} kg"],
    ]
    for d in info.get("daya", []):
        rows.append([f"Daya {d['volt']}V", f"{d['watt']} W ({d['arus_A']} A), adaptor {d['adaptor']}, kabel min. {d['kabel']}"])
    table(pdf, (180, 120, 20), [("Info", 55), ("Keterangan", 125)], rows)
    pdf.ln(5)
    para(pdf, "Alat umum:", 6, 11, WHITE, "B")
    for a in info.get("alat_umum", []):
        para(pdf, f"- {a}")
    pdf.ln(3)
    para(pdf, "Keselamatan kerja:", 6, 11, WHITE, "B")
    for k in info.get("keselamatan", []):
        para(pdf, f"- {k}")

    # BAB 1
    chapter(pdf, f"BAB 1: MASTER BLUEPRINT - {title}")
    para(pdf, "Master Blueprint Visual", 7, 11, WHITE, "B")
    add_image(pdf, data.get("master_image_bytes"))

    specs = data.get("specs", {})
    bom, part_list = specs.get("bom", []), specs.get("part_list", [])

    # BAB 2
    if bom or data.get("bom_image_bytes"):
        chapter(pdf, "BAB 2: BILL OF MATERIALS (BOM)")
        add_image(pdf, data.get("bom_image_bytes"), x=25, w=160)
        rows = [[b["item"], b["qty"], b["satuan"], rupiah(b["harga_satuan"]), rupiah(b["subtotal"])] for b in bom]
        rows.append(["TOTAL", "", "", "", rupiah(sum(b["subtotal"] for b in bom))])
        table(pdf, (180, 120, 20),
              [("Item", 70), ("Qty", 15), ("Satuan", 20), ("Harga sat.", 35), ("Subtotal", 40)],
              rows, ["L", "C", "C", "R", "R"])

    # BAB 3
    if part_list or data.get("cutting_image_bytes"):
        chapter(pdf, "BAB 3: CUTTING LIST / PART DETAIL")
        add_image(pdf, data.get("cutting_image_bytes"), x=25, w=160)
        rows = [[p["nama_bagian"], p["dimensi_detail"], p["material"], p["qty"]] for p in part_list]
        table(pdf, (15, 118, 110),
              [("Nama Bagian", 50), ("Dimensi (P x L x T)", 55), ("Material", 55), ("Qty", 20)],
              rows, ["L", "L", "L", "C"])
        if info.get("finishing"):
            pdf.ln(4)
            para(pdf, f"Finishing: {info['finishing']}")

    # BAB 4
    steps = data.get("steps", [])
    for idx, st in enumerate(steps, 1):
        chapter(pdf, f"BAB 4: LANGKAH PERAKITAN ({idx}/{len(steps)})")
        para(pdf, st.get("title", f"Langkah {idx}"), 6, 11, WHITE, "B")
        pdf.ln(2)
        add_image(pdf, st.get("image_bytes"), x=25, w=150)
        para(pdf, "Alat yang digunakan:", 5, 9, WHITE, "B")
        for a in st.get("alat", []):
            para(pdf, f"- {a}")
        pdf.ln(2)
        para(pdf, "Detail instruksi:", 5, 9, WHITE, "B")
        for n, ins in enumerate(st.get("instruksi", []), 1):
            para(pdf, f"{n}. {ins}")
        pdf.ln(2)
        if st.get("cek_presisi"):
            para(pdf, "Cek presisi:", 5, 9, GOLD, "B")
            para(pdf, st["cek_presisi"])
        # Catatan: "Prompt AI" sengaja TIDAK dicetak ke PDF.

    return bytes(pdf.output())
