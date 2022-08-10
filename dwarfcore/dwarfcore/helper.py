import logging
import os
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Union

from manticore import set_verbosity
from manticore.native import Manticore
from manticore.utils import config

import mate_query.db as db
from dwarfcore.detectors.dwarf_variables import DwarfVariables
from dwarfcore.detectors.heap_oob import ConcreteHeapOOB
from dwarfcore.detectors.testing import DetectAllPaths
from dwarfcore.detectors.uaf import DetectUseAfterFree
from dwarfcore.detectors.uninitialized_stack_variable import DetectUninitializedStackVariable
from dwarfcore.dwarfcore import DwarfCore
from dwarfcore.plugins.under_constrained_symex import UCSE, UnderconstrainedOOB, make_initial_state
from mantiserve.hooks import hook_defaults
from mate_common.models.integration import (
    ConcreteHeapOOBOptions,
    Detector,
    DetectorOptions,
    Explore,
    ExploreFunction,
    ExploreRet,
    ReachingTestCase,
    UnboundedPtrPolicy,
    UnderconstrainedOOBOptions,
)
from mate_common.models.manticore import UnderConstrainedOptions, UserDefinedConstraint


def setup_generic_manticore(
    prog_path: Path,
    prog_args: List[str],
    *,
    env: Optional[Mapping[str, str]] = None,
    workspace_path: Optional[str] = None,
    concrete_start: str = "",
    stdin_size: Optional[int] = None,
    dwarfcore: Optional[DwarfCore] = None,
):
    """Set up some generic settings for Manticore and initialize Manticore with the above arguments.

    :param prog_path: Path to executable
    :param prog_args: Arguments to executable
    :param env: Extra environment variables, combined with existing environment
    :param workspace_path: Path for Manticore to store intermediate files and
        findings (otherwise random temp file)
    :param concrete_start: Concrete stdin to use before symbolic input
    :param stdin_size: symbolic stdin size to use
    :return: A Manticore instance ready to run and add plugins
    """
    # Initialization stuff
    # ------------------------
    consts = config.get_group("core")
    consts.mprocessing = consts.mprocessing.single
    consts.fast_fail = True
    # config.get_group("smt").timeout = 30  # seconds
    # Level 2: Set verbosity to print system calls and other high-level debug info
    # Level 1: Set verbosity to print only warnings
    set_verbosity(2)
    logging.getLogger("manticore.native.cpu.abstractcpu").setLevel(logging.ERROR)
    logging.getLogger("manticore.utils.emulate").setLevel(logging.ERROR)

    if env is None:
        env = {}

    manticore = Manticore(
        str(prog_path),
        argv=prog_args,
        # Need to have this order so that explicit env overwrites same keys
        env={**os.environ, **env},
        workspace_url=workspace_path,
        concrete_start=concrete_start,
        stdin_size=stdin_size,
    )

    if dwarfcore:
        hook_defaults(manticore, dwarfcore)

    return manticore


def setup_under_constrained_manticore(
    prog_path: Path,
    session: db.Session,
    graph: db.Graph,
    target: str,
    input_constraints: Optional[List[UserDefinedConstraint]] = None,
    init_until: Optional[int] = None,
    native_array_size_policy: Optional[UnboundedPtrPolicy] = None,
    complex_array_size_policy: Optional[UnboundedPtrPolicy] = None,
    *,
    env: Optional[Mapping[str, str]] = None,
    workspace_path: Optional[str] = None,
):
    """Set Manticore for under-constrained symbolic execution and initialize Manticore with the
    above arguments.

    :param prog_path: Path to executable
    :param session: DB session to query the CPG
    :param graph: The code property graph for the executable
    :param target: Name of the function to execute in under-constrained mode
    :param input_constraints: Additional constraints on the symbolic state
    :param init_until: Execute the binary normally until this address is reached,
        then jump directly to the target specified by `start`
    :param env: Extra environment variables, combined with existing environment
    :param workspace_path: Path for Manticore to store intermediate files and
        findings (otherwise random temp file)
    :return: A Manticore instance ready to run and add plugins
    """
    # TODO(boyan): this is similar to setup_generic_manticore(), the code below
    # should be factorized

    # Initialization stuff
    # ------------------------
    consts = config.get_group("core")
    consts.mprocessing = consts.mprocessing.single
    consts.fast_fail = True
    # config.get_group("smt").timeout = 30  # seconds
    # Level 2: Set verbosity to print system calls and other high-level debug info
    # Level 1: Set verbosity to print only warnings
    set_verbosity(2)
    logging.getLogger("manticore.native.cpu.abstractcpu").setLevel(logging.ERROR)
    logging.getLogger("manticore.utils.emulate").setLevel(logging.ERROR)

    if env is None:
        env = {}
    env = {**os.environ, **env}

    # Create custom state for UCSE
    init_state = make_initial_state(prog_path)
    manticore = Manticore(init_state, workspace_url=workspace_path)
    uc_options = UnderConstrainedOptions(
        target_function=target,
        init_until=init_until,
        native_array_size_policy=native_array_size_policy,
        complex_array_size_policy=complex_array_size_policy,
        input_constraints=input_constraints,
    )
    # Register the UCSE plugin
    ucse_plugin = UCSE(session, graph, init_state, uc_options)
    manticore.register_plugin(ucse_plugin)

    return manticore


