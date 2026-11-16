"""패키지가 설치되고 임포트되는지만 확인한다. 첫 기능 테스트가 생기면 지워도 된다."""

import minisius


def test_package_imports() -> None:
    assert minisius.__version__
