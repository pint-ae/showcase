"""Command-line interface for the pint-ae toolkit.

`diagnose` accepts files, folders, globs and `.zip` archives, classifies every
input, validates what it can, and can emit the machine-readable result contract
(`--json`). `report` renders the bilingual PDF reports for the accepted files.
`corpus` writes a realistic synthetic portfolio to trial the tool on, `rules`
lists what this installation checks, and `selftest` proves the installation is
intact before it is put in front of a client.
"""

from __future__ import annotations

import json
import platform
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import typer
from lxml import etree
from rich.console import Console

from pint_ae import config as config_module
from pint_ae import corpus, intake, licensing, regulatory
from pint_ae import modules as module_catalogue
from pint_ae.parser import parse
from pint_ae.results import (
    FileResult,
    RunResult,
    dedupe,
    filter_modules,
    filter_not_entitled,
    make_finding,
    sort_findings,
)
from pint_ae.rules import _RULES, set_vat_group, validate
from pint_ae.schematron.validator import (
    OFFICIAL_LAYERS,
    active_layers,
    assertion_counts,
    schematron_assertion_count,
    warm_up,
)
from pint_ae.scope import EXCLUDED_TAX_GROUP, classify, document_type
from pint_ae.types import PintAeInvoice


def _reconfigure_stream(stream: object) -> None:
    """Stop a legacy Windows code page from killing a run on a 'Σ' or an emirati letter.

    Official SVRL messages contain characters (Σ, —, Arabic text) that cp1252 and
    cp437 cannot encode. Without this, printing a finding raises
    UnicodeEncodeError and the whole batch dies - in front of the client, on the
    client's machine.

    A redirected stream (file, pipe, CI log) is switched to UTF-8 so nothing is
    lost; an interactive console keeps its own encoding with replacement, because
    forcing UTF-8 bytes at a cp1252 console would only produce mojibake.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:  # pragma: no cover - exotic stream objects
        return
    isatty = getattr(stream, "isatty", None)
    interactive = bool(isatty()) if callable(isatty) else False
    try:
        if interactive:
            reconfigure(errors="replace")
        else:
            reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):  # pragma: no cover - closed or detached stream
        pass


_reconfigure_stream(sys.stdout)
_reconfigure_stream(sys.stderr)

app = typer.Typer(
    name="pint-ae",
    help="PINT AE toolkit - validate UAE e-invoices against the official rule set.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main() -> None:
    """PINT AE toolkit - validate UAE e-invoices against the official rule set."""


def _parse_error(exc: Exception) -> tuple[str, str]:
    """Map a parse failure to a stable intake classification."""
    if isinstance(exc, etree.XMLSyntaxError):
        return intake.XML_SYNTAX_ERROR, str(exc)
    if isinstance(exc, ValueError):
        return intake.UNSUPPORTED_DOCUMENT, str(exc)
    return intake.UNREADABLE, f"{type(exc).__name__}: {exc}"


#: Worker state for the process pool: the Saxon processor is not thread-safe, so
#: parallelism is across processes, each with its own compiled stylesheets.
_WORKER: dict[str, object] = {}


def _worker_init(
    tax_group_trns: list[str],
    modules: list[str] | None,
    config_payload: dict[str, object] | None,
) -> None:
    """Prepare one worker process: rule globals, first stylesheet compile."""
    from pint_ae.config import PintAeConfig

    set_vat_group(set(tax_group_trns))
    config = PintAeConfig.model_validate(config_payload) if config_payload is not None else None
    if config is not None:
        config_module.apply_config(config)
        set_vat_group(config.tax_group.normalised())
    warm_up()
    _WORKER["config"] = config
    _WORKER["modules"] = list(modules) if modules else None


def _worker_run(payload: tuple[str, str, str, str, int, bytes | None]) -> FileResult:
    """Validate one document in a worker process and return its result."""
    display, classification, detail, sha256_value, size, data = payload
    began = perf_counter()
    result = FileResult(
        source=display,
        classification=classification,
        detail=detail,
        sha256=sha256_value,
        size=size,
    )
    config: config_module.PintAeConfig | None = _WORKER.get("config")  # type: ignore[assignment]
    modules: list[str] | None = _WORKER.get("modules")  # type: ignore[assignment]
    if classification == intake.ACCEPTED and data is not None:
        try:
            inv = parse(data)
        except Exception as exc:  # noqa: BLE001 - classified, never re-raised
            result.classification, result.detail = _parse_error(exc)
        else:
            _validate(
                inv,
                data,
                result,
                False,
                set(),  # tax group already applied in the worker initialiser
                modules,
                config.disabled_modules() if config is not None else [],
                config,
            )
    result.elapsed_ms = int((perf_counter() - began) * 1000)
    return result


def _run_parallel(
    items: list[tuple[str, str, str, str, int, bytes | None]],
    *,
    jobs: int,
    tax_group_trns: set[str],
    modules: list[str] | None,
    config: config_module.PintAeConfig | None,
) -> list[FileResult]:
    """Run the batch across processes; results come back in input order."""
    payload = config.model_dump(mode="json") if config is not None else None
    with ProcessPoolExecutor(
        max_workers=jobs,
        initializer=_worker_init,
        initargs=(sorted(tax_group_trns), modules, payload),
    ) as pool:
        return list(pool.map(_worker_run, items))


def diagnose_paths(
    paths: list[Path],
    *,
    peppol_bis3: bool = False,
    tax_group_trns: set[str] | None = None,
    limits: intake.IntakeLimits | None = None,
    modules: list[str] | None = None,
    config: config_module.PintAeConfig | None = None,
    jobs: int = 1,
) -> RunResult:
    """Run the diagnostic over any mix of files, folders and zips.

    ``modules`` restricts the findings to those owned by the selected modules
    (``None`` keeps every module). Official XSLT evaluation is monolithic, so the
    selection filters findings; it does not skip work.

    ``config`` applies the deployment configuration: tax-group exclusions,
    thresholds, severity overrides and module entitlements. Withdrawn modules are
    reported as ``not_entitled`` (decision A13), never as clean.

    ``jobs > 1`` fans the batch out across **processes** (the bundled Saxon processor
    is not thread-safe). Results are returned in input order, so a parallel run and a
    serial run produce the same document at the same index.
    """
    started = datetime.now(UTC).isoformat()
    run = RunResult(
        started=started,
        environment=f"{platform.python_version()} / {platform.platform()}",
    )
    tax_group_trns = tax_group_trns or set()
    applied = config_module.apply_config(config) if config is not None else None
    licence = licensing.current_licence()
    not_licensed = [
        module.id for module in module_catalogue.MODULES if not licence.covers(module.id)
    ]
    if applied is not None:
        tax_group_trns = applied.config.tax_group.normalised()

    items = list(intake.expand(paths, limits))
    if jobs > 1 and len(items) > 1:
        payloads = [
            (item.display, item.classification, item.detail, item.sha256, item.size, item.data)
            for item in items
        ]
        try:
            results = _run_parallel(
                payloads,
                jobs=jobs,
                tax_group_trns=tax_group_trns,
                modules=modules,
                config=config,
            )
        except (OSError, PermissionError, RuntimeError) as exc:
            # Some locked-down environments forbid spawning worker processes (named
            # pipes, restricted token). A batch must not fail because of that: fall
            # back to serial execution and say so.
            run.extra["jobs_fallback"] = f"{type(exc).__name__}: {exc}"
        else:
            run.files.extend(results)
            run.finished = datetime.now(UTC).isoformat()
            run.extra["peppol_bis3"] = peppol_bis3
            run.extra["tax_group_trns"] = sorted(tax_group_trns)
            run.extra["modules"] = modules
            run.extra["jobs"] = jobs
            if applied is not None:
                run.extra["config"] = applied.provenance()
            run.extra["licence"] = licence.as_dict()
            run.extra["licence_not_licensed"] = not_licensed
            return run

    for item in items:
        began = perf_counter()
        result = FileResult(
            source=item.display,
            classification=item.classification,
            detail=item.detail,
            sha256=item.sha256,
            size=item.size,
        )
        if item.classification == intake.ACCEPTED and item.data is not None:
            try:
                inv = parse(item.data)
            except Exception as exc:  # noqa: BLE001 - classified, never re-raised
                result.classification, result.detail = _parse_error(exc)
            else:
                _validate(
                    inv,
                    item.data,
                    result,
                    peppol_bis3,
                    tax_group_trns,
                    modules,
                    applied.disabled_modules if applied is not None else [],
                    applied.config if applied is not None else None,
                    not_licensed,
                )
        result.elapsed_ms = int((perf_counter() - began) * 1000)
        run.files.append(result)

    run.finished = datetime.now(UTC).isoformat()
    run.extra["peppol_bis3"] = peppol_bis3
    run.extra["tax_group_trns"] = sorted(tax_group_trns)
    run.extra["modules"] = modules
    if applied is not None:
        run.extra["config"] = applied.provenance()
    run.extra["licence"] = licence.as_dict()
    run.extra["licence_not_licensed"] = not_licensed
    return run


def _validate(
    inv: PintAeInvoice,
    source: bytes,
    result: FileResult,
    peppol_bis3: bool,
    tax_group_trns: set[str],
    modules: list[str] | None = None,
    not_entitled: list[str] | None = None,
    config: config_module.PintAeConfig | None = None,
    not_licensed: list[str] | None = None,
) -> None:
    scope, reason = classify(inv, tax_group_trns)
    result.document_type = document_type(inv)
    result.document_id = inv.invoice_id
    result.scope = scope
    result.scope_reason = reason

    violations = validate(inv, source, include_peppol_bis3=peppol_bis3)
    findings, suppressed = dedupe(sort_findings([make_finding(v, config) for v in violations]))

    if scope == EXCLUDED_TAX_GROUP:
        suppressed = suppressed + [
            {
                "rule_id": f.rule_id,
                "layer": f.layer,
                "module": f.module,
                "field": f.field,
                "reason": "excluded transaction (tax group)",
            }
            for f in findings
        ]
        findings = []

    result.findings = filter_not_entitled(
        filter_not_entitled(filter_modules(findings, modules), not_entitled or []),
        not_licensed or [],
    )
    result.suppressed = suppressed


def _load_config(explicit: Path | None) -> config_module.PintAeConfig:
    """Load the deployment config, turning a bad file into a usage error (exit 3)."""
    try:
        return config_module.load_config(config_module.find_config(explicit))
    except config_module.ConfigError as exc:
        console.print(f"[red]X[/red] {exc}")
        raise typer.Exit(code=3) from exc


def exit_code(run: RunResult) -> int:
    """0 clean · 1 errors · 2 some input could not be validated · 3 usage (typer)."""
    unvalidated = [f for f in run.files if f.classification not in ("accepted", "duplicate")]
    if unvalidated:
        return 2
    if any(f.error_count for f in run.files):
        return 1
    return 0


def render(run: RunResult, *, verbose: bool = False, quiet: bool = False) -> None:
    summary = run.summary()
    if not quiet:
        for file in run.files:
            if file.classification not in ("accepted", "duplicate"):
                console.print(
                    f"[yellow]![/yellow] {file.source} -- {file.classification}: {file.detail}"
                )
                continue
            if file.classification == "duplicate":
                if verbose:
                    console.print(f"[dim]=[/dim] {file.source} -- duplicate: {file.detail}")
                continue
            if not file.findings:
                if verbose:
                    console.print(
                        f"[green]OK[/green] {file.source} ({file.document_id}) -- clean"
                        + (f" [{file.scope}]" if file.scope != "in-scope" else "")
                    )
            else:
                marker = "[red]x[/red]" if file.error_count else "[yellow]![/yellow]"
                console.print(
                    f"{marker} {file.source} ({file.document_id}) -- "
                    f"{file.error_count} error(s), {file.warning_count} warning(s)"
                )
                for finding in file.findings:
                    console.print(
                        f"    [{finding.severity}] {finding.rule_id} ({finding.module}) "
                        f"{finding.location}: {finding.message}"
                    )
                    console.print(f"    Citation: {finding.citation}")
            if file.scope == EXCLUDED_TAX_GROUP and verbose:
                console.print(f"    excluded: {file.scope_reason}")
            if file.suppressed and verbose:
                console.print(
                    f"    ({len(file.suppressed)} duplicate/excluded finding(s) recorded in JSON)"
                )

    console.print(
        f"\nSummary: {summary['clean']}/{summary['total']} clean, "
        f"{summary['with_warnings']} with warnings, "
        f"{summary['with_errors']} with errors, "
        f"{summary['failed']} not validated"
        + (f", {summary['suppressed']} suppressed" if summary["suppressed"] else "")
    )
    licence = run.extra.get("licence") or {}
    if licence.get("state") == "free":
        console.print(
            "[yellow]![/yellow] licence: free evaluation - "
            + str(len(summary.get("not_licensed", [])))
            + " module(s) withheld (run `pint-ae modules` to see which)"
        )
    if summary["not_entitled"]:
        console.print(
            "[yellow]![/yellow] not entitled (not checked): "
            + ", ".join(summary["not_entitled"])
            + " - this run does not report on those modules"
        )


@app.command()
def diagnose(
    paths: list[Path] = typer.Argument(..., help="Files, folders, globs or .zip archives"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show clean invoices, duplicates and suppression details"
    ),
    peppol_bis3: bool = typer.Option(
        False,
        "--peppol-bis3",
        help="Also run the legacy Peppol BIS 3.0 layer (not CIUS-safe; off by default)",
    ),
    json_out: Path | None = typer.Option(
        None, "--json", help="Write machine-readable results to this path ('-' for stdout)"
    ),
    tax_group_trn: list[str] = typer.Option(
        [],
        "--tax-group-trn",
        help="TRN of a tax-group member (repeatable); both parties in the set are excluded",
    ),
    module: list[str] = typer.Option(
        [],
        "--modules",
        "-m",
        help="Only report these modules (repeatable or comma-separated; default: all)",
    ),
    config_file: Path | None = typer.Option(
        None, "--config", help="pint-ae.toml to apply (default: ./pint-ae.toml if present)"
    ),
    jobs: int = typer.Option(
        1,
        "--jobs",
        "-j",
        min=1,
        max=32,
        help="Processes for large batches (the Saxon processor is not thread-safe)",
    ),
) -> None:
    """Validate PINT AE documents against the official PINT AE 1.0.4 rules."""
    try:
        selected = module_catalogue.resolve_selection(module) if module else None
    except ValueError as exc:
        console.print(f"[red]X[/red] {exc}")
        raise typer.Exit(code=3) from exc
    licence = licensing.current_licence()
    if selected:
        refused = [module_id for module_id in selected if not licence.covers(module_id)]
        if refused:
            console.print(
                "[red]X[/red] module(s) not licensed: "
                + ", ".join(refused)
                + " - a licence is required for production use of these modules; "
                "contact the licensor or drop them from --modules"
            )
            raise typer.Exit(code=3)

    config = _load_config(config_file)
    extra_trns = {trn.strip() for trn in tax_group_trn if trn.strip()}
    if extra_trns:
        config.tax_group.trns = sorted(set(config.tax_group.trns) | extra_trns)
    set_vat_group(config.tax_group.normalised())
    run = diagnose_paths(paths, peppol_bis3=peppol_bis3, modules=selected, config=config, jobs=jobs)
    render(run, verbose=verbose, quiet=json_out is not None and str(json_out) == "-")

    if json_out is not None:
        payload = run.to_json()
        if str(json_out) == "-":
            sys.stdout.write(payload)
        else:
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(payload, encoding="utf-8")

    raise typer.Exit(code=exit_code(run))


@app.command()
def report(
    paths: list[Path] = typer.Argument(..., help="Files, folders, globs or .zip archives"),
    output_dir: Path = typer.Option(
        Path("reports"), "--output", "-o", help="Output directory for PDFs"
    ),
    lang: str = typer.Option("en", "--lang", "-l", help="Language: en, ar, or both"),
    peppol_bis3: bool = typer.Option(
        False,
        "--peppol-bis3",
        help="Also run the legacy Peppol BIS 3.0 layer (not CIUS-safe; off by default)",
    ),
    tax_group_trn: list[str] = typer.Option(
        [], "--tax-group-trn", help="TRN of a tax-group member (repeatable)"
    ),
    module: list[str] = typer.Option(
        [], "--modules", "-m", help="Only include these modules (repeatable or comma-separated)"
    ),
    config_file: Path | None = typer.Option(
        None, "--config", help="pint-ae.toml to apply (default: ./pint-ae.toml if present)"
    ),
) -> None:
    """Generate PDF diagnostic reports for accepted PINT AE documents."""
    from pint_ae.pdf import generate_report

    try:
        selected = module_catalogue.resolve_selection(module) if module else None
    except ValueError as exc:
        console.print(f"[red]X[/red] {exc}")
        raise typer.Exit(code=3) from exc

    licence = licensing.current_licence()
    if selected:
        refused = [module_id for module_id in selected if not licence.covers(module_id)]
        if refused:
            console.print(
                "[red]X[/red] module(s) not licensed: "
                + ", ".join(refused)
                + " - a licence is required for production use of these modules; "
                "contact the licensor or drop them from --modules"
            )
            raise typer.Exit(code=3)

    config = _load_config(config_file)
    extra_trns = {trn.strip() for trn in tax_group_trn if trn.strip()}
    if extra_trns:
        config.tax_group.trns = sorted(set(config.tax_group.trns) | extra_trns)
    set_vat_group(config.tax_group.normalised())

    output_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0
    for item in intake.expand(paths):
        if item.classification != intake.ACCEPTED or item.data is None:
            console.print(f"[yellow]![/yellow] {item.display} -- {item.classification}")
            failed += 1
            continue
        try:
            inv = parse(item.data)
            violations = validate(inv, item.data, include_peppol_bis3=peppol_bis3)
            findings = filter_not_entitled(
                filter_modules([make_finding(v, config) for v in violations], selected),
                config.disabled_modules(),
            )
            kept_ids = {finding.rule_id for finding in findings}
            violations = [v for v in violations if v.rule_id in kept_ids]
            out = output_dir / f"{inv.invoice_id}-report-{lang}.pdf"
            generate_report(inv, violations, item.data, out, language=lang)
            console.print(f"[green]OK[/green] {item.display} -> {out}")
            success += 1
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop a batch
            console.print(f"[red]X[/red] {item.display} -- {exc}")
            failed += 1
    console.print(f"\n{success} report(s) generated, {failed} failed")
    if failed:
        raise typer.Exit(code=1)


@app.command("corpus")
def corpus_command(
    out: Path = typer.Option(Path("demo"), "--out", "-o", help="Directory to write the corpus to"),
    count: int = typer.Option(100, "--count", "-n", help="Number of documents to generate"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing non-empty folder"),
) -> None:
    """Write a synthetic PINT AE client portfolio to try the tool on.

    No client data is needed: 100 internally consistent documents covering
    standard, zero-rated, exempt and reverse-charge supplies, document-level
    discounts and surcharges, and credit notes, with one known defect in 40 of
    them. The accompanying `manifest.json` states what each document should
    produce, so the result can be checked instead of trusted.
    """
    try:
        manifest = corpus.write_corpus(out, count, force=force)
    except FileExistsError as exc:
        console.print(f"[red]X[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(
        f"[green]OK[/green] {manifest['documents']} documents "
        f"({manifest['clean']} clean, {manifest['defective']} with one known defect) -> "
        f"{out / 'documents'}"
    )
    console.print(f"  expectations: {out / 'manifest.json'}")
    console.print(f"  try it      : pint-ae diagnose {out / 'documents'}")


@app.command()
def rules(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Also list each local rule's source reference"
    ),
) -> None:
    """List the checks this installation runs: local rules plus the official artefact."""
    from pint_ae.pdf import arabic_font_status

    font = arabic_font_status()
    console.print(
        "Arabic font: "
        + (
            f"{font['font_path']}"
            if font["font_path"]
            else "none found - bilingual reports render Latin only; see README limitations"
        )
    )
    counts = assertion_counts()
    layers = active_layers()

    console.print(f"Specification: {regulatory.SPEC_VERSION} (released {regulatory.SPEC_RELEASED})")
    console.print(f"Rule-set SHA-256: {regulatory.rule_set_sha256()}")
    console.print(f"Regulation snapshot: {regulatory.REGULATION_SNAPSHOT}")

    console.print("\nOfficial PINT AE artefact (source of truth)")
    for layer in layers:
        name = layer.name
        kind = "official" if layer in OFFICIAL_LAYERS or "self-billing" in name else "legacy"
        console.print(f"  {name:<34} {counts.get(name, 0):>4} assertions   [{kind}]")
    console.print(f"  {'total':<34} {schematron_assertion_count():>4} assertions")

    console.print(f"\nLocal UAE interpretation rules ({len(_RULES)})")
    for index, rule in enumerate(_RULES, start=1):
        header = (rule.__doc__ or "").strip().splitlines()[0] if rule.__doc__ else ""
        rule_id, _, source = header.partition(" / ")
        rule_id = rule_id.strip() or f"rule {index}"
        owner = module_catalogue.RULE_MODULES.get(rule_id, module_catalogue.CORE)
        if verbose:
            console.print(f"  {rule_id:<8} {owner:<16} {source.strip()}")
        else:
            console.print(f"  {rule_id:<8} {owner:<16} {rule.__name__}")
    console.print(f"\nTotal per invoice: {len(_RULES) + schematron_assertion_count()} checks")


@app.command()
def compare(
    before: Path = typer.Argument(..., help="Earlier results JSON (pint-ae diagnose --json)"),
    after: Path = typer.Argument(..., help="Later results JSON"),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable delta"),
) -> None:
    """Compare two diagnostic runs: what was fixed, what broke, what stayed.

    Exit 0 when nothing regressed, 1 when the later run has findings the earlier one
    did not, 2 when an input cannot be read.
    """
    from pint_ae.compare import CompareError, compare_runs

    try:
        comparison = compare_runs(before, after)
    except CompareError as exc:
        console.print(f"[red]X[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if json_out:
        sys.stdout.write(json.dumps(comparison.summary(), indent=2, sort_keys=True) + "\n")
    else:
        for line in comparison.lines():
            console.print(line)

    raise typer.Exit(code=1 if comparison.regressed_documents else 0)


@app.command()
def modules(
    json_out: bool = typer.Option(False, "--json", help="Machine-readable module summary"),
    config_file: Path | None = typer.Option(
        None, "--config", help="Show entitlement status from this pint-ae.toml"
    ),
) -> None:
    """List the modules that own the checks, with how many checks each owns.

    Module ids are stable and public: `pint-ae diagnose --modules <id>` selects one.
    Prices and the service catalogue are not part of this package.
    """
    counts = module_catalogue.checks_per_module()
    licence = licensing.current_licence()
    config = _load_config(config_file) if config_file is not None else None
    disabled = config.disabled_modules() if config is not None else []
    if json_out:
        payload = {
            "total": sum(counts.values()),
            "not_entitled": disabled,
            "modules": [
                {
                    "id": module.id,
                    "title": module.title,
                    "description": module.description,
                    "checks": counts.get(module.id, 0),
                }
                for module in module_catalogue.MODULES
            ],
        }
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return

    console.print(f"Modules ({len(module_catalogue.MODULES)}) — checks per module\n")
    width = max(len(module.id) for module in module_catalogue.MODULES)
    for module in module_catalogue.MODULES:
        marker = "  (not entitled)" if module.id in disabled else ""
        if not licence.covers(module.id):
            marker += "  (licence required)"
        console.print(
            f"  {module.id:<{width}}  {counts.get(module.id, 0):>4}  {module.title}{marker}"
        )
    console.print(f"  {'total':<{width}}  {sum(counts.values()):>4}  per invoice/document")
    console.print(
        f"\nlicence: {licence.state}"
        + (
            f" ({licence.customer}, expires {licence.expires})"
            if licence.licensed
            else " - free evaluation; paid modules require a signed licence"
        )
    )
    console.print("Select one with: pint-ae diagnose <path> --modules <id>")


config_app = typer.Typer(help="Inspect and validate pint-ae.toml.", no_args_is_help=True)


@config_app.command("show")
def config_show(
    config_file: Path | None = typer.Option(None, "--config", help="File to show"),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable"),
) -> None:
    """Print the effective configuration and its hash."""
    config = _load_config(config_file)
    applied = config_module.AppliedConfig(config, config.disabled_modules())
    if json_out:
        sys.stdout.write(
            json.dumps(
                {"config": config.normalised(), **applied.provenance()}, indent=2, sort_keys=True
            )
            + "\n"
        )
        return
    console.print(f"config sha256: {applied.sha256}")
    console.print(f"source: {config_module.find_config(config_file) or '(defaults)'}")
    console.print(f"not entitled: {', '.join(config.disabled_modules()) or 'none'}")
    console.print(f"tax-group TRNs: {len(config.tax_group.normalised())}")
    console.print(f"transmission window: {config.thresholds.transmission_days} days")
    console.print(f"severity overrides: {config.severity or 'none'}")
    console.print(f"output: {config.output.model_dump()}")


@config_app.command("validate")
def config_validate(
    config_file: Path = typer.Option(..., "--config", help="File to validate"),
) -> None:
    """Validate a config file; exit 1 with the reason if it cannot be used."""
    try:
        config = config_module.load_config(config_file)
    except config_module.ConfigError as exc:
        console.print(f"[red]X[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]OK[/green] {config_file} is valid (sha256 {config.sha256()[:16]}...)")


@config_app.command("init")
def config_init(
    out: Path = typer.Option(
        Path(config_module.DEFAULT_FILENAME), "--out", "-o", help="Where to write the template"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file"),
) -> None:
    """Write a commented pint-ae.toml template."""
    if out.exists() and not force:
        console.print(f"[red]X[/red] {out} exists; pass --force to overwrite")
        raise typer.Exit(code=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(config_module.CONFIG_TEMPLATE, encoding="utf-8", newline="\n")
    console.print(f"[green]OK[/green] wrote {out}")


app.add_typer(config_app, name="config")


@app.command()
def selftest() -> None:
    """Prove this installation is intact before using it on client documents.

    Checks the vendored official artefacts against their pinned hash, loads every
    stylesheet, and validates a small generated sample whose expected findings are
    known. Exit 0 means the installation can be trusted to report what it says it
    reports; exit 1 means it must not be used yet.
    """
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        status = "[green]PASS[/green]" if condition else "[red]FAIL[/red]"
        console.print(f"{status} {label}" + (f" ({detail})" if detail else ""))
        if not condition:
            failures.append(label)

    actual = regulatory.rule_set_sha256()
    check(
        "official rule-set hash matches the pinned value",
        actual == regulatory.EXPECTED_RULE_SET_SHA256,
        actual[:16] + "...",
    )

    try:
        loaded = warm_up()
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        check("stylesheets load", False, str(exc)[:120])
    else:
        check("stylesheets load", bool(loaded), f"{len(loaded)} layers")

    from pint_ae.pdf import arabic_font_status

    font = arabic_font_status()
    console.print(
        "Arabic font: "
        + (
            f"{font['font_path']}"
            if font["font_path"]
            else "none found - bilingual reports render Latin only; see README limitations"
        )
    )
    counts = assertion_counts()
    check(
        "official assertions present",
        schematron_assertion_count() >= 302,
        f"{schematron_assertion_count()} assertions",
    )
    check("local rules registered", len(_RULES) == 24, f"{len(_RULES)} rules")
    check("assertion counts readable", all(value > 0 for value in counts.values()))

    # A generated sample with a known defect: if the engine drifts, this fails.
    name, doc, xml = corpus.build_corpus(3)[2]
    expected = sorted({entry for defect in doc.defects for entry in corpus.DEFECTS[defect][1]})
    try:
        inv = parse(xml.encode("utf-8"))
        found = sorted({v.rule_id for v in validate(inv, xml.encode("utf-8"))})
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        check("engine reproduces a known finding", False, str(exc)[:120])
    else:
        check(
            "engine reproduces a known finding",
            found == expected,
            f"{name}: expected {expected}, got {found}",
        )

    if failures:
        console.print(f"\n[red]{len(failures)} check(s) failed[/red] - do not use this install yet")
        raise typer.Exit(code=1)
    console.print("\n[green]All checks passed[/green] - this installation is intact")


if __name__ == "__main__":
    app()
