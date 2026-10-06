import io
import streamlit as st
from PIL import Image, ImageOps
from pwa_setup import inject_pwa
from app import create_final_ebook_from_memory
from llm_engine import generate_project_data

st.set_page_config(page_title="Generator Ebook Manufaktur", page_icon="🔨", layout="wide")

inject_pwa()

st.title("🔨 Generator Ebook Manufaktur")
st.caption("Sistem penyusun buku panduan otomatis berstandar cetak A4.")

def render_markdown_table(data_list):
    if not data_list or not isinstance(data_list, list):
        return "Tidak ada data."
    headers = list(data_list[0].keys())
    header_titles = [h.replace("_", " ").title() for h in headers]
    md = "| " + " | ".join(header_titles) + " |\n"
    md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for row in data_list:
        values = [str(row.get(h, "")) for h in headers]
        md += "| " + " | ".join(values) + " |\n"
    return md

def prepare_image(file, max_side=1600):
    """Perkecil & normalkan gambar acuan agar cepat dikirim ke Gemini."""
    img = Image.open(file)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue(), "image/jpeg"

# TAHAP 1: INPUT REFERENSI PROYEK
st.header("1. Input Referensi Proyek")
input_url = st.text_input("Masukkan Link YouTube / Web / Deskripsi Singkat Proyek:", placeholder="Contoh: Sofa Bed Minimalis Modern Kayu Jati")

ref_img_file = st.file_uploader(
    "🖼️ Atau unggah gambar desain jadi sebagai acuan (opsional):",
    type=["png", "jpg", "jpeg", "webp"], key="ref_img_upload")
dims_hint = st.text_input(
    "Ukuran total (opsional, mm):", placeholder="Contoh: 1800 x 900 x 750 (L x D x T)")
if ref_img_file:
    st.image(ref_img_file, caption="Gambar desain acuan", use_container_width=True)

if st.button("🚀 Proses & Susun Instruksi Otomatis"):
    if not input_url and not ref_img_file:
        st.warning("Silakan masukkan link/deskripsi proyek atau unggah gambar desain terlebih dahulu!")
    else:
        with st.spinner("Mesin sedang menganalisis material, BOM, dan menyusun instruksi via Gemini AI..."):
            try:
                image = prepare_image(ref_img_file) if ref_img_file else None
                st.session_state["project_data"] = generate_project_data(
                    input_url, image=image, dims_hint=dims_hint)
            except Exception:
                st.error("Server AI sedang sibuk atau melebihi kuota. Coba lagi beberapa saat lagi.")
                st.stop()
            if "pdf_bytes" in st.session_state:
                del st.session_state["pdf_bytes"]
            st.success("Instruksi & Prompt AI Berhasil Disusun!")

