# Copyright Contributors to the Packit project.
# SPDX-License-Identifier: MIT

import json

import pytest
from celery.canvas import Signature
from flexmock import flexmock

from ogr.services.github import GithubProject
from ogr.services.pagure import PagureProject
from packit.exceptions import PackitException
from packit.config import JobConfigTriggerType
from packit_service.config import PackageConfigGetter
from packit_service.models import GitBranchModel, KojiBuildTargetModel, PipelineModel
from packit_service.worker.jobs import SteveJobs
from packit_service.worker.monitoring import Pushgateway
from packit_service.worker.celery_task import CeleryTask
from packit_service.worker.tasks import (
    run_downstream_koji_build,
    run_downstream_koji_build_report,
)
from packit_service.worker.handlers.distgit import (
    DownstreamKojiBuildHandler,
)
from packit_service.models import (
    ProjectEventModelType,
)
from packit_service.worker.events.pagure import (
    PushPagureEvent,
)
from tests.conftest import koji_build_completed_rawhide, koji_build_start_rawhide
from tests.spellbook import first_dict_value, get_parameters_from_results


@pytest.mark.parametrize(
    "koji_build_fixture", [koji_build_start_rawhide, koji_build_completed_rawhide]
)
def test_downstream_koji_build_report_known_build(koji_build_fixture, request):
    koji_build_event = request.getfixturevalue(koji_build_fixture.__name__)
    packit_yaml = (
        "{'specfile_path': 'python-ogr.spec', 'synced_files': [],"
        "'jobs': [{'trigger': 'commit', 'job': 'koji_build'}],"
        "'downstream_package_name': 'python-ogr'}"
    )
    pagure_project = flexmock(
        PagureProject,
        full_repo_name="rpms/python-ogr",
        get_web_url=lambda: "https://src.fedoraproject.org/rpms/python-ogr",
        default_branch="main",
    )
    pagure_project.should_receive("get_files").with_args(
        ref="e029dd5250dde9a37a2cdddb6d822d973b09e5da", filter_regex=r".+\.spec$"
    ).and_return(["python-ogr.spec"])
    pagure_project.should_receive("get_file_content").with_args(
        path=".packit.yaml", ref="e029dd5250dde9a37a2cdddb6d822d973b09e5da"
    ).and_return(packit_yaml)
    pagure_project.should_receive("get_files").with_args(
        ref="e029dd5250dde9a37a2cdddb6d822d973b09e5da", recursive=False
    ).and_return(["python-ogr.spec", ".packit.yaml"])

    flexmock(GitBranchModel).should_receive("get_or_create").with_args(
        branch_name="main",
        namespace="rpms",
        repo_name="python-ogr",
        project_url="https://src.fedoraproject.org/rpms/python-ogr",
    ).and_return(flexmock(id=9, job_config_trigger_type=JobConfigTriggerType.commit))

    # 1*KojiBuildReportHandler
    flexmock(Signature).should_receive("apply_async").once()
    flexmock(Pushgateway).should_receive("push").times(2).and_return()

    # Database
    flexmock(KojiBuildTargetModel).should_receive("get_by_build_id").with_args(
        build_id=1874074
    ).and_return(
        flexmock(
            target="target",
            status="pending",
            web_url="some-url",
            build_logs_url=None,
            get_project_event_object=lambda: flexmock(
                id=1, job_config_trigger_type=JobConfigTriggerType.commit
            ),
        )
        .should_receive("set_build_logs_url")
        .with_args()
        .and_return()
        .mock()
    ).once()  # only when running a handler

    processing_results = SteveJobs().process_message(koji_build_event)
    # 1*KojiBuildReportHandler
    event_dict, job, job_config, package_config = get_parameters_from_results(
        processing_results
    )
    assert json.dumps(event_dict)
    results = run_downstream_koji_build_report(
        package_config=package_config,
        event=event_dict,
        job_config=job_config,
    )

    assert first_dict_value(results["job"])["success"]


