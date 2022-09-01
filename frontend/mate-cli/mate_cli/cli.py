"""CLI for interacting with the MATE REST API."""

import argparse
import enum
import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Type, TypeVar, Union

from halo import Halo
from pydantic import BaseModel
from pydantic.fields import SHAPE_LIST, SHAPE_SET, ModelField

from mate_common.models.artifacts import ArtifactKind
from mate_common.models.builds import BuildOptions, BuildState
from mate_common.models.compilations import CompilationState, CompileOptions
from mate_common.models.graphs import FlowfinderGraph, GraphKind, GraphRequest, SliceRequest
from mate_common.models.manticore import MantiserveTaskState
from mate_common.utils import tarball
from mate_rest_client import Client, RestError
from mate_rest_client.builds import Build
from mate_rest_client.compilations import Compilation

BaseModelVar = TypeVar("BaseModelVar", bound=BaseModel)

_Jsonable = Union[List[Any], Dict[str, Any]]


def _dumps(jsonable: _Jsonable) -> str:
    return json.dumps(jsonable, sort_keys=True, indent=4)


@contextmanager
def _spinner(text: str) -> Iterator[Halo]:
    with Halo(
        text=text,
        stream=sys.stderr,
        enabled=sys.stderr.isatty(),
    ) as spinner:
        yield spinner


def _wait_for_builds(builds: List[Build]) -> None:
    build_count = len(builds)
    completed_builds: Set[str] = set()
    failed_builds: Set[str] = set()
    with _spinner(f"Builds: waiting on {build_count} builds") as spinner:
        while len(completed_builds) < build_count:
            ratio = f"{len(completed_builds)}/{build_count} done, {len(failed_builds)} failed"

            for build in builds:
                if build.state.is_terminal():
                    completed_builds.add(build.id_)
                    if build.state is not BuildState.Built:
                        failed_builds.add(build.id_)

                    # If the build has finished, we don't need to refresh it
                    # or do the spinner update.
                    continue

                build.refresh()
                time.sleep(0.25)

                short_id = build.id_[0:6]
                spinner.text = f"Builds: [{short_id}: {build.state}] {ratio} "

        if len(failed_builds) == 0:
            spinner.succeed(f"{len(completed_builds)} builds completed successfully")
        else:
            spinner.fail(f"{len(completed_builds)} builds, {len(failed_builds)} failed")


def _setup_model_args(parser: argparse.ArgumentParser, cls: Type[BaseModelVar]) -> None:
    # Iterate over the model and create flags for each field
    field: ModelField
    for _, field in cls.__fields__.items():
        flag_name = field.name.replace("_", "-")
        # Prefix the key with the name of the model class to decrease the likelihood of collisions
        # with flags that may have already been added to the parser
        dest_name = f"{cls.__name__}_{field.name}"
        # For boolean types, create on/off CLI flags for each
        if field.type_ == bool:
            parser.add_argument(
                f"--{flag_name}",
                dest=dest_name,
                action="store_true",
            )
            parser.add_argument(
                f"--no-{flag_name}",
                dest=dest_name,
                action="store_false",
            )
            parser.set_defaults(**{dest_name: field.default})
        elif field.type_ in (int, str):
            if field.shape in (SHAPE_LIST, SHAPE_SET):
                parser.add_argument(
                    f"--{flag_name}",
                    dest=dest_name,
                    type=field.type_,
                    action="append",
                    default=field.default,
                )
            else:
                parser.add_argument(
                    f"--{flag_name}", dest=dest_name, type=field.type_, default=field.default
                )
        elif issubclass(field.type_, enum.Enum):
            parser.add_argument(
                f"--{flag_name}",
                dest=dest_name,
                type=field.type_,
                choices=field.type_,
                default=field.default,
            )


def _parse_model_args(args: argparse.Namespace, cls: Type[BaseModelVar]) -> BaseModelVar:
    model = cls()
    for _, field in cls.__fields__.items():
        field_name = f"{cls.__name__}_{field.name}"
        if hasattr(args, field_name):
            setattr(model, field.name, getattr(args, field_name))
    return model


