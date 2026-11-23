"""
Functional Analog Clock using Python's built-in turtle graphics library.

Features:
- Centered circular dial with 60 tick marks and 12 crisp hour numerals (1-12)
- Hour, minute, and second hands with continuous angular interpolation
- Flicker-free rendering using screen.tracer(0) and separate static/dynamic turtles
- Non-blocking event loop updates via screen.ontimer()
- Bonus controls: digital time + date readout, smooth second-hand toggle ('s'),
  pause/resume ('space'), and selectable time zone offsets (Left/Right arrows)
"""

from datetime import datetime, timedelta, timezone
import math
import turtle


# Visual palette and layout constants (centered at (0, 0))
CLOCK_RADIUS = 220
BG_COLOR = "#F8FAFC"
DIAL_FILL = "#FFFFFF"
DIAL_BORDER = "#0F172A"
TICK_MAJOR_COLOR = "#0F172A"
TICK_MINOR_COLOR = "#94A3B8"
NUMERAL_COLOR = "#0F172A"
HOUR_HAND_COLOR = "#0F172A"
MINUTE_HAND_COLOR = "#1E293B"
SECOND_HAND_COLOR = "#DC2626"
ACCENT_TEXT_COLOR = "#475569"

# Timezone presets: (label, UTC offset in hours or None for local system time)
TIMEZONES = [
    ("LOCAL", None),
    ("UTC", 0.0),
    ("EST (UTC-5)", -5.0),
    ("GMT (UTC+0)", 0.0),
    ("CET (UTC+1)", 1.0),
    ("EAT (UTC+3)", 3.0),
    ("IST (UTC+5:30)", 5.5),
    ("JST (UTC+9)", 9.0),
]

# Mutable runtime state for interactive controls
state = {
    "paused": False,
    "smooth_seconds": False,
    "tz_index": 0,
}


def setup_screen() -> turtle.Screen:
    """Initialize and configure the turtle graphics window."""
    screen = turtle.Screen()
    screen.title("Functional Analog Clock — Python Turtle")
    screen.bgcolor(BG_COLOR)
    screen.setup(width=680, height=720)
    # Disable automatic animation so each frame updates atomically with screen.update()
    screen.tracer(0)
    return screen


def create_pen(color: str = DIAL_BORDER) -> turtle.Turtle:
    """Create a hidden turtle pen configured for fast geometric drawing."""
    pen = turtle.Turtle(visible=False)
    pen.speed(0)
    pen.color(color)
    pen.penup()
    return pen


def clock_to_cartesian(clock_deg: float, radius: float) -> tuple[float, float]:
    """
    Convert a clockwise angle measured from 12 o'clock (0 deg at +Y axis)
    into standard Cartesian coordinates (x, y) centered at (0, 0).

    Standard math angles increase counter-clockwise from +X (3 o'clock = 0 deg),
    so theta = 90 - clock_deg maps 12 o'clock -> 90 deg and 3 o'clock -> 0 deg.
    """
    theta_rad = math.radians(90.0 - clock_deg)
    x = radius * math.cos(theta_rad)
    y = radius * math.sin(theta_rad)
    return x, y


def draw_face(face_pen: turtle.Turtle, radius: float = CLOCK_RADIUS) -> None:
    """Draw the static circular dial, 60 tick marks, and hour numerals 1-12."""
    face_pen.clear()

    # Outer bezel shadow ring and main circular dial
    face_pen.goto(0, -(radius + 10))
    face_pen.pensize(2)
    face_pen.color("#CBD5E1", "#E2E8F0")
    face_pen.begin_fill()
    face_pen.pendown()
    face_pen.circle(radius + 10)
    face_pen.end_fill()
    face_pen.penup()

    face_pen.goto(0, -radius)
    face_pen.pensize(3)
    face_pen.color(DIAL_BORDER, DIAL_FILL)
    face_pen.begin_fill()
    face_pen.pendown()
    face_pen.circle(radius)
    face_pen.end_fill()
    face_pen.penup()

    # Inner subtle reference ring
    face_pen.goto(0, -(radius - 14))
    face_pen.pensize(1)
    face_pen.color("#E2E8F0")
    face_pen.pendown()
    face_pen.circle(radius - 14)
    face_pen.penup()

    # 60 tick marks around the perimeter (6 degrees per minute/second)
    for tick in range(60):
        angle_deg = tick * 6.0
        is_hour_mark = (tick % 5 == 0)

        outer_r = radius - 8
        inner_r = radius - (24 if is_hour_mark else 16)

        x_start, y_start = clock_to_cartesian(angle_deg, inner_r)
        x_end, y_end = clock_to_cartesian(angle_deg, outer_r)

        face_pen.pensize(3 if is_hour_mark else 1)
        face_pen.color(TICK_MAJOR_COLOR if is_hour_mark else TICK_MINOR_COLOR)
        face_pen.goto(x_start, y_start)
        face_pen.pendown()
        face_pen.goto(x_end, y_end)
        face_pen.penup()

    # 12 hour numerals positioned inside the hour tick marks
    numeral_radius = radius - 44
    face_pen.color(NUMERAL_COLOR)
    for hour in range(1, 13):
        angle_deg = hour * 30.0
        nx, ny = clock_to_cartesian(angle_deg, numeral_radius)
        face_pen.goto(nx, ny - 11)  # Vertical optical centering for 16pt font
        face_pen.write(
            str(hour),
            align="center",
            font=("Helvetica", 16, "bold"),
        )


