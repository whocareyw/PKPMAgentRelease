# -*- coding: utf-8 -*-
"""在 SAP2000 中生成 JGJ 7-2010 六种常用单层球面网壳之一（肋环型/肋环斜杆型/三向格子型/
联方型/凯威特型/短程线型）。连接已运行的 SAP2000 实例（无实例才启动新实例）；当前模型为
空模型时新建空白模型并设为 N_mm_C，否则在既有模型中追加并按其单位制自动换算。杆件为
Frame 对象（SAP2000 框架默认刚接，符合单层网壳刚接节点要求），圆钢管 Pipe 截面，
材料 STEEL_SHELL（E=206000MPa）。可选在底环节点设三向平动固定铰支座。自动保存。
几何生成见 geometry.py（纯数学模块，与 PKPM 版插件同源）。"""

# ── 参数（界面运行时由 PKPM Agent 传入；直接运行本文件时用下方默认值）──
import argparse

_TYPES = ["肋环型", "肋环斜杆型", "三向格子型", "联方型", "凯威特型", "短程线型"]

_p = argparse.ArgumentParser(description="在 SAP2000 中生成单层球面网壳（JGJ7-2010 六种常用形式）")
_p.add_argument("--shell_type", type=str, default="凯威特型", choices=_TYPES, help="网壳类型")
_p.add_argument("--D",         type=float, default=60,  help="跨度，m")
_p.add_argument("--f",         type=float, default=15,  help="矢高，m")
_p.add_argument("--z_base",    type=float, default=0,   help="底环标高，m")
_p.add_argument("--n_sec",     type=int,   default=8,   help="扇区数K，无量纲（肋环/肋环斜杆/凯威特用）")
_p.add_argument("--n_ring",    type=int,   default=8,   help="径向环带数，无量纲（肋环/肋环斜杆/凯威特用）")
_p.add_argument("--n_div",     type=int,   default=12,  help="细分密度，无量纲（三向/联方=直径向分割数；短程线=细分次数）")
_p.add_argument("--diameter",  type=int,   default=180, help="钢管外径，mm")
_p.add_argument("--thickness", type=int,   default=6,   help="钢管壁厚，mm")
_p.add_argument("--supports",  action=argparse.BooleanOptionalAction, default=True,
                help="底环节点设三向平动固定铰支座")
_a = _p.parse_args()

SHELL = _a.shell_type
D, F, Z_BASE = _a.D, _a.f, _a.z_base
N_SEC, N_RING, N_DIV = _a.n_sec, _a.n_ring, _a.n_div
DIA, TH = _a.diameter, _a.thickness
SUPPORTS = _a.supports

import math
import os
import sys
import time

# ── 写死量：实现手段，与用户决策无关，不做成参数 ──
UNIT = 1000.0                 # m -> mm
MAT_NAME = "STEEL_SHELL"      # 网壳钢材名（E=206000MPa，不依赖材料库）
E_STEEL, NU_STEEL, AL_STEEL = 206000.0, 0.3, 1.17e-5
# eUnits 码 -> 长度单位相对 mm 的换算系数（输入值 = mm 值 * 系数）
LEN_FACTOR = {1: 1 / 25.4, 2: 1 / 304.8, 3: 1 / 25.4, 4: 1 / 304.8,
              5: 1.0, 7: 1.0, 9: 1.0, 11: 1.0,
              6: 1e-3, 8: 1e-3, 10: 1e-3, 12: 1e-3,
              13: 0.1, 14: 0.1, 15: 0.1, 16: 0.1}
UNIT_NAME = {1: "lb_in_F", 2: "lb_ft_F", 3: "kip_in_F", 4: "kip_ft_F", 5: "kN_mm_C",
             6: "kN_m_C", 7: "kgf_mm_C", 8: "kgf_m_C", 9: "N_mm_C", 10: "N_m_C",
             11: "Ton_mm_C", 12: "Ton_m_C", 13: "kN_cm_C", 14: "kgf_cm_C",
             15: "N_cm_C", 16: "Ton_cm_C"}

# ── 1. 参数校验 ──
if D <= 0 or F <= 0:
    print(f"❌ 跨度与矢高必须为正数（D={D}, f={F}），未执行。")
    sys.exit(1)
if F > D / 2 + 1e-9:
    print(f"❌ 球面网壳要求矢高不大于半跨（f={F} > D/2={D / 2}），未执行。")
    sys.exit(1)
# 球面半径是与 D、f 联动的导出量（R=(D²/4+f²)/2f，恒有 R ≥ D/2），不作为表单参数
R = (D * D / 4 + F * F) / (2 * F)