def _setup_artifact_parser(subparsers: argparse._SubParsersAction) -> None:
    artifact_parser = subparsers.add_parser("artifact", help="create or list artifacts")
    artifact_subparsers = artifact_parser.add_subparsers(dest="artifact_cmd", required=True)

    create_subparser = artifact_subparsers.add_parser("create", help="create an artifact")
    create_subparser.add_argument(
        "kind", type=ArtifactKind, choices=ArtifactKind, help="the kind of artifact"
    )
    create_subparser.add_argument(
        "path", type=Path, help="the path to the artifact file to be uploaded"
    )

    dump_subparser = artifact_subparsers.add_parser("dump", help="dump the contents of an artifact")
    dump_subparser.add_argument("id", type=str, help="the ID of the artifact")
    dump_subparser.add_argument(
        "-o",
        "--output",
        # NOTE(ww): Can't use `argparse.FileType` here because of BPO 14156
        # See: https://bugs.python.org/issue14156
        type=Path,
        help="the file to dump to",
    )

    get_subparser = artifact_subparsers.add_parser("get", help="list artifacts")
    get_subparser.add_argument(
        "ids", metavar="artifact-id", type=str, nargs="*", default=[], help="the ID of the artifact"
    )
    get_subparser.add_argument(
        "--kind",
        type=ArtifactKind,
        choices=ArtifactKind,
        default=None,
        help="the kind of artifact to filter for",
    )


def _setup_compile_parser(subparsers: argparse._SubParsersAction) -> None:
    compile_parser = subparsers.add_parser("compile", help="create or list compilations")

    compile_subparsers = compile_parser.add_subparsers(dest="compile_cmd", required=True)

    create_subparser = compile_subparsers.add_parser("create", help="create a compilation")
    create_subparser.add_argument(
        "-w",
        "--wait",
        default=False,
        action="store_true",
        help="wait until the compilation finishes",
    )

    # Only one of the `create` are applicable at any one time
    create_source_flags = create_subparser.add_mutually_exclusive_group()
    create_source_flags.add_argument(
        "--artifact-id", type=str, default=None, help="the ID of the artifact to compile"
    )
    # See doc/hacking.rst#History.
    create_source_flags.add_argument(
        "--challenge-name", type=str, default=None, help="the name of the challenge to compile"
    )
    create_source_flags.add_argument(
        "--challenge-id", type=str, default=None, help="the ID of the challenge to compile"
    )
    create_source_flags.add_argument(
        "--target-id", type=str, default=None, help="The ID of the challenge target to compile"
    )
    _setup_model_args(create_subparser, CompileOptions)

    get_subparser = compile_subparsers.add_parser("get", help="list compilations")
    get_subparser.add_argument(
        "id", type=str, nargs="?", default=None, help="the ID of the compilation"
    )
    get_subparser.add_argument(
        "--state",
        type=CompilationState,
        choices=CompilationState,
        help="the state of compilation we want to filter for",
    )


def _setup_build_parser(subparsers: argparse._SubParsersAction) -> None:
    build_parser = subparsers.add_parser("build", help="create or list builds")

    build_subparsers = build_parser.add_subparsers(dest="build_cmd", required=True)

    create_subparser = build_subparsers.add_parser("create", help="create a build")
    create_subparser.add_argument(
        "-p",
        "--run-all-pois",
        default=False,
        action="store_true",
        help="run all POI analysis on each build",
    )
    create_subparser.add_argument(
        "-w",
        "--wait",
        default=False,
        action="store_true",
        help="wait until all builds finish",
    )
    create_subparser.add_argument(
        "--target", type=str, default=None, required=False, help="the binary to target"
    )
    create_subparser.add_argument("id", type=str, help="the ID of the compilation to build")
    _setup_model_args(create_subparser, BuildOptions)

    get_subparser = build_subparsers.add_parser("get", help="list builds")
    get_subparser.add_argument("id", type=str, nargs="?", default=None, help="the ID of the build")
    get_subparser.add_argument(
        "--state",
        type=BuildState,
        choices=BuildState,
        help="the state of build we want to filter for",
    )

    get_bc_subparser = build_subparsers.add_parser("get-bc", help="get the LLVM IR for a build")
    get_bc_subparser.add_argument("id", type=str, help="the ID of the build")


