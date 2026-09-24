# -*- coding: utf-8 -*-
"""在 PKPM 中生成 JGJ 7-2010 六种常用单层球面网壳之一（肋环型/肋环斜杆型/三向格子型/
联方型/凯威特型/短程线型）。总是新建标准层生成：已有构件不受影响，底环支承于新层
层底（空白工程即 z=0）。球面半径 R 由跨度/矢高自动导出，几何生成见 geometry.py。"""

# ── 参数（界面运行时由 PKPM Agent 传入；直接运行本文件时用下方默认值）──
import argparse

_TYPES = ["肋环型", "肋环斜杆型", "三向格子型", "联方型", "凯威特型", "短程线型"]

_p = argparse.ArgumentParser(description="生成单层球面网壳（JGJ7-2010 六种常用形式，新建标准层）")
_p.add_argument("--shell_type", type=str, default="凯威特型", choices=_TYPES, help="网壳类型")
_p.add_argument("--D",         type=float, default=60,  help="跨度，m")
_p.add_argument("--f",         type=float, default=15,  help="矢高，m")
_p.add_argument("--n_sec",     type=int,   default=8,   help="扇区数K，无量纲（肋环/肋环斜杆/凯威特用）")
_p.add_argument("--n_ring",    type=int,   default=8,   help="径向环带数，无量纲（肋环/肋环斜杆/凯威特用）")
_p.add_argument("--n_div",     type=int,   default=12,  help="细分密度，无量纲（三向/联方=直径向分割数；短程线=细分次数）")
_p.add_argument("--diameter",  type=int,   default=180, help="钢管外径，mm")
_p.add_argument("--thickness", type=int,   default=6,   help="钢管壁厚，mm")
_a = _p.parse_args()

SHELL = _a.shell_type
D, F = _a.D, _a.f                    # m（球面半径 R 为导出量，见下）
N_SEC, N_RING, N_DIV = _a.n_sec, _a.n_ring, _a.n_div
DIA, TH = _a.diameter, _a.thickness  # mm

import math
import sys

# ── 写死量：实现手段，与用户决策无关，不做成参数 ──
UNIT = 1000.0          # m -> mm
STUB_LEN = 500.0       # 临时定位柱长度，mm
STUB_D, STUB_T = 89, 4 # 临时定位柱截面 Φ89x4
BTMP_DROP = 1000.0     # 建模期间网壳层底边界的临时下移量，mm

# ── 1. 参数校验 ──
if D <= 0 or F <= 0:
    print(f"❌ 跨度与矢高必须为正数（D={D}, f={F}），未执行。")
    sys.exit(1)
if F > D / 2 + 1e-9:
    print(f"❌ 球面网壳要求矢高不大于半跨（f={F} > D/2={D / 2}），未执行。")
    sys.exit(1)
# 球面半径是与 D、f 联动的导出量（R=(D²/4+f²)/2f，恒有 R ≥ D/2），不作为表单参数
# 放开，始终按 D、f 计算取值，杜绝误填半径破坏几何自洽
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

D_m, F_m, R_m = D * UNIT, F * UNIT, R * UNIT   # mm

# ── 2. 连接 PKPM（服务可能瞬时未就绪，自动重试 3 次）──
import time
conn = connect_to_server("pkpmmcp")
for _attempt in range(3):
    if conn is True:
        break
    print(f"连接未就绪（第 {_attempt + 1}/3 次重试前等待）：{conn}")
    time.sleep(3)
    conn = connect_to_server("pkpmmcp")
if conn is not True:
    print(f"❌ 连接 PKPM 失败：{conn}")
    print("   排查建议：① 确认 PKPM 已打开工程、未停留在弹窗上；"
          "② 若 PKPM 已长时间运行，其内置服务可能失去响应——请先保存工程并重启 PKPM，再重新运行本插件。")
    sys.exit(1)

# ── 3. 新建标准层方案：读组装表 → 定新层号与底环标高 → 建空层 ──
# 不再要求空白工程：网壳总是生成到新建标准层，与已有构件互不影响
tbl = GetFloorAssemTable()
std_flrs = [int(s) for s in (tbl.get("StdFlr") or [])]
tops = [float(h) for h in (tbl.get("FlrTopH") or [])]
btms = [float(h) for h in (tbl.get("FlrBtmH") or [])]

# 探测实际存在的标准层总数（可能含未组装的层）：GetStandFloorParams 对不存在的层
# 返回 {"错误": ...} 而不抛异常，可作为存在性探测器
n_exist = len(std_flrs)
while n_exist < 64:
    if "错误" in GetStandFloorParams(n_exist + 1):
        break
    n_exist += 1
N = n_exist + 1                                  # 新层号 = 已有最大层号 + 1
base = max(tops) if tops else (btms[0] if btms else 0.0)   # 新层层底 = 既有组装顶部
btm0 = btms[0] if btms else 0.0                  # 全楼底标高

print(f"现状：标准层 1..{n_exist}（组装 {len(std_flrs)} 层），建筑顶部标高 {base:.0f} mm")
print(f"网壳将生成到新建标准层 {N}：层底/底边界名义标高 {base:.0f} mm，层顶 {base + F_m:.0f} mm")

if "错误" in GetStandFloorParams(N):
    print(f"新建标准层 {N}:", CreateOrModifyStandFloor(StdFlr=N))

# ── 4. 几何计算：按类型生成球面网壳（底环锚固于 base）──
# 球心 (0,0,z_c)；geometry.py 为纯几何模块（无 PKPM 依赖），可脱离 PKPM 单独测试
z_c = base - math.sqrt(R_m ** 2 - (D_m / 2) ** 2)    # 球心绝对标高（底环 z=base）

