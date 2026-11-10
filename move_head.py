"""Gentle head demo: nod, look left/right, tilt, return to centre."""
import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

with ReachyMini(media_backend="no_media") as mini:
    centre = create_head_pose()
    mini.goto_target(head=centre, duration=1.0)

    # Nod: look down then up
    for pitch in (15, -10, 0):
        mini.goto_target(head=create_head_pose(pitch=pitch, degrees=True), duration=0.8)

    # Look left and right
    for yaw in (30, -30, 0):
        mini.goto_target(head=create_head_pose(yaw=yaw, degrees=True), duration=1.0)

    # Curious tilt with antennas
    mini.goto_target(
        head=create_head_pose(roll=15, degrees=True),
        antennas=np.deg2rad([30, -30]),
        duration=1.0,
    )
    mini.goto_target(head=centre, antennas=[0, 0], duration=1.0)
    print("done")
