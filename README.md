# Antigravity CLI Quota Status Line

This repository contains a custom status line script for the **Google Antigravity CLI (`agy`)**. It parses telemetry data piped by the CLI and renders a real-time status bar at the bottom of your terminal displaying API quotas, reasoning effort level, context usage, and Git status.

---

## Features

- **Visual Quota Tracking**: Displays model-specific quota limits side-by-side with 5-step progress bars and icons (e.g., `⚡ ▰▰▰▱▱ 55% (3.5h)  │  ⚡⚡ ▰▰▰▰▱ 37% (4.2d)`).
- **Color-Coded Status**: 
  - Green ($\ge 50\%$ remaining quota)
  - Yellow ($20\% - 50\%$ remaining quota)
  - Red ($< 20\%$ remaining quota)
- **Model & Effort Indicators**: Renders the active model name and reasoning effort level right-aligned at the edge of the terminal, color-coding only the inner effort level text (e.g., `Gemini 3.5 Flash (High)`).
- **Context & Mode Tracking**: Dynamic context limits and active execution mode with brain icon (e.g., `🧠 ▰▱▱▱▱ 7%  │  accept-edits`).

---

## Repository Structure

- [statusline.py](file:///home/conmak/development/personal/agy_usage/statusline.py): The main entry point script containing the JSON parser and terminal formatting logic.
  - [main()](file:///home/conmak/development/personal/agy_usage/statusline.py#L44-L135): Processes telemetry input from `sys.stdin`, handles terminal padding, and outputs the status line.
  - [format_duration()](file:///home/conmak/development/personal/agy_usage/statusline.py#L20-L33): Formats `reset_in_seconds` into largest units with decimals (e.g., `3.5h`, `4.2d`).
  - [get_color_for_percentage()](file:///home/conmak/development/personal/agy_usage/statusline.py#L35-L42): Returns ANSI color codes based on remaining quota fractions.

---

## Installation & Setup

### 1. Make the script executable
If you haven't already, ensure the script has execution permissions:
```bash
chmod +x statusline.py
```

### 2. Configure the status line in `agy`

You can activate the status line using either of the following two options:

#### Option A: Run inside the CLI TUI (Recommended)
Start `agy` and execute the following slash command:
```text
/statusline /home/conmak/development/personal/agy_usage/statusline.py
```
*Note: To reset back to default settings later, run `/statusline reset`.*

#### Option B: Edit `settings.json` manually
Add the status line command configuration block to your CLI settings file at `~/.gemini/antigravity-cli/settings.json`:
```json
{
  "statusLine": {
    "enabled": true,
    "command": "/home/conmak/development/personal/agy_usage/statusline.py"
  }
}
```

---

## Verification

Launch `agy` and verify the status bar at the bottom:
```bash
agy
```

> [!TIP]
> Ensure your terminal width is at least **120 columns wide**. The CLI will automatically hide custom status lines if the screen window is too narrow.