RING_TYPES = ("肋环型", "肋环斜杆型", "凯威特型")
if SHELL in RING_TYPES:
    if N_SEC < 3 or N_RING < 1:
        print(f"❌ {SHELL}要求扇区数K≥3、径向环带数≥1（K={N_SEC}, 环带={N_RING}），未执行。")
        sys.exit(1)
    unused = "细分密度"
else:
    if N_DIV < 4:
        print(f"❌ {SHELL}要求细分密度≥4（n={N_DIV}；三向/联方为直径向分割数，短程线为细分次数），未执行。")
        sys.exit(1)
    unused = "扇区数K、径向环带数"
if SHELL == "肋环斜杆型" and N_SEC % 2 == 1:
    print(f"⚠️ 肋环斜杆型扇区数K={N_SEC} 为奇数：斜杆锯齿排布在合拢处两格同向，对称性稍差，建议K取偶数。")
if SHELL == "短程线型":
    # 球冠半顶角内须容纳二十面体细分首环节点（首环纬度≈63.43°/ν），否则壳面退化为单点
    phi_max_deg = math.degrees(math.asin(min(1.0, (D / 2) / R)))
    nu_min = 63.4349 / phi_max_deg
    if N_DIV <= nu_min:
        print(f"❌ 短程线型在当前矢跨比下要求细分次数 ν > {nu_min:.1f}（当前 n={N_DIV}），"
              f"否则球冠内仅含顶点、无法成壳。请增大矢高、减小跨度或改选其它类型。未执行。")
        sys.exit(1)

D_m, F_m, R_m = D * UNIT, F * UNIT, R * UNIT
base_m = Z_BASE * UNIT
TAG = time.strftime("%m%d%H%M%S")     # 运行标识：保证多次运行时 SAP2000 用户名不重名

# ── 2. 连接 SAP2000（优先已运行实例；GetObject 无实例时返回 None 而非抛异常）──
import comtypes.client
comtypes.CoInitialize()
helper = comtypes.client.CreateObject('SAP2000v1.Helper')
helper = helper.QueryInterface(comtypes.gen.SAP2000v1.cHelper)
sap = helper.GetObject("CSI.SAP2000.API.SapObject")
if sap is None:
    sap = helper.CreateObjectProgID("CSI.SAP2000.API.SapObject")
    sap.ApplicationStart()
    print("未检测到运行中的 SAP2000，已启动新实例。")
SapModel = sap.SapModel

def rc_of(r):
    """COM 调用返回元组/列表末位才是状态码；无 ByRef 出参时返回值即状态码。"""
    return r[-1] if isinstance(r, (tuple, list)) else r

# ── 3. 新模型/既有模型判定与单位制 ──
fname = SapModel.GetModelFilename(True)
n_pts0 = SapModel.PointObj.Count()
n_frm0 = SapModel.FrameObj.Count()
if (not fname or str(fname) == "(Untitled)") and n_pts0 == 0 and n_frm0 == 0:
    SapModel.InitializeNewModel()
    SapModel.File.NewBlank()
    SapModel.SetPresentUnits(9)                    # 新模型统一 N_mm_C（须在新建之后设置）
    new_model = True
else:
    new_model = False                              # 既有模型：追加构件，跟随其单位制
u = SapModel.GetPresentUnits()
LF = LEN_FACTOR.get(u)
if LF is None:
    print(f"❌ 当前模型单位制代码 {u} 不在支持范围，未执行。")
    sys.exit(1)
print(f"模型：{'新建空白模型（N_mm_C）' if new_model else '在既有模型中追加'}，"
      f"单位制 {UNIT_NAME[u]}（长度换算系数 {LF:g}），原有 {n_pts0} 节点 / {n_frm0} 框架。")

# ── 3.5 删除上次运行的建模内容（重新生成前先删旧，避免同坐标节点合并/重杆报错）──
old_frames = [n for n in SapModel.FrameObj.GetNameList(0, [])[1] if n.startswith("SRM")]
for n in old_frames:
    SapModel.FrameObj.Delete(n)
old_points = [n for n in SapModel.PointObj.GetNameList(0, [])[1] if n.startswith("SRN")]
del_pts = 0
for n in old_points:
    if rc_of(SapModel.PointObj.DeleteSpecialPoint(n)) == 0:
        del_pts += 1
if old_frames or old_points:
    kept = len(old_points) - del_pts
    print(f"已删除上次运行建模内容：杆件 {len(old_frames)} 根 / 节点 {del_pts} 个"
          + (f"（{kept} 个节点因连接其它构件保留）" if kept else "。"))

