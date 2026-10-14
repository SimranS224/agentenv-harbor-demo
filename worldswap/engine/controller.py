"""Demo landing autopilot. Tuned for one world; needs to work across worlds."""
def control(s):
    def clip(v, lo, hi): return max(lo, min(hi, v))
    dx = s['pad_x'] - s['x']
    target_vx = clip(dx * 0.8, -35, 35)
    lateral = clip((target_vx - s['vx']) * 2.5, -s['max_lateral'], s['max_lateral'])
    target_y = 150 if abs(dx) > 25 else s['pad_y'] - 2
    target_vy = clip((target_y - s['y']) * 0.8, -30, 30)
    thrust = clip(80 + (target_vy - s['vy']) * 3, 0, s['max_thrust'])
    return lateral, thrust