def _setup_analysis_parser(subparsers: argparse._SubParsersAction) -> None:
    analysis_parser = subparsers.add_parser("analysis", help="run and list analysis tasks")
    analysis_subparsers = analysis_parser.add_subparsers(dest="analysis_cmd", required=True)
    analysis_subparsers.add_parser("get")
    task_subparser = analysis_subparsers.add_parser("task", help="list analysis tasks")
    task_subparser.add_argument(
        "id",
        type=str,
        nargs="?",
        default=None,
        help="the ID of the build for which to query analysis tasks",
    )
    run_subparser = analysis_subparsers.add_parser("run", help="run analysis tasks")
    run_subparser.add_argument(
        "build_id", type=str, help="the ID of the build for which to run an analysis task"
    )
    run_subparser.add_argument(
        "analysis_id",
        type=str,
        nargs="?",
        default=None,
        help="the ID of the analysis to run (defaults to running all analyses)",
    )


def _setup_poi_parser(subparsers: argparse._SubParsersAction) -> None:
    poi_parser = subparsers.add_parser("poi", help="list and set parameters on POIs")
    poi_subparsers = poi_parser.add_subparsers(dest="poi_cmd", required=True)
    get_subparser = poi_subparsers.add_parser("get", help="list POIs")
    get_subparser.add_argument(
        "build_id",
        type=str,
        nargs="?",
        default=None,
        help="the ID of the build for which to find POIs for (defaults to returning all POIs)",
    )
    set_subparser = poi_subparsers.add_parser("set", help="set POI parameters")
    set_subparser.add_argument(
        "poi_id", type=str, nargs="?", default=None, help="the ID of the POI of which to modify"
    )
    set_subparser.add_argument(
        "--done", dest="done", default=None, action="store_true", help="mark the POI as done"
    )
    set_subparser.add_argument(
        "--not-done", dest="done", action="store_false", help="mark the POI as not done"
    )
    set_subparser.add_argument(
        "--flagged",
        dest="flagged",
        default=None,
        action="store_true",
        help="mark the POI as flagged",
    )
    set_subparser.add_argument(
        "--not-flagged", dest="flagged", action="store_false", help="mark the POI as not flagged"
    )


def _setup_graph_parser(subparsers: argparse._SubParsersAction) -> None:
    graph_parser = subparsers.add_parser("graph", help="inspect code property graphs")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_cmd", required=True)
    get_subparser = graph_subparsers.add_parser("get", help="retrieve a graph")
    get_subparser.add_argument("build_id", type=str, help="the ID of the build to get graphs")
    get_subparser.add_argument(
        "kind", type=GraphKind, choices=GraphKind, help="the type of graph to retrieve"
    )
    get_subparser.add_argument(
        "origin_node_ids",
        type=str,
        nargs="+",
        help="the origin nodes for which to start looking for graphs",
    )
    node_subparser = graph_subparsers.add_parser("node", help="retrieve a node")
    node_subparser.add_argument(
        "build_id", type=str, help="the ID of the build for which to get nodes"
    )
    node_subparser.add_argument("node_id", type=str, help="the ID of the node to retrieve")
    slice_subparser = graph_subparsers.add_parser("slice", help="retrieve a slice of a graph")
    slice_subparser.add_argument(
        "build_id", type=str, help="the ID of the build from which to retrieve the slice"
    )
    slice_subparser.add_argument(
        "source_id", type=str, help="ID of the node at which to start the slice"
    )
    slice_subparser.add_argument(
        "sink_id", type=str, help="ID of the node at which to end the slice"
    )
    slice_subparser.add_argument(
        "kind", type=GraphKind, choices=GraphKind, help="the type of slice to retrieve"
    )
    slice_subparser.add_argument(
        "--avoid-node-id",
        dest="avoid_node_ids",
        type=str,
        action="append",
        help="the slice will exclude paths through these nodes",
    )
    slice_subparser.add_argument(
        "--focus-node-ids",
        dest="focus_node_ids",
        type=str,
        action="append",
        help="the slice will include only paths through these nodes",
    )
    function_subparser = graph_subparsers.add_parser("function", help="retrieve function nodes")
    function_subparser.add_argument(
        "build_id", type=str, help="the ID of the build for which to get function nodes"
    )


