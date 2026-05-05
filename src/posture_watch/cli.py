from __future__ import annotations

import argparse
from dataclasses import asdict, replace

from .config import Config, load_config
from .evaluation import DEFAULT_TRIGGER, evaluate_synthetic_postures, format_report
from .launchd import install_launch_agent, uninstall_launch_agent
from .placement import format_placement_guide, with_placement
from .runtime import adapt_placement, calibrate, doctor, run_watcher
from .setup_wizard import edit_config, run_setup_wizard, update_config_values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="posture-watch",
        description="Local-first macOS posture monitoring CLI.",
    )
    parser.add_argument("--config", help="Path to .env config file.")
    subparsers = parser.add_subparsers(dest="command", metavar="{setup,start,adapt,doctor}")

    setup_parser = _add_public_parser(subparsers, "setup", help="Create local config.")
    setup_parser.add_argument("--output", help="Config path to write. Defaults to ./.env.")
    setup_parser.add_argument(
        "--adapt",
        action="store_true",
        help="Run camera placement adaptation after writing config.",
    )
    init_parser = _add_hidden_parser(subparsers, "init")
    init_parser.add_argument("--output", help=argparse.SUPPRESS)
    init_parser.add_argument("--adapt", action="store_true", help=argparse.SUPPRESS)

    _add_start_args(_add_public_parser(subparsers, "start", help="Start monitoring."))
    for legacy in ("run", "watch"):
        _add_start_args(_add_hidden_parser(subparsers, legacy))

    for name in ("calibrate", "cal"):
        _add_calibrate_args(_add_hidden_parser(subparsers, name))

    doctor_parser = _add_public_parser(
        subparsers,
        "doctor",
        help="Diagnose camera and local dependencies.",
    )
    _add_config_arg(doctor_parser)
    _add_placement_arg(doctor_parser)
    doctor_parser.add_argument(
        "--camera",
        dest="camera_check",
        action="store_true",
        help="Try opening the camera.",
    )
    doctor_parser.add_argument(
        "--camera-check",
        dest="camera_check",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    doctor_parser.add_argument(
        "--notify",
        dest="notify_check",
        action="store_true",
        help="Send a test notification.",
    )
    check_parser = _add_hidden_parser(subparsers, "check")
    _add_config_arg(check_parser)
    _add_placement_arg(check_parser)
    check_parser.add_argument("--camera", dest="camera_check", action="store_true")
    check_parser.add_argument("--camera-check", dest="camera_check", action="store_true")
    check_parser.add_argument("--notify", dest="notify_check", action="store_true")

    for name in ("eval", "evaluate"):
        eval_parser = _add_hidden_parser(subparsers, name)
        eval_parser.add_argument("--threshold", type=float, default=DEFAULT_TRIGGER)

    for name in ("placements", "placement-guide"):
        placement_parser = _add_hidden_parser(subparsers, name)
        _add_config_arg(placement_parser)
        _add_placement_arg(placement_parser)

    _add_adapt_args(
        _add_public_parser(
            subparsers,
            "adapt",
            help="Re-detect current screen/camera placement.",
        )
    )
    for legacy in ("detect-placement", "reposition"):
        _add_adapt_args(_add_hidden_parser(subparsers, legacy))

    for name in ("install-launch-agent", "autostart-on"):
        install_parser = _add_hidden_parser(subparsers, name)
        _add_config_arg(install_parser)
        _add_placement_arg(install_parser)
        install_parser.add_argument("--start", action="store_true")

    for name in ("uninstall-launch-agent", "autostart-off"):
        uninstall_parser = _add_hidden_parser(subparsers, name)
        _add_config_arg(uninstall_parser)
        uninstall_parser.add_argument("--stop", action="store_true")

    for name in ("print-config", "config"):
        config_parser = _add_hidden_parser(subparsers, name)
        _add_config_arg(config_parser)
        _add_placement_arg(config_parser)

    for name in ("edit-config", "edit"):
        edit_parser = _add_hidden_parser(subparsers, name)
        _add_config_arg(edit_parser)

    args = parser.parse_args(argv)
    command = args.command or "start"
    try:
        if command in {"setup", "init"}:
            path = run_setup_wizard(output_path=args.output)
            if args.adapt:
                config = load_config(path)
                adapted_config, _ = adapt_placement(config)
                _save_adapted_config(path, adapted_config)
            return 0
        if command in {"eval", "evaluate"}:
            report = evaluate_synthetic_postures(threshold=args.threshold)
            print(format_report(report))
            return 0 if report.precision >= 0.9 and report.recall >= 0.9 else 1

        config_path = getattr(args, "command_config", None) or args.config
        config = load_config(config_path)

        if getattr(args, "camera_index", None) is not None:
            config = replace(config, camera_index=args.camera_index)
        if getattr(args, "no_llm", False):
            config = replace(config, enable_llm_verify=False)
        explicit_placement = bool(getattr(args, "placement", None))
        if explicit_placement:
            config = with_placement(config, args.placement)

        if command in {"run", "start", "watch"}:
            return _start_watcher(
                config,
                config_path=config_path,
                recalibrate=getattr(args, "recalibrate", False),
                infer_profile=not explicit_placement,
            )
        if command in {"calibrate", "cal"}:
            calibrate(config, overwrite=args.force)
            return 0
        if command in {"doctor", "check"}:
            return doctor(
                config,
                camera_check=args.camera_check,
                notify_check=getattr(args, "notify_check", False),
            )
        if command in {"placements", "placement-guide"}:
            print(format_placement_guide(config))
            return 0
        if command in {"adapt", "detect-placement", "reposition"}:
            adapted_config, _ = adapt_placement(
                config,
                infer_profile=not explicit_placement,
            )
            if not args.no_save_config:
                saved_path = _save_adapted_config(config_path, adapted_config)
                print(f"Updated config {saved_path}")
            return 0
        if command in {"install-launch-agent", "autostart-on"}:
            path = install_launch_agent(config, config_path=config_path, start=args.start)
            print(f"Installed {path}")
            return 0
        if command in {"uninstall-launch-agent", "autostart-off"}:
            path = uninstall_launch_agent(stop=args.stop)
            print(f"Removed {path}")
            return 0
        if command in {"print-config", "config"}:
            print(_safe_config(config))
            return 0
        if command in {"edit-config", "edit"}:
            return edit_config(config_path)
        parser.print_help()
        return 2
    except RuntimeError as exc:
        print(f"error: {exc}")
        return 1


def _add_public_parser(
    subparsers: argparse._SubParsersAction,
    name: str,
    *,
    help: str,
) -> argparse.ArgumentParser:
    return subparsers.add_parser(name, help=help)


def _add_hidden_parser(
    subparsers: argparse._SubParsersAction,
    name: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=argparse.SUPPRESS)
    subparsers._choices_actions = [
        action for action in subparsers._choices_actions if action.dest != name
    ]
    return parser


def _add_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", dest="command_config", help="Path to .env config file.")


def _add_placement_arg(parser: argparse.ArgumentParser, *, visible: bool = False) -> None:
    parser.add_argument(
        "--placement",
        help=(
            "Baseline profile for this camera/screen/chair layout."
            if visible
            else argparse.SUPPRESS
        ),
    )


def _add_start_args(parser: argparse.ArgumentParser) -> None:
    _add_config_arg(parser)
    _add_placement_arg(parser)
    parser.add_argument("--camera-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--no-llm", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--recalibrate", action="store_true", help=argparse.SUPPRESS)


def _add_calibrate_args(parser: argparse.ArgumentParser) -> None:
    _add_config_arg(parser)
    _add_placement_arg(parser)
    parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--camera-index", type=int, help=argparse.SUPPRESS)


def _add_adapt_args(parser: argparse.ArgumentParser) -> None:
    _add_config_arg(parser)
    _add_placement_arg(parser)
    parser.add_argument("--camera-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--no-save-config", action="store_true", help=argparse.SUPPRESS)


def _start_watcher(
    config: Config,
    *,
    config_path: str | None,
    recalibrate: bool,
    infer_profile: bool,
) -> int:
    if recalibrate or not config.baseline_path.exists():
        adapted_config, _ = adapt_placement(config, infer_profile=infer_profile)
        saved_path = _save_adapted_config(config_path, adapted_config)
        print(f"Updated config {saved_path}")
        config = adapted_config
    return run_watcher(config, recalibrate=False)


def _safe_config(config: Config) -> dict[str, object]:
    data = asdict(config)
    data["openai_api_key"] = "***" if config.openai_api_key else ""
    data["bark_endpoint"] = "***" if config.bark_endpoint else ""
    data["data_dir"] = str(config.data_dir)
    data["baseline_path"] = str(config.baseline_path)
    return data


def _save_adapted_config(path: str | None, config: Config):
    return update_config_values(
        path,
        {
            "PLACEMENT_PROFILE": config.placement_profile,
            "CAMERA_INDEX": str(config.camera_index),
            "BASELINE_PATH": "",
        },
    )
