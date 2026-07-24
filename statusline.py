#!/usr/bin/env python3
import sys
import json
import os
import shutil
import re
import unicodedata
import time
import subprocess

# ANSI escape codes for formatting
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GRAY = "\033[90m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_CYAN = "\033[36m"
COLOR_MAGENTA = "\033[35m"

# Regular expression to strip ANSI escape codes for length calculations
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def visual_len(s):
    """Calculates the visible column width of a string in the terminal (accounting for emojis)."""
    clean_s = ANSI_ESCAPE.sub('', s)
    width = 0
    for char in clean_s:
        code = ord(char)
        # Check if the character is an emoji or wide character
        if (unicodedata.east_asian_width(char) in ('W', 'F') or 
            0x2600 <= code <= 0x27BF or 
            0x1F000 <= code <= 0x1FFFF):
            width += 2
        else:
            width += 1
    return width

def format_duration(seconds):
    """Converts seconds to the largest unit with a decimal (e.g., 3.5h, 4.2d, 1.5m)."""
    if seconds is None:
        return "unknown"
    
    if seconds >= 86400:
        return f"{seconds / 86400:.1f}d"
    elif seconds >= 3600:
        return f"{seconds / 3600:.1f}h"
    elif seconds >= 60:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds}s"

def get_color_for_percentage(pct):
    """Returns ANSI color code based on percentage (remaining fraction)."""
    if pct >= 50:
        return COLOR_GREEN
    elif pct >= 20:
        return COLOR_YELLOW
    else:
        return COLOR_RED

def make_progress_bar(pct, color):
    """Generates a 5-step progress bar (▰▰▰▱▱) styled with the specified color."""
    filled = max(0, min(5, int(round(pct / 20.0))))
    empty = 5 - filled
    bar_str = "▰" * filled + "▱" * empty
    return f"{color}{bar_str}{COLOR_RESET}"

