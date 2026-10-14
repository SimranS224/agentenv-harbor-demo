# Repair a portable landing autopilot

Edit /app/src/controller.py so the same control(state) implementation safely lands
the probe at the pad across environments with different gravity and crosswind.
The existing code is tuned to one world and may hover or drift in another.
Use sensor values, not world-name branching or hard-coded answers.

state contains x,y,vx,vy,pad_x,pad_y,gravity (positive downward acceleration),
wind (constant horizontal acceleration), max_thrust and max_lateral.
Return (horizontal acceleration command, upward thrust acceleration).
Net acceleration is (command_x + wind, thrust - gravity). The simulator clips
commands to +/-max_lateral and 0..max_thrust. Body mass is one and angle is fixed.
The controller is called at 60 Hz. Preserve the interface and do not edit engine
or world files. No external dependencies are required for the controller.

Success means first ground contact within 12 units of the pad center,
abs(vx)<=8 and abs(vy)<=12, within 45 seconds. Stabilize lateral position before
final descent. Do not require mutable state across calls. Example worlds and
simulate.py are available in /app for your own tests; grading is independent.

This is our demo integration using Pymunk, not a seeded bug in upstream Pymunk.
