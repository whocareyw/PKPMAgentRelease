# -*- coding: utf-8 -*-
"""JGJ 7-2010 六种常用单层球面网壳的几何生成（纯数学模块，不依赖 PKPM 接口）。

坐标约定：球心 (0, 0, z_c)，球冠底环名义圆半径 D_m/2、标高 base；所有节点精确
落在半径 R 的球面上（PKPM 存储取整毫米，偏差 <=1mm）。

**六种类型的底边界均为精确圆形**：边界节点全部位于底圆（半径 D_m/2、标高 base）上，
并沿圆周设环形封边杆闭合。三向格子/联方 = 各网格线延伸至与底圆的交点后截断；
短程线 = 跨切除面的棱按球面插值求与底圆的交点后截断。底圆上距离过近（< 0.25
倍名义杆长）的节点自动合并，避免产生极短杆；合并后被弃节点从节点表压实移除。

build_shell(shell, R, z_c, D_m, n_sec, n_ring, n_div, base) 返回 dict：
  nodes    节点表 [(x, y, z), ...]        单位 mm
  members  杆件表 [(i, j), ...]           节点下标对（i<j，已去重）
  boundary 底边界节点下标表（按圆周角度排序，全部位于底圆上）
  descr    杆件构成描述文本

类型与参数对应：
  肋环型/肋环斜杆型/凯威特型  -> 用 n_sec(扇区数K)、n_ring(径向环带数)
  三向格子型/联方型          -> 用 n_div（直径向分割数，杆长约 D/n）
  短程线型                   -> 用 n_div 作细分次数 nu
"""

import math


def _merge_map(nodes, idxs, tol):
    """把 idxs 中的节点按圆周角度排序，相邻间距 < tol 者并入前一节点。
    返回 ({被并节点: 保留节点}, 按角度排序的保留节点表)。"""
    order = sorted(idxs, key=lambda i: math.atan2(nodes[i][1], nodes[i][0]))
    mapping, kept = {}, []
    for i in order:
        if kept and math.dist(nodes[kept[-1]], nodes[i]) < tol:
            mapping[i] = kept[-1]
        else:
            kept.append(i)
    if len(kept) > 1 and math.dist(nodes[kept[0]], nodes[kept[-1]]) < tol:
        mapping[kept[-1]] = kept[0]
        kept.pop()
    return mapping, kept


def _remap(members, mapping):
    out = set()
    for (i0, i1) in members:
        j0, j1 = mapping.get(i0, i0), mapping.get(i1, i1)
        if j0 != j1:
            out.add((min(j0, j1), max(j0, j1)))
    return out


def _close_ring(members, ring):
    """沿圆周把 ring（已按角度排序、已合并）首尾相连（不足 3 点为退化，不封边）。"""
    if len(ring) < 3:
        return
    for k in range(len(ring)):
        i0, i1 = ring[k], ring[(k + 1) % len(ring)]
        members.add((min(i0, i1), max(i0, i1)))


def _compact(nodes, members, ring):
    """移除不被任何杆件引用的节点（合并弃点），压实下标。"""
    used = set(ring)
    for (i0, i1) in members:
        used.add(i0)
        used.add(i1)
    new_idx = {i: t for t, i in enumerate(sorted(used))}
    nodes = [nodes[i] for i in sorted(used)]
    members = sorted((min(new_idx[i0], new_idx[i1]), max(new_idx[i0], new_idx[i1]))
                     for (i0, i1) in members)
    boundary = [new_idx[i] for i in ring]
    return nodes, members, boundary


# ── 环系三类：肋环型 / 肋环斜杆型 / 凯威特型 ──