from geometry import build_shell

geo = build_shell(SHELL, R_m, z_c, D_m, N_SEC, N_RING, N_DIV, base)
nodes, members, boundary = geo["nodes"], geo["members"], geo["boundary"]

lines = []
for (i0, i1) in members:
    p0, p1 = nodes[i0], nodes[i1]
    lines.append(Line3D(P0=Point3D(x=p0[0], y=p0[1], z=p0[2]),
                        P1=Point3D(x=p1[0], y=p1[1], z=p1[2])))

lens = [math.dist(nodes[i0], nodes[i1]) for (i0, i1) in members]
b_z = [nodes[i][2] for i in boundary]
z_top = max(n[2] for n in nodes)
print(f"几何生成（{SHELL}）：{len(nodes)} 节点 / {len(members)} 杆件（{geo['descr']}），"
      f"杆长 {min(lens):.0f}~{max(lens):.0f} mm")
print(f"球面：R={R_m:.0f} mm，顶点标高 {z_top:.0f} mm（实际矢高 {(z_top - base) / UNIT:.3f} m），"
      f"底边界 {len(boundary)} 节点（z {min(b_z):.0f}~{max(b_z):.0f} mm）")
print(f"提示：{SHELL}不使用参数 {unused}，表单取值被忽略。")

# ── 5. 建模：网壳层底边界临时下移 -> 临时柱栽节点标高 -> 建网壳杆件 -> 删临时柱 ──
# MCP 建斜杆时节点默认落在层顶，先用短柱（柱顶=节点标高）把节点"栽"到球面位置；
# 临时下移施加在网壳层与下层的边界（N=1 时即全楼底标高），使全部几何落在网壳层域内
if std_flrs:
    tops_build = tops[:-1] + [base - BTMP_DROP, base + F_m]
    btm_build = btm0
else:
    tops_build = [base + F_m]
    btm_build = btm0 - BTMP_DROP
print("楼层组装(临时下移层底):",
      ModifyFloorAssemTable(StdFlr=std_flrs + [N], FlrTopH=tops_build, BuildingBtmH=btm_build))

stub_sect = Generate_SectionData_TubeSection(diameter=STUB_D, thickness=STUB_T)
stub_lines = [Line3D(P0=Point3D(x=x, y=y, z=z - STUB_LEN), P1=Point3D(x=x, y=y, z=z))
              for (x, y, z) in nodes]
stubs = AddColumnsBy3DLines_WithAutoStdFlrDetection(Lines=stub_lines,
                                                    BarSections=[stub_sect] * len(stub_lines))
print(f"临时定位柱：{len(stubs)} 根（Φ{STUB_D}x{STUB_T}，完成后删除）")

sect = Generate_SectionData_TubeSection(diameter=DIA, thickness=TH)
infos = AddBracesBy3DLines_WithAutoStdFlrDetection(Lines=lines, BarSections=[sect] * len(lines))
print(f"网壳杆件：{len(infos)} 根（Φ{DIA}x{TH} 钢管）")

print("删除临时柱:", DeleteMember(Mems=stubs))
# 恢复边界并保留新层：组装表追加网壳层
print("楼层组装(追加网壳层):",
      ModifyFloorAssemTable(StdFlr=std_flrs + [N], FlrTopH=tops + [base + F_m], BuildingBtmH=btm0))

# ── 6. 校验与保存 ──
# 注意：GetOneStdFlrMember 对不存在/空层可能回退返回其它层的构件，故按标高域过滤后再核对
bars = GetOneStdFlrMember('斜杆', N)
geo2 = ExtractBracesGeometryProperty(bars)
z_lo, z_hi = base - 1.0, base + F_m + 1.0
new_lines = [L for L in geo2["中心线"]
             if z_lo <= min(L.P0.z, L.P1.z) and max(L.P0.z, L.P1.z) <= z_hi]
rerr = max(abs(math.dist((e.x, e.y, e.z), (0, 0, z_c)) - R_m) for L in new_lines
           for e in (L.P0, L.P1))
ok = "✅" if len(new_lines) == len(lines) else "⚠️"
print(f"{ok} 校验：网壳层域内斜杆 {len(new_lines)}/{len(lines)} 根；"
      f"杆端到球心距离最大偏差 {rerr:.2f} mm（整毫米存储所致，≤1mm 属正常）")

try:
    print("保存模型:", SaveModel())
except Exception as e:
    print("保存模型异常:", repr(e))

print(f"\n✅ {SHELL}球面网壳建模完成：D={D:g}m, f={F:g}m, R={R:.2f}m，"
      f"生成于新建标准层 {N}（底边界 {len(boundary)} 节点，最低标高 {min(b_z):.0f} mm），"
      f"{len(nodes)} 节点 / {len(members)} 杆件，截面 Φ{DIA}x{TH}。")
if SHELL in RING_TYPES:
    print(f"⚠️ 支座未设置（接口暂缺）：请在 PKPM 中为底环节点（z={base:.0f} mm，共 {len(boundary)} 个）"
          f"手动添加支座，单层网壳通常取三向固定铰支座。")
else:
    print(f"⚠️ 支座未设置（接口暂缺）：{SHELL}底边界为网格在底圆处截断、环向封边形成的圆环"
          f"（{len(boundary)} 个边界节点，标高 {min(b_z):.0f} mm、半径 D/2），"
          f"请沿底环节点手动添加支座，单层网壳通常取三向固定铰支座。")
if SHELL == "联方型":
    print("⚠️ 联方型为两族斜杆交叉的菱形网格（无径向肋与环向杆），平面外刚度较弱；"
          "必要时可在 PKPM 中后续增设环向杆件，或改选带三角形网格的形式（三向格子/短程线等）。")
