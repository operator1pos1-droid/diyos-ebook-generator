"""Perhitungan ukuran deterministik: AI hanya memberi PARAMETER dan RUMUS,
semua aritmatika, packing lembaran, panjang edging, dan pengecekan dilakukan Python."""
import ast
import io
import math
import operator

_FUNCS = {"ceil": math.ceil, "floor": math.floor, "max": max, "min": min, "round": round}
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv}


def ev(expr, env):
    """Evaluasi rumus aman (hanya angka, nama parameter, + - * / //)."""
    if isinstance(expr, (int, float)):
        return expr

    def _e(n):
        if isinstance(n, ast.Expression):
            return _e(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise ValueError(f"parameter '{n.id}' tidak dikenal")
            return env[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](_e(n.left), _e(n.right))
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in _FUNCS and not n.keywords):
            return _FUNCS[n.func.id](*[_e(a) for a in n.args])
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -_e(n.operand)
        raise ValueError(f"rumus tidak diizinkan: {expr}")
    return _e(ast.parse(str(expr).strip(), mode="eval"))


def resolve_params(params):
    env, pending = {}, dict(params)
    for _ in range(len(pending) + 1):
        for k, v in list(pending.items()):
            try:
                env[k] = round(ev(v, env))
                del pending[k]
            except (ValueError, KeyError):
                pass
        if not pending:
            return env
    raise ValueError("parameter tak bisa dihitung: " + ", ".join(pending))


def hinges_per_door(door_h_mm):
    return 2 if door_h_mm <= 900 else 3 if door_h_mm <= 1600 else 4 if door_h_mm <= 2000 else 5


def pack(pieces, sheet=(2440, 1220), kerf=3):
    """Shelf packing (first-fit decreasing). pieces: [(nama, p, l)]. Rotasi diizinkan."""
    L, W = sheet
    items = []
    for n, a, b in pieces:
        long_, short = max(a, b), min(a, b)
        if long_ > L or short > W:
            raise ValueError(f"Panel {n} ({a}x{b}) tidak muat di lembaran {L}x{W}")
        items.append((n, long_, short))
    items.sort(key=lambda x: (-x[2], -x[1]))
    sheets = []
    for n, w, h in items:
        placed = False
        for s in sheets:
            for sh in s["shelves"]:
                if h <= sh["h"] and sh["x"] + w <= L:
                    s["parts"].append((sh["x"], sh["y"], w, h, n))
                    sh["x"] += w + kerf
                    placed = True
                    break
            if placed:
                break
            if s["y"] + h <= W:
                s["shelves"].append({"y": s["y"], "h": h, "x": w + kerf})
                s["parts"].append((0, s["y"], w, h, n))
                s["y"] += h + kerf
                placed = True
                break
        if not placed:
            sheets.append({"shelves": [{"y": 0, "h": h, "x": w + kerf}], "y": h + kerf,
                           "parts": [(0, 0, w, h, n)]})
    return sheets


def waste_pct(sheets, sheet=(2440, 1220)):
    used = sum(w * h for s in sheets for (_, _, w, h, _) in s["parts"])
    return round(100 * (1 - used / (len(sheets) * sheet[0] * sheet[1])), 1) if sheets else 0


def pack_1d(pieces, stock, kerf=3):
    """Potong batang 1D (first-fit decreasing). pieces: [(nama, panjang)]."""
    bars = []
    for n, l in sorted(pieces, key=lambda x: -x[1]):
        if l > stock:
            raise ValueError(f"Potongan {n} ({l} mm) lebih panjang dari batang {stock} mm")
        for b in bars:
            add = kerf if b["parts"] else 0
            if b["used"] + add + l <= stock:
                b["parts"].append((b["used"] + add, l, n))
                b["used"] += add + l
                break
        else:
            bars.append({"used": l, "parts": [(0, l, n)]})
    return bars


def waste_1d(bars, stock):
    return round(100 * (1 - sum(l for b in bars for (_, l, _) in b["parts"]) / (len(bars) * stock)), 1) if bars else 0


ADAPTOR_W = [24, 36, 60, 100, 150, 200, 300, 350, 400, 500]


def _pick_adaptor(watt):
    need = watt * 1.25  # cadangan 25%
    for w in ADAPTOR_W:
        if w >= need:
            return 1, w
    return math.ceil(need / ADAPTOR_W[-1]), ADAPTOR_W[-1]


def _kabel(amp):
    return "0.75 mm2" if amp <= 5 else "1.5 mm2" if amp <= 10 else "2.5 mm2" if amp <= 15 else None