def _setup_manticore_parser(subparsers: argparse._SubParsersAction) -> None:
    manticore_parser = subparsers.add_parser("manticore", help="list Manticore tasks")

    manticore_subparsers = manticore_parser.add_subparsers(dest="manticore_cmd", required=True)

    get_subparser = manticore_subparsers.add_parser("get", help="list Manticore tasks")
    get_subparser.add_argument(
        "--state",
        type=MantiserveTaskState,
        choices=MantiserveTaskState,
        help="the state of Manticore task we want to filter for",
    )

    stop_subparser = manticore_subparsers.add_parser("stop", help="stop a Manticore task")
    stop_subparser.add_argument(
        "task_ids",
        metavar="task-id",
        type=str,
        nargs="+",
        help="the ID of the Manticore task to stop",
    )


def _setup_oneshot_parser(subparsers: argparse._SubParsersAction) -> None:
    oneshot_parser = subparsers.add_parser(
        "oneshot", help="shorthand for creating compilations and builds for a given source"
    )
    oneshot_parser.add_argument(
        "-p",
        "--run-all-pois",
        dest="run_all_pois",
        default=False,
        action="store_true",
        help="run all POI analysis on each build",
    )
    oneshot_parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        default=False,
        action="store_true",
        help="enable all debugging outputs during the CPG build",
    )
    oneshot_parser.add_argument(
        "source_handle",
        type=str,
        help="describes a source, can be either a source file, tarball, directory, artifact ID or broker challenge name",
    )


def _create_artifact(client: Client, kind: ArtifactKind, path: Path) -> None:
    if path.is_dir():
        if kind is not ArtifactKind.CompileTargetTarball:
            print(f"invalid source for {kind}: must be a non-directory")
            return

        with tarball(path) as path:
            artifact = client.artifacts.create(kind=kind, filename=path)
    else:
        artifact = client.artifacts.create(kind=kind, filename=path)

    print(artifact.json(pretty=True))


def _dump_artifact(client: Client, artifact_id: str, output: Optional[Path]) -> None:
    artifact = client.artifacts.maybe_get(artifact_id)
    if artifact is None:
        print(f"No such artifact: {artifact_id=}", file=sys.stderr)
        sys.exit(1)

    if output:
        with output.open("wb") as io:
            io.write(artifact.contents())
    else:
        sys.stdout.buffer.write(artifact.contents())


def _get_artifact(client: Client, artifact_ids: List[str], kind: Optional[ArtifactKind]) -> None:
    # If we don't choose an artifact id, iterate and print all of them
    if artifact_ids:
        dicts = []
        for artifact_id in artifact_ids:
            try:
                artifact = client.artifacts.get(artifact_id)
                if kind is None or artifact.kind == kind:
                    dicts.append(artifact.dict())
            except RestError as re:
                if re.status_code == 404:
                    print(f"Could not find artifact with id {artifact_id}", file=sys.stderr)
                else:
                    raise
        print(_dumps(dicts))
    else:
        print(_dumps([a.dict() for a in client.artifacts if kind is None or a.kind == kind]))