def get_current_time() -> datetime:
    """Return local system time or the selected fixed-offset timezone."""
    _, offset_hours = TIMEZONES[state["tz_index"]]
    if offset_hours is None:
        return datetime.now()
    tz = timezone(timedelta(hours=offset_hours))
    return datetime.now(tz)


def calculate_angles(now: datetime, smooth_seconds: bool) -> tuple[float, float, float]:
    """
    Compute clockwise angles (in degrees from 12 o'clock) for all three hands.

    - Second hand: 6 deg/sec (plus microsecond fraction when smooth_seconds is True)
    - Minute hand: 6 deg/min + 0.1 deg/sec (smooth progression across the minute)
    - Hour hand:   30 deg/hour + 0.5 deg/min + (0.5/60) deg/sec
    """
    seconds = now.second + (now.microsecond / 1_000_000.0 if smooth_seconds else 0.0)
    minutes = now.minute + (seconds / 60.0)
    hours = (now.hour % 12) + (minutes / 60.0)

    second_angle = seconds * 6.0
    minute_angle = minutes * 6.0
    hour_angle = hours * 30.0
    return hour_angle, minute_angle, second_angle


def draw_hand(
    pen: turtle.Turtle,
    clock_deg: float,
    length: float,
    width: int,
    color: str,
    tail_length: float = 0.0,
) -> None:
    """Draw a single clock hand from the center (0, 0) at the given clockwise angle."""
    tip_x, tip_y = clock_to_cartesian(clock_deg, length)
    if tail_length > 0:
        tail_x, tail_y = clock_to_cartesian((clock_deg + 180.0) % 360.0, tail_length)
    else:
        tail_x, tail_y = 0.0, 0.0

    pen.pensize(width)
    pen.color(color)
    pen.goto(tail_x, tail_y)
    pen.pendown()
    pen.goto(tip_x, tip_y)
    pen.penup()


def draw_center_cap(pen: turtle.Turtle) -> None:
    """Draw the central pivot pin covering the hand origins."""
    pen.goto(0, -7)
    pen.color(DIAL_BORDER, DIAL_BORDER)
    pen.begin_fill()
    pen.pendown()
    pen.circle(7)
    pen.end_fill()
    pen.penup()

    pen.goto(0, -3)
    pen.color(SECOND_HAND_COLOR, SECOND_HAND_COLOR)
    pen.begin_fill()
    pen.pendown()
    pen.circle(3)
    pen.end_fill()
    pen.penup()


def draw_readout(pen: turtle.Turtle, now: datetime) -> None:
    """Render the digital time, date, timezone label, and keyboard shortcut hint."""
    tz_label, _ = TIMEZONES[state["tz_index"]]
    status_suffix = "  [PAUSED]" if state["paused"] else ""
    sweep_label = "Smooth" if state["smooth_seconds"] else "Tick 1s"

    # Subtle date badge inside upper-middle dial area
    pen.color(ACCENT_TEXT_COLOR)
    pen.goto(0, 62)
    pen.write(
        now.strftime("%a, %b %d, %Y").upper(),
        align="center",
        font=("Helvetica", 10, "bold"),
    )

    # Digital time readout inside lower-middle dial area
    pen.color(DIAL_BORDER)
    pen.goto(0, -96)
    pen.write(
        now.strftime("%I:%M:%S %p"),
        align="center",
        font=("Courier", 14, "bold"),
    )

    # Footer controls and active mode summary below the clock bezel
    pen.color(ACCENT_TEXT_COLOR)
    pen.goto(0, -(CLOCK_RADIUS + 46))
    pen.write(
        f"Zone: {tz_label}  |  Motion: {sweep_label}{status_suffix}",
        align="center",
        font=("Helvetica", 11, "bold"),
    )

    pen.color("#64748B")
    pen.goto(0, -(CLOCK_RADIUS + 70))
    pen.write(
        "Controls: [Space] Pause/Resume   [S] Smooth Second Hand   [Left/Right] Timezone",
        align="center",
        font=("Helvetica", 10, "normal"),
    )