def resolve_spec(spec):
    """Spec mentah (rumus) -> spec numerik + packing + daya + peringatan."""
    warns, extra_safety, daya = [], [], []
    env = resolve_params(spec["params"])
    parts = [{**p, "p": round(ev(p["p"], env)), "l": round(ev(p["l"], env)),
              "t": round(ev(p["t"], env)), "qty": round(ev(p["qty"], env))} for p in spec["parts"]]
    for c in spec.get("cek", []):
        a, b = round(ev(c["ekspresi"], env)), round(ev(c["target"], env))
        if a != b:
            warns.append(f"Cek '{c['nama']}' gagal: {a} mm != {b} mm.")

    layouts, bom, leds, loads = {}, [], {}, {}
    for b in spec["bom"]:
        b = dict(b)
        auto, key = b.get("auto"), b.get("bahan_id") or b.get("led_id") or b["item"]
        try:
            if auto == "lembar":
                sz = tuple(b.get("lembar_mm", [2440, 1220]))
                pcs = [(x["nama"], x["p"], x["l"]) for x in parts
                       for _ in range(x["qty"]) if x.get("bahan_id") == key]
                sheets = pack(pcs, sz)
                layouts[key] = {"kind": "sheet", "sheets": sheets, "size": sz, "item": b["item"]}
                b["qty"], b["satuan"] = len(sheets), "lembar"
                b["catatan"] = f"sisa ~{waste_pct(sheets, sz)}%"
            elif auto == "batang":  # rangka balok / hollow / profil
                st = b.get("batang_mm", 3000)
                pcs = [(x["nama"], x["p"]) for x in parts
                       for _ in range(x["qty"]) if x.get("bahan_id") == key]
                bars = pack_1d(pcs, st)
                layouts[key] = {"kind": "bar", "bars": bars, "stock": st, "item": b["item"]}
                b["qty"], b["satuan"] = len(bars), "batang"
                b["catatan"] = f"sisa ~{waste_1d(bars, st)}%"
            elif auto == "edging":
                m = sum(x["qty"] * (x["p"] if e == "p" else x["l"])
                        for x in parts for e in x.get("tepi", [])) / 1000
                b["qty"], b["satuan"] = math.ceil(m * 1.1), "meter"
            elif auto == "panel_linear":  # panel plafon PVC / lis / wall cladding
                P, Lw = round(ev(b["panjang"], env)), round(ev(b["lebar"], env))
                pw, pl = b["panel_mm"]
                rows, pcs = math.ceil(Lw / pw), []
                for r in range(rows):
                    full, rem = divmod(P, pl)
                    pcs += [(f"baris {r+1}", pl)] * full + ([(f"baris {r+1}", rem)] if rem else [])
                bars = pack_1d(pcs, pl, kerf=2)
                layouts[key] = {"kind": "bar", "bars": bars, "stock": pl, "item": b["item"]}
                b["qty"], b["satuan"] = len(bars), "batang panel"
                b["catatan"] = f"{rows} baris x {P} mm, sisa ~{waste_1d(bars, pl)}%"
            elif auto == "keliling":
                P, Lw = round(ev(b["p"], env)), round(ev(b["l"], env))
                b["qty"], b["satuan"] = math.ceil(2 * (P + Lw) / b.get("batang_mm", 3000) * 1.1), "batang"
            elif auto == "led":
                segs = [round(ev(x, env)) for x in b["segmen"]]
                total_m = sum(segs) / 1000
                volt = b.get("volt", 12)
                leds[key] = {"segs": segs, "volt": volt}
                b["qty"], b["satuan"] = math.ceil(total_m * 1.05 * 10) / 10, "meter"
                w = total_m * b.get("watt_per_m", 14.4)
                loads[volt] = loads.get(volt, 0) + w
                run_max = 5 if volt <= 12 else 10
                if total_m > run_max:
                    warns.append(f"LED {key}: {total_m:.1f} m > {run_max} m per jalur {volt}V, "
                                 f"wajib injeksi daya tiap {run_max} m (bagi jalur/kabel suplai).")
            elif auto == "led_profil":
                segs = leds.get(b.get("led_id"), {}).get("segs")
                if not segs:
                    raise ValueError(f"led_profil '{b['item']}' merujuk led_id yang tidak ada")
                st = b.get("batang_mm", 2000)
                pcs = []
                for i, s_ in enumerate(segs):  # segmen lebih panjang dari batang -> disambung
                    full, rem = divmod(s_, st)
                    pcs += [(f"seg {i+1}", st)] * full + ([(f"seg {i+1}", rem)] if rem else [])
                bars = pack_1d(pcs, st)
                layouts[key + "_profil"] = {"kind": "bar", "bars": bars, "stock": st, "item": b["item"]}
                b["qty"], b["satuan"] = len(bars), "batang"
            elif auto == "adaptor":
                b["qty"] = None  # dihitung setelah semua beban diketahui
            else:
                b["qty"] = round(ev(b["qty"], env))
        except ValueError as e:
            warns.append(str(e))
            b["qty"] = b.get("qty") or 0
        if b.get("watt") and b["qty"] is not None:  # komponen elektronik lain (sensor, relay, dll)
            loads[b.get("volt", 12)] = loads.get(b.get("volt", 12), 0) + b["watt"] * b["qty"]
        bom.append(b)

    # adaptor / power supply per level tegangan
    for b in bom:
        if b.get("auto") == "adaptor":
            volt = b.get("volt", 12)
            watt = loads.get(volt, 0)
            n, size = _pick_adaptor(watt)
            b["qty"], b["satuan"] = n, "unit"
            b["item"] = f"{b['item']} {size}W ({volt}V)"
            b["harga_satuan"] = size * b.get("harga_per_watt", 1500)
            amp = watt / volt
            k = _kabel(amp)
            daya.append({"volt": volt, "watt": round(watt, 1), "arus_A": round(amp, 1),
                         "adaptor": f"{n} x {size}W", "kabel": k or "lebih dari 2.5 mm2 (bagi jalur)"})
    for b in bom:
        b["subtotal"] = round((b["qty"] or 0) * b["harga_satuan"])

    low = [b["item"].lower() for b in bom]
    if any(b.get("otomasi") for b in bom) and not any(
            k in t for t in low for k in ("kontroler", "controller", "esp32", "relay", "dimmer", "driver")):
        warns.append("Ada komponen otomasi tapi kontroler/relay/dimmer/driver belum ada di BOM.")
    if loads and not any(b.get("auto") == "adaptor" for b in bom):
        warns.append("Ada beban listrik DC tapi adaptor/power supply belum ada di BOM.")
    if any(b.get("ac") for b in bom):
        extra_safety.append("Instalasi listrik AC 220V wajib dikerjakan teknisi listrik berkompeten, "
                            "dengan MCB/ELCB. Matikan listrik dari MCB sebelum bekerja.")
    if loads:
        extra_safety.append("Wiring DC: pakai kabel sesuai arus, sambungan disolder/terminal (jangan dililit), "
                            "beri sekring, dan sisakan ventilasi untuk adaptor.")

    doors = [x for x in parts if "pintu" in x["nama"].lower()]
    n_doors = sum(x["qty"] for x in doors)
    if doors:
        need = n_doors * hinges_per_door(max(x["p"] for x in doors))
        have = sum(b["qty"] for b in bom if "engsel" in b["item"].lower())
        if have < need:
            warns.append(f"Engsel {have} kurang, butuh minimal {need} untuk {n_doors} pintu.")
        if not any("gagang" in t for t in low):
            warns.append("Pintu ada tapi gagang tidak masuk BOM.")
    if not any("lem" in t for t in low):
        warns.append("Lem kayu belum masuk BOM.")
    return {"env": env, "parts": parts, "bom": bom, "layouts": layouts, "daya": daya,
            "extra_safety": extra_safety, "warnings": warns}


