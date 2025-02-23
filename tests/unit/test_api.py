# Copyright Contributors to the Packit project.
# SPDX-License-Identifier: MIT

from datetime import datetime, timezone

import pytest

from packit_service.models import optional_time


@pytest.mark.parametrize(
    "input_object,expected_type",
    [(datetime.now(timezone.utc), str), (None, type(None))],
)
def test_optional_time(input_object, expected_type):
    # optional_time returns a string if its passed a datetime object
    # None if passed a NoneType object
    assert isinstance(optional_time(input_object), expected_type)
