def test_build_tarball(cpg_db_v2):
    # Explicitly disable containerization here, just in case the default changes.
    cpg = cpg_db_v2("complex-linkage", compile_options=dict(containerized=False))

    assert cpg is not None


def test_build_tarball_containerized(cpg_db_v2, docker_image_build):
    cpg = cpg_db_v2(
        "complex-linkage",
        compile_options=dict(
            containerized=True,
            docker_image=docker_image_build("mate-integration-phase2-environment"),
        ),
    )

    assert cpg is not None