def update_clock(screen: turtle.Screen, hand_pen: turtle.Turtle) -> None:
    """Clear dynamic hands, compute current angles, redraw frame, and schedule next tick."""
    if not state["paused"]:
        now = get_current_time()
        hour_deg, minute_deg, second_deg = calculate_angles(now, state["smooth_seconds"])

        hand_pen.clear()

        # Draw hour, minute, and second hands from shortest/thickest to longest/thinnest
        draw_hand(hand_pen, hour_deg, length=CLOCK_RADIUS * 0.52, width=7, color=HOUR_HAND_COLOR, tail_length=18)
        draw_hand(hand_pen, minute_deg, length=CLOCK_RADIUS * 0.76, width=4, color=MINUTE_HAND_COLOR, tail_length=24)
        draw_hand(hand_pen, second_deg, length=CLOCK_RADIUS * 0.86, width=2, color=SECOND_HAND_COLOR, tail_length=34)

        draw_center_cap(hand_pen)
        draw_readout(hand_pen, now)
        screen.update()

    # Schedule next update via turtle's non-blocking event timer
    refresh_ms = 50 if state["smooth_seconds"] else 200
    try:
        screen.ontimer(lambda: update_clock(screen, hand_pen), refresh_ms)
    except turtle.Terminator:
        # Window was closed by the user
        pass


def toggle_pause(screen: turtle.Screen, hand_pen: turtle.Turtle) -> None:
    """Toggle pause/resume state and refresh status label immediately."""
    state["paused"] = not state["paused"]
    if state["paused"]:
        # Re-render readout once so [PAUSED] appears immediately
        now = get_current_time()
        hour_deg, minute_deg, second_deg = calculate_angles(now, state["smooth_seconds"])
        hand_pen.clear()
        draw_hand(hand_pen, hour_deg, length=CLOCK_RADIUS * 0.52, width=7, color=HOUR_HAND_COLOR, tail_length=18)
        draw_hand(hand_pen, minute_deg, length=CLOCK_RADIUS * 0.76, width=4, color=MINUTE_HAND_COLOR, tail_length=24)
        draw_hand(hand_pen, second_deg, length=CLOCK_RADIUS * 0.86, width=2, color=SECOND_HAND_COLOR, tail_length=34)
        draw_center_cap(hand_pen)
        draw_readout(hand_pen, now)
        screen.update()


def toggle_smooth_seconds() -> None:
    """Switch between discrete 1-second ticks and smooth sweeping second hand."""
    state["smooth_seconds"] = not state["smooth_seconds"]


def cycle_timezone(delta: int) -> None:
    """Cycle through preset time zones."""
    state["tz_index"] = (state["tz_index"] + delta) % len(TIMEZONES)


def main() -> None:
    """Entry point: build static dial, bind controls, and start the clock loop."""
    screen = setup_screen()
    face_pen = create_pen()
    hand_pen = create_pen()

    # Draw the static dial once; only hand_pen is cleared on each tick
    draw_face(face_pen, CLOCK_RADIUS)
    screen.update()

    # Bind optional interactive keyboard shortcuts
    screen.listen()
    screen.onkey(lambda: toggle_pause(screen, hand_pen), "space")
    screen.onkey(lambda: toggle_pause(screen, hand_pen), "p")
    screen.onkey(toggle_smooth_seconds, "s")
    screen.onkey(lambda: cycle_timezone(-1), "Left")
    screen.onkey(lambda: cycle_timezone(1), "Right")

    # Initial draw + start non-blocking timer loop
    update_clock(screen, hand_pen)
    screen.mainloop()


if __name__ == "__main__":
    main()