@pytest.mark.parametrize(
    "koji_build_fixture", [koji_build_start_rawhide, koji_build_completed_rawhide]
)
def test_downstream_koji_build_report_unknown_build(koji_build_fixture, request):
    koji_build_event = request.getfixturevalue(koji_build_fixture.__name__)

    packit_yaml = (
        "{'specfile_path': 'python-ogr.spec', 'synced_files': [],"
        "'jobs': [{'trigger': 'commit', 'job': 'koji_build'}],"
        "'downstream_package_name': 'python-ogr'}"
    )
    pagure_project = flexmock(
        PagureProject,
        full_repo_name="rpms/python-ogr",
        get_web_url=lambda: "https://src.fedoraproject.org/rpms/python-ogr",
        default_branch="main",
    )
    pagure_project.should_receive("get_files").with_args(
        ref="e029dd5250dde9a37a2cdddb6d822d973b09e5da", filter_regex=r".+\.spec$"
    ).and_return(["python-ogr.spec"])
    pagure_project.should_receive("get_file_content").with_args(
        path=".packit.yaml", ref="e029dd5250dde9a37a2cdddb6d822d973b09e5da"
    ).and_return(packit_yaml)
    pagure_project.should_receive("get_files").with_args(
        ref="e029dd5250dde9a37a2cdddb6d822d973b09e5da", recursive=False
    ).and_return(["python-ogr.spec", ".packit.yaml"])

    flexmock(GitBranchModel).should_receive("get_or_create").with_args(
        branch_name="main",
        namespace="rpms",
        repo_name="python-ogr",
        project_url="https://src.fedoraproject.org/rpms/python-ogr",
    ).and_return(flexmock(id=9, job_config_trigger_type=JobConfigTriggerType.commit))

    # 1*KojiBuildReportHandler
    flexmock(Signature).should_receive("apply_async").once()
    flexmock(Pushgateway).should_receive("push").times(2).and_return()

    # Database
    run_model_flexmock = flexmock()
    git_branch_model_flexmock = flexmock(
        id=1, job_config_trigger_type=JobConfigTriggerType.commit
    )
    flexmock(KojiBuildTargetModel).should_receive("get_by_build_id").with_args(
        build_id=1864700
    ).and_return(None)
    flexmock(GitBranchModel).should_receive("get_or_create").and_return(
        git_branch_model_flexmock
    )
    flexmock(PipelineModel).should_receive("create").and_return(run_model_flexmock)
    flexmock(KojiBuildTargetModel).should_receive("create").with_args(
        build_id="1864700",
        commit_sha="0eb3e12005cb18f15d3054020f7ac934c01eae08",
        web_url="https://koji.fedoraproject.org/koji/taskinfo?taskID=79721403",
        target="noarch",
        status="BUILDING",
        run_model=run_model_flexmock,
    ).and_return(flexmock(get_project_event_object=lambda: git_branch_model_flexmock))
    flexmock(KojiBuildTargetModel).should_receive("get_by_build_id").with_args(
        build_id=1874074
    ).and_return(
        flexmock(
            target="noarch",
            status="BUILDING",
            web_url="https://koji.fedoraproject.org/koji/taskinfo?taskID=79721403",
            build_logs_url=None,
            get_project_event_object=lambda: flexmock(
                id=1, job_config_trigger_type=JobConfigTriggerType.commit
            ),
        )
        .should_receive("set_build_logs_url")
        .with_args()
        .and_return()
        .mock()
    ).once()  # only when running a handler

    processing_results = SteveJobs().process_message(koji_build_event)
    # 1*KojiBuildReportHandler
    event_dict, job, job_config, package_config = get_parameters_from_results(
        processing_results
    )
    assert json.dumps(event_dict)
    results = run_downstream_koji_build_report(
        package_config=package_config,
        event=event_dict,
        job_config=job_config,
    )

    assert first_dict_value(results["job"])["success"]


def test_koji_build_error_msg(distgit_push_packit):
    db_project_event = flexmock(
        id=123,
        job_config_trigger_type=JobConfigTriggerType.commit,
        project_event_model_type=ProjectEventModelType.release,
    )
    flexmock(PushPagureEvent).should_receive("db_project_event").and_return(
        db_project_event
    )
    flexmock(DownstreamKojiBuildHandler).should_receive("pre_check").and_return(True)
    flexmock(Signature).should_receive("apply_async").once()

    processing_results = SteveJobs().process_message(distgit_push_packit)
    event_dict, _, job_config, package_config = get_parameters_from_results(
        processing_results
    )
    assert json.dumps(event_dict)

    flexmock(CeleryTask).should_receive("is_last_try").and_return(True)
    error_msg = "error abc"
    dg = flexmock(local_project=flexmock(git_url="an url"))
    packit_api = (
        flexmock(dg=dg)
        .should_receive("build")
        .and_raise(PackitException, error_msg)
        .mock()
    )
    flexmock(DownstreamKojiBuildHandler).should_receive("packit_api").and_return(
        packit_api
    )
    msg = (
        "Packit failed on creating Koji build in dist-git (an url):"
        "\n\n| dist-git branch | error |\n| --------------- | ----- |"
        "\n| `f36` | ```error abc``` |\n\n"
        "Fedora Koji build was triggered by push "
        "with sha ad0c308af91da45cf40b253cd82f07f63ea9cbbf."
        "\n\nYou can retrigger the build by adding a comment "
        "(`/packit koji-build`) into this issue."
        "\n\n---\n\n*Get in [touch with us]"
        "(https://packit.dev/#contact) if you need some help.*\n"
    )
    flexmock(PackageConfigGetter).should_receive("create_issue_if_needed").with_args(
        project=GithubProject,
        title=("Fedora Koji build failed to be triggered"),
        message=msg,
        comment_to_existing=msg,
    ).once()

    with pytest.raises(PackitException):
        run_downstream_koji_build(
            package_config=package_config,
            event=event_dict,
            job_config=job_config,
        )
