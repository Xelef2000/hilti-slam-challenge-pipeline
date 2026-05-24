#!/usr/bin/env python3
"""Extract a representative image frame from a ROS2 bag for window inference."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import rosbag2_py
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def unique_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen or not item:
            continue
        ordered.append(item)
        seen.add(item)
    return ordered


def open_reader(bag_path: Path) -> rosbag2_py.SequentialReader:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    return reader


def decode_image(message, msg_type: str, bridge: CvBridge) -> np.ndarray:
    if msg_type == "sensor_msgs/msg/CompressedImage":
        array = np.frombuffer(message.data, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("Failed to decode CompressedImage payload")
        return image

    if msg_type == "sensor_msgs/msg/Image":
        if message.encoding.lower() in {"rgb8", "rgba8"}:
            return bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
        if message.encoding.lower() in {"mono8", "8uc1"}:
            gray = bridge.imgmsg_to_cv2(message, desired_encoding="mono8")
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")

    raise RuntimeError(f"Unsupported image message type: {msg_type}")


def main() -> int:
    args = json.loads(sys.argv[1])
    bag_path = Path(args["bag_path"])
    output_image_path = Path(args["output_image_path"])
    source_metadata_path = Path(args["source_metadata_path"])
    requested_frame_index = int(args.get("frame_index", -1))
    preferred_topics = unique_preserving_order(args["preferred_topics"])

    reader = open_reader(bag_path)
    topic_types = {
        topic.name: topic.type for topic in reader.get_all_topics_and_types()
    }

    selected_topic = None
    for topic in preferred_topics:
        if topic in topic_types:
            selected_topic = topic
            break

    if selected_topic is None:
        available = ", ".join(sorted(topic_types))
        raise RuntimeError(
            "No suitable image topic found in bag. Tried: "
            f"{preferred_topics}. Available topics: {available}"
        )

    selected_type = topic_types[selected_topic]
    if selected_type not in {
        "sensor_msgs/msg/CompressedImage",
        "sensor_msgs/msg/Image",
    }:
        raise RuntimeError(
            f"Selected topic {selected_topic} has unsupported type {selected_type}"
        )

    total_messages = 0
    while reader.has_next():
        topic_name, _, _ = reader.read_next()
        if topic_name == selected_topic:
            total_messages += 1

    if total_messages == 0:
        raise RuntimeError(f"No messages found on selected topic: {selected_topic}")

    if requested_frame_index < 0:
        selected_index = total_messages // 2
    else:
        selected_index = min(requested_frame_index, total_messages - 1)

    reader = open_reader(bag_path)
    message_class = get_message(selected_type)
    bridge = CvBridge()
    current_index = -1
    selected_stamp = None
    selected_image = None

    while reader.has_next():
        topic_name, data, timestamp = reader.read_next()
        if topic_name != selected_topic:
            continue
        current_index += 1
        if current_index != selected_index:
            continue
        message = deserialize_message(data, message_class)
        selected_image = decode_image(message, selected_type, bridge)
        selected_stamp = int(timestamp)
        break

    if selected_image is None:
        raise RuntimeError(
            f"Failed to extract frame {selected_index} from topic {selected_topic}"
        )

    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_image_path), selected_image):
        raise RuntimeError(f"Failed to write extracted image to {output_image_path}")

    metadata = {
        "schema_version": 1,
        "bag_path": str(bag_path),
        "selected_topic": selected_topic,
        "selected_type": selected_type,
        "requested_frame_index": requested_frame_index,
        "selected_frame_index": selected_index,
        "total_topic_messages": total_messages,
        "timestamp_ns": selected_stamp,
        "image_path": str(output_image_path),
        "shape": list(selected_image.shape),
    }
    source_metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"[windows_extract] Topic: {selected_topic}")
    print(f"[windows_extract] Selected frame: {selected_index}/{total_messages - 1}")
    print(f"[windows_extract] Output: {output_image_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