def _create_build(
    client: Client,
    compile_id: str,
    build_options: BuildOptions,
    *,
    target: Optional[str],
    run_all_pois: bool,
    wait: bool,
) -> None:
    compilation = client.compilations.maybe_get(compile_id)
    if compilation is None:
        print(f"Could not find compilation with id {compile_id}", file=sys.stderr)
        return

    builds = client.builds.create_from_compilation(
        compilation, build_options, target=target, run_all_pois=run_all_pois
    )

    if wait:
        _wait_for_builds(builds)

    print(_dumps([b.dict() for b in builds]))


def _get_build(client: Client, build_id: Optional[str], state: Optional[BuildState]) -> None:
    if build_id is not None:
        try:
            build = client.builds.get(build_id)
            print(build.json(pretty=True))
        except RestError as re:
            if re.status_code == 404:
                print(f"Could not find build with id {build_id}", file=sys.stderr)
            else:
                raise
    else:
        filters = dict()
        if state is not None:
            filters["state"] = str(state)
        print(_dumps([b.dict() for b in client.builds.iter(**filters)]))


def _get_build_bc(client: Client, build_id: str) -> None:
    build = client.builds.maybe_get(build_id)
    if build is None:
        print(f"No build with ID: {build_id}", file=sys.stderr)
        sys.exit(1)

    filename = build.bitcode_artifact.attributes.get("filename")
    if filename is None:
        filename = Path(f"{build_id}.bc")
    else:
        filename = Path(filename)

    if filename.exists():
        print(f"Not overwriting: {filename}", file=sys.stderr)
        sys.exit(1)

    with filename.open("wb") as io:
        io.write(build.bitcode_artifact.contents())

    print(f"Saved as {filename}")


def _create_compilation(
    client: Client,
    compile_options: CompileOptions,
    artifact_id: Optional[str],
    challenge_name: Optional[str],
    challenge_id: Optional[str],
    target_id: Optional[str],
    *,
    wait: bool,
) -> None:
    compilation: Compilation
    if challenge_name is not None:
        compilation = client.compilations.create_from_challenge(
            options=compile_options, challenge_name=challenge_name
        )
    elif challenge_id is not None:
        compilation = client.compilations.create_from_challenge(
            options=compile_options, challenge_id=challenge_id
        )
    elif target_id is not None:
        compilation = client.compilations.create_from_challenge(
            options=compile_options, target_id=target_id
        )
    else:
        assert artifact_id is not None
        artifact = client.artifacts.maybe_get(artifact_id)
        if artifact is None:
            print(f"Could not find artifact with id {artifact_id}", file=sys.stderr)
            return
        compilation = client.compilations.create_from_artifact(artifact, options=compile_options)

    if wait:
        with _spinner(f"{compilation.id_}: {compilation.state}") as spinner:
            while not compilation.state.is_terminal():
                spinner.text = f"{compilation.id_}: {compilation.state}"
                time.sleep(0.25)
                compilation.refresh()

            if compilation.state is CompilationState.Compiled:
                spinner.succeed(f"{compilation.id_}: {compilation.state}")
            else:
                spinner.fail(f"{compilation.id_}: {compilation.state}")
                if compilation.log_artifact is not None:
                    print(
                        compilation.log_artifact.contents().decode(errors="replace"),
                        file=sys.stderr,
                    )
                sys.exit(1)
    print(compilation.json(pretty=True))


def _get_compilation(
    client: Client, compile_id: Optional[str], state: Optional[CompilationState]
) -> None:
    if compile_id is not None:
        try:
            compilation = client.compilations.get(compile_id)
            print(compilation.json(pretty=True))
        except RestError as re:
            if re.status_code == 404:
                print(f"Could not find compilation with id {compile_id}", file=sys.stderr)
            else:
                raise
    else:
        filters = dict()
        if state is not None:
            filters["state"] = str(state)
        print(_dumps([c.dict() for c in client.compilations.iter(**filters)]))