def trigger_background_sync(session_id):
    """Spawns a detached background `agy models` process to force a quota refresh (max once/60s per session)."""
    try:
        cache_file = f"/tmp/agy_quota_sync_timestamp_{session_id}"
        now = time.time()
        if os.path.exists(cache_file):
            mtime = os.path.getmtime(cache_file)
            if now - mtime < 60:
                return
        
        # Update lock timestamp immediately to block concurrent spawns
        with open(cache_file, "w") as f:
            f.write(str(now))
        
        # Spawn detached sync command silently in the background
        subprocess.Popen(
            ["agy", "models"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception:
        pass

def main():
    try:
        # Read the raw JSON payload piped to stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            # Standard default output if no input received
            print("agy | Initializing...")
            return
            
        payload = json.loads(input_data)
        
        # Trigger background quota sync (isolated by window session ID)
        session_id = payload.get("session_id") or payload.get("conversation_id") or "default"
        trigger_background_sync(session_id)
    except Exception as e:
        print(f"agy | Error parsing status line data: {e}")
        return

    # 1. Model & Reasoning Effort (e.g. Gemini 3.5 Flash (High))
    model = payload.get("model", {})
    model_id = model.get("id", "").lower()
    model_name = model.get("display_name", model.get("id", "Unknown Model"))
    
    # Strip any trailing parenthetical effort info (e.g. " (High)") from display name
    model_name = re.sub(r'\s*\([^)]*\)\s*$', '', model_name)
    
    # Extract effort from the nested model dictionary
    effort = model.get("effort")
    if effort and effort.lower() != "none":
        effort_clean = effort.lower()
        if "high" in effort_clean:
            effort_color = COLOR_YELLOW
        elif "medium" in effort_clean:
            effort_color = COLOR_CYAN
        elif "low" in effort_clean:
            effort_color = COLOR_GREEN
        else:
            effort_color = COLOR_GRAY
        # Format effort with first letter capitalized, coloring only the inner text
        model_str = f"{COLOR_BOLD}{model_name}{COLOR_RESET} ({effort_color}{COLOR_BOLD}{effort.capitalize()}{COLOR_RESET})"
    else:
        model_str = f"{COLOR_BOLD}{model_name}{COLOR_RESET}"

    # 2. Context Window & Mode (e.g., 🧠 ▰▱▱▱▱ 7%  │  accept-edits)
    context = payload.get("context_window", {})
    ctx_pct = context.get("used_percentage", 0)
    ctx_color = COLOR_GREEN if ctx_pct < 50 else (COLOR_YELLOW if ctx_pct < 80 else COLOR_RED)
    ctx_bar = make_progress_bar(ctx_pct, ctx_color)
    ctx_str = f"🧠 {ctx_bar} {ctx_color}{ctx_pct:.0f}%{COLOR_RESET}"

    # Retrieve agent execution mode (e.g. plan, accept-edits)
    mode_val = payload.get("cycle_mode") or payload.get("mode") or payload.get("execution_mode") or payload.get("agent_mode")
    if mode_val:
        # Style mode with appropriate colors
        if mode_val == "accept-edits":
            mode_color = COLOR_YELLOW
        elif mode_val == "plan":
            mode_color = COLOR_GREEN
        else:
            mode_color = COLOR_CYAN
        ctx_str += f"  │  {mode_color}{mode_val}{COLOR_RESET}"

    # 3. Quotas Processing (e.g., Short: ▰▰▰▱▱ 55% (3.5h)  │  Long: ▰▰▱▱▱ 37% (4.2d))
    quota_keyword = None
    if "gemini" in model_id:
        quota_keyword = "gemini"
    elif "claude" in model_id or "3p" in model_id:
        quota_keyword = "3p"

    quota = payload.get("quota", {})
    sorted_buckets = []
    
    for bucket_id, bucket_data in quota.items():
        if quota_keyword and quota_keyword not in bucket_id.lower():
            continue
        rem_frac = bucket_data.get("remaining_fraction")
        if rem_frac is None:
            continue
        reset_secs = bucket_data.get("reset_in_seconds", 0)
        sorted_buckets.append((reset_secs, rem_frac))
        
    # Sort buckets ascending by reset duration
    sorted_buckets.sort()
    
    quota_parts = []
    if len(sorted_buckets) >= 2:
        # Separate into Short Limit and Long Limit
        short_secs, short_frac = sorted_buckets[0]
        long_secs, long_frac = sorted_buckets[-1]
        
        short_pct = int(round(short_frac * 100))
        short_color = get_color_for_percentage(short_pct)
        short_reset = format_duration(short_secs)
        short_bar = make_progress_bar(short_pct, short_color)
        quota_parts.append(f"⚡ {short_bar} {short_color}{short_pct}%{COLOR_RESET} ({short_reset})")
        
        long_pct = int(round(long_frac * 100))
        long_color = get_color_for_percentage(long_pct)
        long_reset = format_duration(long_secs)
        long_bar = make_progress_bar(long_pct, long_color)
        quota_parts.append(f"⚡⚡ {long_bar} {long_color}{long_pct}%{COLOR_RESET} ({long_reset})")
    elif len(sorted_buckets) == 1:
        # Only one bucket available
        secs, frac = sorted_buckets[0]
        pct = int(round(frac * 100))
        color = get_color_for_percentage(pct)
        reset = format_duration(secs)
        bar = make_progress_bar(pct, color)
        quota_parts.append(f"⚡ {bar} {color}{pct}%{COLOR_RESET} ({reset})")

    # Assemble the left side
    left_components = []
    if quota_parts:
        left_components.append("  │  ".join(quota_parts))
    left_components.append(ctx_str)
    
    left_side = "  │  ".join(left_components)
    right_side = model_str

    # 4. Padding to achieve right alignment based on terminal width
    # Get columns size from payload if available, fallback to terminal size
    cols = payload.get("terminal_width") or shutil.get_terminal_size(fallback=(120, 20)).columns
    
    # We leave 3 columns space to prevent terminal wrap artifacts
    target_width = max(10, cols - 3)
    
    left_len = visual_len(left_side)
    right_len = visual_len(right_side)
    
    padding_len = max(1, target_width - left_len - right_len)
    padding = " " * padding_len
    
    # Render final output line
    print(f"{left_side}{padding}{right_side}")

if __name__ == "__main__":
    main()
