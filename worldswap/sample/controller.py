"""Sensor-based autopilot for a vertically propelled landing vehicle."""

def control(s):
    def clip(v, lo, hi):
        return max(lo, min(hi, v))

    g = max(0.0, float(s['gravity']))
    wind = float(s['wind'])
    ml = max(0.0, float(s['max_lateral']))
    mt = max(0.0, float(s['max_thrust']))
    dx = float(s['pad_x']) - float(s['x'])
    vx = float(s['vx'])

    # A damped position servo, with wind feed-forward.  The velocity term
    # makes the vehicle brake before crossing the pad rather than chasing it.
    lateral = 0.95 * dx - 2.6 * vx - wind
    lateral = clip(lateral, -ml, ml)

    # Ask for a speed which can be stopped in the remaining height.  This
    # deliberately becomes a gentle descent close to the ground.
    height = max(0.0, float(s['y']) - float(s['pad_y']))
    braking = max(1.0, min(mt + g, 2.0 * max(1.0, mt - g)))
    safe_speed = (2.0 * braking * height) ** 0.5
    desired_vy = -min(10.0, safe_speed)
    # Gravity is compensated explicitly, so this works at any gravity.
    thrust = g + 2.8 * (desired_vy - float(s['vy']))
    thrust = clip(thrust, 0.0, mt)
    return lateral, thrust