def _get_analysis_tasks(client: Client, build_id: Optional[str]) -> None:
    if build_id is None:
        print(_dumps([task.dict() for task in client.analyses.tasks]))
    else:
        try:
            build = client.builds.get(build_id)
            print(_dumps([task.dict() for task in build.tasks]))
        except RestError as re:
            if re.status_code == 404:
                print(f"Could not find build with id {build_id}", file=sys.stderr)
            else:
                raise


def _run_analysis(client: Client, build_id: str, analysis_id: Optional[str]) -> None:
    build: Build
    try:
        build = client.builds.get(build_id)
    except RestError as re:
        if re.status_code == 404:
            print(f"Could not find build with id {build_id}", file=sys.stderr)
            return
        else:
            raise
    # Run all analyses on a build by default
    if analysis_id is None:
        print(_dumps([a.dict() for a in client.analyses.run(build)]))
    else:
        for a in client.analyses:
            if a.id_ == analysis_id:
                print(_dumps(a.run(build).dict()))
                return
        print(f"Could not find analysis with id {analysis_id}", file=sys.stderr)


def _get_pois(client: Client, build_id: Optional[str]) -> None:
    if build_id is None:
        print(_dumps([p.dict() for p in client.pois]))
    else:
        build: Build
        try:
            build = client.builds.get(build_id)
        except RestError as re:
            if re.status_code == 404:
                print(f"Could not find build with id {build_id}", file=sys.stderr)
                return
            else:
                raise
        print(_dumps([p.dict() for p in build.pois]))


def _set_poi(client: Client, poi_id: str, done: Optional[bool], flagged: Optional[bool]) -> None:
    if done is None and flagged is None:
        print("No params provided to POI set command", file=sys.stderr)
        return
    for p in client.pois:
        if p.id_ == poi_id:
            if done is not None:
                p.done = done
            if flagged is not None:
                p.flagged = flagged
            return
    print(f"Could not find POI with id {poi_id}", file=sys.stderr)


def _get_graph(client: Client, build_id: str, kind: GraphKind, origin_node_ids: List[str]) -> None:
    build: Build
    try:
        build = client.builds.get(build_id)
    except RestError as re:
        if re.status_code == 404:
            print(f"Could not find build with id {build_id}", file=sys.stderr)
            return
        else:
            raise
    graph: FlowfinderGraph
    try:
        graph = client.graphs.get_graph(
            build, GraphRequest(origin_node_ids=origin_node_ids, kind=kind)
        )
    except RestError as re:
        if re.status_code == 404:
            print(f"Could not find nodes with origin ids {origin_node_ids}", file=sys.stderr)
            return
        else:
            raise
    print(graph.dict())


def _get_graph_node(client: Client, build_id: str, node_id: str) -> None:
    build: Build
    try:
        build = client.builds.get(build_id)
    except RestError as re:
        if re.status_code == 404:
            print(f"Could not find build with id {build_id}", file=sys.stderr)
            return
        else:
            raise
    graph: FlowfinderGraph
    try:
        graph = client.graphs.get_node(build, node_id)
    except RestError as re:
        if re.status_code == 404:
            print(f"Could not find node with id {node_id}", file=sys.stderr)
            return
        else:
            raise
    print(_dumps(graph.dict()))


def _get_graph_slice(
    client: Client,
    build_id: str,
    source_id: str,
    sink_id: str,
    kind: GraphKind,
    avoid_node_ids: List[str],
    focus_node_ids: List[str],
) -> None:
    build: Build
    try:
        build = client.builds.get(build_id)
    except RestError as re:
        if re.status_code == 404:
            print(f"Could not find build with id {build_id}", file=sys.stderr)
            return
        else:
            raise
    graph = client.graphs.get_slice(
        build,
        SliceRequest(
            source_id=source_id,
            sink_id=sink_id,
            kind=kind,
            avoid_node_ids=avoid_node_ids,
            focus_node_ids=focus_node_ids,
        ),
    )
    print(_dumps(graph.dict()))