def enable_detectors(
    m: Manticore,
    dwarfcore: DwarfCore,
    detector_options: Union[Optional[DetectorOptions], Iterable[DetectorOptions]],
    is_underconstrained: bool = False,
) -> List[
    Union[
        ConcreteHeapOOB,
        UnderconstrainedOOB,
        DwarfVariables,
        DetectUninitializedStackVariable,
        DetectUseAfterFree,
    ]
]:
    """Initialize specified detectors with options and add them to Manticore instance.

    :param m: The manticore instance to add detectors
    :param dwarfcore: The Dwarfcore object
    :param detector_options: The detectors with options to enable
    :param is_underconstrained: Whether the detectors will run in the context of a UC Manticore task
    :return: The instantiations of the chosen detectors, in order specified
    """
    if detector_options is None:
        return []

    if not isinstance(detector_options, Iterable):
        detector_options = [detector_options]

    detectors_ret = []
    for detector_option in detector_options:
        detector = detector_option.detector
        if detector == Detector.UninitializedVar:
            init_detector = DetectUninitializedStackVariable(
                dwarfcore,
                poi_info=detector_option.poi_info,
                fast=detector_option.fast,
            )

        elif detector == Detector.VariableBoundsAccess:
            init_detector = DwarfVariables(
                dwarfcore,
                poi_funcs=detector_option.poi_info,
                fast=detector_option.fast,
            )

        elif detector == Detector.UseAfterFree:
            init_detector = DetectUseAfterFree(
                dwarfcore,
                m,
                poi_info=detector_option.poi_info,
                fast=detector_option.fast,
            )

        elif detector == Detector.DetectAllPaths:
            init_detector = DetectAllPaths()

        elif detector == Detector.UnderconstrainedOOB:
            init_detector = UnderconstrainedOOB(m)

        elif detector == Detector.ConcreteHeapOOB:
            init_detector = ConcreteHeapOOB(
                dwarfcore, m, fast=detector_option.fast, underconstrained=is_underconstrained
            )

        else:
            logging.getLogger().warning(
                f"Specified unknown dwarfcore detector: {detector}. Skipping."
            )
            continue

        m.register_plugin(init_detector)
        detectors_ret.append(init_detector)

    return detectors_ret


def manticore_explore(
    bin_path: Path,
    session: db.Session,
    graph: db.Graph,
    explore_msg: Union[Explore, ExploreFunction],
    logger: logging.Logger,
    manticore_workspace: Optional[str] = None,
) -> ExploreRet:
    """Run Manticore in exploration mode with configuration determined by ``explore_msg``

    :param bin_path: The path to the binary being executed
    :param ctxt: Global context for settings and options
    :param explore_msg: The message to configure Manticore for exploration
    :param manticore_workspace: Location where Manticore will place execution artifacts
    :return: An ``ExploreReturn`` message with details of input that triggered a detector
    """
    dwarfcore = DwarfCore(session, graph, bin_path)

    if isinstance(explore_msg, ExploreFunction):
        m = setup_under_constrained_manticore(
            bin_path,
            session=session,
            graph=graph,
            target=explore_msg.target_function,
            input_constraints=explore_msg.input_constraints,
            init_until=None,
            native_array_size_policy=explore_msg.primitive_ptr_policy,
            complex_array_size_policy=explore_msg.complex_ptr_policy,
            env=explore_msg.env,
            workspace_path=manticore_workspace,
        )
        detectors = enable_detectors(
            m,
            dwarfcore,
            [
                UnderconstrainedOOBOptions(detector=Detector.UnderconstrainedOOB),
                ConcreteHeapOOBOptions(detector=Detector.ConcreteHeapOOB, fast=True),
            ],
            True,
        )
        detectors += enable_detectors(m, dwarfcore, explore_msg.detector_options, True)
    else:
        m = setup_generic_manticore(
            bin_path,
            explore_msg.command_line_flags,
            env=explore_msg.env,
            workspace_path=manticore_workspace,
            concrete_start=explore_msg.concrete_start,
            stdin_size=explore_msg.stdin_size,
            dwarfcore=dwarfcore,
        )
        detectors = enable_detectors(m, dwarfcore, explore_msg.detector_options, False)

    logger.info(f"Enabled detectors: {detectors}")

    logger.debug("Starting Manticore run")
    with m.kill_timeout(timeout=explore_msg.timeout):
        m.run()
    logger.debug("Manticore finished")

    # Gather results and create a return message
    testcases: List[ReachingTestCase] = []
    for detector in detectors:
        testcases.extend(detector.results)

    with m.locked_context() as ctx:
        if isinstance(explore_msg, ExploreFunction):
            return ExploreRet(
                path=str(bin_path),
                cases=testcases,
                exploration_tree=ctx.get(UCSE.ctx_exploration_tree, None),
                warnings=list(set(ctx.get(UCSE.ctx_warnings, []))),
            )
        else:
            return ExploreRet(path=str(bin_path), cases=testcases)
