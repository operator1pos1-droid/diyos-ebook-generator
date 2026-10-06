import os, json, time
from google import genai
from google.genai import types, errors
from geometry import resolve_spec, render_layout_png

# Set model lewat env GEMINI_MODEL (pakai model Gemini yang aktif di akun Anda)
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
# Opsional: model cadangan bila model utama terus gagal (isi lewat Secrets)
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "")
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))


def _call(prompt: str, image: tuple | None = None) -> dict:
    """image = (bytes, mime_type), mis. (data, "image/jpeg"); None bila tanpa gambar."""
    contents = prompt
    if image:
        contents = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt]

    models = [MODEL] + ([FALLBACK_MODEL] if FALLBACK_MODEL else [])
    last_err = None
    for model in models:
        for i in range(4):
            try:
                r = client.models.generate_content(
                    model=model, contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.2))
                return json.loads(r.text)
            except errors.ServerError as e:      # 500/503: server Gemini sibuk
                last_err = e
            except errors.ClientError as e:      # 429 = kena batas kuota/rate limit
                if getattr(e, "code", None) != 429:
                    raise
                last_err = e
            if i < 3:
                time.sleep(2 ** i)               # jeda 1, 2, 4 detik
    raise last_err


SPEC_PROMPT = """Anda pakar manufaktur kayu & DIY. Buat SPESIFIKASI PARAMETRIK proyek ini.
PENTING: JANGAN menghitung sendiri. Tulis ukuran sebagai RUMUS dari params; Python yang menghitung.
Rumus hanya boleh angka, nama params, dan + - * / // ( ).
Balas JSON persis:
{"project_title":"",
 "params":{"W":0,"D":0,"H":0,"T":18,"LEG":0,"DOORS":0,"SIDE_H":"H-LEG-2*T"},
 "parts":[{"nama":"","p":"rumus","l":"rumus","t":"T","qty":"rumus/angka","bahan_id":"ply18",
           "material":"teks","tepi":["p","l"]}],
 "bom":[
   {"item":"Plywood 18mm 122x244","auto":"lembar","bahan_id":"ply18","lembar_mm":[2440,1220],"harga_satuan":0},
   {"item":"Edging PVC 22mm","auto":"edging","harga_satuan":0},
   {"item":"Engsel","qty":"rumus/angka","satuan":"pcs","harga_satuan":0}],
 "cek":[{"nama":"tinggi total","ekspresi":"rumus dari ukuran part","target":"H"}],
 "tingkat_kesulitan":"Pemula/Menengah/Mahir","estimasi_waktu_jam":0,"batas_beban_kg":0,
 "alat_umum":[""],"keselamatan":[""],"finishing":""}
Jenis bom 'auto' yang tersedia (Python yang menghitung qty-nya, jangan diisi):
 * "lembar": panel lembaran (plywood/MDF/HPL), parts ber-bahan_id sama dikelompokkan.
 * "batang": rangka balok/hollow/profil; parts ber-bahan_id sama dipotong dari batang 'batang_mm'.
   Panjang potongan = p. Jumlah batang rangka boleh pakai rumus, mis. qty "ceil(W/400)+1".
 * "panel_linear": panel plafon PVC/wall cladding: {"panjang":"rumus","lebar":"rumus","panel_mm":[200,4000]}.
 * "keliling": list/profil tepi: {"p":"rumus","l":"rumus","batang_mm":3000}.
 * "led": {"led_id":"L1","segmen":["rumus panjang tiap lurus"],"volt":12,"watt_per_m":14.4}; harga_satuan per meter.
 * "led_profil": {"led_id":"L1","batang_mm":2000} profil aluminium untuk LED tsb.
 * "adaptor": {"volt":12,"harga_per_watt":1500}; ukuran adaptor dihitung dari total beban.
 Komponen elektronik biasa (sensor, relay, kontroler) ditulis dengan qty rumus/angka dan boleh diberi
 "watt", "volt", "otomasi":true, atau "ac":true jika memakai listrik 220V.
 Sistem otomasi wajib punya kontroler/relay/dimmer/driver di bom. Semua ukuran DALAM mm.
Aturan:
- 'tepi' = sisi terlihat yang diberi edging: 'p' (sisi sepanjang p) atau 'l' (sepanjang l).
- Tiap panel wajib punya bahan_id; tiap bahan_id lembaran wajib punya 1 baris bom dengan auto='lembar'.
  Jumlah lembar dan panjang edging dihitung Python, jangan diisi.
- Isi 'cek' minimal untuk tinggi, lebar, dan kedalaman rakitan (jumlah ukuran part harus sama dengan target).
- Semua hardware yang dipakai (engsel, gagang, cam lock, sekrup, lem, kaki, dll) wajib ada di bom.
"""