def _get_graph_function_nodes(client: Client, build_id: str) -> None:
    build: Build
    try:
        build = client.builds.get(build_id)
    except RestError as re:
        if re.status_code == 404:
            print(f"Could not find build with id {build_id}", file=sys.stderr)
        else:
            raise
    function_nodes = [n.dict() for n in client.graphs.get_function_nodes(build)]
    print(_dumps(function_nodes))


def _get_manticore_tasks(client: Client, state: Optional[MantiserveTaskState]) -> None:
    filters = dict()
    if state is not None:
        filters["state"] = str(state)
    print(_dumps([m.dict() for m in client.manticore.iter(**filters)]))


def _stop_manticore_task(client: Client, task_ids: List[str]) -> None:
    for task_id in task_ids:
        client.manticore.stop(task_id)


def _create_oneshot(client: Client, source_handle: str, *, run_all_pois: bool, debug: bool) -> None:
    source_path = Path(source_handle)
    compilation: Optional[Compilation] = None
    if source_path.exists():
        kind: ArtifactKind
        if source_path.suffix in [".c", ".cc", ".cpp", ".cxx"]:
            kind = ArtifactKind.CompileTargetSingle
        elif source_path.suffixes == [".tar", ".gz"] or source_path.is_dir():
            kind = ArtifactKind.CompileTargetTarball
        else:
            print(
                f"Unrecognized file type provided to `oneshot` command: {source_path}",
                file=sys.stderr,
            )
            return

        if source_path.is_dir():
            with tarball(source_path) as path:
                artifact = client.artifacts.create(kind=kind, filename=path)
        else:
            artifact = client.artifacts.create(kind=kind, filename=source_path)
        compilation = client.compilations.create_from_artifact(artifact)
    else:
        # A generated UUID should be 32 characters long
        if len(source_handle) == 32:
            try:
                # Now check if it's a valid hexadecimal string. If it is, then we're probably
                # looking at an artifact ID.
                if int(source_handle, 16):
                    artifact = client.artifacts.maybe_get(source_handle)
                    if artifact is not None:
                        compilation = client.compilations.create_from_artifact(artifact)
            # Not a valid hexadecimal string. In that case, it may just be a challenge name that
            # happens to be 36 chars long so let's give that a try.
            except ValueError:
                pass
        if compilation is None:
            compilation = client.compilations.create_from_challenge(challenge_name=source_handle)

    assert compilation is not None

    with _spinner(f"{compilation.id_}: {compilation.state}") as spinner:
        while not compilation.state.is_terminal():
            spinner.text = f"{compilation.id_}: {compilation.state}"
            time.sleep(1)
            compilation.refresh()

        if compilation.state is CompilationState.Compiled:
            spinner.succeed(f"{compilation.id_}: {compilation.state}")
        else:
            spinner.fail(f"{compilation.id_}: {compilation.state}")
            if compilation.log_artifact is not None:
                print(compilation.log_artifact.contents().decode(errors="replace"), file=sys.stderr)
            sys.exit(1)

    builds = client.builds.create_from_compilation(
        compilation,
        BuildOptions(
            debug_pointer_analysis=debug,
            debug_mate_jsonl=debug,
            debug_quotidian_jsonl=debug,
            debug_cpg_jsonl=debug,
        ),
        run_all_pois=run_all_pois,
    )

    _wait_for_builds(builds)

    print(_dumps([b.dict() for b in builds]))


def _parse_artifact_args(client: Client, args: argparse.Namespace) -> None:
    if args.artifact_cmd == "create":
        _create_artifact(client, args.kind, args.path)
    elif args.artifact_cmd == "dump":
        _dump_artifact(client, args.id, args.output)
    else:
        assert args.artifact_cmd == "get"
        _get_artifact(client, args.ids, args.kind)


