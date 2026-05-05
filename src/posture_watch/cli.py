from __future__ import annotations

import argparse
from dataclasses import asdict, replace

from .config import Config, load_config
from .launchd import install_launch_agent, uninstall_launch_agent
from .runtime import calibrate, doctor, run_watcher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="posture-watch",
        description="Local-first macOS posture monitoring CLI.",
    )
    parser.add_argument("--config", help="Path to .env config file.")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the posture watcher.")
    run_parser.add_argument("--config", dest="command_config", help="Path to .env config file.")
    run_parser.add_argument("--camera-index", type=int)
    run_parser.add_argument("--no-llm", action="store_true", help="Disable LLM verification for this run.")
    run_parser.add_argument("--recalibrate", action="store_true", help="Rebuild baseline before watching.")

    cal_parser = subparsers.add_parser("calibrate", help="Collect a normal-posture baseline.")
    cal_parser.add_argument("--config", dest="command_config", help="Path to .env config file.")
    cal_parser.add_argument("--force", action="store_true", help="Overwrite existing baseline.")
    cal_parser.add_argument("--camera-index", type=int)

    doctor_parser = subparsers.add_parser("doctor", help="Check local environment.")
    doctor_parser.add_argument("--config", dest="command_config", help="Path to .env config file.")
    doctor_parser.add_argument("--camera-check", action="store_true", help="Try opening the camera.")

    install_parser = subparsers.add_parser("install-launch-agent", help="Install macOS launchd autostart.")
    install_parser.add_argument("--config", dest="command_config", help="Path to .env config file.")
    install_parser.add_argument("--start", action="store_true", help="Start immediately after installing.")

    uninstall_parser = subparsers.add_parser("uninstall-launch-agent", help="Remove macOS launchd autostart.")
    uninstall_parser.add_argument("--config", dest="command_config", help="Path to .env config file.")
    uninstall_parser.add_argument("--stop", action="store_true", help="Stop the launch agent before removal.")

    print_config_parser = subparsers.add_parser("print-config", help="Print effective config without secrets.")
    print_config_parser.add_argument("--config", dest="command_config", help="Path to .env config file.")

    args = parser.parse_args(argv)
    command = args.command or "run"
    config_path = getattr(args, "command_config", None) or args.config
    config = load_config(config_path)

    if getattr(args, "camera_index", None) is not None:
        config = replace(config, camera_index=args.camera_index)
    if getattr(args, "no_llm", False):
        config = replace(config, enable_llm_verify=False)

    if command == "run":
        return run_watcher(config, recalibrate=getattr(args, "recalibrate", False))
    if command == "calibrate":
        calibrate(config, overwrite=args.force)
        return 0
    if command == "doctor":
        return doctor(config, camera_check=args.camera_check)
    if command == "install-launch-agent":
        path = install_launch_agent(config, config_path=config_path, start=args.start)
        print(f"Installed {path}")
        return 0
    if command == "uninstall-launch-agent":
        path = uninstall_launch_agent(stop=args.stop)
        print(f"Removed {path}")
        return 0
    if command == "print-config":
        print(_safe_config(config))
        return 0
    parser.print_help()
    return 2


def _safe_config(config: Config) -> dict[str, object]:
    data = asdict(config)
    data["openai_api_key"] = "***" if config.openai_api_key else ""
    data["bark_endpoint"] = "***" if config.bark_endpoint else ""
    data["data_dir"] = str(config.data_dir)
    data["baseline_path"] = str(config.baseline_path)
    return data