def build_spec(user_input: str, tries: int = 3, image: tuple | None = None, dims_hint: str = ""):
    # Catatan tambahan bila ada gambar acuan
    note = ""
    if image:
        note = ("\nAcuan: gambar desain terlampir. Tiru bentuk, jumlah part, dan hardware yang TERLIHAT. "
                "Jangan mengarang bagian yang tidak terlihat. Ukuran dari gambar hanya perkiraan; "
                + (f"gunakan ukuran total ini sebagai patokan: {dims_hint}."
                   if dims_hint else
                   "tulis asumsi ukuran di params dan tandai sebagai perkiraan."))
    elif dims_hint:
        note = f"\nGunakan ukuran total ini sebagai patokan: {dims_hint}."

    project = user_input.strip() if user_input and user_input.strip() else "(lihat gambar terlampir)"

    feedback, last = "", None
    for _ in range(tries):
        try:
            raw = _call(f"{SPEC_PROMPT}\nProyek: {project}{note}\n{feedback}", image=image)
            res = resolve_spec(raw)
            last = (raw, res)
            if not res["warnings"]:
                return raw, res
            feedback = ("Spesifikasi sebelumnya bermasalah, perbaiki rumus/params/bom: "
                        + " | ".join(res["warnings"]))
        except (ValueError, KeyError, TypeError) as e:
            feedback = f"Spesifikasi sebelumnya error ({e}). Ikuti format persis."
    if last is None:
        raise RuntimeError("Gagal membuat spesifikasi: " + feedback)
    return last  # kembalikan hasil terakhir + peringatan agar tampil di UI


def generate_project_data(user_input: str, image: tuple | None = None, dims_hint: str = "") -> dict:
    raw, res = build_spec(user_input, image=image, dims_hint=dims_hint)
    title = raw.get("project_title") or user_input or "Proyek"
    env, parts, bom = res["env"], res["parts"], res["bom"]

    dims = "; ".join(f"{p['nama']} {p['p']}x{p['l']}x{p['t']} mm (x{p['qty']})" for p in parts)
    base = ("All labels in Bahasa Indonesia, LARGE readable font (phone-readable), no English text, "
            "clean white background, technical CAD style. Use EXACTLY these numbers: ")
    tot = " x ".join(f"{env[k]}" for k in ("W", "D", "H") if k in env)

    steps_raw = _call(
        "Susun 4-6 langkah perakitan berbahasa Indonesia untuk pemula. HANYA pakai nama part, angka, "
        "dan hardware dari data ini (dilarang mengubah atau menambah angka):\n"
        + json.dumps({"parts": parts, "bom": [{"item": b["item"], "qty": b["qty"]} for b in bom],
                      "params": env}, ensure_ascii=False)
        + '\nBalas JSON: {"steps":[{"title":"LANGKAH 1: ...","alat":[""],"instruksi":[""],"cek_presisi":""}]}'
    )["steps"]
    for i, st in enumerate(steps_raw, 1):
        st["ai_prompt"] = (f"{base}Step {i} assembly diagram for {title}: {st['title']}. "
                           f"Parts: {dims}.")

    part_list = [{"nama_bagian": p["nama"], "dimensi_detail": f"{p['p']} x {p['l']} x {p['t']} mm",
                  "material": p.get("material", ""), "qty": p["qty"]} for p in parts]
    return {
        "project_title": title,
        "master_prompt": f"{base}overall {tot} mm. 3D exploded isometric blueprint of {title}, numbered parts.",
        "bom_prompt": f"{base}flatlay of materials and hardware for {title}: "
                      + "; ".join(f"{b['item']} x{b['qty']}" for b in bom),
        "cutting_prompt": f"{base}part detail sheet for {title}: {dims}.",
        "specs": {"bom": bom, "part_list": part_list},
        "steps": steps_raw, "warnings": res["warnings"],
        # Diagram pola potong dibuat Python (skala nyata, angka pasti benar)
        "cutting_image_bytes": render_layout_png(res["layouts"]),
        "info": {
            "kesulitan": raw.get("tingkat_kesulitan", "-"),
            "waktu_jam": raw.get("estimasi_waktu_jam", "-"),
            "beban_kg": raw.get("batas_beban_kg", "-"),
            "total_biaya": sum(b["subtotal"] for b in bom),
            "alat_umum": raw.get("alat_umum", []),
            "keselamatan": raw.get("keselamatan", []) + res["extra_safety"],
            "daya": res["daya"],
            "finishing": raw.get("finishing", ""),
            "tahun_harga": 2026,
        },
    }