# TAHAP 2: TAMPILKAN HASIL, UPLOAD GAMBAR & CETAK PDF
if "project_data" in st.session_state:
    data = st.session_state["project_data"]
    title = data.get('project_title', 'Proyek DIY')
    
    st.divider()
    st.header(f"📌 {title.upper()}")
    for w in data.get("warnings", []):
        st.warning(f"Periksa: {w}")
    
    # ----------------------------------------------------
    # 1. MASTER BLUEPRINT
    # ----------------------------------------------------
    st.markdown("### 🎨 Bab 1: Master Blueprint")
    st.caption("Prompt AI Master Blueprint:")
    st.code(data.get("master_prompt", f"Master technical blueprint of {title}, 3D isometric view, CAD drawing style, clean background."), language="text")
    master_img_file = st.file_uploader("🖼️ Upload Foto Master Blueprint:", type=["png", "jpg", "jpeg"], key="master_img_upload")
    if master_img_file:
        data["master_image_bytes"] = master_img_file.getvalue()
        st.image(master_img_file, caption="Pratinjau Master Blueprint", use_container_width=True)
    
    st.divider()

    # ----------------------------------------------------
    # 2. BILL OF MATERIALS (BOM)
    # ----------------------------------------------------
    st.markdown("### 📋 Bab 2: Bill of Materials (BOM)")
    if "bom" in data.get("specs", {}):
        st.markdown(render_markdown_table(data["specs"]["bom"]))
        st.markdown(f"**Estimasi total: Rp {data['info']['total_biaya']:,}**".replace(",", "."))
    
    # Prompt AI & Upload Gambar BOM
    bom_default_prompt = f"Technical layout diagram of raw materials, wood boards, hardware, and components for {title}, organized flatlay style, clean white background, architectural CAD drawing."
    st.caption("💡 Prompt AI Gambar Visual BOM:")
    st.code(data.get("bom_prompt") or bom_default_prompt, language="text")
    
    bom_img_file = st.file_uploader("🖼️ Upload Gambar Visual BOM (Hasil AI):", type=["png", "jpg", "jpeg"], key="bom_img_upload")
    if bom_img_file:
        data["bom_image_bytes"] = bom_img_file.getvalue()
        st.image(bom_img_file, caption="Pratinjau Visual BOM", use_container_width=True)
            
    st.divider()

    # ----------------------------------------------------
    # 3. CUTTING LIST
    # ----------------------------------------------------
    st.markdown("### 📐 Bab 3: Cutting List / Part Detail")
    if "part_list" in data.get("specs", {}):
        st.markdown(render_markdown_table(data["specs"]["part_list"]))
        
    # Prompt AI & Upload Gambar Cutting List
    cutting_default_prompt = f"Technical cutting list diagram blueprint showing detailed dimensions, cut plan breakdown for {title}, clean architectural style, white background."
    st.caption("💡 Prompt AI Gambar Visual Cutting List:")
    st.code(data.get("cutting_prompt") or cutting_default_prompt, language="text")
    
    if data.get("cutting_image_bytes"):
        st.image(data["cutting_image_bytes"], caption="Diagram pola potong otomatis (skala nyata, dibuat Python). Tidak perlu upload gambar AI.", use_container_width=True)
    cutting_img_file = st.file_uploader("🖼️ Upload Gambar Visual Cutting List (Hasil AI):", type=["png", "jpg", "jpeg"], key="cutting_img_upload")
    if cutting_img_file:
        data["cutting_image_bytes"] = cutting_img_file.getvalue()
        st.image(cutting_img_file, caption="Pratinjau Visual Cutting List", use_container_width=True)
            
    st.divider()

    # ----------------------------------------------------
    # 4. LANGKAH PERAKITAN
    # ----------------------------------------------------
    st.markdown("### 🛠️ Bab 4: Langkah-Langkah Perakitan")
    for i, step in enumerate(data.get("steps", [])):
        with st.expander(f"{step.get('title', f'Langkah {i+1}')}"):
            st.markdown("**Alat:** " + ", ".join(step.get("alat", [])))
            for n, ins in enumerate(step.get("instruksi", []), 1):
                st.write(f"{n}. {ins}")
            st.info("Cek presisi: " + step.get("cek_presisi", "-"))
            st.caption("Prompt AI Gambar Langkah Ini:")
            st.code(step.get("ai_prompt", ""), language="text")
            
            step_img_file = st.file_uploader(f"🖼️ Upload Foto {step.get('title')}:", type=["png", "jpg", "jpeg"], key=f"step_img_{i}")
            if step_img_file:
                step["image_bytes"] = step_img_file.getvalue()
                st.image(step_img_file, caption=f"Pratinjau {step.get('title')}", use_container_width=True)
            
    st.divider()

    # ----------------------------------------------------
    # CETAK PDF
    # ----------------------------------------------------
    st.header("2. Cetak Ebook PDF")
    
    if st.button("⚙️ Susun & Buat File PDF Ebook"):
        with st.spinner("Memproses pembuatan PDF A4..."):
            st.session_state["pdf_bytes"] = create_final_ebook_from_memory(data)
            st.success("File PDF Ebook Berhasil Dibuat!")
    
    if "pdf_bytes" in st.session_state:
        st.download_button(
            label="📥 UNDUH EBOOK PDF SEKARANG",
            data=st.session_state["pdf_bytes"],
            file_name=f"Blueprint_{title}.pdf",
            mime="application/pdf",
            key="download_pdf_button"
        )