# ── 4. 几何计算：按类型生成球面网壳（底环锚固于 z_base）──
from geometry import build_shell
z_c = base_m - math.sqrt(R_m ** 2 - (D_m / 2) ** 2)   # 球心绝对标高
geo = build_shell(SHELL, R_m, z_c, D_m, N_SEC, N_RING, N_DIV, base_m)
nodes, members, boundary = geo["nodes"], geo["members"], geo["boundary"]
lens = [math.dist(nodes[i0], nodes[i1]) for (i0, i1) in members]
z_top = max(n[2] for n in nodes)
print(f"几何生成（{SHELL}）：{len(nodes)} 节点 / {len(members)} 杆件（{geo['descr']}），"
      f"杆长 {min(lens):.0f}~{max(lens):.0f} mm")
print(f"球面：R={R_m:.0f} mm，顶点标高 {z_top:.0f} mm（实际矢高 {(z_top - base_m) / UNIT:.3f} m），"
      f"底环 {len(boundary)} 节点（标高 {base_m:.0f} mm、半径 {D_m / 2:.0f} mm）")
print(f"提示：{SHELL}不使用参数 {unused}，表单取值被忽略。")

# ── 5. 材料与截面 ──
rc = rc_of(SapModel.PropMaterial.SetMaterial(MAT_NAME, 1))          # 1 = Steel
rc = rc_of(SapModel.PropMaterial.SetMPIsotropic(MAT_NAME, E_STEEL, NU_STEEL, AL_STEEL))
if rc != 0:
    print(f"❌ 钢材材料定义失败（rc={rc}），未执行。")
    sys.exit(1)
SEC_NAME = f"PIPE{DIA}x{TH}"
rc = SapModel.PropFrame.SetPipe(SEC_NAME, MAT_NAME, DIA * LF, TH * LF)
if rc != 0:
    print(f"❌ 圆钢管截面 {SEC_NAME} 定义失败（rc={rc}），未执行。")
    sys.exit(1)
print(f"材料 {MAT_NAME}（E={E_STEEL:.0f}MPa）/ 截面 {SEC_NAME}（Φ{DIA}x{TH}）已定义。")

# ── 6. 节点与杆件 ──
pnames = []
for i, (x, y, z) in enumerate(nodes):
    res = SapModel.PointObj.AddCartesian(x * LF, y * LF, z * LF, ' ', f"SRN{TAG}_{i}")
    if isinstance(res, (tuple, list)):
        name, rc = res[0], res[-1]
    else:
        name, rc = f"SRN{TAG}_{i}", res
    if rc != 0:
        print(f"❌ 节点 {i} 创建失败（rc={rc}），未执行。")
        sys.exit(1)
    pnames.append(name)

fail = 0
for k, (i0, i1) in enumerate(members):
    rc = rc_of(SapModel.FrameObj.AddByPoint(pnames[i0], pnames[i1], ' ', SEC_NAME, f"SRM{TAG}_{k}"))
    if rc != 0:
        fail += 1
if fail:
    print(f"❌ {fail} 根杆件创建失败，请检查模型状态。")
    sys.exit(1)
print(f"杆件：{len(members)} 根 Frame（{SEC_NAME}，默认刚接）。")

# ── 7. 底环支座（三向平动固定铰）──
if SUPPORTS:
    fail = 0
    for i in boundary:
        rc = rc_of(SapModel.PointObj.SetRestraint(pnames[i],
                                                  [True, True, True, False, False, False]))
        if rc != 0:
            fail += 1
    print(f"支座：底环 {len(boundary)} 节点设三向平动固定铰（UX/UY/UZ），失败 {fail} 个。"
          if not fail else f"⚠️ 支座设置失败 {fail} 个。")
else:
    print("支座：按参数要求未设置，请自行在 SAP2000 中添加。")

# ── 8. 刷新视图与保存 ──
try:
    SapModel.View.RefreshView(0, False)
except Exception:
    pass
if new_model or not fname or str(fname) == "(Untitled)":
    outdir = os.path.join(os.getcwd(), "SAP2000球面网壳")
    os.makedirs(outdir, exist_ok=True)
    save_path = os.path.join(outdir, f"{SHELL}_D{D:g}_f{F:g}.sdb")
    rc = SapModel.File.Save(save_path)
else:
    save_path = str(fname)
    rc = SapModel.File.Save()
print(f"保存模型：{save_path}（rc={rc}）")

print(f"\n✅ {SHELL}球面网壳已在 SAP2000 中生成：D={D:g}m, f={F:g}m, R={R:.2f}m，底环标高 {Z_BASE:g}m，"
      f"{len(nodes)} 节点 / {len(members)} 杆件，截面 {SEC_NAME}，"
      f"{'含' if SUPPORTS else '不含'}底环支座。")
print("⚠️ 本插件不运行分析；如需计算请在 SAP2000 中自行定义工况并运行。"
      "每次运行已自动先删除上次运行的建模内容（SRM*/SRN* 命名的杆件与节点）。")