def render_layout_png(layouts):
    """Diagram pola potong presisi (skala nyata): lembaran 2D dan batang 1D."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    sheets = [(lay["item"], s, lay["size"]) for lay in layouts.values()
              if lay["kind"] == "sheet" for s in lay["sheets"]]
    bars = [lay for lay in layouts.values() if lay["kind"] == "bar" and lay["bars"]]
    if not sheets and not bars:
        return None
    rows = len(sheets) + len(bars)
    heights = [3.6] * len(sheets) + [max(1.6, 0.42 * len(b["bars"]) + 0.9) for b in bars]
    fig, axes = plt.subplots(rows, 1, figsize=(9, sum(heights)), squeeze=False,
                             gridspec_kw={"height_ratios": heights})
    axes = list(axes[:, 0])
    for ax, (item, s, (L, W)) in zip(axes, sheets):
        ax.add_patch(Rectangle((0, 0), L, W, fill=False, lw=2))
        for x, y, w, h, n in s["parts"]:
            ax.add_patch(Rectangle((x, y), w, h, fc="#f3d9a4", ec="#7a5200"))
            ax.text(x + w / 2, y + h / 2, f"{n}\n{w}x{h}", ha="center", va="center",
                    fontsize=9 if w > 500 and h > 200 else 7)
        ax.set_xlim(-30, L + 30); ax.set_ylim(-30, W + 30); ax.set_aspect("equal")
        ax.set_title(f"{item} - lembar {L}x{W} mm (mm)", fontsize=10); ax.axis("off")
    for ax, lay in zip(axes[len(sheets):], bars):
        st = lay["stock"]
        for i, b in enumerate(lay["bars"]):
            ax.add_patch(Rectangle((0, -i), st, 0.8, fill=False, lw=1.5))
            for x, l, n in b["parts"]:
                ax.add_patch(Rectangle((x, -i), l, 0.8, fc="#cfe3f5", ec="#1f4e79"))
                if l > st * 0.06:
                    ax.text(x + l / 2, -i + 0.4, f"{l}", ha="center", va="center", fontsize=7)
        ax.set_xlim(-st * 0.01, st * 1.01); ax.set_ylim(-len(lay["bars"]) + 0.5, 1)
        ax.set_title(f"{lay['item']} - batang {st} mm (mm)", fontsize=10); ax.axis("off")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()