def _ring_shell(R, z_c, D_m, K, N, kind):
    """kind: 'rib'=肋环型, 'ribdiag'=肋环斜杆型, 'kiewitt'=凯威特型。
    径向沿母线等弧长分 N 环带；底环（第 N 环）精确落在底圆上（z=base）。"""
    phi_max = math.asin(min(1.0, (D_m / 2) / R))
    r = [R * math.sin(k * phi_max / N) for k in range(N + 1)]
    z = [z_c + math.sqrt(max(R * R - rr * rr, 0.0)) for rr in r]

    nodes = [(0.0, 0.0, z[0])]          # 0 号 = 顶点
    members = []

    if kind == "kiewitt":
        # 每环 2K 节点：先 K 个肋节点（方位角 j*360/K），再 K 个扇区中间节点（偏半格）。
        # 注意排布顺序必须与 rib()/mid() 下标公式一致（前 K 为肋、后 K 为中），否则杆件错连。
        for k in range(1, N + 1):
            for j in range(K):
                a1 = 2.0 * math.pi * j / K
                nodes.append((r[k] * math.cos(a1), r[k] * math.sin(a1), z[k]))
            for j in range(K):
                a2 = 2.0 * math.pi * (j + 0.5) / K
                nodes.append((r[k] * math.cos(a2), r[k] * math.sin(a2), z[k]))

        def rib(k, j):
            return 1 + (k - 1) * 2 * K + j

        def mid(k, j):
            return 1 + (k - 1) * 2 * K + K + j

        for j in range(K):                            # 径向肋（含顶点段）
            members.append((0, rib(1, j)))
            for k in range(1, N):
                members.append((rib(k, j), rib(k + 1, j)))
        for j in range(K):                            # 扇区脊线（含顶点段）
            members.append((0, mid(1, j)))
            for k in range(1, N):
                members.append((mid(k, j), mid(k + 1, j)))
        for k in range(1, N + 1):                     # 环向杆件
            for j in range(K):
                members.append((rib(k, j), mid(k, j)))
                members.append((mid(k, j), rib(k, (j + 1) % K)))
        for k in range(1, N):                         # V 形斜杆：环k中间节点 -> 环k+1两肋节点
            for j in range(K):
                members.append((mid(k, j), rib(k + 1, j)))
                members.append((mid(k, j), rib(k + 1, (j + 1) % K)))

        boundary = [rib(N, j) for j in range(K)] + [mid(N, j) for j in range(K)]
        descr = f"肋 {K * N} + 脊线 {K * N} + 环杆 {2 * K * N} + V形斜杆 {2 * K * (N - 1)}"
    else:
        # 每环 K 个肋节点
        for k in range(1, N + 1):
            for j in range(K):
                a = 2.0 * math.pi * j / K
                nodes.append((r[k] * math.cos(a), r[k] * math.sin(a), z[k]))

        def nd(k, j):
            return 1 + (k - 1) * K + (j % K)

        for j in range(K):                            # 径向肋（含顶点段）
            members.append((0, nd(1, j)))
            for k in range(1, N):
                members.append((nd(k, j), nd(k + 1, j)))
        for k in range(1, N + 1):                     # 环向杆件
            for j in range(K):
                members.append((nd(k, j), nd(k, j + 1)))
        if kind == "ribdiag":                         # 斜杆：相邻格反向（锯齿对称）
            for k in range(1, N):
                for j in range(K):
                    if j % 2 == 0:
                        members.append((nd(k, j), nd(k + 1, j + 1)))
                    else:
                        members.append((nd(k + 1, j), nd(k, j + 1)))
            descr = f"肋 {K * N} + 环杆 {K * N} + 斜杆 {K * (N - 1)}"
        else:
            descr = f"肋 {K * N} + 环杆 {K * N}"

        boundary = [nd(N, j) for j in range(K)]

    # 底环节点按圆周角度排序输出（位置不变，仅排序）
    boundary.sort(key=lambda i: math.atan2(nodes[i][1], nodes[i][0]))
    return nodes, members, boundary, descr


# ── 平面网格投影两类：三向格子型（3 线族）/ 联方型（2 线族）──

