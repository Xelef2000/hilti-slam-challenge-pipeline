#!/usr/bin/env python3
"""Extract the map->global static TF from a rosbag and write orientation.json.

Executed inside the ROS container. Reads the bag mounted at /input directly via
rosbag2_py (no ROS daemon required) and writes /output/orientation.json in the
same format produced by save_tf.py in the Floorplan-Alignment repo.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

OUTPUT = Path("/output/orientation.json")
BAG_PATH = "/input"
PARENT_FRAME = "map"
CHILD_FRAME = "global"


def quat_xyzw_to_rotmat(qx, qy, qz, qw):
    n = qx * qx + qy * qy + qz * qz + qw * qw
    if n < 1e-12:
        return np.eye(3)
    s = 2.0 / n
    xx, yy, zz = qx * qx * s, qy * qy * s, qz * qz * s
    xy, xz, yz = qx * qy * s, qx * qz * s, qy * qz * s
    wx, wy, wz = qw * qx * s, qw * qy * s, qw * qz * s
    return np.array([
        [1.0 - (yy + zz),       xy - wz,         xz + wy],
        [xy + wz,               1.0 - (xx + zz), yz - wx],
        [xz - wy,               yz + wx,         1.0 - (xx + yy)],
    ])


def main():
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from tf2_msgs.msg import TFMessage
    except ImportError as exc:
        print(f"[save_tf] ERROR: Missing ROS2 dependency: {exc}", flush=True)
        sys.exit(1)

    print(f"[save_tf] Opening bag: {BAG_PATH}", flush=True)
    reader = rosbag2_py.SequentialReader()
    storage_options = rosbag2_py.StorageOptions(uri=BAG_PATH, storage_id="")
    converter_options = rosbag2_py.ConverterOptions("cdr", "cdr")
    reader.open(storage_options, converter_options)

    storage_filter = rosbag2_py.StorageFilter(topics=["/tf_static"])
    reader.set_filter(storage_filter)

    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic != "/tf_static":
            continue
        msg = deserialize_message(data, TFMessage)
        for tf in msg.transforms:
            if tf.header.frame_id != PARENT_FRAME or tf.child_frame_id != CHILD_FRAME:
                continue

            tx = tf.transform.translation.x
            ty = tf.transform.translation.y
            tz = tf.transform.translation.z
            qx = tf.transform.rotation.x
            qy = tf.transform.rotation.y
            qz = tf.transform.rotation.z
            qw = tf.transform.rotation.w

            T = np.eye(4)
            T[:3, :3] = quat_xyzw_to_rotmat(qx, qy, qz, qw)
            T[:3, 3] = [tx, ty, tz]
            yaw = float(np.arctan2(T[1, 0], T[0, 0]))

            payload = {
                "parent_frame": PARENT_FRAME,
                "child_frame": CHILD_FRAME,
                "translation_xyz": [tx, ty, tz],
                "quaternion_xyzw": [qx, qy, qz, qw],
                "yaw_rad": yaw,
                "yaw_deg": float(np.degrees(yaw)),
                "T_parent_child": T.tolist(),
            }
            OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"[save_tf] Saved {PARENT_FRAME} -> {CHILD_FRAME} transform to {OUTPUT}", flush=True)
            print(f"[save_tf] Yaw: {math.degrees(yaw):.3f} deg", flush=True)
            print(f"[save_tf] Translation: x={tx:.6f}, y={ty:.6f}, z={tz:.6f}", flush=True)
            sys.exit(0)

    print(
        f"[save_tf] ERROR: '{PARENT_FRAME}' -> '{CHILD_FRAME}' not found in /tf_static",
        flush=True,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
