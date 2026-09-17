#!/usr/bin/env python3
"""
J.A.R.V.I.S. Holographic Engineering System (v2)
--------------------------------------------------
Single-file, gesture-controlled holographic HUD, built for low-end
hardware (target: Intel Celeron N4120 / UHD 600 / 4GB RAM).

Dependencies: opencv-python, mediapipe, numpy
Run:          python hologram.py
Quit:         press 'q'

Performance approach:
  - MediaPipe Hands runs with model_complexity=0 (lightest model),
    camera captured at 640x480 regardless of the (larger) display window.
  - All "3D" rendering is pure math: rotation matrices + perspective
    projection + line/polygon drawing with OpenCV. No OpenGL, no meshes,
    no textures, no neural nets.
  - A lightweight bloom effect is achieved by downscaling the hologram
    layer, blurring the SMALL version, then upscaling back -- this is
    far cheaper than blurring the full-resolution frame.
  - An adaptive quality system watches the smoothed FPS and disables
    expensive layers (bloom, translucent faces, particle count) if the
    machine falls behind, so hand tracking always stays responsive.
"""

import math
import time
from collections import deque

import cv2
import numpy as np
import mediapipe as mp

# ============================================================
# CONFIGURATION
# ============================================================

CAM_INDEX = 0
CAM_W, CAM_H = 640, 480              # camera / MediaPipe resolution (kept small for speed)
DISPLAY_W, DISPLAY_H = 1280, 720     # large display window

COOLDOWN = 6.0                       # seconds between discrete page/select actions
DEBOUNCE_LEN = 4
DEBOUNCE_MIN = 3

PINCH_RATIO = 0.40                   # pinch distance / hand size threshold
THUMB_EXT_RATIO = 0.95

YAW_SENSITIVITY = 9.0                # one-hand grab -> rotation sensitivity
PITCH_SENSITIVITY = 7.0
TRANSLATE_SENSITIVITY = 140.0        # one-hand grab -> translation sensitivity (px)
GRAB_SMOOTHING = 0.35                # lerp factor applied to grab-driven transforms
HAND_SMOOTH = 0.5                    # EMA smoothing factor on raw hand position

ZOOM_SMOOTHING = 0.20                # lerp factor for two-hand zoom / rotation
ROT2_SENSITIVITY = 1.3               # two-hand angle -> rotation sensitivity
ZOOM_MIN, ZOOM_MAX = 0.5, 2.5

AUTO_ROTATE_SPEED = 0.010            # idle auto-spin, radians/frame

FOCAL = 560.0                        # projection focal length (pixels)
CAM_DIST = 3.5                       # virtual camera distance from object origin

TRANSITION_DURATION = 0.5            # seconds for page-switch dissolve/reveal

MODEL_COMPLEXITY = 0                 # 0 = lite model (fastest)
MIN_DETECTION_CONF = 0.6
MIN_TRACKING_CONF = 0.5

FONT = cv2.FONT_HERSHEY_SIMPLEX

# Colors are BGR (OpenCV convention)
MAIN = (255, 225, 60)        # bright cyan-blue (primary structure)
SECOND = (255, 170, 40)      # dimmer blue (secondary structure)
ACCENT = (255, 255, 210)     # near-white glow (cores / eyes / highlights)
HOUSING = (220, 150, 40)     # muted mechanical blue-grey
SELECT_COLOR = (0, 200, 255)  # amber "target lock" accent

PAGE_NAMES = [
    "IRON MAN SUIT",
    "ARC REACTOR",
    "ROBO ARM",
    "3D PRINTER",
    "IRON MAN MASK",
]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ============================================================
# GEOMETRY HELPERS  ->  (points Nx3 ndarray, edges list[(i,j)])
# ============================================================