def _parse_build_args(client: Client, args: argparse.Namespace) -> None:
    if args.build_cmd == "create":
        build_options = _parse_model_args(args, BuildOptions)
        _create_build(
            client,
            args.id,
            build_options,
            target=args.target,
            run_all_pois=args.run_all_pois,
            wait=args.wait,
        )
    elif args.build_cmd == "get":
        _get_build(client, args.id, args.state)
    else:
        assert args.build_cmd == "get-bc"
        _get_build_bc(client, args.id)


def _parse_compile_args(client: Client, args: argparse.Namespace) -> None:
    if args.compile_cmd == "create":
        compile_options = _parse_model_args(args, CompileOptions)
        _create_compilation(
            client,
            compile_options,
            args.artifact_id,
            args.challenge_name,
            args.challenge_id,
            args.target_id,
            wait=args.wait,
        )
    else:
        assert args.compile_cmd == "get"
        _get_compilation(client, args.id, args.state)


def _parse_analysis_args(client: Client, args: argparse.Namespace) -> None:
    if args.analysis_cmd == "get":
        print(_dumps([a.dict() for a in client.analyses]))
    elif args.analysis_cmd == "task":
        _get_analysis_tasks(client, args.id)
    else:
        assert args.analysis_cmd == "run"
        _run_analysis(client, args.build_id, args.analysis_id)


def _parse_poi_args(client: Client, args: argparse.Namespace) -> None:
    if args.poi_cmd == "get":
        _get_pois(client, args.build_id)
    else:
        assert args.poi_cmd == "set"
        _set_poi(client, args.poi_id, args.done, args.flagged)


def _parse_graph_args(client: Client, args: argparse.Namespace) -> None:
    if args.graph_cmd == "get":
        _get_graph(client, args.build_id, args.kind, args.origin_node_ids)
    elif args.graph_cmd == "node":
        _get_graph_node(client, args.build_id, args.node_id)
    elif args.graph_cmd == "slice":
        _get_graph_slice(
            client,
            args.build_id,
            args.source_id,
            args.sink_id,
            args.kind,
            args.avoid_node_ids,
            args.focus_node_ids,
        )
    else:
        assert args.graph_cmd == "function"
        _get_graph_function_nodes(client, args.build_id)


def _parse_manticore_args(client: Client, args: argparse.Namespace) -> None:
    if args.manticore_cmd == "get":
        _get_manticore_tasks(client, args.state)
    else:
        assert args.manticore_cmd == "stop"
        _stop_manticore_task(client, args.task_ids)


def _parse_oneshot_args(client: Client, args: argparse.Namespace) -> None:
    _create_oneshot(client, args.source_handle, run_all_pois=args.run_all_pois, debug=args.debug)


parser = argparse.ArgumentParser(
    prog="mate-cli", description="A CLI tool to interact with the MATE REST API"
)
parser.add_argument("--conn", type=str, default=None, help="the connection string of the REST API")
subparsers = parser.add_subparsers(dest="command", required=True)
_setup_artifact_parser(subparsers)
_setup_build_parser(subparsers)
_setup_compile_parser(subparsers)
_setup_analysis_parser(subparsers)
_setup_poi_parser(subparsers)
_setup_graph_parser(subparsers)
_setup_manticore_parser(subparsers)
_setup_oneshot_parser(subparsers)


def cli() -> None:
    args = parser.parse_args()
    client = Client(args.conn) if args.conn is not None else Client()
    if args.command == "artifact":
        _parse_artifact_args(client, args)
    elif args.command == "build":
        _parse_build_args(client, args)
    elif args.command == "compile":
        _parse_compile_args(client, args)
    elif args.command == "analysis":
        _parse_analysis_args(client, args)
    elif args.command == "graph":
        _parse_graph_args(client, args)
    elif args.command == "poi":
        _parse_poi_args(client, args)
    elif args.command == "manticore":
        _parse_manticore_args(client, args)
    else:
        assert args.command == "oneshot"
        _parse_oneshot_args(client, args)


if __name__ == "__main__":
    cli()