def _plan_grid(R, z_c, D_m, n, fam_angles):
    """平面等边三角形/菱形网格竖投影到球面：fam_angles 为各平行线族的法向角（度）。
    线族间距 s = sqrt(3)/2 * a（a = D_m/n 为名义杆长），网格边长约 a；
    各族 m=0 线均过原点，保证球顶存在节点。
    每条网格线延伸至与底圆（半径 D_m/2）的交点后截断，交点沿圆周环形封边，
    底边界为精确圆形。"""
    a = D_m / n
    s = a * math.sqrt(3.0) / 2.0
    rmax = D_m / 2.0
    rmax2 = rmax * rmax
    z_base = z_c + math.sqrt(max(R * R - rmax2, 0.0))   # 底圆标高（=base）
    tol = 0.25 * a                                      # 底圆节点合并/吸附容差
    norms = [(math.cos(math.radians(t)), math.sin(math.radians(t))) for t in fam_angles]
    dirs = [(-ny, nx) for (nx, ny) in norms]

    pts = {}                                          # 1/4 mm 网格键 -> (x, y)，兼去重

    def add_point(x, y):
        if x * x + y * y <= rmax2 + 1e-6:
            key = (round(x * 4), round(y * 4))
            if key not in pts:
                pts[key] = (x, y)

    M = int(math.ceil((rmax + s) / s)) + 1
    for i in range(len(norms)):                       # 两两线族求全部交点
        for j in range(i + 1, len(norms)):
            n1, n2 = norms[i], norms[j]
            det = n1[0] * n2[1] - n1[1] * n2[0]       # 法向夹角 60 度，恒非零
            for m1 in range(-M, M + 1):
                b1 = m1 * s
                for m2 in range(-M, M + 1):
                    b2 = m2 * s
                    add_point((b1 * n2[1] - b2 * n1[1]) / det,
                              (n1[0] * b2 - n2[0] * b1) / det)

    nodes2d = list(pts.values())
    nodes = [(x, y, z_c + math.sqrt(max(R * R - x * x - y * y, 0.0))) for (x, y) in nodes2d]
    n_orig = len(nodes)                               # 原始网格节点数（其后才追加底圆节点）

    def add_bdy_node(x, y):
        """在底圆上取节点：若 tol 内已有节点则吸附（移到圆上）复用，否则新增。
        吸附只可能命中底圆附近最外圈网格节点（移动 <=0.25a，仍在其各属线上，
        0.25a < 0.5*线间距，不致归线错误）。"""
        best, bestd = None, tol
        for idx in range(len(nodes2d)):
            px, py = nodes2d[idx]
            d = math.hypot(px - x, py - y)
            if d < bestd:
                best, bestd = idx, d
        if best is not None:
            nodes2d[best] = (x, y)
            nodes[best] = (x, y, z_base)
            return best
        nodes2d.append((x, y))
        nodes.append((x, y, z_base))
        return len(nodes) - 1

    # 先按原始网格节点把各线族的点归线（此时尚无底圆节点，不会串线），
    # 再把每条线两端延伸至底圆交点，沿线相邻点连杆
    members = set()
    bdy = set()
    for i, (nx, ny) in enumerate(norms):
        dx, dy = dirs[i]
        lines = {}
        for idx in range(n_orig):
            x, y = nodes2d[idx]
            m = int(round((x * nx + y * ny) / s))
            lines.setdefault(m, []).append((x * dx + y * dy, idx))
        for m, lst in lines.items():
            b = m * s
            if abs(b) < rmax:                         # 该线与底圆相交，两端延伸至交点
                h = math.sqrt(max(rmax2 - b * b, 0.0))
                for t_edge in (-h, h):
                    bi = add_bdy_node(b * nx + t_edge * dx, b * ny + t_edge * dy)
                    bdy.add(bi)
                    lst.append((t_edge, bi))
            lst.sort()
            for (t0, i0), (t1, i1) in zip(lst, lst[1:]):
                if i0 != i1:
                    members.add((min(i0, i1), max(i0, i1)))

    # 底圆节点近距合并 + 环向封边 + 压实弃点
    mapping, ring = _merge_map(nodes, bdy, tol)
    members = _remap(members, mapping)
    _close_ring(members, ring)
    nodes, members, boundary = _compact(nodes, members, ring)

    if len(norms) == 3:
        descr = f"三族斜杆（三角形网格），边长≈{a:.0f} mm，底圆封边 {len(ring)} 节点"
    else:
        descr = f"两族斜杆（菱形网格），边长≈{a:.0f} mm，底圆封边 {len(ring)} 节点"
    return nodes, members, boundary, descr


# ── 短程线型：内接正二十面体细分 ──