def gen_box(center, size):
    cx, cy, cz = center
    w, h, d = size
    hw, hh, hd = w / 2.0, h / 2.0, d / 2.0
    pts = np.array([
        [cx - hw, cy - hh, cz - hd], [cx + hw, cy - hh, cz - hd],
        [cx + hw, cy + hh, cz - hd], [cx - hw, cy + hh, cz - hd],
        [cx - hw, cy - hh, cz + hd], [cx + hw, cy - hh, cz + hd],
        [cx + hw, cy + hh, cz + hd], [cx - hw, cy + hh, cz + hd],
    ])
    edges = [(0, 1), (1, 2), (2, 3), (3, 0),
             (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    return pts, edges


def gen_ring(center, radius, segments=24, plane='xy'):
    cx, cy, cz = center
    pts = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        if plane == 'xy':
            pts.append([cx + radius * math.cos(a), cy + radius * math.sin(a), cz])
        elif plane == 'xz':
            pts.append([cx + radius * math.cos(a), cy, cz + radius * math.sin(a)])
        else:  # 'yz'
            pts.append([cx, cy + radius * math.cos(a), cz + radius * math.sin(a)])
    edges = [(i, (i + 1) % segments) for i in range(segments)]
    return np.array(pts), edges


def gen_sphere_wire(center, radius, lat=5, lon=10):
    cx, cy, cz = center
    pts = []
    idx_map = {}
    idx = 0
    for i in range(lat + 1):
        phi = math.pi * i / lat - math.pi / 2.0
        for j in range(lon):
            theta = 2 * math.pi * j / lon
            x = cx + radius * math.cos(phi) * math.cos(theta)
            y = cy + radius * math.sin(phi)
            z = cz + radius * math.cos(phi) * math.sin(theta)
            pts.append([x, y, z])
            idx_map[(i, j)] = idx
            idx += 1
    edges = []
    for i in range(lat + 1):
        for j in range(lon):
            edges.append((idx_map[(i, j)], idx_map[(i, (j + 1) % lon)]))
            if i < lat:
                edges.append((idx_map[(i, j)], idx_map[(i + 1, j)]))
    return np.array(pts), edges


def gen_grid(y, size=1.0, divisions=6):
    pts = []
    edges = []
    step = (size * 2) / divisions
    idx = 0
    for i in range(divisions + 1):
        x = -size + i * step
        pts.append([x, y, -size]); pts.append([x, y, size])
        edges.append((idx, idx + 1)); idx += 2
    for i in range(divisions + 1):
        z = -size + i * step
        pts.append([-size, y, z]); pts.append([size, y, z])
        edges.append((idx, idx + 1)); idx += 2
    return np.array(pts), edges


def gen_helix(center, radius, height, turns, segments):
    cx, cy, cz = center
    pts = []
    for i in range(segments):
        tt = i / (segments - 1)
        a = 2 * math.pi * turns * tt
        x = cx + radius * math.cos(a)
        z = cz + radius * math.sin(a)
        y = cy + height * tt
        pts.append([x, y, z])
    edges = [(i, i + 1) for i in range(segments - 1)]
    return np.array(pts), edges


# ============================================================
# HOLOGRAM DEFINITIONS
#   wire_groups : list of (points, edges, color, thickness)
#   face_groups : list of (points, faces[list of index-tuples], color)
#   labels      : list of (text, local_point3d, side)
# ============================================================

def build_suit():
    wire = []
    def W(pts, edges, color, thick=1): wire.append((pts, edges, color, thick))

    W(*gen_box((0, 1.55, 0), (0.34, 0.38, 0.34)), MAIN, 2)         # helmet
    W(*gen_box((0, 1.28, 0), (0.20, 0.12, 0.20)), SECOND)          # neck
    W(*gen_box((0, 0.85, 0), (0.78, 0.55, 0.40)), MAIN, 2)         # chest
    W(*gen_box((0, 0.30, 0), (0.62, 0.42, 0.36)), SECOND, 2)       # waist / abdomen
    W(*gen_box((-0.62, 1.05, 0), (0.28, 0.26, 0.28)), SECOND)      # L shoulder
    W(*gen_box((0.62, 1.05, 0), (0.28, 0.26, 0.28)), SECOND)       # R shoulder
    W(*gen_box((-0.74, 0.60, 0), (0.22, 0.52, 0.22)), MAIN)        # L upper arm
    W(*gen_box((0.74, 0.60, 0), (0.22, 0.52, 0.22)), MAIN)         # R upper arm
    W(*gen_sphere_wire((-0.75, 0.20, 0), 0.14, 3, 6), ACCENT)      # L elbow
    W(*gen_sphere_wire((0.75, 0.20, 0), 0.14, 3, 6), ACCENT)       # R elbow
    W(*gen_box((-0.76, -0.10, 0), (0.19, 0.45, 0.19)), SECOND)     # L forearm
    W(*gen_box((0.76, -0.10, 0), (0.19, 0.45, 0.19)), SECOND)      # R forearm
    W(*gen_box((-0.76, -0.42, 0), (0.20, 0.16, 0.14)), MAIN)       # L hand
    W(*gen_box((0.76, -0.42, 0), (0.20, 0.16, 0.14)), MAIN)        # R hand
    W(*gen_box((-0.30, -0.15, 0), (0.30, 0.55, 0.30)), MAIN, 2)    # L thigh
    W(*gen_box((0.30, -0.15, 0), (0.30, 0.55, 0.30)), MAIN, 2)     # R thigh
    W(*gen_sphere_wire((-0.30, -0.55, 0), 0.16, 3, 6), ACCENT)     # L knee
    W(*gen_sphere_wire((0.30, -0.55, 0), 0.16, 3, 6), ACCENT)      # R knee
    W(*gen_box((-0.30, -0.95, 0), (0.24, 0.55, 0.24)), SECOND)     # L shin
    W(*gen_box((0.30, -0.95, 0), (0.24, 0.55, 0.24)), SECOND)      # R shin
    W(*gen_box((-0.30, -1.32, 0.06), (0.26, 0.16, 0.42)), MAIN)    # L boot
    W(*gen_box((0.30, -1.32, 0.06), (0.26, 0.16, 0.42)), MAIN)     # R boot
    W(*gen_ring((0, 0.90, 0.21), 0.13, 18, 'xy'), ACCENT, 2)       # arc core outer
    W(*gen_ring((0, 0.90, 0.21), 0.06, 10, 'xy'), ACCENT)          # arc core inner

    faces = [
        (*gen_box((0, 0.85, 0), (0.78, 0.55, 0.40))[0:1], [(0, 1, 2, 3)], MAIN),
    ]
    # rebuild faces properly (need matching points, not sliced tuple trick above)
    chest_pts, _ = gen_box((0, 0.85, 0), (0.78, 0.55, 0.40))
    waist_pts, _ = gen_box((0, 0.30, 0), (0.62, 0.42, 0.36))
    helm_pts, _ = gen_box((0, 1.55, 0), (0.34, 0.38, 0.34))
    faces = [
        (chest_pts, [(0, 1, 2, 3)], MAIN),
        (waist_pts, [(0, 1, 2, 3)], SECOND),
        (helm_pts, [(0, 1, 2, 3)], ACCENT),
    ]

    labels = [
        ("HELMET UNIT", (0, 1.55, 0.34), 'right'),
        ("CHEST MODULE", (0, 0.85, 0.40), 'left'),
        ("POWER CORE", (0, 0.90, 0.40), 'right'),
        ("SHOULDER ASSEMBLY", (0.62, 1.05, 0.20), 'right'),
        ("JOINT SYSTEM", (0.75, 0.20, 0.15), 'left'),
    ]
    return wire, faces, labels


def build_reactor():
    wire = []
    def W(pts, edges, color, thick=1): wire.append((pts, edges, color, thick))

    W(*gen_sphere_wire((0, 0, 0), 0.22, 4, 10), ACCENT, 2)
    W(*gen_ring((0, 0, 0), 0.40, 28, 'xy'), MAIN, 2)
    W(*gen_ring((0, 0, 0), 0.60, 24, 'xy'), MAIN)
    W(*gen_ring((0, 0, 0), 0.82, 10, 'xy'), HOUSING)
    W(*gen_ring((0, 0, 0), 1.00, 8, 'xy'), HOUSING, 2)
    W(*gen_ring((0, 0, 0.16), 0.60, 20, 'xy'), SECOND)
    W(*gen_ring((0, 0, -0.16), 0.60, 20, 'xy'), SECOND)
    W(*gen_ring((0, 0, 0.28), 0.40, 16, 'xy'), SECOND)
    W(*gen_ring((0, 0, -0.28), 0.40, 16, 'xy'), SECOND)

    spoke_pts = [[0, 0, 0]]
    spoke_edges = []
    ring_o, _ = gen_ring((0, 0, 0), 0.82, 12, 'xy')
    for i, pt in enumerate(ring_o):
        spoke_pts.append(pt.tolist())
        spoke_edges.append((0, i + 1))
    W(np.array(spoke_pts), spoke_edges, SECOND)

    core_pts, _ = gen_ring((0, 0, 0), 0.40, 28, 'xy')
    housing_pts, _ = gen_ring((0, 0, 0), 1.00, 8, 'xy')
    faces = [
        (core_pts, [tuple(range(len(core_pts)))], ACCENT),
        (housing_pts, [tuple(range(len(housing_pts)))], HOUSING),
    ]

    labels = [
        ("CORE UNIT", (0, 0, 0.25), 'right'),
        ("CONTAINMENT RING", (0.62, 0, 0), 'left'),
        ("HOUSING FRAME", (0.95, 0.3, 0), 'right'),
        ("ENERGY OUTPUT", (0, -0.75, 0), 'left'),
    ]
    return wire, faces, labels


def build_arm():
    wire = []
    def W(pts, edges, color, thick=1): wire.append((pts, edges, color, thick))

    W(*gen_box((0, -1.0, 0), (0.9, 0.18, 0.9)), HOUSING, 2)        # base plate
    W(*gen_ring((0, -0.91, 0), 0.5, 20, 'xz'), SECOND)             # base ring
    W(*gen_sphere_wire((0, -0.55, 0), 0.20, 4, 8), ACCENT)         # shoulder joint
    W(*gen_box((0, -0.15, 0), (0.22, 0.8, 0.22)), MAIN, 2)         # upper arm
    W(*gen_sphere_wire((0, 0.30, 0), 0.16, 3, 8), ACCENT)          # elbow joint
    W(*gen_box((0.5, 0.30, 0), (0.9, 0.18, 0.18)), MAIN, 2)        # forearm
    W(*gen_sphere_wire((0.95, 0.30, 0), 0.12, 3, 6), ACCENT)       # wrist joint
    W(*gen_box((1.10, 0.44, 0), (0.15, 0.32, 0.10)), SECOND)       # gripper top
    W(*gen_box((1.10, 0.16, 0), (0.15, 0.32, 0.10)), SECOND)       # gripper bottom
    W(*gen_box((1.10, 0.30, 0.12), (0.10, 0.10, 0.10)), SECOND)    # gripper 3rd finger

    base_pts, _ = gen_box((0, -1.0, 0), (0.9, 0.18, 0.9))
    faces = [(base_pts, [(0, 1, 2, 3)], HOUSING)]

    labels = [
        ("BASE MOUNT", (0, -1.0, 0.45), 'left'),
        ("JOINT 01 / SERVO", (0, -0.55, 0.2), 'right'),
        ("JOINT 02 / ROTATION", (0, 0.30, 0.15), 'left'),
        ("GRIPPER", (1.10, 0.30, 0.12), 'right'),
    ]
    return wire, faces, labels


def build_printer():
    wire = []
    def W(pts, edges, color, thick=1): wire.append((pts, edges, color, thick))

    W(*gen_box((0, 0.10, 0), (1.3, 1.6, 1.0)), HOUSING, 2)         # frame envelope
    W(*gen_box((0, -0.75, 0), (1.1, 0.08, 0.9)), MAIN, 2)          # print bed
    W(*gen_grid(-0.71, 0.5, 6), SECOND)                            # bed grid
    W(*gen_box((-0.6, 0.10, 0), (0.06, 1.5, 0.06)), SECOND)        # Z rod L
    W(*gen_box((0.6, 0.10, 0), (0.06, 1.5, 0.06)), SECOND)         # Z rod R
    W(*gen_box((0.15, 0.55, 0), (1.1, 0.07, 0.07)), MAIN)          # X gantry
    W(*gen_box((0.15, 0.55, 0), (0.20, 0.20, 0.20)), ACCENT)       # print head
    W(*gen_helix((0.55, -0.30, 0.35), 0.10, 1.1, 4, 36), ACCENT)   # filament spool path
    W(*gen_box((0.10, -0.55, 0.05), (0.28, 0.30, 0.28)), MAIN)     # object being printed

    bed_pts, _ = gen_box((0, -0.75, 0), (1.1, 0.08, 0.9))
    faces = [(bed_pts, [(4, 5, 6, 7)], MAIN)]

    labels = [
        ("FRAME", (-0.65, 0.5, 0.5), 'left'),
        ("X-AXIS RAIL", (0.6, 0.55, 0), 'right'),
        ("Z-AXIS", (0.6, 0.10, 0), 'right'),
        ("PRINT BED", (0, -0.75, 0.5), 'left'),
        ("EXTRUDER HEAD", (0.15, 0.55, 0.20), 'right'),
    ]
    return wire, faces, labels


def build_mask():
    wire = []
    def W(pts, edges, color, thick=1): wire.append((pts, edges, color, thick))

    W(*gen_sphere_wire((0, 0.20, 0), 0.62, 5, 12), MAIN, 2)        # helmet dome
    W(*gen_box((0, -0.35, 0.10), (0.55, 0.4, 0.5)), SECOND, 2)     # jaw
    W(*gen_ring((-0.22, 0.22, 0.56), 0.13, 16, 'xy'), ACCENT, 2)   # left eye
    W(*gen_ring((0.22, 0.22, 0.56), 0.13, 16, 'xy'), ACCENT, 2)    # right eye
    W(*gen_ring((0, 0.20, 0), 0.66, 20, 'yz'), HOUSING)            # profile silhouette
    W(*gen_ring((0, -0.05, 0), 0.50, 16, 'yz'), SECOND)            # lower profile band
    center_line = np.array([[0, 0.78, 0.55], [0, -0.55, 0.45]])
    W(center_line, [(0, 1)], SECOND)                               # faceplate seam

    visor_pts = np.array([
        [-0.35, 0.35, 0.60], [0.35, 0.35, 0.60],
        [0.35, -0.05, 0.58], [-0.35, -0.05, 0.58],
    ])
    faces = [(visor_pts, [(0, 1, 2, 3)], ACCENT)]

    labels = [
        ("HELMET SHELL", (0, 0.62, 0.30), 'right'),
        ("EYE SENSOR", (-0.22, 0.22, 0.60), 'left'),
        ("JAW UNIT", (0, -0.35, 0.35), 'right'),
        ("INTERNAL CORE", (0, 0.05, 0), 'left'),
    ]
    return wire, faces, labels


HOLOGRAM_BUILDERS = [build_suit, build_reactor, build_arm, build_printer, build_mask]


# ============================================================
# MATH: ROTATION + PROJECTION
# ============================================================

def rotation_matrix(yaw, pitch):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cx, sx = math.cos(pitch), math.sin(pitch)
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    return ry.dot(rx)


def project_points(pts3d, cx, cy, f):
    z = pts3d[:, 2] + CAM_DIST
    z = np.clip(z, 0.6, None)
    s = f / z
    x2 = cx + pts3d[:, 0] * s
    y2 = cy - pts3d[:, 1] * s
    return np.stack([x2, y2], axis=1)


def draw_glow_line(img, p1, p2, color, thickness=1, single_pass=False):
    p1 = (int(p1[0]), int(p1[1]))
    p2 = (int(p2[0]), int(p2[1]))
    if not single_pass:
        dim = tuple(int(c * 0.45) for c in color)
        cv2.line(img, p1, p2, dim, thickness + 2, cv2.LINE_AA)
    cv2.line(img, p1, p2, color, thickness, cv2.LINE_AA)


def composite_layer(canvas, layer, alpha=1.0):
    if alpha >= 0.999:
        canvas[:] = cv2.add(canvas, layer)
    elif alpha > 0.001:
        canvas[:] = cv2.addWeighted(layer, alpha, canvas, 1.0, 0)


# ============================================================
# HOLOGRAM OBJECT
# ============================================================

class Hologram:
    def __init__(self, name, build_fn):
        self.name = name
        self.wire_groups, self.face_groups, self.labels = build_fn()
        self.yaw = 0.35
        self.pitch = 0.15
        self.ox = 0.0
        self.oy = 0.0
        self.zoom = 1.0
        self.grabbed = False
        self.grab_start_hand = None
        self.grab_start_yaw = 0.0
        self.grab_start_pitch = 0.0
        self.grab_start_ox = 0.0
        self.grab_start_oy = 0.0

    def update_auto(self):
        if not self.grabbed:
            self.yaw += AUTO_ROTATE_SPEED

    def begin_grab(self, hand_pos):
        self.grabbed = True
        self.grab_start_hand = hand_pos
        self.grab_start_yaw = self.yaw
        self.grab_start_pitch = self.pitch
        self.grab_start_ox = self.ox
        self.grab_start_oy = self.oy

    def update_grab(self, hand_pos):
        dx = hand_pos[0] - self.grab_start_hand[0]
        dy = hand_pos[1] - self.grab_start_hand[1]
        target_yaw = self.grab_start_yaw + dx * YAW_SENSITIVITY
        target_pitch = clamp(self.grab_start_pitch - dy * PITCH_SENSITIVITY, -1.3, 1.3)
        target_ox = clamp(self.grab_start_ox + dx * TRANSLATE_SENSITIVITY, -140, 140)
        target_oy = clamp(self.grab_start_oy - dy * TRANSLATE_SENSITIVITY, -100, 100)
        s = GRAB_SMOOTHING
        self.yaw += (target_yaw - self.yaw) * s
        self.pitch += (target_pitch - self.pitch) * s
        self.ox += (target_ox - self.ox) * s
        self.oy += (target_oy - self.oy) * s

    def end_grab(self):
        self.grabbed = False
        self.grab_start_hand = None


def render_object(canvas, effect_layer, holo, cx, cy, t, perf_level, alpha):
    effect_layer[:] = 0
    R = rotation_matrix(holo.yaw, holo.pitch)
    f = FOCAL * holo.zoom
    bob = math.sin(t * 0.6) * 6
    ccx = cx + holo.ox
    ccy = cy + holo.oy + bob

    if perf_level >= 1 and holo.face_groups:
        items = []
        for pts, faces, color in holo.face_groups:
            rotated = pts.dot(R.T)
            proj = project_points(rotated, ccx, ccy, f)
            for face in faces:
                idx = list(face)
                zavg = float(np.mean(rotated[idx, 2]))
                poly = proj[idx].astype(np.int32)
                items.append((zavg, poly, color))
        items.sort(key=lambda it: it[0], reverse=True)  # far first, near last
        for _, poly, color in items:
            dim = tuple(int(c * 0.15) for c in color)
            cv2.fillPoly(effect_layer, [poly], dim, lineType=cv2.LINE_AA)

    single_pass = (perf_level == 0)
    for pts, edges, color, thick in holo.wire_groups:
        rotated = pts.dot(R.T)
        proj = project_points(rotated, ccx, ccy, f)
        n = len(proj)
        for i, j in edges:
            if 0 <= i < n and 0 <= j < n:
                draw_glow_line(effect_layer, proj[i], proj[j], color, thick, single_pass)

    if perf_level >= 2:
        small = cv2.resize(effect_layer, (effect_layer.shape[1] // 3, effect_layer.shape[0] // 3),
                            interpolation=cv2.INTER_LINEAR)
        small = cv2.GaussianBlur(small, (5, 5), 0)
        bloom = cv2.resize(small, (effect_layer.shape[1], effect_layer.shape[0]),
                            interpolation=cv2.INTER_LINEAR)
        cv2.add(effect_layer, bloom, dst=effect_layer)

    composite_layer(canvas, effect_layer, alpha)

    if perf_level >= 1 and alpha > 0.6:
        draw_labels(canvas, holo, R, ccx, ccy, f)

    return ccx, ccy


def draw_labels(canvas, holo, R, ccx, ccy, f):
    for text, point, side in holo.labels:
        p = np.array(point, dtype=np.float64)
        rotated = p.dot(R.T)
        z = max(rotated[2] + CAM_DIST, 0.6)
        s = f / z
        ax = int(ccx + rotated[0] * s)
        ay = int(ccy - rotated[1] * s)
        if side == 'right':
            elbow = (ax + 55, ay - 30)
            line_end = (elbow[0] + 150, elbow[1])
            text_pos = (line_end[0] + 6, line_end[1] + 4)
        else:
            elbow = (ax - 55, ay - 30)
            line_end = (elbow[0] - 150, elbow[1])
            size = cv2.getTextSize(text, FONT, 0.4, 1)[0]
            text_pos = (line_end[0] - size[0] - 6, line_end[1] + 4)
        cv2.circle(canvas, (ax, ay), 3, ACCENT, -1, cv2.LINE_AA)
        cv2.line(canvas, (ax, ay), elbow, SECOND, 1, cv2.LINE_AA)
        cv2.line(canvas, elbow, line_end, SECOND, 1, cv2.LINE_AA)
        cv2.putText(canvas, text, text_pos, FONT, 0.4, MAIN, 1, cv2.LINE_AA)


# ============================================================
# GESTURE RECOGNITION
# ============================================================

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def finger_states(lm):
    def d(i, j):
        return math.hypot(lm[i][0] - lm[j][0], lm[i][1] - lm[j][1])
    thumb_ext = d(4, 17) > d(2, 17) * THUMB_EXT_RATIO
    idx_up = lm[8][1] < lm[6][1]
    mid_up = lm[12][1] < lm[10][1]
    ring_up = lm[16][1] < lm[14][1]
    pinky_up = lm[20][1] < lm[18][1]
    return thumb_ext, idx_up, mid_up, ring_up, pinky_up


def normalized_pinch_dist(lm):
    hand_size = dist(lm[0], lm[9]) + 1e-6
    return dist(lm[4], lm[8]) / hand_size


def is_pinching(lm):
    return normalized_pinch_dist(lm) < PINCH_RATIO


def pinch_midpoint(lm):
    return ((lm[4][0] + lm[8][0]) / 2.0, (lm[4][1] + lm[8][1]) / 2.0)


def classify_gesture(lm):
    if lm is None:
        return 'NONE'
    if is_pinching(lm):
        return 'PINCH'
    thumb_ext, idx_up, mid_up, ring_up, pinky_up = finger_states(lm)
    if thumb_ext and idx_up and mid_up and ring_up and pinky_up:
        return 'FIVE'
    if idx_up and mid_up and ring_up and not pinky_up:
        return 'THREE'
    if idx_up and mid_up and not ring_up and not pinky_up:
        return 'TWO'
    if idx_up and not mid_up and not ring_up and not pinky_up:
        return 'ONE'
    return 'OTHER'


class GestureController:
    def __init__(self, num_pages):
        self.num_pages = num_pages
        self.page = 1
        self.selected = False
        self.history = deque(maxlen=DEBOUNCE_LEN)
        self.stable_gesture = 'NONE'
        self.prev_discrete = 'NONE'
        self.last_action_time = 0.0
        self.status_message = "SYSTEM READY"
        self.raw_gesture_display = "NONE"
        self.tracking_status = "NO SIGNAL"

        self.smoothed_hand_pos = None

        self.two_hand_active = False
        self.two_hand_base_dist = 0.0
        self.two_hand_base_zoom = 1.0
        self.two_hand_base_angle = 0.0
        self.two_hand_base_yaw = 0.0

        self.transition_active = False
        self.transition_start = 0.0

    def stabilize(self, raw):
        self.history.append(raw)
        if self.history.count(raw) >= DEBOUNCE_MIN:
            self.stable_gesture = raw
        return self.stable_gesture

    def _smooth_hand(self, pos):
        if self.smoothed_hand_pos is None:
            self.smoothed_hand_pos = pos
        else:
            a = HAND_SMOOTH
            self.smoothed_hand_pos = (
                self.smoothed_hand_pos[0] + (pos[0] - self.smoothed_hand_pos[0]) * a,
                self.smoothed_hand_pos[1] + (pos[1] - self.smoothed_hand_pos[1]) * a,
            )
        return self.smoothed_hand_pos

    def _end_two_hand(self, obj):
        if self.two_hand_active:
            self.two_hand_active = False
            obj.grabbed = False

    def _trigger_transition(self, now):
        self.transition_active = True
        self.transition_start = now

    def update(self, hands_landmarks, now, holograms):
        n = len(hands_landmarks)
        self.tracking_status = "ACTIVE" if n > 0 else "NO SIGNAL"
        obj = holograms[self.page - 1]

        if n == 1:
            lm = hands_landmarks[0]
            raw = classify_gesture(lm)
            stable = self.stabilize(raw)
            self._end_two_hand(obj)

            if stable == 'PINCH':
                if self.selected:
                    hand_pos = self._smooth_hand(pinch_midpoint(lm))
                    if not obj.grabbed:
                        obj.begin_grab(hand_pos)
                        self.status_message = "GRABBED"
                    else:
                        obj.update_grab(hand_pos)
                        self.status_message = "MANIPULATING"
                else:
                    if obj.grabbed:
                        obj.end_grab()
                    self.smoothed_hand_pos = None
                    self.status_message = "SELECT OBJECT FIRST (3 FINGERS)"
            else:
                if obj.grabbed:
                    obj.end_grab()
                self.smoothed_hand_pos = None

                if stable in ('ONE', 'TWO', 'THREE') and stable != self.prev_discrete:
                    if now - self.last_action_time >= COOLDOWN:
                        if stable == 'ONE':
                            self.page = min(self.num_pages, self.page + 1)
                            self.selected = False
                            self.status_message = "NEXT HOLOGRAM"
                            self._trigger_transition(now)
                        elif stable == 'TWO':
                            self.page = max(1, self.page - 1)
                            self.selected = False
                            self.status_message = "PREVIOUS HOLOGRAM"
                            self._trigger_transition(now)
                        else:  # THREE
                            self.selected = not self.selected
                            self.status_message = "SELECTED" if self.selected else "DESELECTED"
                        self.last_action_time = now
                    else:
                        self.status_message = "COOLDOWN ACTIVE"
                elif stable == 'FIVE':
                    self.status_message = "OPEN PALM - SYSTEM READY"
                elif stable == 'NONE':
                    self.status_message = "NO HAND DETECTED"
                elif stable == 'OTHER':
                    self.status_message = "STANDBY"

            self.prev_discrete = stable
            self.raw_gesture_display = raw

        elif n == 2:
            self.history.clear()
            self.prev_discrete = 'NONE'
            lm0, lm1 = hands_landmarks[0], hands_landmarks[1]
            pinch0, pinch1 = is_pinching(lm0), is_pinching(lm1)

            if pinch0 and pinch1:
                if obj.grabbed and not self.two_hand_active:
                    obj.end_grab()
                self.smoothed_hand_pos = None
                p0, p1 = pinch_midpoint(lm0), pinch_midpoint(lm1)
                d = dist(p0, p1)
                ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
                if self.selected:
                    if not self.two_hand_active:
                        self.two_hand_active = True
                        obj.grabbed = True
                        self.two_hand_base_dist = max(d, 1e-4)
                        self.two_hand_base_zoom = obj.zoom
                        self.two_hand_base_angle = ang
                        self.two_hand_base_yaw = obj.yaw
                        self.status_message = "ZOOM LOCK"
                    else:
                        ratio = d / self.two_hand_base_dist
                        target_zoom = clamp(self.two_hand_base_zoom * ratio, ZOOM_MIN, ZOOM_MAX)
                        obj.zoom += (target_zoom - obj.zoom) * ZOOM_SMOOTHING
                        d_ang = ang - self.two_hand_base_angle
                        target_yaw = self.two_hand_base_yaw + d_ang * ROT2_SENSITIVITY
                        obj.yaw += (target_yaw - obj.yaw) * ZOOM_SMOOTHING
                        self.status_message = "ZOOM {}%".format(int(obj.zoom * 100))
                else:
                    self._end_two_hand(obj)
                    self.status_message = "SELECT OBJECT TO ZOOM"
                self.raw_gesture_display = "TWO-HAND PINCH"
            else:
                self._end_two_hand(obj)
                active_lm = lm0 if pinch0 else (lm1 if pinch1 else None)
                if active_lm is not None and self.selected:
                    hand_pos = self._smooth_hand(pinch_midpoint(active_lm))
                    if not obj.grabbed:
                        obj.begin_grab(hand_pos)
                        self.status_message = "GRABBED"
                    else:
                        obj.update_grab(hand_pos)
                        self.status_message = "MANIPULATING"
                    self.raw_gesture_display = "PINCH"
                else:
                    if obj.grabbed:
                        obj.end_grab()
                    self.smoothed_hand_pos = None
                    self.status_message = "TWO HANDS DETECTED"
                    self.raw_gesture_display = "TWO HANDS"

        else:  # n == 0
            self._end_two_hand(obj)
            if obj.grabbed:
                obj.end_grab()
            self.smoothed_hand_pos = None
            self.history.clear()
            self.prev_discrete = 'NONE'
            self.status_message = "NO HAND DETECTED"
            self.raw_gesture_display = "NONE"

        return holograms[self.page - 1]


# ============================================================
# HUD / BACKGROUND RENDERING
# ============================================================

def prep_background(frame_big):
    bg = frame_big.astype(np.float32)
    bg *= 0.22
    bg[:, :, 0] = np.clip(bg[:, :, 0] * 1.3, 0, 255)  # boost blue channel (cool tone)
    return bg.astype(np.uint8)


def draw_perspective_grid(canvas, cx, floor_y):
    color = (70, 45, 15)
    vp = (cx, floor_y - 260)
    for i in range(-4, 5):
        x_bottom = cx + i * 90
        cv2.line(canvas, (x_bottom, floor_y + 140), (vp[0] + i * 14, vp[1]), color, 1, cv2.LINE_AA)
    for j in range(1, 6):
        y = floor_y + j * 22
        half_w = 40 + j * 55
        cv2.line(canvas, (cx - half_w, y), (cx + half_w, y), color, 1, cv2.LINE_AA)


def draw_hand_skeleton(canvas, pts_px):
    connections = mp.solutions.hands.HAND_CONNECTIONS
    for a, b in connections:
        cv2.line(canvas, pts_px[a], pts_px[b], (255, 200, 60), 1, cv2.LINE_AA)
    for p in pts_px:
        cv2.circle(canvas, p, 2, (255, 255, 255), -1, cv2.LINE_AA)


def draw_scan_and_rings(canvas, cx, cy, t, selected):
    """Layered circular 'iris' HUD in the classic Jarvis style: a static
    outer ring, a clock-style tick ring, two counter-rotating dashed rings,
    a handful of orbiting marker dots, and a rotating radar-style sweep
    with a fading trail. All pure line/ellipse draws -- cheap on low-end
    hardware."""
    ring_color = SELECT_COLOR if selected else MAIN
    dim_color = tuple(int(c * 0.45) for c in SECOND)

    r_outer = 232      # static faint outer boundary
    r_tick = 210        # clock-tick ring
    r_dash1 = 190        # inner dashed ring (rotates one way)
    r_dash2 = 166        # second dashed ring (rotates the other way)
    r_orbit = 202        # radius of orbiting marker dots
    r_sweep = 210        # radar sweep reach

    # --- static faint outer boundary ---
    cv2.circle(canvas, (cx, cy), r_outer, dim_color, 1, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), r_outer + 6, dim_color, 1, cv2.LINE_AA)

    # --- clock-style tick ring (72 ticks, every 6th longer/brighter) ---
    for i in range(72):
        ang = math.radians(i * 5)
        long_tick = (i % 6 == 0)
        length = 13 if long_tick else 5
        col = ring_color if long_tick else dim_color
        x1 = cx + r_tick * math.cos(ang); y1 = cy + r_tick * math.sin(ang)
        x2 = cx + (r_tick + length) * math.cos(ang); y2 = cy + (r_tick + length) * math.sin(ang)
        cv2.line(canvas, (int(x1), int(y1)), (int(x2), int(y2)), col, 1, cv2.LINE_AA)

    # --- two counter-rotating dashed rings (depth / parallax feel) ---
    ang1 = int((t * 40) % 360)
    for k in range(0, 360, 30):
        a0 = (k + ang1) % 360
        cv2.ellipse(canvas, (cx, cy), (r_dash1, r_dash1), 0, a0, a0 + 14, ring_color, 1, cv2.LINE_AA)

    ang2 = int((-t * 27) % 360)
    for k in range(0, 360, 18):
        a0 = (k + ang2) % 360
        cv2.ellipse(canvas, (cx, cy), (r_dash2, r_dash2), 0, a0, a0 + 7, SECOND, 1, cv2.LINE_AA)

    # --- orbiting marker dots ---
    for k in range(4):
        oang = t * 0.5 + k * (math.pi / 2.0)
        ox = int(cx + r_orbit * math.cos(oang))
        oy = int(cy + r_orbit * math.sin(oang))
        cv2.circle(canvas, (ox, oy), 3, ACCENT, -1, cv2.LINE_AA)
        cv2.circle(canvas, (ox, oy), 6, ring_color, 1, cv2.LINE_AA)

    # --- rotating radar sweep with a fading trail ---
    sweep_ang = (t * 0.9) % (2 * math.pi)
    trail_steps = 8
    for k in range(trail_steps):
        a = sweep_ang - k * 0.055
        fade = 1.0 - (k / float(trail_steps))
        col = tuple(int(c * fade) for c in ring_color)
        x2 = int(cx + r_sweep * math.cos(a)); y2 = int(cy + r_sweep * math.sin(a))
        cv2.line(canvas, (cx, cy), (x2, y2), col, 1, cv2.LINE_AA)

    # --- cardinal degree ticks with small labels ---
    for deg in (0, 90, 180, 270):
        rad = math.radians(deg - 90)
        x1 = int(cx + (r_outer + 12) * math.cos(rad)); y1 = int(cy + (r_outer + 12) * math.sin(rad))
        x2 = int(cx + (r_outer + 26) * math.cos(rad)); y2 = int(cy + (r_outer + 26) * math.sin(rad))
        cv2.line(canvas, (x1, y1), (x2, y2), SECOND, 1, cv2.LINE_AA)

    # --- center crosshair ---
    cv2.line(canvas, (cx - 14, cy), (cx - 4, cy), ring_color, 1, cv2.LINE_AA)
    cv2.line(canvas, (cx + 4, cy), (cx + 14, cy), ring_color, 1, cv2.LINE_AA)
    cv2.line(canvas, (cx, cy - 14), (cx, cy - 4), ring_color, 1, cv2.LINE_AA)
    cv2.line(canvas, (cx, cy + 4), (cx, cy + 14), ring_color, 1, cv2.LINE_AA)

    if selected:
        cv2.putText(canvas, "TARGET LOCK", (cx - 64, cy - r_outer - 26), FONT, 0.55, SELECT_COLOR, 1, cv2.LINE_AA)


def draw_target_brackets(canvas, cx, cy, size, color):
    L = 34
    corners = [(cx - size, cy - size, 1, 1), (cx + size, cy - size, -1, 1),
               (cx - size, cy + size, 1, -1), (cx + size, cy + size, -1, -1)]
    for x, y, sx, sy in corners:
        cv2.line(canvas, (x, y), (x + sx * L, y), color, 2, cv2.LINE_AA)
        cv2.line(canvas, (x, y), (x, y + sy * L), color, 2, cv2.LINE_AA)


def draw_particles(canvas, cx, cy, t, count=10):
    for i in range(count):
        ang = t * 0.6 + i * (2 * math.pi / count)
        rad = 150 + 30 * math.sin(t * 1.3 + i)
        x = int(cx + rad * math.cos(ang))
        y = int(cy + rad * math.sin(ang) * 0.55)
        cv2.circle(canvas, (x, y), 2, ACCENT, -1, cv2.LINE_AA)


def draw_title(canvas):
    w = canvas.shape[1]
    t1, t2 = "J.A.R.V.I.S.", "HOLOGRAPHIC ENGINEERING SYSTEM"
    cv2.putText(canvas, t1, (w // 2 - 115, 44), FONT, 1.1, (40, 30, 10), 3, cv2.LINE_AA)
    cv2.putText(canvas, t1, (w // 2 - 115, 44), FONT, 1.1, MAIN, 1, cv2.LINE_AA)
    cv2.putText(canvas, t2, (w // 2 - 175, 68), FONT, 0.55, SECOND, 1, cv2.LINE_AA)
    cv2.line(canvas, (50, 80), (w - 50, 80), (120, 90, 20), 1, cv2.LINE_AA)


def draw_side_panels(canvas, controller, obj, t, fps):
    h, w = canvas.shape[:2]
    rot_deg = int(math.degrees(obj.yaw) % 360)
    zoom_pct = int(obj.zoom * 100)
    scan_pct = int((t * 15) % 100)
    left = [
        "PAGE {}/5".format(controller.page),
        "OBJECT: {}".format(obj.name),
        "SYSTEM: ONLINE",
        "TRACKING: {}".format(controller.tracking_status),
    ]
    right = [
        "SCAN: {}%".format(scan_pct),
        "ZOOM: {}%".format(zoom_pct),
        "ROTATION: {:03d} DEG".format(rot_deg),
        "FPS: {:0.0f}".format(fps),
    ]
    for i, line in enumerate(left):
        cv2.putText(canvas, line, (28, 112 + i * 26), FONT, 0.5, SECOND, 1, cv2.LINE_AA)
    for i, line in enumerate(right):
        size = cv2.getTextSize(line, FONT, 0.5, 1)[0]
        cv2.putText(canvas, line, (w - 40 - size[0], 112 + i * 26), FONT, 0.5, SECOND, 1, cv2.LINE_AA)


def draw_bottom_status(canvas, controller, cooldown_remaining):
    h = canvas.shape[0]
    y0 = h - 66
    lines = [
        "GESTURE: {}".format(controller.raw_gesture_display),
        "STATUS: {}   {}".format("SELECTED" if controller.selected else "STANDBY", controller.status_message),
        "COOLDOWN: {:0.1f}s".format(cooldown_remaining),
    ]
    for i, line in enumerate(lines):
        cv2.putText(canvas, line, (28, y0 + i * 22), FONT, 0.5, MAIN, 1, cv2.LINE_AA)


def get_perf_level(fps):
    if fps < 18:
        return 0
    if fps < 24:
        return 1
    return 2


# ============================================================
# MAIN
# ============================================================

def main():
    cap = cv2.VideoCapture(CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("ERROR: could not open webcam at index", CAM_INDEX)
        return

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        model_complexity=MODEL_COMPLEXITY,
        max_num_hands=2,
        min_detection_confidence=MIN_DETECTION_CONF,
        min_tracking_confidence=MIN_TRACKING_CONF,
    )

    holograms = [Hologram(name, builder) for name, builder in zip(PAGE_NAMES, HOLOGRAM_BUILDERS)]
    controller = GestureController(len(holograms))

    effect_layer = np.zeros((DISPLAY_H, DISPLAY_W, 3), dtype=np.uint8)

    prev_time = time.time()
    fps = 0.0

    window_name = "J.A.R.V.I.S. HOLOGRAPHIC ENGINEERING SYSTEM"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, DISPLAY_W, DISPLAY_H)

    cx, cy = DISPLAY_W // 2, DISPLAY_H // 2 + 10

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            if frame.shape[1] != CAM_W or frame.shape[0] != CAM_H:
                frame = cv2.resize(frame, (CAM_W, CAM_H))

            # Mirror ONCE; use this same mirrored frame for both MediaPipe
            # processing and display so gesture math stays consistent with
            # what's on screen.
            frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = hands.process(rgb)

            hands_landmarks = []
            hands_px = []
            if results.multi_hand_landmarks:
                for hand_lms in results.multi_hand_landmarks:
                    lm = [(p.x, p.y) for p in hand_lms.landmark]
                    hands_landmarks.append(lm)
                    hands_px.append([(int(p.x * DISPLAY_W), int(p.y * DISPLAY_H)) for p in hand_lms.landmark])

            now = time.time()
            current_obj = controller.update(hands_landmarks, now, holograms)
            current_obj.update_auto()

            big_frame = cv2.resize(frame, (DISPLAY_W, DISPLAY_H))
            canvas = prep_background(big_frame)

            draw_perspective_grid(canvas, cx, cy + 230)

            for pts_px in hands_px:
                draw_hand_skeleton(canvas, pts_px)

            bob = math.sin(now * 0.6) * 6
            ccx = cx + current_obj.ox
            ccy = cy + current_obj.oy + bob

            fps_int = fps if fps > 0 else 30
            perf_level = get_perf_level(fps_int)

            draw_scan_and_rings(canvas, ccx, ccy, now, controller.selected)
            draw_target_brackets(canvas, ccx, ccy, 300,
                                  SELECT_COLOR if controller.selected else MAIN)
            if perf_level >= 1:
                draw_particles(canvas, ccx, ccy, now, count=(14 if perf_level == 2 else 8))

            alpha = 1.0
            if controller.transition_active:
                progress = min(1.0, (now - controller.transition_start) / TRANSITION_DURATION)
                alpha = progress
                if progress >= 1.0:
                    controller.transition_active = False

            render_object(canvas, effect_layer, current_obj, cx, cy, now, perf_level, alpha)

            if controller.transition_active:
                sweep_y = int(ccy - 260 + (alpha * 520))
                cv2.line(canvas, (ccx - 260, sweep_y), (ccx + 260, sweep_y), (255, 255, 255), 2, cv2.LINE_AA)

            draw_title(canvas)
            draw_side_panels(canvas, controller, current_obj, now, fps_int)
            cooldown_remaining = max(0.0, COOLDOWN - (now - controller.last_action_time))
            draw_bottom_status(canvas, controller, cooldown_remaining)

            dt = now - prev_time
            prev_time = now
            if dt > 0:
                inst_fps = 1.0 / dt
                fps = inst_fps if fps == 0 else (fps * 0.9 + inst_fps * 0.1)

            cv2.imshow(window_name, canvas)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q')):
                break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        hands.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