def _geodesic(R, z_c, nu, z_base):
    """正二十面体内接于球、顶点朝上，每条棱 nu 等分后各点投影到球面（细分 nu 次，
    共 20*nu^2 个小球面三角形），取 z >= z_base 的球冠。跨切除面的棱按球面插值
    （slerp）求与底圆的交点后截断，交点沿圆周环形封边，底边界为精确圆形。"""
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    verts = []
    for sa in (-1.0, 1.0):
        for sb in (-phi, phi):
            verts.append((0.0, sa, sb))
            verts.append((sa, sb, 0.0))
            verts.append((sb, 0.0, sa))
    nrm = math.sqrt(1.0 + phi * phi)
    verts = [(x / nrm, y / nrm, z / nrm) for (x, y, z) in verts]

    # Rodrigues 旋转：把最靠上的顶点转到 (0,0,1)，保证球顶有节点
    top = max(verts, key=lambda p: p[2])
    ax, ay, az = top[1], -top[0], 0.0                 # top × (0,0,1)
    alen = math.sqrt(ax * ax + ay * ay)
    if alen < 1e-12:
        rot = lambda p: p
    else:
        ax, ay = ax / alen, ay / alen
        ang = math.acos(max(-1.0, min(1.0, top[2])))
        c, sn = math.cos(ang), math.sin(ang)

        def rot(p):
            cx, cy, cz = ay * p[2], -ax * p[2], ax * p[1] - ay * p[0]
            dot = ax * p[0] + ay * p[1]
            return (p[0] * c + cx * sn + ax * dot * (1 - c),
                    p[1] * c + cy * sn + ay * dot * (1 - c),
                    p[2] * c + cz * sn + 0.0 * dot * (1 - c))
    verts = [rot(v) for v in verts]

    def dist(p, q):
        return math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)

    edge = 2.0 / nrm                                  # 单位球上二十面体棱长（弦长）
    faces = []                                        # 20 个基本面：三顶点两两相邻
    for i in range(12):
        for j in range(i + 1, 12):
            for k in range(j + 1, 12):
                if (dist(verts[i], verts[j]) < edge * 1.1
                        and dist(verts[i], verts[k]) < edge * 1.1
                        and dist(verts[j], verts[k]) < edge * 1.1):
                    faces.append((i, j, k))

    nodes_u = []                                      # 单位球坐标
    index = {}

    def nid(p):
        n = math.sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2])  # 插值点在弦面内侧，须投影回球面
        p = (p[0] / n, p[1] / n, p[2] / n)
        key = (round(R * p[0] * 4), round(R * p[1] * 4), round((z_c + R * p[2]) * 4))
        idx = index.get(key)
        if idx is None:
            idx = len(nodes_u)
            index[key] = idx
            nodes_u.append(p)
        return idx

    edges = set()
    for (A, B, C) in faces:
        va, vb, vc = verts[A], verts[B], verts[C]
        lat = {}
        for i in range(nu + 1):
            for j in range(nu + 1 - i):
                w0, w1, w2 = (nu - i - j) / nu, i / nu, j / nu
                lat[(i, j)] = nid((w0 * va[0] + w1 * vb[0] + w2 * vc[0],
                                   w0 * va[1] + w1 * vb[1] + w2 * vc[1],
                                   w0 * va[2] + w1 * vb[2] + w2 * vc[2]))
        for i in range(nu):
            for j in range(nu - i):
                e = lambda u, v: (min(lat[u], lat[v]), max(lat[u], lat[v]))
                edges.add(e((i, j), (i + 1, j)))
                edges.add(e((i, j), (i, j + 1)))
                edges.add(e((i + 1, j), (i, j + 1)))
                if j < nu - 1 - i:
                    edges.add(e((i + 1, j), (i + 1, j + 1)))
                    edges.add(e((i, j + 1), (i + 1, j + 1)))

    # 切除 z < z_base 部分：底圆纬度的单位 z；跨切面的棱用球面插值求交点（必在底圆上）
    zeta = (z_base - z_c) / R
    keep = [i for i, p in enumerate(nodes_u) if p[2] >= zeta - 1e-9]
    keepset = set(keep)

    def cut_point(p, q):
        """p 在保留侧、q 在切除侧：球面插值（大圆弧）上 z=zeta 的点，二分求解。"""
        dot = max(-1.0, min(1.0, p[0] * q[0] + p[1] * q[1] + p[2] * q[2]))
        om = math.acos(dot)
        so = math.sin(om)
        lo, hi = 0.0, 1.0
        for _ in range(48):
            t = 0.5 * (lo + hi)
            zz = (math.sin((1.0 - t) * om) * p[2] + math.sin(t * om) * q[2]) / so
            if zz > zeta:
                lo = t
            else:
                hi = t
        t = 0.5 * (lo + hi)
        w0, w1 = math.sin((1.0 - t) * om) / so, math.sin(t * om) / so
        u = (w0 * p[0] + w1 * q[0], w0 * p[1] + w1 * q[1], w0 * p[2] + w1 * q[2])
        n = math.sqrt(u[0] * u[0] + u[1] * u[1] + u[2] * u[2])
        return (u[0] / n, u[1] / n, u[2] / n)

    # 底圆节点池：切面附近的保留节点（可吸附，含恰在切面上的节点）+ 新增交点。
    # 吸附避免「保留节点紧贴切面」时产生极短杆/零长杆（如半球 + 低细分的赤道节点）。
    tol = 0.25 * R * edge / nu
    tol_u = tol / R
    cand = [i for i in keepset if nodes_u[i][2] < zeta + tol_u]
    bdy = set()

    def add_cut(u):
        best, bestd = None, tol_u
        for i in cand:
            d = dist(nodes_u[i], u)
            if d < bestd:
                best, bestd = i, d
        if best is not None:
            nodes_u[best] = u                          # 吸附到底圆上
            bdy.add(best)
            return best
        nodes_u.append(u)
        idx = len(nodes_u) - 1
        cand.append(idx)
        bdy.add(idx)
        return idx

    members = set()
    for (a_, b_) in edges:
        ka, kb = a_ in keepset, b_ in keepset
        if ka and kb:
            members.add((min(a_, b_), max(a_, b_)))
        elif ka != kb:
            pi, qi = (a_, b_) if ka else (b_, a_)
            ci = add_cut(cut_point(nodes_u[pi], nodes_u[qi]))
            if ci != pi:                               # 吸附到自身时该杆退化为点，丢弃
                members.add((min(pi, ci), max(pi, ci)))

    # 底圆节点近距合并 + 环向封边 + 压实弃点
    nodes = [(R * u[0], R * u[1], z_c + R * u[2]) for u in nodes_u]
    mapping, ring = _merge_map(nodes, bdy, tol)
    members = _remap(members, mapping)
    _close_ring(members, ring)
    nodes, members, boundary = _compact(nodes, members, ring)

    descr = f"正二十面体细分ν={nu}（20×{nu}² 面），底圆封边 {len(ring)} 节点"
    return nodes, members, boundary, descr


# ── 类型分发 ──

def build_shell(shell, R, z_c, D_m, n_sec, n_ring, n_div, base):
    """按 JGJ 7-2010 六种常用形式之一生成单层球面网壳几何。"""
    if shell == "肋环型":
        nodes, members, boundary, descr = _ring_shell(R, z_c, D_m, n_sec, n_ring, "rib")
    elif shell == "肋环斜杆型":
        nodes, members, boundary, descr = _ring_shell(R, z_c, D_m, n_sec, n_ring, "ribdiag")
    elif shell == "凯威特型":
        nodes, members, boundary, descr = _ring_shell(R, z_c, D_m, n_sec, n_ring, "kiewitt")
    elif shell == "三向格子型":
        nodes, members, boundary, descr = _plan_grid(R, z_c, D_m, n_div, (0.0, 60.0, 120.0))
    elif shell == "联方型":
        nodes, members, boundary, descr = _plan_grid(R, z_c, D_m, n_div, (60.0, 120.0))
    elif shell == "短程线型":
        nodes, members, boundary, descr = _geodesic(R, z_c, n_div, base)
    else:
        raise ValueError(f"未知网壳类型：{shell}")
    return {"nodes": nodes, "members": members, "boundary": boundary, "descr": descr}
